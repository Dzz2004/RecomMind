# ucount.c

> 自动生成时间: 2025-10-25 17:42:48
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `ucount.c`

---

# ucount.c 技术文档

## 1. 文件概述

`ucount.c` 是 Linux 内核中用于实现用户资源计数（user counts）管理的核心模块。该文件提供了一套机制，用于跟踪和限制每个用户（在特定用户命名空间中）所使用的各种系统资源（如命名空间数量、inotify 实例等）的上限。它通过引用计数、哈希表和 RCU（Read-Copy-Update）机制，高效地管理跨用户命名空间层级的资源使用统计，并支持与 `sysctl` 接口集成，允许用户空间动态配置资源限制。

## 2. 核心功能

### 主要数据结构

- **`struct ucounts`**：表示一个用户（UID）在特定用户命名空间（`user_namespace`）下的资源使用计数器集合。
  - `ns`：所属的用户命名空间。
  - `uid`：关联的用户 ID。
  - `count`：该 `ucounts` 实例自身的引用计数（使用 `rcuref`）。
  - `ucount[]`：按 `enum ucount_type` 索引的原子计数器，用于跟踪各类命名空间等资源的使用量。
  - `rlimit[]`：按 `enum rlimit_type` 索引的原子计数器，用于跟踪与 rlimit 相关的资源（如进程数）。
  - `node`：用于链接到全局哈希表的链表节点。
  - `rcu`：用于 RCU 释放的回调字段。

- **`init_ucounts`**：全局初始化的 `ucounts` 实例，代表初始用户命名空间中的 root 用户。

- **`ucounts_hashtable`**：全局哈希表，用于快速查找特定 `(ns, uid)` 对应的 `ucounts` 实例。

### 主要函数

- **资源计数管理**
  - `alloc_ucounts()`：为指定 `(ns, uid)` 分配或查找对应的 `ucounts` 实例。
  - `put_ucounts()`：减少 `ucounts` 引用计数，若为零则释放资源。
  - `get_ucounts()`（隐含在 `rcuref_get` 中）：增加 `ucounts` 引用计数。

- **资源使用量增减**
  - `inc_ucount()` / `dec_ucount()`：增加/减少指定类型（`ucount_type`）的资源使用计数，自动遍历用户命名空间层级。
  - `inc_rlimit_ucounts()` / `dec_rlimit_ucounts()`：增加/减少指定类型（`rlimit_type`）的 rlimit 相关资源计数。
  - `inc_rlimit_get_ucounts()` / `dec_rlimit_put_ucounts()`：在增减 rlimit 计数的同时管理 `ucounts` 引用（用于资源首次使用/完全释放时）。

- **Sysctl 接口**
  - `setup_userns_sysctls()`：为新创建的用户命名空间注册 sysctl 表项。
  - `retire_userns_sysctls()`：销毁用户命名空间时注销 sysctl 表项。

## 3. 关键实现

### 哈希表与并发控制
- 使用大小为 `2^10` 的哈希表 (`ucounts_hashtable`) 存储所有 `ucounts` 实例。
- 哈希函数 `ucounts_hashfn` 结合用户命名空间指针和 UID 值进行散列。
- 读操作（`find_ucounts`）使用 RCU 保护，无需加锁，提高并发性能。
- 写操作（插入、删除）使用自旋锁 `ucounts_lock` 保证原子性，并配合 RCU 安全释放内存。

### 用户命名空间层级遍历
- 资源计数（`ucount[]` 和 `rlimit[]`）在用户命名空间层级中自底向上累加。
- `inc_ucount` 等函数从当前命名空间开始，逐级向上遍历父命名空间（通过 `iter->ns->ucounts`），确保所有祖先命名空间的资源限制都被检查和更新。

### 资源限制检查
- `atomic_long_inc_below()` 使用原子比较交换（CAS）循环，在增加计数前检查是否超过上限，避免竞态条件。
- 若在层级遍历中任一命名空间的资源超限，会回滚已增加的计数并返回失败。

### Sysctl 集成
- 每个用户命名空间拥有独立的 sysctl 表（`ns->sysctls`），通过 `set_root` 和 `set_lookup` 机制动态绑定。
- 权限控制：拥有 `CAP_SYS_RESOURCE` 的进程可读写，其他进程仅可读。
- sysctl 表项（如 `max_user_namespaces`）直接映射到 `ns->ucount_max[]` 数组，供资源计数函数使用。

### 内存安全
- 使用 `kmemleak` 注解避免内存泄漏误报。
- 通过 `get_user_ns()` / `put_user_ns()` 管理用户命名空间生命周期，防止 `ucounts` 持有已销毁的命名空间引用。
- 使用 `kfree_rcu()` 安全释放 `ucounts` 结构体。

## 4. 依赖关系

- **`<linux/user_namespace.h>`**：核心依赖，提供用户命名空间结构和操作函数（如 `get_user_ns`, `put_user_ns`）。
- **`<linux/sysctl.h>`**：用于实现用户命名空间特定的 sysctl 接口。
- **`<linux/rcupdate.h>`**（隐含）：通过 `rcuref` 和 RCU 链表实现无锁读取。
- **`<linux/atomic.h>`**：提供原子操作（`atomic_long_*`）用于资源计数。
- **命名空间子系统**：与 PID、UTS、IPC、NET、MNT、CGROUP、TIME 等命名空间的创建/销毁逻辑紧密集成。
- **文件监控子系统**：与 `inotify` 和 `fanotify` 集成，限制其实例和监视项数量。

## 5. 使用场景

- **命名空间创建限制**：当进程尝试创建新的用户、PID、网络等命名空间时，内核调用 `inc_ucount()` 检查并增加对应计数，防止资源耗尽。
- **文件监控资源管理**：`inotify_init()` 和 `fanotify_init()` 调用 `inc_ucount()` 限制每个用户的监控实例和监视项总数。
- **进程/线程数限制**：通过 `rlimit` 相关计数器（如 `RLIMIT_NPROC`）跟踪用户进程数，结合 `inc_rlimit_ucounts()` 实现。
- **动态资源调优**：系统管理员可通过 `/proc/sys/user/` 下的 sysctl 接口（如 `max_user_namespaces`）调整各用户命名空间的资源上限。
- **容器环境隔离**：在容器运行时（如 Docker、LXC）中，每个容器通常运行在独立的用户命名空间内，`ucounts` 机制确保容器间的资源使用相互隔离且受控。