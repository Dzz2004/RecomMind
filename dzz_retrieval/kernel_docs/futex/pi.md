# futex\pi.c

> 自动生成时间: 2025-10-25 13:33:45
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `futex\pi.c`

---

# futex/pi.c 技术文档

## 1. 文件概述

`futex/pi.c` 是 Linux 内核中实现 **Priority Inheritance (PI) futex**（优先级继承 futex）机制的核心文件。该文件负责管理与 PI futex 相关的 `pi_state` 对象的生命周期、引用计数、所有者更新以及与用户空间状态的一致性校验。PI futex 允许在使用互斥锁（mutex）时，通过优先级继承避免优先级反转问题，确保高优先级任务不会因低优先级任务持有锁而被无限期阻塞。

## 2. 核心功能

### 主要数据结构
- `struct futex_pi_state`：表示一个 PI futex 的状态对象，包含：
  - `pi_mutex`：关联的实时互斥锁（`rt_mutex`）
  - `owner`：当前锁的所有者任务（`task_struct *`）
  - `list`：挂载到任务 `pi_state_list` 的链表节点
  - `refcount`：引用计数
  - `key`：futex 键，用于标识用户空间地址

### 主要函数
- `refill_pi_state_cache(void)`：为当前任务预分配一个 `pi_state` 缓存对象
- `alloc_pi_state(void)`：从当前任务的缓存中取出一个 `pi_state` 对象
- `pi_state_update_owner(struct futex_pi_state *, struct task_struct *)`：更新 `pi_state` 的所有者，并维护任务的 `pi_state_list`
- `get_pi_state(struct futex_pi_state *)`：增加 `pi_state` 的引用计数
- `put_pi_state(struct futex_pi_state *)`：减少引用计数，若为 0 则释放或缓存对象
- `attach_to_pi_state(u32 __user *, u32, struct futex_pi_state *, struct futex_pi_state **)`：验证并附加到现有的 `pi_state`，确保用户空间值与内核状态一致

## 3. 关键实现

### pi_state 缓存机制
- 每个任务（`task_struct`）维护一个 `pi_state_cache`，用于缓存一个预分配的 `pi_state` 对象。
- `refill_pi_state_cache()` 在首次需要时分配对象，避免在关键路径上进行内存分配。
- `put_pi_state()` 在引用计数归零时优先将对象放回当前任务的缓存，而非直接释放，以提高性能。

### 所有者管理与一致性校验
- `pi_state_update_owner()` 在更新所有者时，需持有 `pi_mutex.wait_lock` 和对应任务的 `pi_lock`，确保链表操作的原子性。
- `attach_to_pi_state()` 实现了复杂的用户空间与内核状态一致性校验逻辑，涵盖 10 种状态组合（见代码注释），防止用户空间篡改 futex 值导致内核状态不一致。
- 特别处理 `FUTEX_OWNER_DIED` 位：当所有者进程退出时，内核需接管 `pi_state` 并允许新任务获取锁。

### 引用计数与生命周期
- `pi_state` 的生命周期由引用计数管理，引用来源包括：
  - 等待队列中的 `futex_q`
  - 正在执行 `futex_lock_pi`/`futex_unlock_pi` 的任务
- `put_pi_state()` 在释放前会调用 `rt_mutex_proxy_unlock()` 清理 `rt_mutex` 状态，并从原所有者任务的 `pi_state_list` 中移除。

### 锁顺序与并发控制
- 严格遵守锁顺序：`hb->lock` → `pi_mutex.wait_lock` → `task->pi_lock`
- 使用 `raw_spin_lock` 保证在中断上下文中的安全性
- 通过 `lockdep_assert_held()` 验证锁持有状态，防止死锁

## 4. 依赖关系

- **头文件依赖**：
  - `linux/slab.h`：内存分配（`kzalloc`/`kfree`）
  - `linux/sched/rt.h`：实时调度相关功能
  - `linux/sched/task.h`：任务结构体操作
  - `"futex.h"`：futex 核心定义
  - `"../locking/rtmutex_common.h"`：实时互斥锁实现

- **模块依赖**：
  - **futex 核心模块**（`kernel/futex.c`）：调用本文件函数处理 PI futex 操作
  - **rtmutex 子系统**：提供 `rt_mutex_proxy_unlock()` 等底层锁操作
  - **调度器**：依赖任务结构体中的 `pi_lock` 和 `pi_state_list`

## 5. 使用场景

- **PI futex 加锁**（`FUTEX_LOCK_PI`）：
  - 当用户空间尝试获取 PI futex 时，内核通过 `attach_to_pi_state()` 验证状态并附加到现有 `pi_state`
  - 若无可用 `pi_state`，则通过 `alloc_pi_state()` 分配新对象

- **PI futex 解锁**（`FUTEX_UNLOCK_PI`）：
  - 调用 `put_pi_state()` 释放 `pi_state` 引用，可能触发缓存或清理

- **进程退出处理**：
  - 当持有 PI futex 的进程退出时，内核通过 `exit_pi_state_list()` 清理其拥有的 `pi_state`，设置 `owner = NULL` 并唤醒等待者

- **robust futex 支持**：
  - 与 `FUTEX_OWNER_DIED` 位协同工作，确保进程异常退出后 futex 状态可被恢复

- **优先级继承**：
  - 当高优先级任务等待低优先级任务持有的 PI futex 时，内核通过 `rt_mutex` 机制临时提升低优先级任务的优先级，避免优先级反转