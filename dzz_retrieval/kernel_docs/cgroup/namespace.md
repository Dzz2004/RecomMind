# cgroup\namespace.c

> 自动生成时间: 2025-10-25 12:49:06
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cgroup\namespace.c`

---

# cgroup/namespace.c 技术文档

## 1. 文件概述

`cgroup/namespace.c` 实现了 cgroup 命名空间（cgroup namespace）的核心功能。该文件为 Linux 内核提供了对 cgroup 命名空间的支持，使得不同进程可以拥有隔离的 cgroup 视图，从而增强容器化环境中的资源隔离能力。cgroup 命名空间允许进程看到一个以当前进程所属 cgroup 为根的虚拟 cgroup 文件系统视图，而不是全局的 cgroup 层次结构。

## 2. 核心功能

### 主要函数

- `alloc_cgroup_ns()`：分配并初始化一个新的 cgroup 命名空间结构体。
- `free_cgroup_ns()`：释放 cgroup 命名空间及其关联资源。
- `copy_cgroup_ns()`：在进程 fork 或 clone 时复制 cgroup 命名空间，支持 `CLONE_NEWCGROUP` 标志创建新命名空间。
- `cgroupns_install()`：将指定的 cgroup 命名空间安装到当前进程的 `nsproxy` 中。
- `cgroupns_get()` / `cgroupns_put()`：用于引用计数管理，获取和释放 cgroup 命名空间。
- `cgroupns_owner()`：返回该 cgroup 命名空间所属的用户命名空间。

### 关键数据结构

- `struct cgroup_namespace`：表示一个 cgroup 命名空间，包含：
  - `ns`：通用命名空间结构（`struct ns_common`）
  - `root_cset`：指向该命名空间根 css_set（控制组集合）
  - `user_ns`：关联的用户命名空间
  - `ucounts`：用于资源计数（限制命名空间数量）

- `cgroupns_operations`：`proc_ns_operations` 类型的全局常量，定义了 cgroup 命名空间在 `/proc/[pid]/ns/cgroup` 中的操作接口。

## 3. 关键实现

### 命名空间创建与资源限制
- 使用 `inc_cgroup_namespaces()` 和 `dec_cgroup_namespaces()` 通过 `ucounts` 机制限制每个用户命名空间可创建的 cgroup 命名空间数量，防止资源耗尽。
- 仅允许具有 `CAP_SYS_ADMIN` 能力的进程创建新的 cgroup 命名空间，确保安全性。

### 命名空间复制逻辑
- 在 `copy_cgroup_ns()` 中：
  - 若未设置 `CLONE_NEWCGROUP`，则直接复用父进程的 cgroup 命名空间（引用计数加一）。
  - 若设置 `CLONE_NEWCGROUP`，则创建新命名空间，并将当前任务的 `css_set` 作为新命名空间的根（`root_cset`）。
  - 使用 `spin_lock_irq(&css_set_lock)` 安全地获取当前任务的 `css_set`，避免在持有 `cgroup_mutex` 的上下文中操作。

### 命名空间安装与切换
- `cgroupns_install()` 在 `setns()` 系统调用中被调用，用于将目标命名空间切换到当前进程。
- 实现双重权限检查：要求调用者在其自身用户命名空间和目标 cgroup 命名空间的用户命名空间中均具备 `CAP_SYS_ADMIN`。

### 生命周期管理
- 通过 `refcount_set()` 和 `get_cgroup_ns()` / `put_cgroup_ns()` 实现引用计数。
- `free_cgroup_ns()` 负责释放所有关联资源：`css_set`、用户命名空间、ucounts 计数及 inum（用于 `/proc` 中的命名空间标识）。

## 4. 依赖关系

- **内部依赖**：
  - `cgroup-internal.h`：提供 cgroup 内部数据结构和辅助函数（如 `css_set`、`get_css_set()` 等）。
- **内核模块依赖**：
  - `<linux/nsproxy.h>`：提供 `nsproxy` 结构，用于管理进程的命名空间集合。
  - `<linux/proc_ns.h>`：定义 `proc_ns_operations` 接口，用于 `/proc/[pid]/ns/` 下的命名空间文件操作。
  - `<linux/sched/task.h>`：提供 `current` 和任务锁相关操作。
  - `<linux/slab.h>`：内存分配接口（`kzalloc`/`kfree`）。
  - `<linux/ucount.h>`（通过 `cgroup-internal.h` 间接包含）：用户资源计数机制。

## 5. 使用场景

- **容器运行时**：Docker、Podman、containerd 等容器引擎在创建容器时使用 `CLONE_NEWCGROUP` 创建新的 cgroup 命名空间，使容器内进程看到以容器 cgroup 为根的视图，提升隔离性和安全性。
- **系统调用支持**：
  - `clone()` / `unshare()`：通过 `CLONE_NEWCGROUP` 标志创建新 cgroup 命名空间。
  - `setns()`：将进程加入现有 cgroup 命名空间。
- **/proc 文件系统**：通过 `/proc/[pid]/ns/cgroup` 提供命名空间文件，支持命名空间的查看和操作（如 `nsenter` 工具）。
- **资源隔离**：结合用户命名空间，实现多租户环境下对 cgroup 命名空间创建数量的限制，防止 DoS 攻击。