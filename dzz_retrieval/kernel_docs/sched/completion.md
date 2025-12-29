# sched\completion.c

> 自动生成时间: 2025-10-25 15:59:12
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\completion.c`

---

# `sched/completion.c` 技术文档

## 1. 文件概述

`sched/completion.c` 实现了 Linux 内核中的 **completion（完成量）** 同步原语。该机制用于一个或多个线程等待某个事件完成后再继续执行。与信号量（semaphore）不同，completion 的默认行为是阻塞等待，且其语义明确表示“等待某事完成”，而非用于互斥访问，因此避免了因互斥导致的优先级反转问题。completion 支持唤醒单个或所有等待者，并提供多种等待变体（不可中断、可中断、可被 kill、带超时、IO 等待等）。

## 2. 核心功能

### 主要函数

- **`complete(struct completion *x)`**  
  唤醒一个等待在 completion `x` 上的线程（按 FIFO 顺序）。

- **`complete_all(struct completion *x)`**  
  唤醒所有等待在 `x` 上的线程，并将 `x->done` 设为 `UINT_MAX`，表示永久完成。

- **`complete_on_current_cpu(struct completion *x)`**  
  在当前 CPU 上唤醒一个等待者，用于优化调度局部性。

- **`wait_for_completion(struct completion *x)`**  
  不可中断地无限期等待 completion 完成。

- **`wait_for_completion_timeout(...)`**  
  带超时的不可中断等待。

- **`wait_for_completion_io(...)` / `wait_for_completion_io_timeout(...)`**  
  用于 IO 上下文的等待，调度器将其归类为 IO 等待。

- **`wait_for_completion_interruptible(...)`**  
  可被信号中断的等待。

- **`wait_for_completion_interruptible_timeout(...)`**  
  可中断且带超时的等待。

- **`wait_for_completion_killable(...)`**  
  仅可被 kill 信号（如 SIGKILL）中断的等待。

### 核心数据结构（隐含）

- **`struct completion`**（定义在 `<linux/completion.h>`）  
  包含：
  - `unsigned int done`：完成计数，0 表示未完成，>0 表示可唤醒的等待者数量，`UINT_MAX` 表示已调用 `complete_all()`。
  - `struct swait_queue_head wait`：基于 simple waitqueue 的等待队列。

## 3. 关键实现

### 完成信号机制
- `complete()` 和 `complete_on_current_cpu()` 通过 `complete_with_flags()` 实现，增加 `done` 计数（除非已达 `UINT_MAX`），并调用 `swake_up_locked()` 唤醒一个等待者。
- `complete_all()` 将 `done` 设为 `UINT_MAX`，并调用 `swake_up_all_locked()` 唤醒所有等待者。此后 `done` 不再递减，因此需调用 `reinit_completion()` 才能复用。

### 等待逻辑
- 所有 `wait_for_*` 函数最终调用 `__wait_for_common()`，后者：
  1. 调用 `complete_acquire()`（用于 lockdep 跟踪）。
  2. 获取自旋锁，进入 `do_wait_for_common()`。
  3. 若 `done == 0`，则加入等待队列，设置任务状态（如 `TASK_UNINTERRUPTIBLE`），释放锁，调用调度函数（如 `schedule_timeout`）。
  4. 被唤醒后重新获取锁，检查是否完成或超时。
  5. 若成功完成且未调用 `complete_all()`，则 `done` 计数减 1。
  6. 调用 `complete_release()` 结束 lockdep 跟踪。

### 内存屏障与调度
- 唤醒操作（`swake_up*`）内部包含完整的内存屏障，确保唤醒前的写操作对被唤醒任务可见。
- `complete_on_current_cpu()` 使用 `WF_CURRENT_CPU` 标志，优化唤醒路径，避免跨 CPU 调度开销。

### 中断与超时处理
- 可中断/可 kill 等待在每次调度前检查信号（`signal_pending_state()`），若存在有效信号则返回 `-ERESTARTSYS`。
- 超时值以 jiffies 为单位，返回值语义：
  - `0`：超时；
  - 正数：剩余 jiffies（至少为 1）；
  - 负数：错误码（如 `-ERESTARTSYS`）。

## 4. 依赖关系

- **`<linux/completion.h>`**：定义 `struct completion` 及 API 声明。
- **`<linux/swait.h>`**：使用 simple waitqueue（`swait_queue_head`、`swake_up*` 等）实现高效等待队列。
- **`<linux/sched.h>`**：依赖任务状态（`TASK_*`）、调度函数（`schedule_timeout`、`io_schedule_timeout`）及内存屏障。
- **Lockdep**：通过 `complete_acquire()`/`complete_release()` 集成死锁检测。
- **RT 补丁支持**：`complete_all()` 中包含 `lockdep_assert_RT_in_threaded_ctx()`，用于实时内核上下文检查。

## 5. 使用场景

- **驱动程序同步**：设备操作完成后通知等待线程（如 DMA 传输完成）。
- **内核线程协调**：一个线程等待另一个线程完成初始化或清理工作。
- **异步操作完成通知**：如文件系统或网络子系统中等待后台任务结束。
- **模块卸载同步**：确保所有使用模块的线程退出后再卸载。
- **IO 路径等待**：使用 `wait_for_completion_io*` 变体，使调度器正确统计 IO 等待时间。

> **注意**：`complete_all()` 后必须调用 `reinit_completion()` 才能复用 completion 对象，且需确保所有等待者已退出。`completion_done()` 不能用于判断 `complete_all()` 后是否仍有等待者。