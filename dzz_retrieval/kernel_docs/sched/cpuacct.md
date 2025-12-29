# sched\cpuacct.c

> 自动生成时间: 2025-10-25 16:01:42
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\cpuacct.c`

---

# `sched/cpuacct.c` 技术文档

## 1. 文件概述

`sched/cpuacct.c` 是 Linux 内核中用于实现 **CPU 资源使用量统计**（CPU accounting）的 cgroup 子系统模块。该文件基于 cgroup v1 架构，为任务组（task groups）提供细粒度的 CPU 时间消耗追踪功能，支持按用户态（user）和内核态（system）分别统计，并可按 CPU 核心粒度进行聚合或展示。其核心目标是为容器、资源隔离和性能监控等场景提供精确的 CPU 使用数据。

## 2. 核心功能

### 主要数据结构

- **`enum cpuacct_stat_index`**  
  定义 CPU 使用统计的类别：
  - `CPUACCT_STAT_USER`：用户态执行时间（含 nice 进程）
  - `CPUACCT_STAT_SYSTEM`：内核态执行时间（含 IRQ/softirq）
  - `CPUACCT_STAT_NSTATS`：特殊值，表示总使用时间

- **`struct cpuacct`**  
  表示一个 CPU accounting 控制组实例：
  - `css`：嵌入的 cgroup 子系统状态
  - `cpuusage`：每个 CPU 核心上的总 CPU 使用时间（纳秒）
  - `cpustat`：每个 CPU 核心上按类别细分的使用时间（对应 `kernel_cpustat`）

- **`root_cpuacct`**  
  全局根 cgroup 的 `cpuacct` 实例，复用全局 `kernel_cpustat` 数据。

### 主要函数

- **资源分配与释放**
  - `cpuacct_css_alloc()`：为新 cgroup 分配 `cpuacct` 结构及 per-CPU 数据
  - `cpuacct_css_free()`：释放 `cpuacct` 及其 per-CPU 数据

- **CPU 使用量读写**
  - `cpuacct_cpuusage_read()`：读取指定 CPU 上指定类别的使用时间
  - `cpuacct_cpuusage_write()`：重置指定 CPU 上的使用时间（仅非根 cgroup）
  - `__cpuusage_read()`：聚合所有 CPU 的使用时间

- **cgroup 文件接口**
  - `cpuusage_read()` / `cpuusage_user_read()` / `cpuusage_sys_read()`：提供 `usage`、`usage_user`、`usage_sys` 文件的读取
  - `cpuusage_write()`：支持向 `usage` 文件写入 `0` 以重置计数
  - `cpuacct_percpu_*_seq_show()`：提供 per-CPU 粒度的使用时间输出
  - `cpuacct_all_seq_show()`：输出所有 CPU 及所有类别的使用时间表格
  - `cpuacct_stats_show()`：输出经 `cputime_adjust()` 调整后的 `stat` 文件内容（单位转换为 clock ticks）

- **运行时统计更新**
  - `cpuacct_charge()`：在任务调度时累加总 CPU 使用时间（纳秒）
  - `cpuacct_account_field()`：累加用户态或内核态的细分时间（代码片段未完整）

### cgroup 文件接口（`files[]`）

| 文件名 | 读取函数 | 写入函数 | 说明 |
|--------|----------|----------|------|
| `usage` | `cpuusage_read` | `cpuusage_write` | 总 CPU 使用时间（纳秒） |
| `usage_user` | `cpuusage_user_read` | — | 用户态 CPU 时间 |
| `usage_sys` | `cpuusage_sys_read` | — | 内核态 CPU 时间 |
| `usage_percpu` | `cpuacct_percpu_seq_show` | — | 每个 CPU 的总使用时间 |
| `usage_percpu_user` | `cpuacct_percpu_user_seq_show` | — | 每个 CPU 的用户态时间 |
| `usage_percpu_sys` | `cpuacct_percpu_sys_seq_show` | — | 每个 CPU 的内核态时间 |
| `usage_all` | `cpuacct_all_seq_show` | — | 所有 CPU 及类别的完整表格 |
| `stat` | `cpuacct_stats_show` | — | 调整后的时间（clock ticks） |

## 3. 关键实现

### Per-CPU 数据结构
- 每个 `cpuacct` 实例维护两个 per-CPU 数组：
  - `cpuusage`：总 CPU 使用时间（纳秒），用于 `usage` 等文件
  - `cpustat`：细分时间（`CPUTIME_USER`、`CPUTIME_SYSTEM` 等），用于 `stat` 和 per-CPU 统计

### 32 位平台原子性保障
- 在 32 位系统上，64 位变量的读写非原子，因此在访问 per-CPU 数据时需持有对应 CPU 的 `rq->lock`（通过 `raw_spin_rq_lock_irq()`）。

### 层级累加机制
- `cpuacct_charge()` 和 `cpuacct_account_field()` 采用 **自底向上遍历 cgroup 层级** 的方式，将时间同时计入当前 cgroup 及其所有祖先，确保层级聚合正确。

### 根 cgroup 特殊处理
- 根 cgroup（`root_cpuacct`）复用全局 `kernel_cpustat`，且 **禁止重置**（`cpuacct_cpuusage_write()` 中直接返回）。

### 时间单位转换
- `cpuacct_stats_show()` 使用 `cputime_adjust()` 对原始纳秒值进行平滑处理，并通过 `nsec_to_clock_t()` 转换为传统 `clock_t` 单位（通常为 jiffies），以兼容 `/proc/stat` 风格的输出。

## 4. 依赖关系

- **cgroup 核心框架**：依赖 `cgroup_subsys_state`、`task_css()` 等 cgroup 基础设施
- **调度器**：通过 `cpuacct_charge()` 与调度器集成，在任务切换时更新统计
- **Per-CPU 基础设施**：使用 `alloc_percpu()`、`per_cpu_ptr()` 管理 per-CPU 数据
- **时间子系统**：依赖 `kernel_cpustat` 和 `cputime_adjust()` 进行时间统计与调整
- **锁机制**：在 32 位平台依赖 `rq->lock` 保证 64 位操作原子性

## 5. 使用场景

- **容器资源监控**：Docker、Kubernetes 等容器运行时通过读取 `cpuacct` 的 cgroup 文件获取容器 CPU 使用情况
- **系统性能分析**：`perf`、`top` 等工具可利用 per-cgroup 的 CPU 统计数据进行进程组级性能分析
- **资源配额与限制**：虽然 `cpuacct` 本身不实施限制，但其统计数据可被其他子系统（如 `cpu` 子系统）用于配额控制
- **多租户环境隔离**：云平台通过 cgroup 层级结构为不同租户分配独立的 CPU 统计视图
- **调试与诊断**：通过 `usage_all`、`stat` 等文件快速定位特定 cgroup 的 CPU 消耗模式（用户态 vs 内核态）