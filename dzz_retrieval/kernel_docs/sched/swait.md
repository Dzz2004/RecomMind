# sched\swait.c

> 自动生成时间: 2025-10-25 16:18:23
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\swait.c`

---

# `sched/swait.c` 技术文档

## 1. 文件概述

`sched/swait.c` 是 Linux 内核中 **简单等待队列（simple wait queues）** 的核心实现文件，对应头文件为 `<linux/swait.h>`。该机制提供了一种轻量级、低开销的进程等待与唤醒基础设施，相比传统的 `wait_queue`，`swait` 去除了复杂的回调函数、唤醒过滤器等特性，仅保留最基本的 FIFO 等待队列功能，适用于对性能和代码简洁性要求较高的场景（如 completion 机制）。

## 2. 核心功能

### 主要数据结构
- `struct swait_queue_head`：简单等待队列头，包含一个自旋锁 `lock` 和一个任务链表 `task_list`。
- `struct swait_queue`：代表一个等待项，包含指向当前任务 `task` 的指针和链表节点 `task_list`。

### 主要函数

| 函数名 | 功能描述 |
|--------|---------|
| `__init_swait_queue_head()` | 初始化 `swait_queue_head` 结构，设置锁类信息和初始化链表。 |
| `swake_up_locked()` | 在已持有队列锁的前提下，唤醒队列中的**第一个**等待任务并将其从队列中移除。 |
| `swake_up_all_locked()` | 在已持有队列锁的前提下，**循环唤醒所有**等待任务（专用于 completion）。 |
| `swake_up_one()` | 安全地唤醒队列中的**第一个**等待任务（自动加锁/关中断）。 |
| `swake_up_all()` | 安全地唤醒**所有**等待任务，支持从中断上下文调用，但内部会临时释放锁以避免长时间持锁。 |
| `__prepare_to_swait()` | 将当前任务加入等待队列（需外部加锁）。 |
| `prepare_to_swait_exclusive()` | 将当前任务以指定状态加入等待队列，并设置任务状态（自动加锁/关中断）。 |
| `prepare_to_swait_event()` | 类似 `prepare_to_swait_exclusive()`，但会检查是否有挂起信号，若有则返回 `-ERESTARTSYS`。 |
| `__finish_swait()` / `finish_swait()` | 清理等待状态，将任务从队列中移除并恢复为 `TASK_RUNNING` 状态。 |

## 3. 关键实现

### 等待队列管理
- 所有等待任务通过 `list_add_tail()` 按 FIFO 顺序加入 `q->task_list`。
- 每个 `swait_queue` 实例通常作为局部变量在栈上分配，生命周期由调用者控制。

### 唤醒机制
- **`swake_up_locked()`**：仅唤醒队首任务，适用于“一次唤醒一个”的场景（如互斥资源）。
- **`swake_up_all()`**：
  - 先将整个等待链表 `splice` 到临时链表 `tmp`，避免在唤醒过程中队列被并发修改。
  - 采用 **“唤醒一个 → 释放锁 → 重新加锁”** 的循环策略，防止在唤醒大量任务时长时间持有自旋锁，从而避免影响系统实时性。
  - **不适用于中断上下文**（因其内部会启用中断）。
- **`swake_up_all_locked()`**：
  - 专为 **completion** 设计，可在硬中断上下文或关中断区域调用。
  - 直接循环调用 `swake_up_locked()`，不释放锁，因此要求调用者确保上下文安全。

### 信号处理
- `prepare_to_swait_event()` 在加入队列前检查 `signal_pending_state()`，若存在挂起信号，则**不加入队列**并返回 `-ERESTARTSYS`，确保后续 `swake_up_one()` 不会错误唤醒一个本应被信号中断的任务。

### 锁与中断控制
- 所有对外接口（如 `swake_up_one`, `prepare_to_swait_exclusive`）均使用 `raw_spin_lock_irqsave()` / `raw_spin_unlock_irqrestore()`，保证在中断上下文和 SMP 环境下的安全性。
- `finish_swait()` 使用 `list_empty_careful()` 避免在无锁情况下误判链表状态，仅在必要时加锁删除节点。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/swait.h>`：定义 `swait_queue_head` 和 `swait_queue` 结构及函数原型。
  - `<linux/sched.h>`：提供 `try_to_wake_up()`, `wake_up_state()`, `set_current_state()` 等调度器接口。
  - `<linux/list.h>`：提供链表操作宏。
  - `<linux/spinlock.h>`：提供原始自旋锁实现。
  - `<linux/lockdep.h>`：用于锁类调试（`lockdep_set_class_and_name`）。
- **模块依赖**：
  - **Completion 机制**（`kernel/completion.c`）：是 `swait` 的主要用户，依赖 `swake_up_all_locked()` 实现中断安全的批量唤醒。
  - 其他需要轻量级等待机制的子系统（如某些驱动或底层同步原语）。

## 5. 使用场景

- **Completion 同步原语**：`swait` 是 completion 的底层实现基础，用于线程间“完成通知”场景。
- **轻量级条件等待**：当不需要传统 `wait_queue` 的复杂功能（如唤醒回调、非互斥等待等）时，可使用 `swait` 减少开销。
- **中断上下文唤醒**：通过 `swake_up_all_locked()`，允许在硬中断或关中断区域安全地唤醒等待任务（仅限 completion 使用）。
- **性能敏感路径**：由于 `swait` 代码路径短、无动态内存分配、无复杂逻辑，适用于对延迟要求极高的内核路径。