# rcu\srcutiny.c

> 自动生成时间: 2025-10-25 15:42:53
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rcu\srcutiny.c`

---

# `rcu/srcutiny.c` 技术文档

## 1. 文件概述

`srcutiny.c` 是 Linux 内核中 **Sleepable Read-Copy Update (SRCU)** 机制的“精简版”（tiny version）实现，专为 **单 CPU 且不可抢占（non-preemptible）** 的系统环境设计。该文件提供了一种轻量级的读-拷贝-更新（RCU）变体，允许读端临界区中睡眠（即“sleepable”），适用于对性能要求不高但需要简单同步语义的嵌入式或特殊用途内核配置。

与完整版 SRCU 不同，`srcutiny` 利用单 CPU 无并发的特性，大幅简化了同步逻辑，避免了复杂的锁和内存屏障操作，从而实现极简的代码路径。

## 2. 核心功能

### 主要数据结构
- `struct srcu_struct`：SRCU 同步域的核心结构，包含：
  - `srcu_lock_nesting[2]`：两个计数器，用于跟踪两个交替的读端临界区嵌套深度。
  - `srcu_wq`：等待队列，用于在宽限期（grace period）结束时唤醒等待者。
  - `srcu_cb_head` / `srcu_cb_tail`：回调链表头尾指针，存储待执行的宽限期后回调。
  - `srcu_gp_running` / `srcu_gp_waiting`：标志位，表示宽限期是否正在运行或等待读端退出。
  - `srcu_idx` / `srcu_idx_max`：宽限期索引，用于状态追踪和轮转。
  - `srcu_work`：工作队列项，用于异步驱动宽限期处理。

### 主要函数
- `init_srcu_struct()` / `__init_srcu_struct()`：初始化 `srcu_struct` 实例。
- `cleanup_srcu_struct()`：清理并验证 `srcu_struct` 状态，防止资源泄漏。
- `__srcu_read_unlock()`：读端解锁，减少嵌套计数，必要时唤醒宽限期等待者。
- `srcu_drive_gp()`：工作队列处理函数，执行宽限期推进和回调调用。
- `call_srcu()`：注册一个宽限期结束后的回调函数。
- `synchronize_srcu()`：同步等待当前所有读端临界区完成。
- `get_state_synchronize_srcu()` / `start_poll_synchronize_srcu()` / `poll_state_synchronize_srcu()`：提供异步轮询接口，用于非阻塞式宽限期检测。
- `srcu_init()`：内核启动后期初始化函数，处理早期注册的 SRCU 回调。
- `rcu_scheduler_starting()`：标记调度器已启动，使 SRCU 进入活跃状态。

## 3. 关键实现

### 宽限期轮转机制
- 使用 **双缓冲计数器**（`srcu_lock_nesting[0]` 和 `[1]`）实现读端计数。
- `srcu_idx` 为递增整数，其低两位隐含当前活跃的计数器索引：
  - 当 `srcu_idx & 0x2 == 0` 时，使用索引 0；
  - 当 `srcu_idx & 0x2 == 2` 时，使用索引 1。
- 宽限期推进时，先切换索引（`srcu_idx += 1`），等待旧索引计数归零，再切换回（`srcu_idx += 1`），完成一个完整周期。

### 回调处理
- 所有通过 `call_srcu()` 注册的回调被追加到 `srcu_cb_head` 链表。
- `srcu_drive_gp()` 在工作队列上下文中执行：
  1. 原子地摘下整个回调链表；
  2. 等待对应读端计数归零（使用 `swait_event_exclusive`）；
  3. 依次调用所有回调函数（在 `local_bh_disable()` 保护下）；
  4. 若仍有新回调，重新调度自身。

### 启动阶段处理
- 在调度器启动前（`rcu_scheduler_active == RCU_SCHEDULER_INACTIVE`），`synchronize_srcu()` 直接返回，不执行同步。
- 早期调用 `call_srcu()` 会将 `srcu_work` 加入 `srcu_boot_list`。
- `srcu_init()` 在调度器启动后被调用，将 `srcu_boot_list` 中的结构体加入工作队列执行。

### 轮询接口设计
- `get_state_synchronize_srcu()` 返回一个“宽限期结束 cookie”：`(srcu_idx + 3) & ~0x1`，确保该值落在未来某个完整宽限期之后。
- `poll_state_synchronize_srcu()` 通过比较当前 `srcu_idx` 与 cookie 判断宽限期是否已过，支持环绕比较（`ULONG_CMP_GE/LT`）。

### 单 CPU 优化
- 由于仅支持单 CPU 且不可抢占，无需内存屏障或复杂同步原语。
- 使用 `local_irq_save/restore` 保护回调链表操作，避免中断上下文干扰。
- 宽限期等待使用简单的等待队列，无需跨 CPU 通信。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/srcu.h>`：SRCU 接口定义。
  - `<linux/rcupdate_wait.h>`：提供 `swait_*` 等待原语。
  - `<linux/workqueue.h>`（隐式）：通过 `INIT_WORK` 和 `schedule_work` 使用工作队列。
  - `"rcu.h"` / `"rcu_segcblist.h"`：RCU 内部辅助结构。
- **内核配置依赖**：
  - 仅在 `CONFIG_PREEMPT=n` 且单 CPU 环境下启用（由构建系统控制）。
  - `CONFIG_DEBUG_LOCK_ALLOC` 影响初始化函数签名，用于锁依赖验证。
- **与其他 RCU 子系统关系**：
  - 与 `tree_srcu.c`（完整版 SRCU）互斥，根据配置选择其一。
  - 共享 `rcu_head`、`rcu_callback_t` 等通用 RCU 类型。

## 5. 使用场景

- **嵌入式或实时系统**：在资源受限、单核、不可抢占的内核配置中提供轻量级读写同步。
- **允许读端睡眠的场景**：当读端临界区需要调用可能阻塞的函数（如内存分配、文件操作）时，传统 RCU 不适用，SRCU 是合适选择。
- **模块或子系统私有同步域**：每个 `srcu_struct` 实例代表一个独立的同步域，适用于需要隔离同步范围的驱动或内核组件。
- **启动早期同步**：通过 `srcu_boot_list` 机制，支持在调度器启动前注册回调，延迟到初始化后期执行。
- **异步宽限期检测**：通过 `start_poll_synchronize_srcu()` + `poll_state_synchronize_srcu()` 组合，实现非阻塞式宽限期等待，适用于不能睡眠的上下文。