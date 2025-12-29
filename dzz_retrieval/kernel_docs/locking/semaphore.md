# locking\semaphore.c

> 自动生成时间: 2025-10-25 14:52:31
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `locking\semaphore.c`

---

# `locking/semaphore.c` 技术文档

## 1. 文件概述

`locking/semaphore.c` 实现了 Linux 内核中的**计数信号量（counting semaphore）**机制。计数信号量允许多个任务（最多为初始计数值）同时持有该锁，当计数值耗尽时，后续请求者将被阻塞，直到有其他任务释放信号量。与互斥锁（mutex）不同，信号量支持更灵活的并发控制，适用于资源池、限流等场景。该文件提供了多种获取和释放信号量的接口，包括可中断、可超时、不可中断等变体，并支持在中断上下文中调用部分函数。

## 2. 核心功能

### 主要函数

| 函数名 | 功能描述 |
|--------|--------|
| `down(struct semaphore *sem)` | 不可中断地获取信号量，若不可用则睡眠。**已弃用**，建议使用可中断版本。 |
| `down_interruptible(struct semaphore *sem)` | 可被普通信号中断的获取操作，成功返回 0，被信号中断返回 `-EINTR`。 |
| `down_killable(struct semaphore *sem)` | 可被致命信号（fatal signal）中断的获取操作，返回值同上。 |
| `down_trylock(struct semaphore *sem)` | 非阻塞尝试获取信号量，成功返回 0，失败返回 1（**注意返回值与 mutex/spinlock 相反**）。 |
| `down_timeout(struct semaphore *sem, long timeout)` | 带超时的获取操作，超时返回 `-ETIME`，成功返回 0。 |
| `up(struct semaphore *sem)` | 释放信号量，可由任意上下文（包括中断）调用，唤醒等待队列中的任务。 |

### 静态辅助函数

- `__down*()` 系列：处理信号量争用时的阻塞逻辑。
- `__up()`：在有等待者时执行唤醒逻辑。
- `___down_common()`：通用的阻塞等待实现，支持不同睡眠状态和超时。
- `__sem_acquire()`：原子减少计数并记录持有者（用于 hung task 检测）。

### 数据结构

- `struct semaphore`（定义在 `<linux/semaphore.h>`）：
  - `count`：当前可用资源数（>0 表示可立即获取）。
  - `wait_list`：等待该信号量的任务链表。
  - `lock`：保护上述成员的原始自旋锁（`raw_spinlock_t`）。
  - `last_holder`（条件编译）：记录最后持有者，用于 `CONFIG_DETECT_HUNG_TASK_BLOCKER`。

- `struct semaphore_waiter`：
  - 用于将任务加入等待队列，包含任务指针和唤醒标志（`up`）。

## 3. 关键实现

### 中断安全与自旋锁
- 所有对外接口（包括 `down*` 和 `up`）均使用 `raw_spin_lock_irqsave()` 获取自旋锁，确保在中断上下文安全。
- 即使 `down()` 等函数通常在进程上下文调用，也使用 `irqsave` 变体，因为内核某些部分依赖在中断上下文成功调用 `down()`（当确定信号量可用时）。

### 计数语义
- `sem->count` 表示**还可被获取的次数**。初始值由 `sema_init()` 设置。
- 获取时：若 `count > 0`，直接减 1；否则加入等待队列。
- 释放时：若等待队列为空，`count++`；否则唤醒队首任务。

### 等待与唤醒机制
- 使用 `wake_q`（批量唤醒队列）优化唤醒路径，避免在持有自旋锁时调用 `wake_up_process()`。
- 等待任务通过 `schedule_timeout()` 睡眠，并在循环中检查：
  - 是否收到信号（根据睡眠状态判断）。
  - 是否超时。
  - 是否被 `__up()` 标记为 `waiter.up = true`（表示已被选中唤醒）。

### Hung Task 支持
- 当启用 `CONFIG_DETECT_HUNG_TASK_BLOCKER` 时：
  - 获取信号量时记录当前任务为 `last_holder`。
  - 释放时若当前任务是持有者，则清除记录。
  - 提供 `sem_last_holder()` 供 hung task 检测模块查询阻塞源头。

### 返回值约定
- `down_trylock()` 返回 **0 表示成功**，**1 表示失败**，这与 `mutex_trylock()` 和 `spin_trylock()` **相反**，需特别注意。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/semaphore.h>`：信号量结构体和 API 声明。
  - `<linux/spinlock.h>`：原始自旋锁实现。
  - `<linux/sched.h>`、`<linux/sched/wake_q.h>`：任务调度和批量唤醒。
  - `<trace/events/lock.h>`：锁争用跟踪点。
  - `<linux/hung_task.h>`：hung task 检测支持。

- **内核配置依赖**：
  - `CONFIG_DETECT_HUNG_TASK_BLOCKER`：启用信号量持有者跟踪。

- **与其他同步原语关系**：
  - 与 `mutex.c` 形成对比：mutex 是二值、不可递归、带调试信息的互斥锁；信号量是计数、可被任意任务释放、更轻量。
  - 底层依赖调度器（`schedule_timeout`）和中断管理（`irqsave`）。

## 5. 使用场景

- **资源池管理**：如限制同时访问某类硬件设备的任务数量。
- **读写并发控制**：配合其他机制实现多读者/单写者模型。
- **内核驱动**：设备驱动中控制对共享资源的并发访问。
- **中断上下文释放**：因 `up()` 可在中断中调用，适用于中断处理程序释放资源的场景。
- **不可睡眠路径**：使用 `down_trylock()` 在原子上下文尝试获取资源。

> **注意**：由于信号量不强制所有权（任意任务可调用 `up()`），且缺乏死锁检测等调试特性，现代内核开发中更推荐使用 `mutex` 或 `rwsem`，除非明确需要计数语义或多释放者特性。