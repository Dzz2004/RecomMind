# utsname.c

> 自动生成时间: 2025-10-25 17:47:46
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `utsname.c`

---

# utsname.c 技术文档

## 1. 文件概述

`utsname.c` 是 Linux 内核中实现 UTS（Unix Timesharing System）命名空间（UTS namespace）的核心文件。UTS 命名空间允许不同进程拥有独立的主机名（nodename）和域名（domainname），这是 Linux 容器技术（如 Docker、LXC）实现隔离的基础组件之一。该文件负责 UTS 命名空间的创建、复制、释放以及与进程命名空间代理（nsproxy）的集成，并支持通过 `/proc/[pid]/ns/uts` 进行命名空间操作。

## 2. 核心功能

### 主要数据结构
- `struct uts_namespace`：表示一个 UTS 命名空间，包含 `struct ns_common`（通用命名空间结构）、`struct new_utsname name`（存储主机名和域名）、`struct user_namespace *user_ns`（所属用户命名空间）以及资源计数器 `ucounts`。
- `uts_ns_cache`：用于高效分配和释放 `uts_namespace` 结构的 slab 缓存。

### 主要函数
- `copy_utsname()`：根据 `CLONE_NEWUTS` 标志决定是复用还是克隆一个新的 UTS 命名空间。
- `clone_uts_ns()`：创建并初始化一个新的 UTS 命名空间，复制源命名空间的主机名和域名。
- `free_uts_ns()`：释放 UTS 命名空间资源，包括减少用户命名空间资源计数、释放用户命名空间引用和 slab 内存。
- `uts_ns_init()`：初始化 UTS 命名空间的 slab 缓存。
- `utsns_get()` / `utsns_put()` / `utsns_install()` / `utsns_owner()`：实现 `proc_ns_operations` 接口，用于 `/proc` 文件系统对 UTS 命名空间的操作。
- `inc_uts_namespaces()` / `dec_uts_namespaces()`：管理每个用户命名空间中 UTS 命名空间实例数量的资源限制。

## 3. 关键实现

### 命名空间克隆机制
- 当进程调用 `clone()` 或 `unshare()` 并指定 `CLONE_NEWUTS` 时，`copy_utsname()` 会调用 `clone_uts_ns()` 创建新命名空间。
- `clone_uts_ns()` 首先通过 `inc_uts_namespaces()` 检查并增加用户命名空间中 UTS 命名空间的使用计数（防止资源耗尽），然后分配内存、初始化引用计数、分配 inode 编号（`ns_alloc_inum`），最后在 `uts_sem` 读锁保护下复制源命名空间的 `name` 字段。

### 资源管理与安全
- 使用 `kmem_cache_create_usercopy()` 创建 slab 缓存，特别标记 `name` 字段为可用户态复制区域，增强安全性。
- 通过 `ucounts` 机制限制每个用户命名空间可创建的 UTS 命名空间数量，防止 DoS 攻击。
- 在 `utsns_install()` 中进行双重权限检查：要求目标命名空间和当前凭证的用户命名空间均具备 `CAP_SYS_ADMIN` 能力，确保命名空间切换的安全性。

### 命名空间生命周期
- 引用计数由 `refcount_t ns.count` 管理，通过 `get_uts_ns()` 和 `put_uts_ns()` 操作。
- 当引用计数归零时，`free_uts_ns()` 被调用，依次释放资源：减少 `ucounts`、释放 `user_ns` 引用、释放 inode 编号、归还 slab 内存。

### `/proc` 集成
- 通过 `utsns_operations` 结构体将 UTS 命名空间注册到 proc 文件系统，支持通过 `/proc/[pid]/ns/uts` 进行命名空间的获取、安装（setns）和查询所有者。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/uts.h>` / `<linux/utsname.h>`：定义 UTS 相关结构（如 `new_utsname`）和常量。
  - `<linux/user_namespace.h>`：用户命名空间支持，用于权限检查和资源计数。
  - `<linux/proc_ns.h>`：提供 `proc_ns_operations` 接口定义。
  - `<linux/sched/task.h>`：访问任务结构中的 `nsproxy`。
  - `<linux/cred.h>`：凭证和能力检查（`ns_capable`）。
  - `<linux/slab.h>`：slab 内存分配器。
- **内核子系统**：
  - **命名空间子系统**：与 `nsproxy`、`ns_common` 紧密集成。
  - **用户命名空间子系统**：依赖其进行资源限制（`ucounts`）和权限模型。
  - **VFS/proc 文件系统**：通过 `proc_ns_operations` 暴露命名空间操作接口。
  - **能力（Capabilities）子系统**：用于 `CAP_SYS_ADMIN` 权限验证。

## 5. 使用场景

- **容器启动**：当容器运行时（如 Docker）创建新容器时，会通过 `clone()` 系统调用并设置 `CLONE_NEWUTS` 标志，为容器分配独立的主机名和域名，实现与宿主机及其他容器的隔离。
- **命名空间操作**：用户可通过 `/proc/[pid]/ns/uts` 文件使用 `setns()` 系统调用加入指定进程的 UTS 命名空间，或通过 `nsenter` 工具切换命名空间。
- **资源限制**：系统管理员可通过 `/proc/sys/user/max_uts_namespaces` 限制每个用户命名空间可创建的 UTS 命名空间数量，防止资源滥用。
- **内核初始化**：系统启动时调用 `uts_ns_init()` 初始化 slab 缓存，为后续命名空间操作提供内存分配支持。