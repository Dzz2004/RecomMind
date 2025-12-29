# locking\mcs_spinlock.h

> 自动生成时间: 2025-10-25 14:41:16
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `locking\mcs_spinlock.h`

---

# `locking/mcs_spinlock.h` 技术文档

## 1. 文件概述

`mcs_spinlock.h` 定义了 MCS 自旋锁（Mellor-Crummey and Scott Spinlock）的核心数据结构和 API。MCS 锁是一种公平、可扩展的自旋锁实现，其关键优势在于每个 CPU 在等待锁时仅自旋于本地内存变量，从而显著减少传统 test-and-set 自旋锁中常见的缓存行（cache line）争用（cache bouncing）问题。该文件为 Linux 内核中更高级的排队自旋锁（如 `qspinlock`）提供了底层支持。

## 2. 核心功能

### 数据结构

- **`struct mcs_spinlock`**  
  MCS 锁的基本节点结构，每个尝试获取锁的线程需在栈上分配一个该结构实例：
  - `next`：指向下一个等待该锁的节点。
  - `locked`：锁状态标志，1 表示已获得锁，0 表示正在等待。
  - `count`：嵌套计数字段，主要用于 `qspinlock.c` 中支持锁的嵌套获取。

### 主要函数

- **`mcs_spin_lock(struct mcs_spinlock **lock, struct mcs_spinlock *node)`**  
  获取 MCS 锁。调用者需传入一个本地 `node` 实例。若锁空闲则立即返回；否则将当前节点加入等待队列，并自旋等待 `node->locked` 被前驱节点置为 1。

- **`mcs_spin_unlock(struct mcs_spinlock **lock, struct mcs_spinlock *node)`**  
  释放 MCS 锁。调用者传入与加锁时相同的 `node`。若存在后继节点，则通过设置其 `locked` 字段唤醒下一个等待者；否则尝试将全局锁指针置为 `NULL`。

### 架构相关宏（可被架构代码覆盖）

- **`arch_mcs_spin_lock_contended(l)`**  
  默认使用 `smp_cond_load_acquire()` 实现自旋等待，提供 acquire 语义，并在部分架构（如 ARM64）上支持更高效的自旋策略（如 yield 或 pause）。

- **`arch_mcs_spin_unlock_contended(l)`**  
  默认使用 `smp_store_release()` 设置 `locked = 1`，确保存储操作具有 release 语义，保证临界区内的内存操作在解锁前完成。

## 3. 关键实现

### 公平性与本地自旋
MCS 锁通过链表组织等待者。每个等待线程仅监控自己节点的 `locked` 字段，避免了多个 CPU 同时写入同一缓存行，从而消除缓存颠簸。

### 原子交换与内存序
- 加锁时使用 `xchg(lock, node)` 原子地将当前节点加入队列头。该操作隐含全内存屏障，确保 `node` 的初始化（`locked=0`, `next=NULL`）对其他 CPU 可见。
- 若 `xchg` 返回 `NULL`，说明无竞争，直接获得锁。
- 否则，将自身节点链接到前驱节点的 `next` 字段，并等待前驱在释放锁时设置 `node->locked = 1`。

### 解锁逻辑
- 首先读取 `node->next`。若为 `NULL`，尝试通过 `cmpxchg_release` 将全局锁指针置为 `NULL`（表示无后继）。
- 若 `cmpxchg` 失败（说明有新节点刚加入），则自旋等待 `next` 被设置。
- 一旦获得有效 `next`，调用 `arch_mcs_spin_unlock_contended(&next->locked)` 唤醒后继。

### 内存屏障说明
- `smp_load_acquire` / `smp_store_release` 对在 x86 上足以提供顺序一致性，但在弱内存模型架构（如 ARM、PowerPC）上不足以构成跨 CPU 的全屏障。
- 若使用 MCS 锁对实现需要全屏障语义的同步原语，应在 `mcs_spin_lock()` 后显式调用 `smp_mb__after_unlock_lock()`。

## 4. 依赖关系

- **架构相关头文件**：包含 `<asm/mcs_spinlock.h>`，允许特定架构覆盖默认的 `arch_mcs_spin_lock_contended` 和 `arch_mcs_spin_unlock_contended` 实现。
- **内核同步原语**：依赖 `xchg`、`cmpxchg_release`、`READ_ONCE`、`WRITE_ONCE`、`smp_cond_load_acquire`、`smp_store_release` 等内核原子操作和内存屏障原语。
- **上层锁实现**：主要被 `kernel/locking/qspinlock.c` 使用，作为 Linux 内核排队自旋锁（qspinlock）的底层等待机制。

## 5. 使用场景

- **内核自旋锁底层实现**：作为 `qspinlock` 的等待队列机制，在高竞争场景下提供可扩展性和公平性。
- **需要公平锁语义的子系统**：适用于对锁获取顺序敏感、且需避免饥饿的内核路径。
- **NUMA 或多核系统优化**：在具有非一致性内存访问（NUMA）或大量 CPU 的系统中，MCS 锁可显著降低锁竞争带来的性能开销。
- **实时内核补丁（如 PREEMPT_RT）**：MCS 结构也常用于实现可睡眠的 mutex 或 rwlock 的排队逻辑。