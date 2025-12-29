# futex\requeue.c

> 自动生成时间: 2025-10-25 13:34:56
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `futex\requeue.c`

---

# futex/requeue.c 技术文档

## 1. 文件概述

`futex/requeue.c` 是 Linux 内核 FUTEX（Fast Userspace muTEX）子系统中的关键实现文件，专门负责 **FUTEX_REQUEUE** 和 **FUTEX_CMP_REQUEUE_PI** 等操作中涉及的 **futex 等待队列重排队（requeue）逻辑**，尤其针对 **PI（Priority Inheritance，优先级继承）futex** 的复杂场景。该文件的核心目标是在保证正确性和避免死锁的前提下，高效地将等待在源 futex（uaddr1）上的任务迁移到目标 futex（uaddr2）上，并处理 PI 相关的状态同步与唤醒机制。特别地，它解决了在 **PREEMPT_RT** 实时内核配置下，由于底层使用 rtmutex 实现自旋锁而引发的潜在状态冲突问题。

## 2. 核心功能

### 主要数据结构

- **`enum requeue_pi_state`**: 定义 PI futex 重排队过程中的状态机，用于协调重排队操作者（requeue side）与被重排队任务（waiter side）之间的同步。
  - `Q_REQUEUE_PI_NONE`: 初始状态。
  - `Q_REQUEUE_PI_IGNORE`: 等待者已提前唤醒，应忽略此次重排队。
  - `Q_REQUEUE_PI_IN_PROGRESS`: 重排队操作正在进行中。
  - `Q_REQUEUE_PI_WAIT`: 等待者在重排队过程中被唤醒，需等待操作完成。
  - `Q_REQUEUE_PI_DONE`: 重排队成功，任务在目标 futex 上等待。
  - `Q_REQUEUE_PI_LOCKED`: 重排队成功，且任务已原子地获取了目标 futex 锁。
- **`futex_q_init`**: `futex_q` 结构体的初始化模板，将 `requeue_state` 初始化为 `Q_REQUEUE_PI_NONE`。

### 主要函数

- **`requeue_futex()`**: 将一个 `futex_q` 从源哈希桶 (`hb1`) 移动到目标哈希桶 (`hb2`)，并更新其关联的 futex key。如果源和目标哈希桶相同，则跳过移动操作。
- **`futex_requeue_pi_prepare()`**: 为 PI 重排队操作做准备。尝试将等待者的 `requeue_state` 从 `NONE` 设置为 `IN_PROGRESS`。如果状态已是 `IGNORE`，则返回 `false` 表示应跳过此等待者。
- **`futex_requeue_pi_complete()`**: 完成 PI 重排队操作。根据操作结果（成功/失败/死锁）和当前状态，将 `requeue_state` 更新为 `DONE`、`LOCKED`、`NONE` 或 `IGNORE`。在 `PREEMPT_RT` 下，若存在状态交错（`WAIT`），会唤醒等待者。
- **`futex_requeue_pi_wakeup_sync()`**: 由被重排队的等待者调用，用于处理在重排队过程中发生的提前唤醒（如超时或信号）。它会根据当前重排队状态，设置自身状态为 `IGNORE` 或 `WAIT`，并在必要时阻塞等待重排队操作完成。
- **`requeue_pi_wake_futex()`**: 在重排队过程中，如果目标 futex 锁可以被原子获取（无竞争或通过锁窃取），则直接唤醒该等待者。此函数负责更新 `futex_q` 的状态（key、rt_waiter、lock_ptr），完成重排队状态机，并最终唤醒任务。
- **`futex_proxy_trylock_atomic()`**: （声明未在片段中完整给出，但为关键函数）尝试为重排队目标 futex 的 top waiter 原子地获取锁，并建立 PI 状态（`pi_state`）。这是实现 `FUTEX_CMP_REQUEUE_PI` 无竞争快速路径的核心。

## 3. 关键实现

### PI 重排队状态机
文件的核心是一个精心设计的无锁状态机，通过 `atomic_t requeue_state` 字段在重排队操作者和被操作的等待者之间进行同步。该状态机定义了双方允许的状态转换，确保了在并发唤醒（如信号、超时）和重排队操作交错发生时，系统状态的一致性和正确性。

### PREEMPT_RT 兼容性
在 `PREEMPT_RT` 内核中，哈希桶锁（`hb->lock`）底层是 `rtmutex`。一个任务不能同时阻塞在两个 `rtmutex` 上。如果一个刚被唤醒的任务（因信号/超时）试图获取源 futex 的哈希桶锁，而该锁正被重排队代码持有，就会与重排队过程中可能涉及的代理锁（proxy lock）操作冲突。本文件通过状态机机制，让提前唤醒的任务能“通知”重排队代码忽略它，从而避免了这种冲突和潜在的状态损坏。

### 原子锁获取与唤醒
`requeue_pi_wake_futex()` 函数实现了在重排队过程中直接获取目标 futex 锁并唤醒任务的优化路径。这避免了任务先被加入目标等待队列再被唤醒的开销，提高了性能。该函数必须在持有源和目标哈希桶锁的情况下调用，以保证操作的原子性。

### 同步原语
- **`atomic_try_cmpxchg`**: 用于无锁地更新 `requeue_state`，实现状态机的原子转换。
- **`rcuwait`**: 在 `PREEMPT_RT` 下，当等待者需要等待重排队完成时，使用 `rcuwait` 机制进行高效等待。
- **`atomic_cond_read_relaxed`**: 在非 `PREEMPT_RT` 下，用于自旋等待状态改变。

## 4. 依赖关系

- **`<linux/plist.h>`**: 提供优先级链表（`plist`）的实现，用于管理 futex 等待队列。
- **`<linux/sched/signal.h>`**: 提供任务唤醒（`wake_up_state`）和信号处理相关的功能。
- **`"futex.h"`**: 包含 FUTEX 子系统的核心定义，如 `futex_q`, `futex_hash_bucket`, `futex_key` 等。
- **`../locking/rtmutex_common.h`**: 提供实时互斥锁（`rtmutex`）的通用接口，`PREEMPT_RT` 的关键依赖。
- **内核调度器**: 依赖 `wake_up_state` 等函数与内核调度器交互，唤醒被阻塞的任务。
- **内存屏障原语**: 代码中隐含使用了 `acquire`/`release` 语义的原子操作来保证内存访问顺序。

## 5. 使用场景

- **`FUTEX_REQUEUE` 系统调用**: 当用户空间调用 `futex(uaddr1, FUTEX_REQUEUE, ...)` 时，内核会调用此文件中的逻辑，将等待在 `uaddr1` 上的指定数量的任务移动到 `uaddr2` 的等待队列上。
- **`FUTEX_CMP_REQUEUE_PI` 系统调用**: 这是 PI futex 的关键操作。它首先检查 `uaddr1` 的值，如果匹配，则尝试将 `uaddr1` 上的等待者重排队到 `uaddr2`。在此过程中，会尝试为 `uaddr2` 的 top waiter 原子地获取锁（通过 `futex_proxy_trylock_atomic`）。如果成功，则直接唤醒该任务（通过 `requeue_pi_wake_futex`）；如果失败，则将其加入 `uaddr2` 的等待队列。整个过程需要本文件提供的状态机来处理并发唤醒。
- **PI futex 的唤醒与超时处理**: 当一个正在被重排队的 PI futex 等待者收到信号或发生超时时，会调用 `futex_requeue_pi_wakeup_sync` 来安全地退出等待，并与正在进行的重排队操作进行协调。