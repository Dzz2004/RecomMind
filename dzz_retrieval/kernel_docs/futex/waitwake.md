# futex\waitwake.c

> 自动生成时间: 2025-10-25 13:36:23
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `futex\waitwake.c`

---

# futex/waitwake.c 技术文档

## 文件概述

`futex/waitwake.c` 是 Linux 内核 futex（快速用户空间互斥锁）子系统的核心实现文件之一，主要负责 **futex 的唤醒（wake）逻辑**。该文件实现了从用户空间触发唤醒操作时，内核如何安全、高效地查找并唤醒等待在指定 futex 地址上的任务。文件重点处理了并发场景下的内存序问题，确保 waiter 不会因竞态条件而永久阻塞。

## 核心功能

### 主要函数

- **`futex_wake_mark()`**  
  将指定的等待队列项（`futex_q`）从哈希桶中移除，并将其关联的任务加入唤醒队列（`wake_q`），为后续实际唤醒做准备。

- **`futex_wake()`**  
  根据用户提供的地址、唤醒数量（`nr_wake`）和位掩码（`bitset`），唤醒匹配条件的等待者。这是 `FUTEX_WAKE` 系统调用的后端实现。

- **`futex_atomic_op_inuser()`**  
  在用户空间地址上执行原子操作（如加、或、与等），并根据比较条件返回布尔结果。用于支持复合 futex 操作。

- **`futex_wake_op()`**（部分实现）  
  执行原子操作后，根据操作结果唤醒两个不同 futex 地址上的等待者。这是 `FUTEX_WAKE_OP` 系统调用的后端实现（代码在文档中被截断）。

### 关键数据结构

- **`struct futex_q`**  
  表示一个 futex 等待队列项，包含任务指针、futex 键、位掩码等信息。

- **`struct futex_hash_bucket`**  
  futex 等待队列的哈希桶，包含自旋锁和优先级链表（`plist`）。

- **`struct wake_q_head`**  
  批量唤醒队列，用于延迟唤醒任务，避免在持有哈希桶锁时直接调用调度器。

## 关键实现

### 内存序与竞态条件防护

文件开头的注释详细阐述了 **futex 等待/唤醒的核心内存序问题**。为防止 waiter 错过唤醒，内核采用以下机制：

1. **等待者计数（waiters counter）**：  
   在获取哈希桶锁前，先通过原子操作增加桶的等待者计数（`futex_hb_waiters_inc`）。
2. **内存屏障配对**：  
   - 等待者：在增加计数后使用 `smp_mb()`，确保后续的 futex 值读取不会重排到计数增加之前。
   - 唤醒者：在修改 futex 值后使用 `smp_mb()`，确保后续的等待者计数读取不会重排到值修改之前。
3. **双重检查**：  
   唤醒者先检查 `futex_hb_waiters_pending()`，若无等待者则直接返回，避免不必要的锁开销。

### 安全唤醒机制

- **`futex_wake_mark()`** 使用 `smp_store_release(&q->lock_ptr, NULL)` 确保 `__futex_unqueue()` 的链表操作在 `lock_ptr` 清零前完成，防止 waiter 在未完成出队时释放 `futex_q` 结构。
- **`wake_q_add_safe()`** 将任务加入批量唤醒队列，实际唤醒（`wake_up_q()`）在释放哈希桶锁后执行，避免死锁。

### 位掩码匹配

`futex_wake()` 支持通过 `bitset` 参数选择性唤醒等待者。只有当等待者的 `bitset` 与唤醒者的 `bitset` 存在交集时，才会被唤醒，这为高级同步原语（如条件变量）提供了灵活性。

## 依赖关系

- **头文件依赖**：
  - `<linux/plist.h>`：优先级链表，用于管理不同优先级的等待任务。
  - `<linux/sched/task.h>` 和 `<linux/sched/signal.h>`：任务管理和信号处理。
  - `<linux/freezer.h>`：支持系统挂起/恢复时的冻结操作。
  - `"futex.h"`：futex 子系统的内部头文件，定义关键数据结构和辅助函数。

- **内核子系统**：
  - **调度器（Scheduler）**：通过 `wake_up_q()` 触发任务唤醒。
  - **内存管理（MM）**：通过 `get_futex_key()` 将用户虚拟地址转换为内核可识别的物理键。
  - **架构相关代码**：`arch_futex_atomic_op_inuser()` 由各架构实现原子操作。

## 使用场景

- **`FUTEX_WAKE` 系统调用**：  
  用户空间通过 `futex(uaddr, FUTEX_WAKE, nr_wake, NULL, NULL, 0)` 唤醒等待在 `uaddr` 上的任务。

- **`FUTEX_WAKE_OP` 系统调用**：  
  用户空间执行原子操作（如 `*uaddr1 += oparg`）后，根据操作结果唤醒 `uaddr1` 和 `uaddr2` 上的任务，常用于实现更复杂的同步原语。

- **PI-aware futex 的非 PI 路径**：  
  该文件明确拒绝唤醒 PI（优先级继承）futex（通过 `WARN` 检查），确保 PI futex 由专用路径处理。

- **高并发同步原语**：  
  作为底层同步机制，被用户空间的 mutex、条件变量、信号量等广泛使用，尤其在需要避免不必要的系统调用开销时。