# pid.c

> 自动生成时间: 2025-10-25 15:16:06
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `pid.c`

---

# `pid.c` 技术文档

## 1. 文件概述

`pid.c` 是 Linux 内核中实现进程标识符（PID）管理和分配机制的核心文件。它提供了可扩展、时间有界的 PID 分配器，支持 PID 哈希表（pidhash）以及 PID 命名空间（pid namespace）功能。该文件负责 PID 的分配、释放、引用计数管理，并确保在多处理器（SMP）环境下的线程安全性。其设计目标是在高并发场景下高效、无锁地分配和回收 PID，同时支持容器化环境中的 PID 隔离。

## 2. 核心功能

### 主要数据结构

- **`struct pid`**  
  表示一个 PID 实例，包含：
  - 引用计数（`count`）
  - 多种任务类型链表（`tasks[PIDTYPE_MAX]`），用于关联不同类型的进程（如线程组、会话等）
  - PID 层级（`level`），用于命名空间嵌套
  - `numbers[]` 数组：每个命名空间层级对应的 `struct upid`（包含实际 PID 编号 `nr` 和所属命名空间 `ns`）
  - `rcu` 字段：用于 RCU 安全释放
  - `wait_pidfd`：用于 pidfd 机制的等待队列
  - `inodes`：关联的 pidfs inode 列表

- **`struct pid_namespace`**  
  PID 命名空间结构，包含：
  - IDR（整数 ID 映射）结构 `idr`，用于高效 PID 分配
  - `pid_allocated`：当前已分配 PID 数量（含特殊状态如 `PIDNS_ADDING`）
  - `child_reaper`：命名空间中的 init 进程（子进程回收者）
  - `level`：命名空间嵌套层级
  - `pid_cachep`：用于分配 `struct pid` 的 slab 缓存

- **全局变量**
  - `init_struct_pid`：初始 PID 结构（PID 0，用于 idle 进程）
  - `init_pid_ns`：初始 PID 命名空间
  - `pid_max` / `pid_max_min` / `pid_max_max`：PID 分配上限控制
  - `pidfs_ino`：pidfs 文件系统的 inode 编号起始值
  - `pidmap_lock`：保护 IDR 和 `pid_allocated` 的自旋锁（SMP 对齐）

### 主要函数

- **`alloc_pid(struct pid_namespace *ns, pid_t *set_tid, size_t set_tid_size)`**  
  在指定 PID 命名空间中分配一个新的 PID。支持通过 `set_tid` 数组在嵌套命名空间中预设 PID（用于容器恢复等场景）。

- **`free_pid(struct pid *pid)`**  
  释放 PID 资源，从所有嵌套命名空间的 IDR 中移除，并减少 `pid_allocated` 计数。若命名空间中仅剩 reaper 进程，则唤醒它。

- **`put_pid(struct pid *pid)`**  
  减少 PID 引用计数，若引用归零则释放内存并减少命名空间引用。

- **`delayed_put_pid(struct rcu_head *rhp)`**  
  RCU 回调函数，用于安全释放 PID 结构。

## 3. 关键实现

### PID 分配机制
- 使用 **IDR（Integer ID Allocator）** 替代传统的位图（bitmap），实现 O(1) 分配与释放。
- 默认采用**循环分配策略**（`idr_alloc_cyclic`），从 `RESERVED_PIDS`（通常为 300）开始，避免低编号 PID 被耗尽。
- 支持**预设 PID 分配**：通过 `set_tid` 参数在创建进程时指定特定 PID（需具备 `CAP_CHECKPOINT_RESTORE` 权限），用于容器快照恢复。

### 命名空间支持
- 每个 PID 在嵌套的命名空间中拥有不同的编号（`upid->nr`），通过 `pid->numbers[]` 数组维护层级关系。
- `pid->level` 表示该 PID 所属的最深命名空间层级。
- 分配时从最深层命名空间向上遍历至根命名空间，逐层分配 PID。

### 并发与同步
- **`pidmap_lock`**：保护 IDR 操作和 `pid_allocated` 计数器，使用 `spin_lock_irqsave` 禁用本地中断，防止与 `tasklist_lock` 的死锁。
- **RCU 释放**：`free_pid` 通过 `call_rcu` 延迟释放 PID 结构，避免在持有锁时执行内存释放。
- **引用计数**：`struct pid` 使用 `refcount_t` 管理生命周期，确保多任务共享 PID 时的安全释放。

### 特殊状态处理
- **`PIDNS_ADDING`**：标记命名空间正在添加新进程，防止在 fork 失败时错误减少计数。
- **Reaper 唤醒**：当命名空间中 PID 数量降至 1 或 2 时，唤醒 `child_reaper`（通常为 init 进程），用于处理命名空间退出（`zap_pid_ns_processes`）。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/pid_namespace.h>`：PID 命名空间定义
  - `<linux/idr.h>`：IDR 分配器实现
  - `<linux/rculist.h>`：RCU 安全链表操作
  - `<linux/sched/task.h>`、`<linux/sched/signal.h>`：任务调度与信号处理
  - `<linux/pidfs.h>`、`<uapi/linux/pidfd.h>`：pidfd 和 pidfs 支持
  - `<linux/refcount.h>`：引用计数机制

- **内核模块交互**：
  - **进程管理子系统**：与 `fork`/`clone` 系统调用集成，分配 PID 并关联到 `task_struct`
  - **命名空间子系统**：与 `pidns_operations` 协同实现 PID 隔离
  - **VFS 子系统**：通过 `pidfs_ino` 为 `/proc/[pid]` 提供 inode 编号
  - **内存管理**：使用 slab 分配器（`kmem_cache_alloc`）管理 `struct pid` 内存

## 5. 使用场景

- **进程创建**：在 `copy_process` 中调用 `alloc_pid` 为新进程分配唯一 PID。
- **容器运行时**：通过 `clone(CLONE_NEWPID)` 创建 PID 命名空间，实现容器内 PID 隔离。
- **检查点/恢复（CRIU）**：使用 `set_tid` 参数在恢复进程时精确还原原始 PID。
- **pidfd 机制**：`pid->wait_pidfd` 支持通过文件描述符等待进程退出（`pidfd_send_signal` 等系统调用）。
- **命名空间清理**：当容器退出时，`free_pid` 触发 reaper 唤醒，确保孤儿进程被正确回收。