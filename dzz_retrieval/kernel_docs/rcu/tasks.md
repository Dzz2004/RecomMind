# rcu\tasks.h

> 自动生成时间: 2025-10-25 15:45:09
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rcu\tasks.h`

---

# `rcu/tasks.h` 技术文档

## 1. 文件概述

`rcu/tasks.h` 是 Linux 内核中实现 **基于任务的 RCU（Read-Copy-Update）机制** 的核心头文件。该机制扩展了传统 RCU 的语义，使其能够感知任务（task）状态（如用户态执行、阻塞、退出等），从而在特定场景（如用户空间 RCU、跟踪 RCU、通用任务 RCU）下提供更高效的宽限期（grace period）检测能力。此文件定义了通用的任务 RCU 框架所需的数据结构、回调函数类型和宏，为不同变体（如 `tasks_rcu`、`tasks_trace_rcu` 等）提供统一的实现基础。

## 2. 核心功能

### 主要数据结构

- **`struct rcu_tasks_percpu`**  
  每 CPU 的任务 RCU 组件，包含：
  - 回调链表（`cblist`）及其保护锁（`lock`）
  - 统计字段（`rtp_jiffies`, `rtp_n_lock_retries`）
  - 懒回调定时器（`lazy_timer`）和紧急宽限期计数（`urgent_gp`）
  - 工作队列（`rtp_work`）和中断上下文工作（`rtp_irq_work`）
  - 屏障操作相关字段（`barrier_q_head`）
  - 被阻塞任务列表（`rtp_blkd_tasks`）和退出任务列表（`rtp_exit_list`）
  - CPU 编号及指向全局 `rcu_tasks` 实例的指针

- **`struct rcu_tasks`**  
  全局任务 RCU 实例定义，包含：
  - 宽限期控制（`gp_func`, `tasks_gp_mutex`, `tasks_gp_seq`）
  - 各阶段回调函数指针（`pregp_func`, `pertask_func`, `postscan_func`, `holdouts_func`, `postgp_func`）
  - 回调管理（`call_func`, `rtpcpu`, `rtpcp_array`）
  - 多队列回调分发控制（`percpu_enqueue_shift/lim`, `percpu_dequeue_lim`）
  - 屏障同步机制（`barrier_q_mutex`, `barrier_q_count`, `barrier_q_completion`）
  - 调试与统计字段（`gp_state`, `n_ipis`, `name`, `kname`）

### 主要函数类型定义

- `rcu_tasks_gp_func_t`：宽限期等待函数
- `pregp_func_t`：宽限期前预处理函数
- `pertask_func_t`：遍历每个任务的处理函数
- `postscan_func_t`：任务扫描后处理函数
- `holdouts_func_t`：检查未完成宽限期任务（holdouts）的函数
- `postgp_func_t`：宽限期结束后处理函数

### 宏定义

- **`DEFINE_RCU_TASKS(rt_name, gp, call, n)`**  
  用于静态定义一个完整的任务 RCU 实例，包括每 CPU 变量和全局结构体，并初始化关键字段（如锁、工作队列、名称、回调函数等）。

### 全局参数（可通过 sysfs 调整）

- `rcu_task_ipi_delay`：宽限期初期延迟发送 IPI 的时间（避免过早中断）
- `rcu_task_stall_timeout`：宽限期卡住超时阈值（默认 10 分钟）
- `rcu_task_stall_info`：卡住信息打印间隔（默认 10 秒）
- `rcu_task_enqueue_lim`：回调入队 CPU 队列数量限制
- `rcu_task_contend_lim` / `collapse_lim` / `lazy_lim`：用于动态调整回调队列行为的阈值

### 调试状态常量

- `RTGS_*` 系列宏（如 `RTGS_INIT`, `RTGS_SCAN_TASKLIST` 等）：用于跟踪任务 RCU 宽限期状态机的当前阶段，便于调试。

## 3. 关键实现

- **通用任务 RCU 框架**：通过 `struct rcu_tasks` 将不同变体（如用户态 RCU、跟踪 RCU）的共性抽象出来，使用函数指针实现策略定制。
- **多队列回调分发**：支持将 RCU 回调分散到多个 per-CPU 队列（通过 `percpu_enqueue_shift` 控制），以减少锁竞争，提升可扩展性。
- **懒回调机制**：通过 `lazy_timer` 和 `lazy_jiffies` 实现延迟执行非紧急回调，减少上下文切换开销。
- **宽限期状态机**：使用 `gp_state` 字段记录宽限期执行阶段，配合 `RTGS_*` 常量实现清晰的状态流转，便于诊断卡住问题。
- **屏障（Barrier）支持**：通过 `barrier_q_*` 字段实现 `rcu_barrier()` 类操作，确保所有已提交回调执行完毕。
- **动态队列调整**：根据锁竞争情况（`rtp_n_lock_retries`）和系统负载，动态调整入队/出队队列数量（`rcu_task_cb_adjust` 相关逻辑，虽未在本文件完整体现，但结构已预留支持）。

## 4. 依赖关系

- **`rcu_segcblist.h`**：提供分段回调链表（`rcu_segcblist`）实现，用于高效管理不同状态的 RCU 回调。
- **`CONFIG_TASKS_RCU_GENERIC`**：本文件功能的编译开关，需启用此配置。
- **`CONFIG_TASKS_RCU`**：启用标准任务 RCU（用户态感知）时，会包含额外逻辑（如 `tasks_rcu_exit_srcu_stall_timer`）。
- **`CONFIG_TASKS_TRACE_RCU_READ_MB`**：影响 `rcu_task_ipi_delay` 的默认值，用于跟踪 RCU 场景。
- **内核基础组件**：依赖 `raw_spinlock_t`、`mutex`、`workqueue`、`irq_work`、`timer`、`completion` 等内核同步与调度原语。

## 5. 使用场景

- **用户空间 RCU（Tasks RCU）**：当需要等待所有曾经运行在用户空间的任务完成其 RCU 读端临界区时使用（例如模块卸载、内存回收）。
- **跟踪 RCU（Tasks Trace RCU）**：用于 ftrace 等跟踪子系统，确保在修改跟踪点时所有可能执行跟踪代码的上下文（包括内核线程）都已完成。
- **通用任务宽限期检测**：任何需要等待“所有可能持有某种资源引用的任务”完成的场景，均可基于此框架实现定制化 RCU 变体。
- **内核模块与子系统同步**：为需要与任务生命周期强关联的内核组件提供高效、可扩展的同步原语。