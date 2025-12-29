# locking\ww_rt_mutex.c

> 自动生成时间: 2025-10-25 14:57:15
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `locking\ww_rt_mutex.c`

---

# `locking/ww_rt_mutex.c` 技术文档

## 1. 文件概述

`ww_rt_mutex.c` 是 Linux 内核中实现 **Wound/Wait 语义的实时互斥锁（ww_mutex）** 的核心文件之一。该文件基于通用的 `rtmutex.c` 实时互斥锁机制，通过宏定义 `WW_RT` 和 `RT_MUTEX_BUILD_MUTEX` 复用 `rtmutex.c` 的代码，专门构建支持 **Wound/Wait 死锁避免协议** 的实时互斥锁变体。其主要作用是在支持优先级继承（Priority Inheritance）的实时调度环境中，提供一种可避免死锁的锁获取机制，特别适用于图形子系统（如 DRM）等需要复杂锁排序的场景。

## 2. 核心功能

### 主要函数

- `ww_mutex_trylock(struct ww_mutex *lock, struct ww_acquire_ctx *ww_ctx)`  
  尝试非阻塞地获取一个 ww_mutex 锁。若提供 `ww_ctx`，则参与 Wound/Wait 协议。

- `ww_mutex_lock(struct ww_mutex *lock, struct ww_acquire_ctx *ctx)`  
  以不可中断方式阻塞获取 ww_mutex 锁，参与 Wound/Wait 死锁避免协议。

- `ww_mutex_lock_interruptible(struct ww_mutex *lock, struct ww_acquire_ctx *ctx)`  
  以可中断方式阻塞获取 ww_mutex 锁，支持信号中断。

- `ww_mutex_unlock(struct ww_mutex *lock)`  
  释放已持有的 ww_mutex 锁，并更新锁依赖跟踪信息。

- `__ww_rt_mutex_lock(...)`（静态辅助函数）  
  上述两个 `lock` 函数的通用实现，封装了锁获取的公共逻辑。

### 关键数据结构（引用自其他头文件）

- `struct ww_mutex`：包含底层 `struct rt_mutex base` 和 Wound/Wait 上下文指针 `ctx`。
- `struct ww_acquire_ctx`：Wound/Wait 获取上下文，记录已获取锁数量（`acquired`）、是否被“刺伤”（`wounded`）等状态，用于死锁检测与避免。

## 3. 关键实现

### Wound/Wait 协议集成
- 所有锁操作均通过 `ww_ctx` 参与 Wound/Wait 协议。当 `ww_ctx->acquired == 0`（即尚未持有任何锁）时，重置 `wounded` 标志，确保上下文处于干净状态。
- 在 `__ww_rt_mutex_lock` 中，若检测到当前线程试图重复获取同一把锁（`ww_ctx == lock->ctx`），立即返回 `-EALREADY`，防止自死锁。

### 锁获取路径
1. **快速路径**：首先尝试 `rt_mutex_try_acquire()` 非阻塞获取锁。成功则通过 `ww_mutex_set_context_fastpath()` 绑定锁与上下文，并记录锁依赖。
2. **慢速路径**：若快速路径失败，调用 `rt_mutex_slowlock()` 进入阻塞等待，该函数内部处理优先级继承、Wound/Wait 死锁检测及“刺伤”逻辑。

### 锁释放路径
- 调用 `__ww_mutex_unlock()` 清理 ww_mutex 特定状态（如从上下文移除该锁）。
- 通过 `mutex_release()` 通知锁依赖验证器（Lockdep）。
- 最终调用 `__rt_mutex_unlock()` 释放底层实时互斥锁，可能触发优先级恢复或唤醒等待者。

### 锁依赖跟踪（Lockdep）
- 使用 `mutex_acquire_nest()` 和 `mutex_release()` 与内核 Lockdep 子系统交互，支持嵌套锁依赖分析，其中 `nest_lock` 指向 `ww_ctx->dep_map` 以正确建模 Wound/Wait 上下文的锁序。

### 代码复用机制
- 通过定义 `WW_RT` 和 `RT_MUTEX_BUILD_MUTEX` 宏，包含 `rtmutex.c` 文件，使其在编译时生成专用于 ww_mutex 的 rtmutex 实现，避免代码重复。

## 4. 依赖关系

- **`rtmutex.c`**：核心实时互斥锁实现，本文件通过宏包含方式复用其逻辑。
- **`<linux/spinlock.h>`**：提供底层自旋锁原语，用于 rtmutex 内部同步。
- **`<linux/export.h>`**：导出符号供其他内核模块使用（如 DRM 驱动）。
- **Lockdep 子系统**：通过 `mutex_acquire_nest()`、`mutex_release()` 等接口集成运行时锁依赖验证。
- **调度器**：依赖 `might_sleep()`、`TASK_UNINTERRUPTIBLE`、`TASK_INTERRUPTIBLE` 等调度原语实现可睡眠锁语义。

## 5. 使用场景

- **图形驱动（DRM/KMS）**：在需要获取多个资源锁（如 CRTCs、planes、buffers）时，使用 ww_mutex 避免因锁序不一致导致的死锁。
- **实时任务调度环境**：在启用 `CONFIG_PREEMPT_RT` 的系统中，替代普通 mutex 以获得优先级继承和确定性延迟。
- **复杂资源管理子系统**：任何需要动态获取多个互斥资源且无法静态确定锁序的内核子系统，均可利用 Wound/Wait 协议实现安全的并发控制。