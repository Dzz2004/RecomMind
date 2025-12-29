# pid_namespace.c

> 自动生成时间: 2025-10-25 15:16:50
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `pid_namespace.c`

---

# `pid_namespace.c` 技术文档

## 1. 文件概述

`pid_namespace.c` 是 Linux 内核中实现 **PID 命名空间（PID Namespace）** 的核心源文件。PID 命名空间是 Linux 容器技术（如 Docker、LXC）的关键基础组件之一，用于为不同进程组提供隔离的进程 ID 视图。每个 PID 命名空间拥有独立的 PID 分配空间，使得不同命名空间中的进程可以拥有相同的 PID 而互不干扰。

该文件负责 PID 命名空间的创建、销毁、引用计数管理、资源回收以及命名空间内进程的批量终止（如容器退出时清理所有子进程）等核心功能。

## 2. 核心功能

### 主要数据结构
- `struct pid_namespace`：表示一个 PID 命名空间，包含：
  - `level`：命名空间层级（init_pid_ns 为 0，子命名空间依次递增）
  - `parent`：指向父命名空间的指针
  - `user_ns`：关联的用户命名空间
  - `idr`：用于分配和管理 PID 的 IDR（整数到指针映射）结构
  - `pid_cachep`：用于分配 `struct pid` 对象的 slab 缓存
  - `pid_allocated`：当前命名空间中已分配的 PID 数量
  - `ucounts`：用于限制用户命名空间下 PID 命名空间数量的计数器

### 主要函数
- `create_pid_cachep(unsigned int level)`  
  为指定层级的 PID 命名空间创建专用的 `struct pid` slab 缓存。
  
- `create_pid_namespace(struct user_namespace *user_ns, struct pid_namespace *parent_pid_ns)`  
  创建一个新的 PID 命名空间，设置层级、父命名空间、用户命名空间等属性，并初始化 IDR 和引用计数。

- `copy_pid_ns(unsigned long flags, struct user_namespace *user_ns, struct pid_namespace *old_ns)`  
  在 `clone()` 或 `unshare()` 系统调用中被调用，根据 `CLONE_NEWPID` 标志决定是否创建新的 PID 命名空间。

- `put_pid_ns(struct pid_namespace *ns)`  
  递减 PID 命名空间的引用计数，若引用计数归零则递归销毁该命名空间及其子命名空间。

- `zap_pid_ns_processes(struct pid_namespace *pid_ns)`  
  在 PID 命名空间的 init 进程退出时调用，向命名空间内所有剩余进程发送 `SIGKILL`，并等待其全部退出，确保命名空间干净回收。

- `delayed_free_pidns(struct rcu_head *p)`  
  通过 RCU 机制延迟释放 PID 命名空间结构体，确保所有并发读取完成后再释放内存。

## 3. 关键实现

### PID 命名空间层级与缓存管理
- PID 命名空间支持嵌套，最大深度由 `MAX_PID_NS_LEVEL` 限制（通常为 32）。
- 每个层级使用独立的 slab 缓存（`pid_cache[level - 1]`）来分配 `struct pid`，因为 `struct pid` 中的 `numbers[]` 数组大小依赖于命名空间层级（`level + 1`）。
- 缓存创建通过 `create_pid_cachep()` 实现，使用互斥锁 `pid_caches_mutex` 避免并发创建冲突。

### 引用计数与生命周期管理
- 使用 `refcount_t` 管理命名空间引用计数。
- `put_pid_ns()` 采用**尾递归方式**向上遍历父命名空间链，逐级释放无引用的命名空间。
- 实际内存释放通过 RCU 回调 `delayed_free_pidns()` 延迟执行，保证并发安全。

### 命名空间退出清理机制（`zap_pid_ns_processes`）
- **禁用新 PID 分配**：调用 `disable_pid_allocation()` 阻止新进程加入。
- **忽略 SIGCHLD**：使 init 进程自动回收僵尸子进程，避免阻塞。
- **批量 SIGKILL**：遍历 IDR 中所有 PID，向对应进程发送 `SIGKILL`。
- **等待所有进程退出**：通过 `kernel_wait4()` 回收直接子进程，并通过检查 `pid_allocated == init_pids` 确保所有进程（包括跨命名空间 fork 的僵尸进程）均已退出。
- **RCU 安全调度**：在等待循环中调用 `exit_tasks_rcu_stop/start()` 避免与 `synchronize_rcu_tasks()` 死锁。

### 资源限制
- 通过 `inc_pid_namespaces()` / `dec_pid_namespaces()` 调用 `ucounts` 机制，限制每个用户命名空间可创建的 PID 命名空间数量，防止资源耗尽。

## 4. 依赖关系

- **`<linux/pid.h>` / `<linux/pid_namespace.h>`**：定义 `struct pid` 和 `struct pid_namespace`。
- **`<linux/user_namespace.h>`**：依赖用户命名空间进行权限和资源限制。
- **`<linux/idr.h>`**：使用 IDR 数据结构管理 PID 分配。
- **`<linux/slab.h>`**：使用 kmem_cache 管理内存分配。
- **`<linux/sched/*.h>`**：访问任务结构、信号处理、RCU 任务同步等。
- **`<linux/proc_ns.h>`**：支持 `/proc/[pid]/ns/pid` 接口。
- **`"pid_sysctl.h"`**：提供 sysctl 配置（如 `memfd_noexec_scope`）。
- **`<linux/acct.h>`**：在命名空间销毁时清理进程会计信息。

## 5. 使用场景

- **容器启动**：当执行 `unshare(CLONE_NEWPID)` 或 `clone(CLONE_NEWPID)` 时，内核调用 `copy_pid_ns()` 创建新的 PID 命名空间，使容器内进程拥有独立的 PID 视图（容器内 PID 1 对应宿主机某个高 PID）。
- **容器退出**：当容器的 init 进程（PID 1）退出时，内核自动调用 `zap_pid_ns_processes()` 终止命名空间内所有剩余进程，防止孤儿进程泄漏。
- **命名空间嵌套**：支持多层容器或 sandbox 场景，如 systemd-nspawn 嵌套运行容器。
- **资源隔离与限制**：结合用户命名空间，限制非特权用户创建过多 PID 命名空间，提升系统安全性。
- **进程迁移与检查点**：配合 CRIU（Checkpoint/Restore in Userspace）等工具，通过 sysctl 接口控制命名空间行为（如 memfd 执行权限）。