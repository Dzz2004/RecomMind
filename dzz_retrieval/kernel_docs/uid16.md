# uid16.c

> 自动生成时间: 2025-10-25 17:43:42
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `uid16.c`

---

# uid16.c 技术文档

## 文件概述

`uid16.c` 是 Linux 内核中用于提供 16 位用户 ID（UID）和组 ID（GID）系统调用兼容性的封装层。该文件实现了旧式 16 位 UID/GID 系统调用（如 `chown16`、`setuid16` 等）到现代 32 位 UID/GID 内核接口的桥接，确保运行在 32 位 UID/GID 架构上的旧应用程序仍能在支持高 UID（high UID）的现代内核上正常工作。文件注释中提到“希望五年后能移除这些接口”，表明其为临时兼容性方案。

## 核心功能

### 主要系统调用函数

- **文件所有权变更类**：
  - `chown16`：变更文件所有者和所属组（16 位接口）
  - `lchown16`：变更符号链接指向文件的所有者和组（16 位接口）
  - `fchown16`：通过文件描述符变更文件所有者和组（16 位接口）

- **用户 ID 设置类**：
  - `setuid16` / `seteuid16`（通过 `setreuid16` 实现）：设置真实/有效 UID
  - `setreuid16`：同时设置真实 UID 和有效 UID
  - `setresuid16`：设置真实、有效和保存的 UID
  - `setfsuid16`：设置文件系统 UID

- **组 ID 设置类**：
  - `setgid16` / `setegid16`（通过 `setregid16` 实现）：设置真实/有效 GID
  - `setregid16`：同时设置真实 GID 和有效 GID
  - `setresgid16`：设置真实、有效和保存的 GID
  - `setfsgid16`：设置文件系统 GID

- **查询类**：
  - `getuid16` / `geteuid16`：获取当前真实/有效 UID（16 位返回）
  - `getgid16` / `getegid16`：获取当前真实/有效 GID（16 位返回）
  - `getresuid16` / `getresgid16`：获取三类 UID/GID（真实、有效、保存）
  - `getgroups16`：获取当前进程的附加组列表（16 位格式）
  - `setgroups16`：设置当前进程的附加组列表（16 位输入）

### 辅助函数

- `groups16_to_user`：将内核 `group_info` 中的 GID 转换为 16 位格式并复制到用户空间
- `groups16_from_user`：从用户空间读取 16 位 GID 列表并转换为内核 `kgid_t` 格式

### 关键宏与类型

- `old_uid_t` / `old_gid_t`：定义为 16 位整数类型（通常为 `__u16`）
- `low2highuid` / `low2highgid`：将 16 位 UID/GID 扩展为 32 位内核表示
- `high2lowuid` / `high2lowgid`：将 32 位内核 UID/GID 截断为 16 位返回用户空间
- `from_kuid_munged` / `from_kgid_munged`：在用户命名空间上下文中将内核 UID/GID 转换为用户可见值，并处理无效 ID

## 关键实现

### UID/GID 转换机制

- 所有 16 位系统调用首先使用 `low2highuid()` 或 `low2highgid()` 将传入的 16 位值转换为内核使用的 32 位 `kuid_t`/`kgid_t` 类型。
- 查询类调用（如 `getuid16`）则通过 `from_kuid_munged()` 将内核 UID 映射到当前用户命名空间的用户可见值，再用 `high2lowuid()` 截断为 16 位返回。
- `from_kuid_munged()` 在 UID 超出 16 位范围（>65535）时会返回 `(uid_t) -1`，确保旧程序不会收到无法处理的大值。

### 用户命名空间支持

- 所有转换均通过 `current_user_ns()` 获取当前进程的用户命名空间，确保在容器或用户命名空间隔离环境中正确映射 UID/GID。
- 例如：`from_kuid_munged(cred->user_ns, cred->uid)` 将内核 UID 转换为该命名空间下的用户视角 UID。

### 组列表处理

- `getgroups16` 和 `setgroups16` 通过辅助函数 `groups16_to_user`/`groups16_from_user` 实现 16 位与内核 `kgid_t` 数组的双向转换。
- `setgroups16` 在设置前调用 `groups_sort()` 对组列表排序，符合内核对 `group_info` 的要求。

### 错误处理与边界检查

- `setgroups16` 检查 `gidsetsize` 是否超过 `NGROUPS_MAX`，防止内存溢出。
- `getgroups16` 在 `gidsetsize` 小于实际组数时返回 `-EINVAL`，符合 POSIX 语义。
- 所有用户空间访问均通过 `put_user`/`get_user` 进行，失败时返回 `-EFAULT`。

## 依赖关系

- **头文件依赖**：
  - `<linux/cred.h>`：访问 `struct cred` 和 `current_cred()`
  - `<linux/highuid.h>`：提供 `low2highuid`/`high2lowuid` 等转换宏
  - `<linux/uaccess.h>`：提供 `put_user`/`get_user` 用户空间访问接口
  - `<linux/syscalls.h>`：使用 `SYSCALL_DEFINE` 宏定义系统调用
  - `<linux/security.h>`：间接依赖安全模块钩子（如 `may_setgroups`）

- **内核子系统依赖**：
  - **用户命名空间**（`user_namespace`）：所有 UID/GID 转换基于当前命名空间
  - **凭证管理**（`cred`）：读取/修改进程的 UID/GID 属性
  - **组管理**（`group_info`）：处理附加组列表的分配、排序和设置
  - **系统调用框架**：通过 `ksys_*` 和 `__sys_*` 内核内部接口复用主逻辑

## 使用场景

- **旧版二进制兼容**：运行在早期 Linux 发行版（仅支持 16 位 UID/GID）上的应用程序在现代内核上执行时，自动通过这些 16 位系统调用接口与内核交互。
- **嵌入式或资源受限系统**：某些遗留嵌入式系统可能仍使用 16 位 UID/GID 接口以节省空间或保持 ABI 兼容。
- **用户命名空间容器环境**：在容器中运行的旧程序可通过这些接口正确映射容器内 UID/GID 到宿主机内核表示。
- **系统调用拦截与审计**：安全模块可通过这些封装层监控或控制对 UID/GID 的变更操作。

> 注：随着 16 位 UID/GID 的淘汰，这些接口在现代系统中已极少使用，主要用于维持向后兼容性。