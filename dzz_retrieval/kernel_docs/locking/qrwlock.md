# locking\qrwlock.c

> 自动生成时间: 2025-10-25 14:45:12
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `locking\qrwlock.c`

---

# `locking/qrwlock.c` 技术文档

## 1. 文件概述

`qrwlock.c` 实现了 **排队读写锁（Queued Read-Write Lock, qrwlock）** 的慢路径（slowpath）逻辑。该机制在标准读写锁基础上引入了排队语义，以减少高并发场景下的缓存行抖动（cache line bouncing）并提升可扩展性。当快速路径（fastpath）无法立即获取锁时，调用本文件中的慢路径函数进行阻塞或自旋等待。

## 2. 核心功能

### 主要函数

- `queued_read_lock_slowpath(struct qrwlock *lock)`  
  获取排队读写锁的**读锁**慢路径实现。当快速路径失败时被调用。

- `queued_write_lock_slowpath(struct qrwlock *lock)`  
  获取排队读写锁的**写锁**慢路径实现。当快速路径失败时被调用。

### 关键数据结构（隐含依赖）

- `struct qrwlock`：排队读写锁结构体（定义在头文件中），包含：
  - `cnts`：原子计数器，编码读锁数量、写锁状态和等待标志。
  - `wait_lock`：底层自旋锁，用于保护等待队列的串行化访问。

### 核心常量（来自头文件）

- `_QR_BIAS`：读计数的偏移量（通常为 `1U << _QR_SHIFT`）。
- `_QW_LOCKED`：表示写锁已被持有。
- `_QW_WAITING`：表示有写者正在等待。

## 3. 关键实现

### 读锁慢路径 (`queued_read_lock_slowpath`)

1. **中断上下文特殊处理**：  
   若调用者处于中断上下文（`in_interrupt()` 为真），则直接使用 `atomic_cond_read_acquire()` 自旋等待写锁释放，**不进入等待队列**，避免死锁风险。

2. **普通上下文流程**：
   - 先从 `cnts` 中减去 `_QR_BIAS`（临时“取消”读请求）。
   - 调用 `trace_contention_begin()` 记录锁竞争事件。
   - 获取 `wait_lock` 自旋锁，进入临界区。
   - 恢复 `_QR_BIAS`（重新声明读请求）。
   - 使用 `atomic_cond_read_acquire()` 自旋等待 `cnts` 中无写锁（`!(VAL & _QW_LOCKED)`）。
   - 释放 `wait_lock`，结束竞争跟踪。

> **关键点**：通过 `wait_lock` 串行化所有慢路径读者，避免多个读者同时修改 `cnts` 导致的 ABA 问题；`atomic_cond_read_acquire()` 提供 ACQUIRE 语义，确保后续临界区访问不会重排到锁获取之前。

### 写锁慢路径 (`queued_write_lock_slowpath`)

1. **尝试直接获取**：  
   在持有 `wait_lock` 后，若 `cnts == 0`（无读者/写者），则通过 `atomic_try_cmpxchg_acquire()` 直接设置 `_QW_LOCKED` 获取锁。

2. **设置等待标志**：  
   若无法直接获取，通过 `atomic_or(_QW_WAITING, &lock->cnts)` 通知读者有写者等待，阻止新读者进入。

3. **等待并获取锁**：  
   - 使用 `atomic_cond_read_relaxed()` 等待 `cnts` 变为 `_QW_WAITING`（即所有读者退出，仅剩等待标志）。
   - 通过 `atomic_try_cmpxchg_acquire()` 将状态从 `_QW_WAITING` 原子替换为 `_QW_LOCKED`，完成锁获取。

> **关键点**：`_QW_WAITING` 标志用于阻塞新读者；`wait_lock` 确保写者按 FIFO 顺序排队；`atomic_cond_read_relaxed()` + `try_cmpxchg_acquire` 组合实现无锁等待与安全状态转换。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/smp.h>`：SMP 相关宏（如 `in_interrupt()`）。
  - `<linux/atomic.h>`（隐含）：原子操作（`atomic_read`, `atomic_sub`, `atomic_try_cmpxchg_acquire` 等）。
  - `<linux/spinlock.h>`：提供 `arch_spin_lock/unlock`。
  - `<trace/events/lock.h>`：锁竞争跟踪事件。

- **架构依赖**：
  - `arch_spinlock_t` 和 `arch_spin_lock/unlock` 由具体架构实现（如 x86、ARM）。
  - `atomic_cond_read_acquire/relaxed` 依赖架构的原子内存操作语义。

- **配套组件**：
  - 快速路径实现在头文件（如 `qrwlock.h`）中以内联函数形式提供。
  - 与内核锁调试、性能分析子系统（如 lockdep、ftrace）集成。

## 5. 使用场景

- **高并发读多写少场景**：  
  如文件系统元数据访问、网络协议栈状态表、RCU 替代方案等，需允许多个读者并发访问，同时保证写者互斥。

- **实时性要求较高的写路径**：  
  通过排队机制避免写者饿死，确保写请求按 FIFO 顺序处理。

- **中断上下文读操作**：  
  支持在中断处理程序中安全获取读锁（仅限慢路径中的特殊处理分支）。

- **替代传统 rwlock**：  
  在需要更好可扩展性和公平性的场景中，替代内核原有的 `rwlock_t`。