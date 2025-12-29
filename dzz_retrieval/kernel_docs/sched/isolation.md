# sched\isolation.c

> 自动生成时间: 2025-10-25 16:11:16
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\isolation.c`

---

# `sched/isolation.c` 技术文档

## 1. 文件概述

`sched/isolation.c` 实现了 Linux 内核中的 **housekeeping（家务管理）机制**，用于管理那些必须在特定 CPU 上运行的通用内核任务（如未绑定的工作队列、定时器、内核线程、RCU 回调、调度器相关任务等）。该机制支持通过内核启动参数（如 `nohz_full=` 和 `isolcpus=`）将某些 CPU 从常规内核任务中“隔离”出来，以提升实时性或减少干扰，常用于高性能计算、低延迟或实时系统场景。

核心目标是：**允许用户指定一组“非隔离”CPU（即 housekeeping CPU）专门处理内核后台任务，而将其他 CPU 保留给用户关键任务使用**。

## 2. 核心功能

### 数据结构

- **`enum hk_flags`**  
  定义 housekeeping 功能类型对应的位标志，包括：
  - `HK_FLAG_TIMER`：定时器
  - `HK_FLAG_RCU`：RCU 回调
  - `HK_FLAG_MISC`：杂项内核任务
  - `HK_FLAG_SCHED`：调度器相关任务
  - `HK_FLAG_TICK`：周期性 tick（与 NO_HZ_FULL 相关）
  - `HK_FLAG_DOMAIN`：调度域构建
  - `HK_FLAG_WQ`：工作队列
  - `HK_FLAG_MANAGED_IRQ`：托管中断亲和性
  - `HK_FLAG_KTHREAD`：内核线程

- **`struct housekeeping`**  
  全局结构体，包含：
  - `cpumasks[HK_TYPE_MAX]`：每种 housekeeping 类型对应的 CPU 掩码
  - `flags`：启用的 housekeeping 功能位图

- **`housekeeping_overridden`**  
  静态分支键（`static_key`），用于快速判断是否启用了自定义 housekeeping 配置。

### 主要函数

- **`housekeeping_enabled(enum hk_type type)`**  
  检查指定类型的 housekeeping 是否启用。

- **`housekeeping_any_cpu(enum hk_type type)`**  
  返回适合执行指定类型 housekeeping 任务的 CPU（优先 NUMA 亲和，其次任意在线 CPU）。

- **`housekeeping_cpumask(enum hk_type type)`**  
  返回指定类型 housekeeping 任务允许运行的 CPU 掩码。

- **`housekeeping_affine(struct task_struct *t, enum hk_type type)`**  
  将任务 `t` 的 CPU 亲和性限制为指定类型 housekeeping 的 CPU 集合。

- **`housekeeping_test_cpu(int cpu, enum hk_type type)`**  
  检查指定 CPU 是否属于指定类型 housekeeping 的允许集合。

- **`housekeeping_init(void)`**  
  初始化 housekeeping 子系统，启用静态分支并验证配置。

- **`housekeeping_setup(char *str, unsigned long flags)`**  
  解析启动参数（CPU 列表），设置 housekeeping 的 CPU 掩码和功能标志。

- **`housekeeping_nohz_full_setup()` / `housekeeping_isolcpus_setup()`**  
  分别处理 `nohz_full=` 和 `isolcpus=` 内核启动参数。

- **`enhanced_isolcpus_setup()`**  
  处理 `enhanced_isolcpus` 启动参数，启用增强隔离模式（仅设标志，具体行为由其他子系统实现）。

## 3. 关键实现

### 静态分支优化
使用 `static_branch_unlikely(&housekeeping_overridden)` 实现零开销快速路径：当未配置隔离时，所有 housekeeping 函数直接返回默认值（如 `smp_processor_id()` 或 `cpu_possible_mask`），避免条件判断开销。

### 启动参数解析
- **`nohz_full=cpu-list`**：自动启用 `HK_FLAG_TICK | WQ | TIMER | RCU | MISC | KTHREAD`，表示这些任务只能在非 `nohz_full` CPU 上运行。
- **`isolcpus=flags,cpu-list`**：支持细粒度控制，如：
  - `nohz` → 启用 `HK_FLAG_TICK`
  - `domain` → 启用 `HK_FLAG_DOMAIN`（影响调度域构建）
  - `managed_irq` → 启用 `HK_FLAG_MANAGED_IRQ`
  - 无标志时默认启用 `HK_FLAG_DOMAIN`

### 配置一致性检查
若同时使用 `nohz_full=` 和 `isolcpus=`，要求两者指定的 housekeeping CPU 集合必须一致，否则报错。

### 安全兜底机制
若用户指定的 housekeeping CPU 集合中没有在线 CPU，则自动将引导 CPU（`smp_processor_id()`）加入，确保至少有一个 CPU 可处理内核任务。

### NO_HZ_FULL 集成
当启用 `HK_FLAG_TICK` 时：
- 检查 `CONFIG_NO_HZ_FULL` 是否启用
- 调用 `tick_nohz_full_setup()` 配置无周期 tick
- 调用 `sched_tick_offload_init()` 初始化 tick 卸载

## 4. 依赖关系

- **调度器子系统 (`kernel/sched/`)**  
  依赖 `sched_numa_find_closest()` 实现 NUMA 亲和调度；`housekeeping_affine()` 调用 `set_cpus_allowed_ptr()`。

- **时间子系统 (`kernel/time/`)**  
  与 `tick_nohz_full_setup()` 和 `sched_tick_offload_init()` 紧密集成，实现无周期 tick。

- **CPU 热插拔与拓扑 (`kernel/cpu.c`, `arch/`)**  
  使用 `cpu_possible_mask`、`cpu_online_mask`、`cpu_present_mask` 等全局 CPU 掩码。

- **启动内存分配 (`mm/`)**  
  使用 `alloc_bootmem_cpumask_var()` 在初始化阶段分配 CPU 掩码内存。

- **RCU 子系统 (`kernel/rcu/`)**  
  通过 `HK_FLAG_RCU` 控制 RCU 回调的执行 CPU。

- **工作队列 (`kernel/workqueue.c`)**  
  通过 `HK_FLAG_WQ` 限制未绑定工作队列的执行 CPU。

## 5. 使用场景

1. **实时系统**  
   通过 `isolcpus=domain,managed_irq,1-7` 将 CPU 1-7 从调度域和中断中隔离，仅保留 CPU 0 处理内核任务，降低关键任务延迟。

2. **高性能计算 (HPC)**  
   使用 `nohz_full=1-15` 禁用 CPU 1-15 的周期性 tick，减少干扰，提升计算密集型应用性能。

3. **低延迟应用**  
   结合 `isolcpus=nohz,domain,1` 和用户空间任务绑定，确保 CPU 1 无内核后台活动，实现微秒级响应。

4. **虚拟化环境**  
   将部分 CPU 完全分配给虚拟机（通过隔离），避免宿主机内核任务抢占。

5. **增强隔离模式**  
   启用 `enhanced_isolcpus` 参数（需其他子系统支持），进一步限制隔离 CPU 上的内核活动（如禁止 softirq、禁止 page reclaim 等）。