# softirq.c

> 自动生成时间: 2025-10-25 16:26:22
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `softirq.c`

---

# softirq.c 技术文档

## 1. 文件概述

`softirq.c` 是 Linux 内核中实现软中断（softirq）机制的核心文件。软中断是一种延迟执行中断处理下半部（bottom half）的机制，用于在中断上下文之外安全、高效地处理高频率、低延迟要求的任务。该文件负责软中断的注册、调度、执行以及与内核其他子系统（如调度器、RCU、SMP 等）的协同工作，并为每个 CPU 维护独立的软中断状态，确保无锁化和良好的 CPU 局部性。

## 2. 核心功能

### 主要数据结构

- `softirq_vec[NR_SOFTIRQS]`：全局数组，存储所有软中断类型的处理函数（`softirq_action`），每个软中断类型（如 `NET_RX`、`TIMER` 等）对应一个条目。
- `ksoftirqd`：每 CPU 变量，指向该 CPU 上专用于处理软中断的内核线程（`ksoftirqd`）。
- `softirq_to_name[NR_SOFTIRQS]`：软中断类型的名称字符串数组，用于调试和追踪。
- `softirq_ctrl`（仅限 `CONFIG_PREEMPT_RT`）：每 CPU 结构体，包含本地锁（`local_lock_t`）和计数器（`cnt`），用于在实时内核中管理软中断禁用状态，支持抢占。
- `irq_stat`：每 CPU 的中断统计结构体（若架构未提供）。

### 主要函数

- `wakeup_softirqd()`：唤醒当前 CPU 的 `ksoftirqd` 内核线程。
- `__local_bh_disable_ip()` / `__local_bh_enable_ip()`：用于禁用/启用软中断（Bottom Half），并处理嵌套计数、RCU 锁、锁依赖追踪等。
- `local_bh_blocked()`（仅限 RT）：检查当前 CPU 是否处于软中断被阻塞状态，用于 idle 任务避免误报。
- `ksoftirqd_run_begin()` / `ksoftirqd_run_end()`：`ksoftirqd` 线程执行软中断前后的上下文管理。
- `invoke_softirq()`：根据当前软中断状态决定是否唤醒 `ksoftirqd`。
- `__do_softirq()`（声明在别处，但在此被调用）：实际执行挂起的软中断处理函数。

## 3. 关键实现

### 软中断执行模型
- 软中断是 **CPU 本地** 的，无共享变量，天然支持 SMP。
- 若软中断需要序列化（如 `TASKLET`），由其自身通过自旋锁实现。
- 软中断执行具有 **弱 CPU 绑定**：仅在触发中断的 CPU 上标记为待执行，提升缓存局部性。

### 实时内核（PREEMPT_RT）支持
- 在 `CONFIG_PREEMPT_RT` 下，软中断禁用状态不再依赖抢占计数器，而是使用每任务（`task_struct::softirq_disable_cnt`）和每 CPU（`softirq_ctrl::cnt`）两个计数器。
- 引入 `local_lock_t` 保护软中断临界区，允许在 BH 禁用期间被其他高优先级任务抢占。
- `ksoftirqd` 线程通过 `ksoftirqd_run_begin/end` 获取本地锁，确保重入安全。

### 软中断调度策略
- 当软中断在原子上下文（不可抢占）中被启用且有待处理任务时，不直接执行，而是唤醒 `ksoftirqd` 线程处理，避免用户空间饥饿。
- 在可抢占上下文中启用软中断时，若有待处理软中断，则立即调用 `__do_softirq()` 执行。

### 调试与追踪
- 集成 `lockdep` 锁依赖分析器，通过 `bh_lock_map` 跟踪软中断禁用区域。
- 支持 `ftrace` 的 `irq` 事件追踪（通过 `trace/events/irq.h`）。
- 提供 `in_softirq()`、`softirq_count()` 等宏用于上下文判断。

## 4. 依赖关系

- **中断子系统**：依赖 `irq.h`、`interrupt.h` 提供硬中断接口和状态管理。
- **调度器**：与 `kthread.h` 协作创建和管理 `ksoftirqd` 内核线程；依赖 `sched.h` 相关机制进行唤醒和调度。
- **RCU**：在 RT 模式下，软中断禁用区域需持有 `rcu_read_lock()`，确保 RCU 语义正确。
- **SMP 支持**：使用 `smp.h`、`smpboot.h` 实现每 CPU 变量和 CPU 热插拔支持。
- **内存管理**：依赖 `mm.h` 和 `percpu.h` 管理每 CPU 数据。
- **调试设施**：集成 `lockdep`（`DEBUG_LOCK_ALLOC`）、`ftrace`、`irqflags tracing` 等调试框架。
- **架构相关代码**：可能使用 `asm/softirq_stack.h` 提供的架构特定栈处理。

## 5. 使用场景

- **网络子系统**：`NET_RX` 和 `NET_TX` 软中断用于高效处理网络包接收和发送。
- **块设备层**：`BLOCK` 软中断处理块 I/O 完成回调。
- **定时器**：`TIMER` 和 `HRTIMER` 软中断用于执行高精度和普通定时器回调。
- **RCU**：`RCU` 软中断用于执行宽限期（grace period）相关的回调。
- **任务队列**：`TASKLET` 软中断提供轻量级、序列化的下半部机制。
- **调度器事件**：`SCHED` 软中断用于处理调度相关的延迟任务（如负载均衡触发）。
- **中断轮询**：`IRQ_POLL` 用于高吞吐场景下的中断合并与轮询。

该机制广泛应用于需要在中断后快速、批量、低开销处理任务的内核子系统中，是 Linux 中断处理下半部的核心基础设施之一。