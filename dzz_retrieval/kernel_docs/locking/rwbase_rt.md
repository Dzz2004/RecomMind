# locking\rwbase_rt.c

> 自动生成时间: 2025-10-25 14:50:50
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `locking\rwbase_rt.c`

---

# `locking/rwbase_rt.c` 技术文档

## 1. 文件概述

`rwbase_rt.c` 是 Linux 内核实时（RT）补丁中用于实现 **实时读者-写者同步原语**（包括 `rw_semaphore` 和 `rwlock`）的通用底层代码。该文件为实时调度环境（如 `PREEMPT_RT`）提供了一套基于 `rtmutex` 的读写锁实现，以解决传统读写锁在实时系统中可能导致的优先级反转和不可预测延迟问题。

该实现通过将写者操作与 `rtmutex` 绑定，利用 `rtmutex` 的优先级继承（PI）或截止时间（DL）调度机制，确保写者不会被低优先级读者无限阻塞，同时在多数情况下允许读者通过无锁快速路径（fast path）高效执行。

## 2. 核心功能

### 主要数据结构
- `struct rwbase_rt`：读写同步原语的通用底层结构，包含：
  - `atomic_t readers`：读者计数器，使用偏置（bias）机制区分读/写状态
  - `struct rt_mutex_base rtmutex`：底层实时互斥锁，用于串行化写者和阻塞读者

### 关键常量
- `READER_BIAS`：正偏置值（通常为 `0x7fffffff`），表示允许读者使用快速路径
- `WRITER_BIAS`：负偏置值（通常为 `-0x80000000`），表示写者已持有锁

### 主要函数

| 函数 | 功能 |
|------|------|
| `rwbase_read_trylock()` | 尝试快速获取读锁（仅当 `READER_BIAS` 存在时） |
| `__rwbase_read_lock()` / `rwbase_read_lock()` | 获取读锁（慢路径 + 快路径组合） |
| `__rwbase_read_unlock()` / `rwbase_read_unlock()` | 释放读锁，必要时唤醒等待的写者 |
| `__rwbase_write_unlock()` / `rwbase_write_unlock()` | 释放写锁，恢复 `READER_BIAS` 并释放 `rtmutex` |
| `rwbase_write_downgrade()` | 将写锁降级为读锁 |
| `__rwbase_write_trylock()` | 在持有 `wait_lock` 下尝试获取写锁 |
| `rwbase_write_lock()` | 获取写锁（完整慢路径，含阻塞等待） |
| `rwbase_write_trylock()` | 尝试非阻塞获取写锁（代码片段未完整） |

## 3. 关键实现

### 3.1 读者-写者状态管理
- 使用 `atomic_t readers` 字段统一管理状态：
  - **初始状态**：`readers = READER_BIAS`（正值），允许读者走快速路径
  - **写者加锁时**：先获取 `rtmutex`，然后 `atomic_sub(READER_BIAS, &readers)`，使值变为负或零，强制后续读者进入慢路径
  - **写者持有锁**：`readers = WRITER_BIAS`（最小负值）
  - **读者持有锁**：`readers = READER_BIAS + N`（N 为活跃读者数）

### 3.2 快速路径（Fast Path）
- **读锁获取**：通过 `atomic_try_cmpxchg_acquire()` 原子递增 `readers`（仅当 `< 0` 不成立，即偏置存在）
- **读锁释放**：`atomic_dec_and_test()`，仅当计数归零（即最后一个读者）时才需唤醒写者
- 所有原子操作均使用 `_acquire` / `_release` 语义，确保内存顺序正确

### 3.3 写者加锁流程
1. 获取底层 `rtmutex`（可能阻塞）
2. 清除 `READER_BIAS`，阻止新读者进入快速路径
3. 在 `rtmutex.wait_lock` 保护下检查是否所有读者已退出（`readers == 0`）
4. 若仍有读者，循环等待并调度，直到可安全设置 `WRITER_BIAS`

### 3.4 非写者公平性
- **明确不保证写者公平**：新到达的读者即使在写者等待时仍可获取读锁（若写者尚未清除 `READER_BIAS`）
- 原因：实现完全公平需为每个读者代理锁定 `rtmutex` 并逐个继承优先级，这在 `SCHED_DEADLINE` 下不可行
- 权衡：接受潜在写者饥饿风险，换取实现简洁性和典型 RT 场景下的低延迟

### 3.5 与 `rtmutex` 的集成
- 所有慢路径操作均在 `rtmutex.wait_lock`（raw spinlock）保护下进行
- 写者通过 `rtmutex` 阻塞，天然获得 PI/DL 调度支持
- 读者在慢路径中临时获取 `rtmutex` 以确保与写者互斥，成功后立即释放

## 4. 依赖关系

- **`rtmutex` 子系统**：依赖 `rt_mutex_base`、`rt_mutex_lock/unlock`、`rt_mutex_wake_q` 等接口实现阻塞/唤醒和优先级继承
- **原子操作**：使用 `atomic_read`、`atomic_try_cmpxchg_acquire`、`atomic_add_return_release` 等提供内存序保证
- **调度器**：调用 `rwbase_pre_schedule()` / `rwbase_post_schedule()`、`rwbase_schedule()` 与 RT 调度器交互
- **跟踪机制**：使用 `trace_contention_begin/end` 提供锁竞争跟踪
- **中断管理**：使用 `raw_spin_lock_irq{save/restore}` 保护关键区
- **信号处理**：通过 `rwbase_signal_pending_state()` 支持可中断等待

## 5. 使用场景

- **实时任务中的读写同步**：适用于需要低延迟响应的 RT 任务访问共享数据结构
- **`mmap_sem` 等内核锁的 RT 实现**：作为 `rw_semaphore` 的底层支持，用于内存管理等子系统
- **避免优先级反转**：当高优先级写者需等待低优先级读者时，通过 `rtmutex` 的 PI 机制临时提升读者优先级
- **高并发读场景**：允许多个读者无锁并发执行，仅在写者存在时才串行化
- **不适用于强写者公平需求场景**：如需严格 FIFO 写者调度，应避免在 RT 任务中使用此类锁