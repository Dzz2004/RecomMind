# power\energy_model.c

> 自动生成时间: 2025-10-25 15:20:12
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `power\energy_model.c`

---

# `power/energy_model.c` 技术文档

## 1. 文件概述

`power/energy_model.c` 是 Linux 内核中实现 **能量模型（Energy Model, EM）** 的核心文件，主要用于描述设备（尤其是 CPU）在不同性能状态（Performance State, OPP）下的功耗、频率、性能和能效成本等信息。该模型为 **能耗感知调度器（Energy Aware Scheduling, EAS）** 提供关键数据支持，以实现更优的任务调度和能效管理。

该文件由 Arm Ltd. 开发并维护，支持动态注册/更新设备的性能域（Performance Domain），并通过 debugfs 提供调试接口（在 `CONFIG_DEBUG_FS` 启用时）。

---

## 2. 核心功能

### 主要数据结构

- `struct em_perf_domain`：表示一个性能域，包含多个性能状态。
- `struct em_perf_state`：描述单个性能状态，包含 `frequency`、`power`、`performance`、`cost` 和 `flags` 等字段。
- `struct em_perf_table`：包含性能状态数组及引用计数（`kref`）和 RCU 释放机制。
- `struct em_data_callback`：用于从驱动获取功耗/成本数据的回调接口（部分在头文件中定义）。

### 主要函数

| 函数 | 功能说明 |
|------|--------|
| `em_table_alloc()` | 为性能域分配新的 EM 表，初始化引用计数 |
| `em_table_free()` | 安全释放 EM 表（基于 `kref` 和 RCU） |
| `em_init_performance()` | 为 CPU 设备初始化 `performance` 字段（基于最大频率和 CPU 容量） |
| `em_compute_costs()` | 计算每个性能状态的 `cost`（功耗/性能比）并标记低效状态 |
| `em_dev_compute_costs()` | 对外接口，用于运行时更新 EM 表的成本值 |
| `em_debug_create_pd()` / `em_debug_remove_pd()` | 创建/移除 debugfs 调试节点（仅当 `CONFIG_DEBUG_FS` 启用） |
| `_is_cpu_device()` | 判断设备是否为 CPU 子系统设备 |

### 全局变量与机制

- `em_pd_mutex`：互斥锁，用于串行化性能域注册和回调执行。
- `em_update_work`：延迟工作队列，用于异步更新 EM（部分实现在其他文件）。
- RCU + `kref` 机制：确保 EM 表在多读者场景下的安全释放。

---

## 3. 关键实现

### 3.1 性能与成本计算

- **性能值（`performance`）**：  
  对于 CPU，通过线性映射计算：
  ```
  performance[i] = (arch_scale_cpu_capacity(cpu) * freq[i]) / max_freq
  ```
  其中 `arch_scale_cpu_capacity()` 返回 CPU 的最大计算能力（通常由调度器拓扑初始化）。

- **成本值（`cost`）**：  
  默认使用 `cost = (power * 10) / performance`，提高精度。  
  若设备标记为 `EM_PERF_DOMAIN_ARTIFICIAL` 且提供 `get_cost` 回调，则使用驱动提供的成本值。

- **低效状态标记**：  
  从高频到低频遍历，若当前状态的 `cost` 不小于前一状态，则标记为 `EM_PERF_STATE_INEFFICIENT`，供 EAS 调度时避开。

### 3.2 内存管理与生命周期

- EM 表通过 `kref` 管理引用计数，确保在无使用者时才释放。
- 释放通过 `call_rcu()` 异步执行，避免在 RCU 读侧临界区访问已释放内存。
- `em_table_free()` 是唯一释放入口，保证线程安全。

### 3.3 Debugfs 调试支持

当启用 `CONFIG_DEBUG_FS` 时：
- 在 `/sys/kernel/debug/energy_model/` 下为每个设备创建目录。
- 每个性能状态（`ps:freq`）有独立子目录，包含 `frequency`、`power`、`cost`、`performance`、`inefficient` 等只读文件。
- CPU 设备额外提供 `cpus` 文件，显示所属 CPU 掩码。

---

## 4. 依赖关系

- **调度子系统**：依赖 `#include <linux/sched/topology.h>` 获取 CPU 拓扑和容量信息。
- **CPUFreq 子系统**：通过 `#include <linux/cpufreq.h>` 与 OPP（Operating Performance Point）机制交互。
- **设备模型**：使用 `cpu_subsys` 判断设备类型。
- **内存管理**：使用 `kzalloc`、`devm_kcalloc` 等分配内存。
- **同步机制**：依赖 `mutex`、`RCU` 和 `kref` 实现安全并发。
- **调试支持**：可选依赖 `debugfs`。

---

## 5. 使用场景

1. **EAS（Energy Aware Scheduling）**：  
   调度器在任务迁移或唤醒时，查询目标 CPU 的 EM 表，选择能效最优的 CPU 和频率。

2. **热插拔与 DVFS**：  
   在 CPU 热插拔或频率切换时，EM 表提供功耗预测依据。

3. **运行时 EM 更新**：  
   通过 `em_dev_compute_costs()` 动态更新 EM 表（例如在 thermal 事件后调整 OPP）。

4. **系统调试与验证**：  
   开发者可通过 debugfs 检查 EM 数据是否符合预期，验证低效状态标记是否正确。

5. **异构多核系统（如 big.LITTLE）**：  
   不同 CPU 集群拥有独立 EM 表，EAS 利用这些信息实现大小核任务分配优化。