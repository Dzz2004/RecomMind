# cred.c

> 自动生成时间: 2025-10-25 12:58:25
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cred.c`

---

# cred.c 技术文档

## 文件概述

`cred.c` 是 Linux 内核中负责任务（task）凭证（credentials）管理的核心实现文件。它提供了凭证的分配、复制、修改、释放以及任务间凭证共享的完整机制。凭证结构体 `struct cred` 包含了进程运行所需的所有安全上下文信息，如用户 ID、组 ID、能力集（capabilities）、密钥环（keyrings）、安全模块数据等。该文件实现了基于引用计数和 RCU（Read-Copy-Update）的安全高效凭证管理，确保在多线程和并发环境下凭证操作的正确性与性能。

## 核心功能

### 主要数据结构
- `struct cred`：任务凭证结构体，包含 UID/GID、能力集、用户命名空间、组信息、密钥环、安全模块数据等。
- `init_cred`：初始任务（`init_task`）的全局初始凭证实例。
- `init_groups`：初始组信息，引用计数初始化为 2，防止被释放。

### 主要函数
- `__put_cred(struct cred *cred)`：释放凭证，通过 RCU 延迟回收或立即释放。
- `put_cred_rcu(struct rcu_head *rcu)`：RCU 回调函数，执行凭证的实际销毁。
- `exit_creds(struct task_struct *tsk)`：任务退出时清理其凭证。
- `get_task_cred(struct task_struct *task)`：安全获取另一任务的客观凭证（带引用计数）。
- `cred_alloc_blank(void)`：分配一个空白凭证结构体，用于后续填充。
- `prepare_creds(void)`：为当前任务准备一份可修改的新凭证副本。
- `prepare_exec_creds(void)`：为 `execve()` 系统调用准备凭证，重置 SUID/SGID 等字段。
- `copy_creds(struct task_struct *p, unsigned long clone_flags)`：在 `fork()` 时复制或共享凭证。

## 关键实现

### 引用计数与 RCU 机制
- 所有凭证通过 `atomic_long_t usage` 字段进行引用计数管理。
- 凭证释放采用 RCU 机制：`__put_cred()` 根据 `non_rcu` 标志决定是否立即调用 `put_cred_rcu()` 或通过 `call_rcu()` 延迟执行。
- `put_cred_rcu()` 在 RCU 宽限期结束后执行实际资源释放，包括密钥环、用户信息、用户命名空间、组信息等。

### 凭证修改的安全模型
- 内核禁止直接修改任务的 `cred` 字段。必须通过 `prepare_creds()` 创建副本，修改后调用 `commit_creds()` 提交。
- `prepare_creds()` 深拷贝当前凭证，并对所有可共享子结构（如 `group_info`、`user`、`user_ns`、密钥环等）增加引用计数。
- 安全模块（LSM）通过 `security_prepare_creds()` 和 `security_cred_free()` 钩子参与凭证生命周期管理。

### 特殊场景处理
- **execve()**：调用 `prepare_exec_creds()`，清除线程密钥环，重置 `suid/fsuid` 等为 `euid`，符合 POSIX 语义。
- **fork() / clone()**：
  - 若 `CLONE_THREAD` 且无线程密钥环，则直接共享凭证（仅增加引用计数）。
  - 否则调用 `prepare_creds()` 创建新凭证。
  - 若指定 `CLONE_NEWUSER`，则创建新的用户命名空间并设置 `ucounts`。
- **线程密钥环**：新线程若继承父线程密钥环，则在 `copy_creds()` 中显式安装新的线程密钥环。

### 调试支持
- 通过条件编译宏 `kdebug` 提供凭证操作的调试日志（默认关闭）。
- 多处使用 `BUG_ON()` 确保引用计数和状态一致性（如释放时 usage 必须为 0）。

## 依赖关系

- **头文件依赖**：
  - `<linux/cred.h>`：定义 `struct cred` 和相关 API。
  - `<linux/sched.h>`：任务结构体 `task_struct` 及调度相关。
  - `<linux/key.h>` / `<linux/keyctl.h>`：内核密钥管理子系统。
  - `<linux/security.h>`：Linux 安全模块（LSM）接口。
  - `<linux/uidgid.h>`：用户/组 ID 抽象（`kuid_t`/`kgid_t`）。
  - `<linux/user_namespace.h>`：用户命名空间支持。
  - `<linux/rcupdate.h>`：RCU 机制（通过 `call_rcu` 等间接使用）。

- **模块交互**：
  - **LSM 框架**：通过 `security_cred_alloc_blank()`、`security_prepare_creds()`、`security_cred_free()` 钩子集成。
  - **密钥服务**：管理 `session_keyring`、`process_keyring`、`thread_keyring` 等。
  - **用户/组管理**：依赖 `free_uid()`、`put_group_info()`、`put_ucounts()` 等用户资源管理函数。
  - **进程管理**：与 `fork()`、`execve()`、`exit()` 等系统调用路径紧密集成。

## 使用场景

1. **进程创建（fork/clone）**：
   - `copy_creds()` 在 `copy_process()` 中被调用，根据 `clone_flags` 决定凭证共享或复制策略。

2. **程序执行（execve）**：
   - `prepare_exec_creds()` 在 `bprm_creds_from_file()` 等路径中被调用，为新程序设置正确的凭证上下文。

3. **特权操作**：
   - 系统调用如 `setuid()`、`setgid()`、`capset()` 等通过 `prepare_creds()` → 修改字段 → `commit_creds()` 流程更新凭证。

4. **任务退出**：
   - `exit_creds()` 在 `do_exit()` 中被调用，释放任务持有的 `real_cred` 和 `cred`。

5. **跨任务凭证查询**：
   - 安全审计、进程间权限检查等场景通过 `get_task_cred()` 安全获取目标任务的凭证快照。

6. **内核线程凭证管理**：
   - 内核线程创建时通过 `cred_alloc_blank()` 或 `prepare_creds()` 初始化其凭证。