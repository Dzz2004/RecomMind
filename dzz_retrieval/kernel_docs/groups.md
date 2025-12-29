# groups.c

> 自动生成时间: 2025-10-25 13:42:54
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `groups.c`

---

# groups.c 技术文档

## 文件概述

`groups.c` 是 Linux 内核中用于管理进程**补充组 ID（supplementary group IDs）**的核心实现文件。它提供了对进程所属附加用户组的分配、释放、排序、搜索、用户空间交互以及权限验证等完整功能，是内核凭证（credentials）子系统的重要组成部分。该文件支撑了 `getgroups()` 和 `setgroups()` 系统调用，并为内核其他模块提供组成员关系检查接口。

## 核心功能

### 主要数据结构
- `struct group_info`：表示一个进程的补充组列表，包含组数量（`ngroups`）和动态数组（`gid[]`），通过引用计数（`usage`）管理生命周期。

### 主要函数

| 函数 | 功能描述 |
|------|--------|
| `groups_alloc(int gidsetsize)` | 分配并初始化一个 `group_info` 结构体，指定组数量 |
| `groups_free(struct group_info *group_info)` | 释放 `group_info` 结构体内存 |
| `groups_to_user(gid_t __user *grouplist, const struct group_info *group_info)` | 将内核组列表复制到用户空间缓冲区 |
| `groups_from_user(struct group_info *group_info, gid_t __user *grouplist)` | 从用户空间读取组列表填充到内核结构 |
| `groups_sort(struct group_info *group_info)` | 对组列表进行升序排序（用于二分查找） |
| `groups_search(const struct group_info *group_info, kgid_t grp)` | 在已排序的组列表中二分查找指定组 |
| `set_groups(struct cred *new, struct group_info *group_info)` | 将新的组信息设置到凭证结构中 |
| `set_current_groups(struct group_info *group_info)` | 安全地将新组列表应用到当前进程 |
| `getgroups()` 系统调用 | 获取当前进程的补充组列表 |
| `setgroups()` 系统调用 | 设置当前进程的补充组列表 |
| `in_group_p(kgid_t grp)` | 检查当前进程是否属于指定组（含 `fsgid`） |
| `in_egroup_p(kgid_t grp)` | 检查当前进程是否属于指定组（含 `egid`） |
| `may_setgroups(void)` | 检查当前进程是否有权限调用 `setgroups()` |

## 关键实现

### 1. 内存管理与引用计数
- 使用 `kvmalloc()` 分配 `group_info`，支持大内存分配（可回退到 vmalloc）。
- 通过 `atomic_t usage` 实现引用计数，配合 `get_group_info()` / `put_group_info()` 宏进行安全共享。
- `groups_free()` 使用 `kvfree()` 释放内存，与分配方式匹配。

### 2. 用户命名空间与 GID 转换
- 所有用户空间与内核空间的 GID 交互均通过 `current_user_ns()` 获取当前用户命名空间。
- `from_kgid_munged()`：将内核 GID 转换为用户命名空间可见的 GID（无效时返回 `overflowgid`）。
- `make_kgid()` + `gid_valid()`：验证用户传入的 GID 在当前命名空间中是否有效。

### 3. 高效组成员查找
- 组列表在 `setgroups()` 中强制排序（`groups_sort()`）。
- `groups_search()` 使用标准二分查找算法，时间复杂度 O(log n)，提升权限检查效率。
- 比较函数 `gid_cmp()` 基于 `gid_gt()` / `gid_lt()` 宏，确保跨架构正确性。

### 4. 凭证更新安全机制
- `set_current_groups()` 使用 `prepare_creds()` / `commit_creds()` 机制：
  - 先复制当前凭证（COW）
  - 更新组信息
  - 调用 LSM 钩子 `security_task_fix_setgroups()` 进行安全策略检查
  - 成功则提交，失败则回滚（`abort_creds()`）

### 5. 权限控制
- `may_setgroups()` 同时检查：
  - `CAP_SETGID` 能力（在当前用户命名空间中）
  - `userns_may_setgroups()`（用户命名空间是否允许设置组）

## 依赖关系

- **`<linux/cred.h>`**：凭证结构 `struct cred` 及相关操作（`current_cred()`, `prepare_creds()` 等）
- **`<linux/user_namespace.h>`**：用户命名空间支持，GID 映射与验证
- **`<linux/security.h>`**：LSM 安全模块钩子（`security_task_fix_setgroups()`）
- **`<linux/sort.h>`**：通用排序函数 `sort()`
- **`<linux/uaccess.h>`**：用户空间内存访问（`get_user()` / `put_user()`）
- **`<linux/vmalloc.h>`**：大内存分配支持（`kvmalloc()` / `kvfree()`）
- **`<linux/syscalls.h>`**：系统调用定义宏（`SYSCALL_DEFINE2`）

## 使用场景

1. **系统调用处理**：
   - 用户程序调用 `getgroups()` 获取当前进程所属的补充组列表
   - 特权进程（如 `init`、`sudo`）调用 `setgroups()` 切换组上下文

2. **权限检查**：
   - 文件系统访问控制（如检查进程是否属于文件所属组）
   - 网络操作权限验证（如绑定特权端口）
   - 通过 `in_group_p()` / `in_egroup_p()` 在内核各子系统中快速验证组成员资格

3. **进程凭证管理**：
   - `execve()` 执行时继承或重置组信息
   - 用户命名空间创建时初始化组列表
   - 容器运行时（如 Docker）通过 `setgroups()` 实现组隔离

4. **安全模块集成**：
   - SELinux、AppArmor 等 LSM 模块在 `setgroups()` 时进行策略校验
   - 用户命名空间的组映射限制（防止逃逸）