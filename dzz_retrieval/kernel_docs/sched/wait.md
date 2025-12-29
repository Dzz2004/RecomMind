# sched\wait.c

> 自动生成时间: 2025-10-25 16:20:46
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\wait.c`

---

# `sched/wait.c` 技术文档

## 1. 文件概述

`sched/wait.c` 是 Linux 内核中实现通用等待队列（wait queue）机制的核心文件。该机制用于线程在特定条件满足前进入睡眠状态，并在条件就绪时被唤醒。文件提供了等待队列的初始化、添加/移除等待项、以及多种唤醒策略（包括普通唤醒、独占唤醒、优先级唤醒、同步唤醒等）的实现，是内核同步与调度子系统的重要组成部分。

## 2. 核心功能

### 主要函数

- **`__init_waitqueue_head`**  
  初始化一个等待队列头，设置自旋锁、锁类信息和空链表。

- **`add_wait_queue`**  
  将一个非独占等待项添加到等待队列头部。

- **`add_wait_queue_exclusive`**  
  将一个独占等待项添加到等待队列尾部（用于避免“惊群”问题）。

- **`add_wait_queue_priority`**  
  添加具有独占性和优先级标志的等待项，插入到队列头部。

- **`remove_wait_queue`**  
  从等待队列中安全移除指定的等待项。

- **`__wake_up` / `__wake_up_common`**  
  核心唤醒函数，支持唤醒非独占任务和指定数量的独占任务。

- **`__wake_up_sync_key` / `__wake_up_locked_sync_key`**  
  同步唤醒函数，避免目标任务被迁移到其他 CPU，减少缓存颠簸。

- **`__wake_up_on_current_cpu`**  
  仅在当前 CPU 上唤醒一个任务。

- **`__wake_up_pollfree`**  
  专用于 poll 机制的唤醒，发送 `POLLFREE` 事件并验证队列已清空。

- **`prepare_to_wait` / `prepare_to_wait_exclusive`**  
  将当前任务加入等待队列并设置其睡眠状态，后者返回是否为队列中首个等待者。

### 关键数据结构

- **`struct wait_queue_head`**  
  等待队列头，包含自旋锁 `lock` 和双向链表 `head`。

- **`struct wait_queue_entry`**  
  等待队列项，包含回调函数 `func`、任务指针、标志位（如 `WQ_FLAG_EXCLUSIVE`、`WQ_FLAG_PRIORITY`）及链表节点。

## 3. 关键实现

### 等待队列组织策略

- **非独占任务**：通过 `add_wait_queue` 添加至队列**头部**，唤醒时优先处理。
- **独占任务**：通过 `add_wait_queue_exclusive` 添加至队列**尾部**，确保在非独占任务之后唤醒，避免多个独占任务同时被唤醒（解决“惊群”问题）。
- **优先级任务**：通过 `add_wait_queue_priority` 添加至**头部**，并标记为独占+优先级，可在唤醒时优先消费事件。

### 唤醒逻辑（`__wake_up_common`）

1. 遍历等待队列中的每个等待项。
2. 调用其回调函数 `func`（通常为 `default_wake_function`），尝试唤醒对应任务。
3. 若回调返回正值且该项为独占任务，则减少 `nr_exclusive` 计数；当计数归零时停止唤醒。
4. 非独占任务始终被唤醒（除非回调返回负值中断流程）。

### 内存屏障与 SMP 安全

- 在 `prepare_to_wait` 中，**先加锁添加等待项，再调用 `set_current_state()`**，确保 SMP 系统下唤醒者能看到完整的等待状态，避免竞态。
- 所有对外接口均使用 `spin_lock_irqsave`/`restore` 保证中断上下文安全。

### 同步唤醒优化

- `WF_SYNC` 标志告知调度器：唤醒者即将主动调度（如调用 `schedule()`），因此被唤醒任务应尽量留在当前 CPU，减少迁移开销。
- 在单处理器（UP）系统上可避免不必要的抢占。

## 4. 依赖关系

- **调度子系统**：依赖 `try_to_wake_up()` 等底层唤醒函数（定义于 `kernel/sched/core.c`）。
- **锁调试机制**：使用 `lockdep_set_class_and_name` 进行锁类跟踪（`kernel/locking/lockdep.c`）。
- **内存屏障原语**：依赖架构相关的内存屏障实现（如 `smp_mb()`）。
- **poll 机制**：`__wake_up_pollfree` 与 `fs/select.c` 中的 poll 实现紧密耦合。
- **EXPORT_SYMBOL**：向内核其他模块（如驱动、文件系统）导出通用等待/唤醒接口。

## 5. 使用场景

- **设备驱动**：驱动程序在无数据可读/写时将进程加入等待队列，硬件就绪时唤醒。
- **文件系统**：如 inode 锁、页缓存 I/O 等待。
- **IPC 机制**：信号量、互斥锁、完成量（completion）等同步原语的底层实现。
- **网络子系统**：socket 接收/发送缓冲区满或空时的阻塞等待。
- **内核线程同步**：工作者线程等待工作项到达。
- **poll/epoll**：通过 `poll_wait()` 注册等待队列，事件触发时唤醒用户进程。