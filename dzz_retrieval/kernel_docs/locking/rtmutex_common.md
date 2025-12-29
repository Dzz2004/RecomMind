# locking\rtmutex_common.h

> 自动生成时间: 2025-10-25 14:49:56
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `locking\rtmutex_common.h`

---

# `locking/rtmutex_common.h` 技术文档

## 1. 文件概述

`rtmutex_common.h` 是 Linux 内核中实时互斥锁（RT Mutex）子系统的内部头文件，定义了 RT Mutex 的核心数据结构、辅助函数和调试接口。该文件为支持优先级继承（Priority Inheritance, PI）的阻塞型互斥锁提供底层支持，主要用于实时调度场景，以避免优先级反转问题。此头文件包含 RT Mutex 的私有 API 和数据结构，不对外暴露给通用内核代码，仅供 RT Mutex 实现内部及特定子系统（如 futex、RCU）使用。

## 2. 核心功能

### 数据结构

- **`struct rt_waiter_node`**  
  表示等待者在红黑树中的节点，包含优先级（`prio`）和截止时间（`deadline`），用于在不同红黑树中排序。

- **`struct rt_mutex_waiter`**  
  表示一个被 RT Mutex 阻塞的任务，包含两个 `rt_waiter_node`：
  - `tree`：用于加入锁的等待者红黑树（由 `lock->wait_lock` 保护）
  - `pi_tree`：用于加入锁持有者任务的 PI 等待者红黑树（由 `task->pi_lock` 保护）
  还包含指向被阻塞任务、所等待锁、唤醒状态（`wake_state`）和 WW 依赖上下文的指针。

- **`struct rt_wake_q_head`**  
  扩展标准 `wake_q_head`，支持 RT 自旋锁/读写锁的唤醒机制，额外包含 `rtlock_task` 字段用于处理 RT 锁的特殊唤醒路径。

### 关键函数（声明）

- **代理锁操作（PI-futex 支持）**：
  - `rt_mutex_init_proxy_locked()`：初始化代理锁定状态
  - `rt_mutex_proxy_unlock()`：代理解锁
  - `rt_mutex_start_proxy_lock()` / `__rt_mutex_start_proxy_lock()`：启动代理加锁
  - `rt_mutex_wait_proxy_lock()`：等待代理锁
  - `rt_mutex_cleanup_proxy_lock()`：清理代理锁状态

- **futex 相关操作**：
  - `rt_mutex_futex_trylock()` / `__rt_mutex_futex_trylock()`：尝试获取 futex 使用的 RT Mutex
  - `rt_mutex_futex_unlock()` / `__rt_mutex_futex_unlock()`：解锁 futex 使用的 RT Mutex
  - `rt_mutex_postunlock()`：批量唤醒因解锁而就绪的任务

- **内联辅助函数（仅当 `CONFIG_RT_MUTEXES` 启用时）**：
  - `rt_mutex_has_waiters()`：判断锁是否有等待者
  - `rt_mutex_waiter_is_top_waiter()`：无锁检查某等待者是否为最高优先级
  - `rt_mutex_top_waiter()`：获取锁的最高优先级等待者（需持有 `wait_lock`）
  - `task_has_pi_waiters()` / `task_top_pi_waiter()`：查询任务的 PI 等待者
  - `rt_mutex_owner()`：安全读取锁的当前持有者（忽略等待者标志位）
  - `__rt_mutex_base_init()`：初始化 RT Mutex 基础结构
  - `rt_mutex_init_waiter()` / `rt_mutex_init_rtlock_waiter()`：初始化等待者结构

### 调试函数（条件编译）

- `debug_rt_mutex_*` 系列函数：在 `CONFIG_DEBUG_RT_MUTEXES` 启用时提供运行时一致性检查和内存污染检测。

### 常量与宏

- `RT_MUTEX_HAS_WAITERS`：用于在 `lock->owner` 指针低位标记是否存在等待者
- `RT_MUTEX_MIN_CHAINWALK` / `RT_MUTEX_FULL_CHAINWALK`：死锁检测的遍历策略
- `DEFINE_RT_WAKE_Q(name)`：定义并初始化 `rt_wake_q_head` 实例

## 3. 关键实现

### 双红黑树设计

每个 `rt_mutex_waiter` 同时存在于两个红黑树中：
- **锁的等待者树（`tree`）**：按等待者优先级/截止时间排序，由 `lock->wait_lock` 保护，用于确定下一个锁获得者。
- **持有者任务的 PI 树（`pi_tree`）**：按相同排序规则组织，由 `task->pi_lock` 保护，用于实现优先级继承——当高优先级任务等待低优先级任务持有的锁时，临时提升持有者优先级。

### 锁持有者指针的位标记

`lock->owner` 使用最低有效位（LSB）存储 `RT_MUTEX_HAS_WAITERS` 标志，其余位存储 `task_struct*` 指针。`rt_mutex_owner()` 通过掩码操作安全提取任务指针，避免竞态。

### 无锁 top-waiter 检查

`rt_mutex_waiter_is_top_waiter()` 通过比较 `rb_first_cached()` 返回的节点指针与等待者地址，实现无锁判断。该操作不访问节点内容，仅比较指针值，适用于锁释放路径的快速路径优化。

### 代理锁机制

为支持 PI-futex（用户空间 futex 的优先级继承语义），内核需代表用户任务持有锁。相关函数（如 `rt_mutex_start_proxy_lock`）允许内核任务为另一个任务（`task`）申请锁，而实际阻塞的是内核上下文。

### RT 唤醒队列扩展

`rt_wake_q_head` 在标准唤醒队列基础上增加 `rtlock_task` 字段，用于处理 RT 自旋锁变体（如 `sleeping spinlock`）的唤醒逻辑，确保在 RT 内核中正确调度。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/debug_locks.h>`：提供 `DEBUG_LOCKS_WARN_ON` 等调试宏
  - `<linux/rtmutex.h>`：定义 `rt_mutex_base` 等公共接口
  - `<linux/sched/wake_q.h>`：提供标准唤醒队列 `wake_q_head`

- **配置依赖**：
  - 主要功能受 `CONFIG_RT_MUTEXES` 控制；若未启用，仅提供空实现的 `rt_mutex_owner()`
  - 调试功能依赖 `CONFIG_DEBUG_RT_MUTEXES`

- **模块依赖**：
  - 被 `kernel/locking/rtmutex.c` 实现文件包含
  - 被 `kernel/futex.c` 用于 PI-futex 支持
  - 被 `kernel/rcu/tree_plugin.h` 条件包含（用于 RCU 与 RT 互斥的集成）

## 5. 使用场景

- **实时任务同步**：在启用了 `PREEMPT_RT` 补丁的内核中，RT Mutex 替代普通 mutex 用于内核同步原语，确保高优先级任务不会因低优先级任务持有锁而被长时间阻塞。
- **PI-futex 实现**：用户空间通过 `FUTEX_LOCK_PI` 等操作触发内核代理加锁，此文件提供底层支持。
- **死锁检测**：在锁争用路径中，通过 `RT_MUTEX_FULL_CHAINWALK` 触发完整的锁依赖链遍历，检测潜在死锁。
- **优先级继承传播**：当任务阻塞在 RT Mutex 上时，其优先级通过 `pi_tree` 传播给锁持有者，此文件的数据结构是该机制的基础。
- **RCU 与 RT 集成**：在 RCU 实现中，某些场景需与 RT Mutex 交互（如 `rcu/tree_plugin.h` 所示），此头文件提供必要接口。