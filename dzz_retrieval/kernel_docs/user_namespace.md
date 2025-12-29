# user_namespace.c

> 自动生成时间: 2025-10-25 17:46:37
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `user_namespace.c`

---

# user_namespace.c 技术文档

## 1. 文件概述

`user_namespace.c` 是 Linux 内核中实现用户命名空间（User Namespace）核心功能的源文件。用户命名空间是 Linux 命名空间机制的一部分，用于隔离用户和组 ID（UID/GID），使得不同命名空间中的相同 UID 可以映射到宿主系统中的不同实际 UID/GID。该文件负责用户命名空间的创建、销毁、引用计数管理、ID 映射查找以及与凭证（credentials）的集成，是容器化技术（如 Docker、LXC）实现非特权容器和用户隔离的关键组件。

## 2. 核心功能

### 主要函数

- **`create_user_ns(struct cred *new)`**  
  创建一个新的用户命名空间，设置其父命名空间、层级、所有者、资源限制，并初始化凭证中的命名空间指针。

- **`unshare_userns(unsigned long unshare_flags, struct cred **new_cred)`**  
  为当前进程创建新的用户命名空间（通过 `unshare(CLONE_NEWUSER)` 系统调用触发），并返回新的凭证结构。

- **`free_user_ns(struct work_struct *work)`**  
  异步释放用户命名空间及其关联资源（如 ID 映射、sysctl 表、密钥环等），通过工作队列延迟执行以避免死锁。

- **`__put_user_ns(struct user_namespace *ns)`**  
  减少用户命名空间引用计数，若引用计数归零则调度 `free_user_ns` 工作项进行释放。

- **`map_id_range_down_base()` / `map_id_range_down_max()`**  
  在 UID/GID 映射表中查找指定 ID 范围对应的映射条目，分别处理小规模（≤4 条）和大规模（>4 条）映射。

- **`cmp_map_id()`**  
  用于二分查找的比较函数，支持正向（内核 ID → 用户 ID）和反向（用户 ID → 内核 ID）映射查询。

- **`set_cred_user_ns()`**  
  初始化新凭证中的用户命名空间相关字段，包括能力集（capabilities）、安全位（securebits）和密钥认证上下文。

- **`enforced_nproc_rlimit()`**  
  根据当前用户是否为全局 root 以及是否处于初始用户命名空间，决定是否对 `RLIMIT_NPROC` 施加限制。

### 主要数据结构

- **`struct user_namespace`**  
  用户命名空间的核心结构体，包含父命名空间指针、层级、所有者 UID/GID、ID 映射表（uid_map、gid_map、projid_map）、资源使用计数器（ucounts）、引用计数、标志位、密钥环列表等。

- **`struct idmap_key`**  
  用于 ID 映射查找的辅助结构，封装待查找的 ID、范围长度及映射方向（向上/向下）。

- **`struct uid_gid_extent`**  
  表示单个 UID/GID 映射区间的结构，包含起始内核 ID、起始用户 ID 和映射长度。

## 3. 关键实现

### 用户命名空间创建流程
1. **层级限制检查**：防止命名空间嵌套过深（最大 32 层）。
2. **资源计数**：通过 `inc_user_namespaces()` 增加父命名空间中创建者的用户命名空间使用计数。
3. **安全策略验证**：
   - 禁止在 chroot 环境中创建新用户命名空间。
   - 确保创建者的 UID/GID 在父命名空间中有有效映射。
4. **安全模块回调**：调用 LSM（如 SELinux、AppArmor）的 `security_create_user_ns()` 钩子进行权限检查。
5. **初始化新命名空间**：
   - 分配内存并设置层级、所有者、父指针。
   - 初始化资源限制（如进程数、消息队列大小等）。
   - 继承父命名空间的标志（如 `USERNS_SETGROUPS_ALLOWED`）。
   - 设置凭证中的用户命名空间指针并重置能力集。

### ID 映射查找算法
- **小规模映射（≤4 条）**：使用线性遍历（`map_id_range_down_base`）。
- **大规模映射（>4 条）**：使用二分查找（`map_id_range_down_max` + `bsearch`），映射表按 `first` 字段排序。
- **双向映射支持**：通过 `idmap_key.map_up` 标志区分内核 ID → 用户 ID（map down）和用户 ID → 内核 ID（map up）。

### 异步释放机制
- 使用 `INIT_WORK()` 将释放操作注册为工作队列任务。
- 在 `free_user_ns()` 中循环释放命名空间链（处理引用计数级联归零的情况）。
- 释放动态分配的映射表内存、sysctl 表、密钥环资源，并减少资源使用计数。

### 能力与安全上下文初始化
- 新命名空间的初始凭证拥有 `CAP_FULL_SET`，但这些能力仅在新命名空间内有效。
- 清除请求密钥认证（`request_key_auth`）上下文，防止跨命名空间密钥泄露。
- 重置安全位（`securebits`）为默认值。

## 4. 依赖关系

- **命名空间基础设施**：依赖 `<linux/nsproxy.h>` 和 `ns_common` 结构，与 `proc_ns.c` 协作提供 `/proc/<pid>/ns/user` 接口。
- **凭证管理**：与 `<linux/cred.h>` 紧密集成，通过 `prepare_creds()`/`put_cred()` 管理凭证生命周期。
- **资源计数**：使用 `<linux/user_namespace.h>` 中的 `ucounts` 机制跟踪用户命名空间、进程数等资源使用。
- **安全模块**：通过 LSM 接口（`security_create_user_ns()`）与安全子系统交互。
- **密钥管理**：依赖 `<keys/user-type.h>` 实现命名空间隔离的用户密钥环。
- **内存管理**：使用 SLAB 分配器（`kmem_cache`）高效分配 `user_namespace` 结构。
- **ID 映射**：与 `uidgid.c` 协同实现 UID/GID 映射的设置与查询。

## 5. 使用场景

- **容器运行时**：Docker、Podman、LXC 等通过 `unshare(CLONE_NEWUSER)` 创建非特权容器，实现用户隔离。
- **用户态命名空间管理**：`unshare(1)` 命令或 `clone(2)` 系统调用创建独立用户上下文。
- **特权降级**：进程在创建用户命名空间后映射自身为新命名空间的 root，获得有限特权。
- **安全沙箱**：浏览器、应用沙箱利用用户命名空间限制潜在攻击面。
- **ID 映射服务**：`newuidmap`/`newgidmap` 工具通过写入 `/proc/<pid>/uid_map` 配置映射，内核通过本文件中的查找函数解析映射关系。
- **资源隔离**：结合 `ucounts` 机制限制单个用户可创建的用户命名空间数量，防止资源耗尽攻击。