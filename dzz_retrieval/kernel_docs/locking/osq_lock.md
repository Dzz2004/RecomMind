# locking\osq_lock.c

> 自动生成时间: 2025-10-25 14:43:41
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `locking\osq_lock.c`

---

# `locking/osq_lock.c` 技术文档

## 1. 文件概述

`osq_lock.c` 实现了一种专为**乐观自旋（Optimistic Spinning）**设计的轻量级排队自旋锁机制，称为 **OSQ（Optimistic Spin Queue）锁**。该机制主要用于支持如互斥锁（mutex）、读写信号量（rwsem）等**可睡眠锁**在争用时进行乐观自旋，以避免不必要的上下文切换和调度开销。OSQ 锁基于 MCS（Mellor-Crummey and Scott）锁的思想，但针对 Linux 内核的调度和抢占模型进行了优化，利用每个 CPU 的静态 per-CPU 节点结构，确保在禁用抢占的自旋上下文中安全使用。

## 2. 核心功能

### 主要数据结构
- `struct optimistic_spin_node`：每个 CPU 对应一个静态节点，包含：
  - `cpu`：编码后的 CPU 编号（实际值 = CPU ID + 1）
  - `locked`：布尔标志，表示是否已获得锁
  - `next`：指向队列中下一个节点的指针
  - `prev`：指向前一个节点的指针
- `struct optimistic_spin_queue`：OSQ 锁结构体，仅包含一个原子变量 `tail`，用于指向队列尾部（编码后的 CPU 编号），`OSQ_UNLOCKED_VAL`（值为 0）表示无锁。

### 主要函数
- `bool osq_lock(struct optimistic_spin_queue *lock)`  
  尝试获取 OSQ 锁。若成功获得锁或决定放弃自旋（如需要调度或前驱被抢占），返回 `true`；若成功排队但未获得锁且需继续等待，则返回 `false`（实际逻辑中，失败路径最终也返回 `false` 表示未获得锁）。
  
- `void osq_unlock(struct optimistic_spin_queue *lock)`  
  释放 OSQ 锁，唤醒队列中的下一个等待者（若存在）。

- `static inline struct optimistic_spin_node *osq_wait_next(...)`  
  辅助函数，用于在解锁或取消排队时安全地获取下一个节点，并处理队列尾部的原子更新。

- `encode_cpu()` / `decode_cpu()` / `node_cpu()`  
  用于在 CPU 编号与 per-CPU 节点指针之间进行编码/解码转换，其中 CPU 编号 0 被编码为 1，以 0 表示“无 CPU”（即锁空闲）。

## 3. 关键实现

### Per-CPU 静态节点设计
- 每个 CPU 拥有一个静态的 `osq_node`（通过 `DEFINE_PER_CPU_SHARED_ALIGNED` 定义），避免动态分配开销。
- 由于 OSQ 仅在**禁用抢占**的上下文中使用（如 mutex 的乐观自旋阶段），且**不可在中断上下文调用**，因此 per-CPU 节点的生命周期安全。

### 锁获取流程 (`osq_lock`)
1. **初始化本地节点**：设置 `locked=0`、`next=NULL`，并确保 `cpu` 字段为当前 CPU 编码值。
2. **原子交换尾指针**：通过 `atomic_xchg(&lock->tail, curr)` 尝试入队。若原值为 `OSQ_UNLOCKED_VAL`，直接获得锁。
3. **链接到前驱**：若已有前驱（`prev`），通过 `smp_wmb()` 确保内存顺序后，设置 `prev->next = node`。
4. **自旋等待**：使用 `smp_cond_load_relaxed()` 等待 `node->locked` 变为 1，或满足退出条件（`need_resched()` 或前驱 CPU 被抢占 `vcpu_is_preempted()`）。
5. **取消排队（Unqueue）**：若需退出自旋：
   - **Step A**：尝试将 `prev->next` 置为 `NULL`，断开链接。
   - **Step B**：调用 `osq_wait_next()` 确定下一个节点，并可能将锁尾指针回退。
   - **Step C**：若存在 `next`，将其与 `prev` 直接链接，完成队列修复。

### 锁释放流程 (`osq_unlock`)
1. **快速路径**：若当前 CPU 是唯一持有者（`tail == curr`），直接将 `tail` 设为 `OSQ_UNLOCKED_VAL`。
2. **慢速路径**：
   - 若本地节点的 `next` 非空，直接设置 `next->locked = 1` 唤醒后继。
   - 否则调用 `osq_wait_next()` 获取下一个节点（处理并发取消排队的情况），再唤醒。

### 内存屏障与原子操作
- 使用 `atomic_xchg`、`atomic_cmpxchg_acquire/release` 确保对 `lock->tail` 的操作具有适当的内存序。
- `smp_wmb()` 保证在设置 `prev->next` 前，本地节点的初始化对其他 CPU 可见。
- `WRITE_ONCE`/`READ_ONCE` 防止编译器优化破坏并发访问语义。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/percpu.h>`：提供 per-CPU 变量支持（`this_cpu_ptr`, `per_cpu_ptr`）。
  - `<linux/sched.h>`：提供调度相关函数（`need_resched()`）和虚拟 CPU 抢占检测（`vcpu_is_preempted()`）。
  - `<linux/osq_lock.h>`：定义 `struct optimistic_spin_queue`、`struct optimistic_spin_node` 及 `OSQ_UNLOCKED_VAL`。
- **架构依赖**：依赖底层架构的原子操作（`atomic_*`）、内存屏障（`smp_wmb`, `smp_load_acquire`）和 CPU ID 获取（`smp_processor_id()`）。
- **调度器集成**：与内核调度器紧密协作，通过 `need_resched()` 和 `vcpu_is_preempted()` 决定是否继续自旋。

## 5. 使用场景

OSQ 锁主要用于**可睡眠锁的乐观自旋优化**，典型场景包括：
- **Mutex（互斥锁）**：在 `mutex_spin_on_owner()` 中，若锁持有者正在运行，当前 CPU 会尝试 OSQ 自旋而非立即睡眠。
- **Rwsem（读写信号量）**：在写者争用时，若满足条件，会使用 OSQ 进行乐观自旋。
- **其他睡眠锁**：任何希望在锁争用时避免立即进入睡眠、以降低延迟的同步原语。

其核心价值在于：当锁持有者很可能在**另一个 CPU 上运行且未被抢占**时，通过短暂自旋可避免昂贵的上下文切换，提升性能；同时通过 `vcpu_is_preempted()` 检测虚拟化环境中的抢占，避免在持有者已让出 CPU 时无效自旋。