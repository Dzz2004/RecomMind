# user.c

> 自动生成时间: 2025-10-25 17:45:58
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `user.c`

---

# user.c 技术文档

## 1. 文件概述

`user.c` 实现了 Linux 内核中的 **用户缓存（user cache）** 机制，用于跟踪每个用户（以 UID 标识）所占用的系统资源（如进程数、打开文件数等），从而支持基于用户的资源限制（per-user limits）。该文件维护了一个全局的哈希表，用于快速查找和管理 `user_struct` 结构体实例，并提供了用户结构的分配、引用计数管理和释放接口。此外，文件还定义了初始用户命名空间 `init_user_ns` 和根用户结构 `root_user`，为系统启动和用户命名空间功能提供基础支持。

## 2. 核心功能

### 主要数据结构

- **`init_user_ns`**：全局初始用户命名空间（`struct user_namespace`），作为所有用户命名空间的根，包含完整的 UID/GID/ProjID 映射（0~2³²-1），引用计数初始化为 3。
- **`root_user`**：代表 UID 为 0 的根用户的 `struct user_struct` 实例，引用计数初始化为 1（供 init 进程使用）。
- **`uidhash_table`**：大小为 `2^UIDHASH_BITS`（通常为 128）的哈希表，用于存储 `user_struct` 实例，实现 O(1) 平均查找复杂度。
- **`uid_cachep`**：SLAB 缓存，用于高效分配和释放 `struct user_struct` 对象。

### 主要函数

- **`alloc_uid(kuid_t uid)`**：根据 UID 查找或创建对应的 `user_struct`。若不存在则分配新结构体，初始化资源计数器（如 epoll watches），并插入哈希表；若已存在则增加引用计数。处理并发创建的竞争条件。
- **`find_user(kuid_t uid)`**：在哈希表中查找指定 UID 的 `user_struct`，若找到则增加引用计数并返回，否则返回 NULL。
- **`free_uid(struct user_struct *up)`**：减少 `user_struct` 的引用计数，若计数归零则调用 `free_user` 释放资源。
- **`free_user(struct user_struct *up, unsigned long flags)`**：内部函数，从哈希表中移除用户结构，释放 epoll 计数器，并通过 SLAB 缓存回收内存。
- **`uid_cache_init(void)`**：初始化函数（通过 `subsys_initcall` 注册），创建 SLAB 缓存、初始化哈希表、为 `root_user` 分配 epoll 计数器，并将 `root_user` 插入哈希表。

### 辅助函数

- **`uid_hash_insert/remove/find`**：哈希表操作的内部封装，必须在持有 `uidhash_lock` 自旋锁时调用。
- **`user_epoll_alloc/free`**：条件编译函数，用于初始化/销毁 `user_struct` 中的 epoll watches per-CPU 计数器（仅当 `CONFIG_EPOLL` 启用时有效）。

## 3. 关键实现

### 哈希表设计与并发控制

- **哈希函数**：使用 `__uidhashfn(uid) = ((uid >> UIDHASH_BITS) + uid) & UIDHASH_MASK`，将 32 位 UID 映射到 `UIDHASH_SZ`（默认 128）个桶中，减少冲突。
- **锁机制**：使用 `DEFINE_SPINLOCK(uidhash_lock)` 保护哈希表操作。该锁需 **软中断安全（softirq-safe）**，因为 `free_uid()` 可能在 RCU 回调（软中断上下文）中被调用。
- **中断处理**：所有哈希表操作均使用 `spin_lock_irqsave/restore` 或 `spin_lock_irq/unlock`，确保在中断上下文和进程上下文间的正确同步。

### 引用计数与资源管理

- **引用计数**：`user_struct.__count` 使用 `refcount_t` 类型，确保原子操作。`alloc_uid` 返回时已持有引用，调用者必须通过 `free_uid` 释放。
- **延迟释放**：`free_uid` 使用 `refcount_dec_and_lock_irqsave` 原子地减少计数并在归零时获取锁，避免竞态条件。
- **资源初始化**：新创建的 `user_struct` 会初始化速率限制器（`ratelimit`）和 epoll watches 计数器（若启用）。

### 初始化与竞态处理

- **`root_user` 预置**：在 `uid_cache_init` 中预先将 `root_user` 插入哈希表，确保 init 进程可直接使用。
- **双重检查**：`alloc_uid` 在分配新结构后再次检查哈希表，防止多线程同时创建同一 UID 的 `user_struct`，确保唯一性。

### 用户命名空间支持

- **`init_user_ns`**：作为初始用户命名空间，其 UID/GID 映射覆盖全范围（0 到 2³²-1），标志位 `USERNS_INIT_FLAGS` 启用特定行为（如允许 setgroups）。
- **密钥环支持**：若启用 `CONFIG_KEYS`，`init_user_ns` 包含密钥环名称列表和读写信号量。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/sched/user.h>`：定义 `struct user_struct`。
  - `<linux/user_namespace.h>`：定义 `struct user_namespace` 和相关操作。
  - `<linux/key.h>`：提供密钥环支持（条件编译）。
  - `<linux/percpu_counter.h>`（隐含）：用于 epoll watches 计数（通过 `CONFIG_EPOLL`）。
- **内核配置依赖**：
  - `CONFIG_EPOLL`：控制 epoll watches 计数器的编译。
  - `CONFIG_USER_NS`：控制用户命名空间操作函数的绑定。
  - `CONFIG_KEYS`：控制密钥环相关字段的初始化。
- **子系统依赖**：
  - **进程调度子系统**：`user_struct` 被嵌入到进程凭证（`cred`）中，用于资源统计。
  - **用户命名空间子系统**：`init_user_ns` 是用户命名空间层次结构的根。
  - **内存管理子系统**：依赖 SLAB 分配器管理 `user_struct` 对象。

## 5. 使用场景

- **进程凭证管理**：当进程通过 `setuid()`、`setreuid()` 等系统调用切换用户身份时，内核调用 `alloc_uid` 获取目标 UID 的 `user_struct`，并更新进程凭证中的用户引用。
- **资源限制实施**：内核在创建进程、打开文件、分配内存等操作时，通过 `current_uid()` 获取当前用户的 `user_struct`，检查并更新资源使用计数（如 `processes`、`files` 字段），确保不超过 `ulimit` 限制。
- **用户命名空间创建**：新用户命名空间的创建依赖 `init_user_ns` 作为父命名空间，并继承其映射逻辑。
- **系统初始化**：在内核启动早期（`subsys_initcall` 阶段），初始化用户缓存和根用户结构，为 init 进程（PID 1）提供用户上下文。
- **资源回收**：当进程退出或切换用户时，通过 `free_uid` 释放不再需要的 `user_struct` 引用，最终在引用计数归零时回收内存和相关资源（如 epoll 计数器）。