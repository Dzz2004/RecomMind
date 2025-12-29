# sched\core.c

> 自动生成时间: 2025-10-25 16:00:02
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\core.c`

---

# `sched/core.c` 技术文档

## 1. 文件概述

`sched/core.c` 是 Linux 内核调度器的核心实现文件，负责 CPU 调度器的基础框架、任务入队/出队逻辑、调度类管理、上下文切换协调以及调度器全局状态维护。该文件是整个调度子系统（`kernel/sched/`）的中枢，为 CFS（完全公平调度器）、RT（实时调度器）、DL（截止时间调度器）以及新兴的 SCX（可扩展调度器）等调度类提供统一的调度接口和运行时支持。此外，该文件还实现了与 CPU 热插拔、负载均衡、能耗调度、调度调试等功能的集成。

## 2. 核心功能

### 主要数据结构
- `struct rq`（运行队列）：每个 CPU 对应一个，通过 `DEFINE_PER_CPU_SHARED_ALIGNED(struct rq, runqueues)` 定义，是调度器操作的基本单元。
- `core_cookie` 与 `core_node`：用于 **SCHED_CORE** 特性（任务协同调度）的任务分组标识和红黑树节点。
- `sysctl_sched_features`：调度器调试特性开关（仅在 `CONFIG_SCHED_DEBUG` 下有效）。
- `scheduler_running`：全局标志，指示调度器是否已初始化并运行。

### 主要函数
- `sched_core_enqueue(struct rq *rq, struct task_struct *p)`  
  将任务加入 SCHED_CORE 协同调度红黑树。
- `sched_core_dequeue(struct rq *rq, struct task_struct *p, int flags)`  
  从 SCHED_CORE 红黑树中移除任务，并在特定条件下触发重调度。
- `__task_prio(const struct task_struct *p)`  
  返回任务的内部优先级数值，用于 SCHED_CORE 中的任务排序（数值越小优先级越高）。
- `prio_less(const struct task_struct *a, const struct task_struct *b, bool in_fi)`  
  比较两个任务的优先级，考虑调度类（stop、dl、rt、fair、idle、scx）及截止时间。
- `__sched_core_less(const struct task_struct *a, const struct task_struct *b)`  
  SCHED_CORE 专用的任务比较函数，先按 `core_cookie` 分组，组内按优先级排序（高优先级靠左）。
- `sched_task_is_throttled(struct task_struct *p, int cpu)`  
  查询任务是否被其调度类限流（如 CFS 带宽控制）。

### 全局变量与宏
- `sysctl_sched_nr_migrate`：单次负载均衡迁移任务数上限（IRQ 关闭期间执行）。
- `sysctl_resched_latency_warn_ms` / `sysctl_resched_latency_warn_once`：调度延迟警告阈值与模式（调试用）。
- `__sched_core_enabled`：静态键（static key），用于动态启用/禁用 SCHED_CORE 功能。

### Tracepoint 导出
导出多个调度相关 tracepoint 供外部模块（如 ftrace、perf）探测，包括：
- PELT 负载跟踪（`pelt_cfs_tp`, `pelt_rt_tp` 等）
- CPU 容量与过载状态（`sched_cpu_capacity_tp`, `sched_overutilized_tp`）
- 能耗调度（`sched_compute_energy_tp`）
- 运行任务数变化（`sched_update_nr_running_tp`）

## 3. 关键实现

### SCHED_CORE 协同调度机制
- **任务分组**：通过 `core_cookie` 将需协同调度的任务归为一组（如来自同一 cgroup 或用户指定）。
- **红黑树组织**：每 CPU 的 `rq->core_tree` 按 `core_cookie` 和优先级维护任务，确保同组高优先级任务优先执行。
- **优先级映射**：
  - Stop 任务：`-2`
  - DL 任务（含 DL server）：`-1`
  - RT 任务：`[0, 99]`
  - Fair 任务：`119`
  - SCX 任务：`120`
  - Idle 任务：`140`
- **强制空闲处理**：当 CPU 处于 forced-idle 状态且最后一个运行任务被移出时，调用 `resched_curr()` 触发重调度，以更新 forced-idle 的会计统计并重新评估状态。

### 优先级比较逻辑
- `prio_less()` 实现跨调度类的统一优先级比较：
  - DL 任务按截止时间（deadline）排序（越早越高优）。
  - Fair 任务委托给 `cfs_prio_less()`（通常基于虚拟运行时间）。
  - SCX 任务委托给 `scx_prio_less()`（由 BPF 调度器定义）。
- 在 SCHED_CORE 中，通过 `__sched_core_less()` **反转优先级顺序**，使红黑树左端为最高优先级任务，便于快速选取。

### 调试与可观测性
- `CONFIG_SCHED_DEBUG` 启用后，提供运行时可调参数（如 `sysctl_sched_nr_migrate`）和延迟警告机制。
- 大量 tracepoint 覆盖调度器内部状态变化，支持性能分析与问题诊断。

## 4. 依赖关系

### 头文件依赖
- **调度子系统内部**：`sched.h`, `pelt.h`, `smp.h`, `stats.h`, `autogroup.h`
- **核心内核组件**：
  - 内存管理：`highmem.h`, `mm.h`, `mmu_context.h`
  - 锁与同步：`spinlock_api.h`, `mutex_api.h`, `rcuwait_api.h`
  - 时间与定时器：`ktime_api.h`, `hrtimer_api.h`, `jiffies.h`
  - CPU 拓扑与热插拔：`topology.h`, `sched/hotplug.h`
  - RCU 与中断：`hardirq.h`, `softirq.h`, `nmi.h`
- **架构相关**：`asm/switch_to.h`, `asm/tlb.h`, `asm/irq_regs.h`
- **其他子系统**：`workqueue_internal.h`, `io_uring/io-wq.h`, `psi.h`, `perf_event_api.h`

### 功能依赖
- **调度类**：CFS (`fair.c`)、RT (`rt.c`)、DL (`deadline.c`)、SCX (`scx.c`)
- **负载跟踪**：PELT（Per-Entity Load Tracking）算法
- **CPU 管理**：CPU 热插拔、隔离（`isolcpus`）、NO_HZ（动态 tick）
- **安全与权限**：`capability.h`, `cpuset.h`, `ioprio.h`

## 5. 使用场景

- **任务调度主路径**：每次调用 `schedule()` 时，调度器核心协调各调度类选择下一个运行任务。
- **负载均衡**：在 `migration` 线程或定时器中断中，通过 `sysctl_sched_nr_migrate` 限制单次迁移任务数。
- **SCHED_CORE 应用**：在需要多任务协同执行的场景（如 HPC、实时音视频处理），通过 `core.sched` 接口设置 `core_cookie` 实现组调度。
- **调试与监控**：
  - 通过 `/proc/sys/kernel/sched_*` 调整调度参数。
  - 使用 `ftrace` 或 `perf` 捕获 tracepoint 数据分析调度行为。
  - 启用 `LATENCY_WARN` 检测调度延迟异常。
- **系统初始化**：`scheduler_running` 标志在 `sched_init()` 中设置，确保调度器在 SMP 启动前就绪。
- **强制空闲管理**：在能耗敏感场景（如手机待机），配合 `core_forceidle_count` 实现 CPU 核心协同休眠。