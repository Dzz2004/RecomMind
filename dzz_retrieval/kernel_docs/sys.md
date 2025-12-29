# sys.c

> 自动生成时间: 2025-10-25 16:30:52
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sys.c`

---

# `sys.c` 内核源码技术文档

## 1. 文件概述

`sys.c` 是 Linux 内核中实现系统调用（system calls）的核心源文件之一，位于 `kernel/` 目录下。该文件主要负责处理与进程调度优先级、用户/组 ID 溢出处理、系统信息查询等相关的通用系统调用。其历史可追溯至 Linus Torvalds 早期开发阶段，是内核中提供 POSIX 兼容性的重要组成部分。当前文档所涵盖的代码片段聚焦于 `setpriority` 和 `getpriority` 系统调用的实现，以及与 UID/GID 溢出相关的全局变量定义。

## 2. 核心功能

### 全局变量
- `overflowuid` / `overflowgid`：用于在 32 位 UID/GID 架构中表示无法表示的旧式 16 位 UID/GID 的回退值，默认为 `DEFAULT_OVERFLOWUID`/`DEFAULT_OVERFLOWGID`。
- `fs_overflowuid` / `fs_overflowgid`：专用于仅支持 16 位 UID/GID 的文件系统的溢出回退值，适用于所有架构。

### 主要函数
- `set_one_prio_perm(struct task_struct *p)`：检查当前进程是否有权限修改目标进程 `p` 的调度优先级（nice 值）。
- `set_one_prio(struct task_struct *p, int niceval, int error)`：在权限检查通过后，实际设置目标进程的 nice 值。
- `SYSCALL_DEFINE3(setpriority, int, which, int, who, int, niceval)`：实现 `setpriority(2)` 系统调用，支持按进程、进程组或用户 ID 修改一组进程的优先级。
- `SYSCALL_DEFINE2(getpriority, int, which, int, who)`：实现 `getpriority(2)` 系统调用，返回指定范围（进程、进程组、用户）内最高优先级（即最小 nice 值）对应的兼容值。

## 3. 关键实现

### 权限控制机制
- `set_one_prio_perm()` 函数通过比较当前进程的有效 UID（`euid`）与目标进程的 UID 或有效 UID 是否相等来判断基本权限。
- 若不满足 UID 匹配，则检查当前进程是否在目标进程所属的用户命名空间（`user_ns`）中拥有 `CAP_SYS_NICE` 能力。
- 所有凭证（`cred`）访问均在 RCU 读锁保护下进行，确保并发安全。

### 优先级设置逻辑
- `setpriority` 系统调用首先将用户传入的 `niceval` 限制在 `[MIN_NICE, MAX_NICE]` 范围内（通常为 -20 到 19）。
- 根据 `which` 参数（`PRIO_PROCESS`、`PRIO_PGRP` 或 `PRIO_USER`）分别处理：
  - **进程**：通过 `find_task_by_vpid()` 查找目标进程。
  - **进程组**：使用 `do_each_pid_thread()` 遍历指定进程组内的所有线程。
  - **用户**：遍历所有进程，筛选 UID 匹配的进程；若目标 UID 非当前用户，则通过 `find_user()` 获取用户结构并最终 `free_uid()` 释放引用。
- 实际设置前调用 LSM（Linux Security Module）钩子 `security_task_setnice()` 进行安全策略检查。

### 优先级获取的兼容性处理
- `getpriority` 返回值采用历史兼容格式：将实际 nice 值（-20~19）转换为 `20 - nice`，即返回 1~40 的正整数。
- 该转换通过 `nice_to_rlimit()` 宏实现（定义在 `<linux/resource.h>` 中）。
- 返回的是指定范围内**最高优先级**（即最大 `nice_to_rlimit` 值，对应最小实际 nice 值）。

### 架构无关性处理
- 文件开头通过一系列 `#ifndef` 宏定义（如 `SET_UNALIGN_CTL`、`GET_FP_MODE` 等）为不支持特定 CPU 控制功能的架构提供默认 `-EINVAL` 返回值，避免编译错误。

## 4. 依赖关系

### 头文件依赖
- **调度子系统**：`<linux/sched.h>` 及其子头文件（如 `sched/task.h`、`sched/cputime.h`）提供任务结构、nice 值操作和遍历接口。
- **用户/组管理**：`<linux/cred.h>`、`<linux/uidgid.h>`、`<linux/user_namespace.h>` 处理凭证、UID/GID 映射及命名空间。
- **安全模块**：`<linux/security.h>`、`<linux/capability.h>` 提供 LSM 钩子和能力检查。
- **进程管理**：`<linux/pid.h>`（通过 `find_vpid` 等）、`<linux/rcupdate.h>`（RCU 锁）、`<linux/task_io_accounting_ops.h>`。
- **系统调用框架**：`<linux/syscalls.h>`、`<linux/uaccess.h>`。
- **其他**：`<linux/resource.h>`（`nice_to_rlimit`）、`<linux/utsname.h>`（系统信息）、`<generated/utsrelease.h>`（内核版本）。

### 内核子系统交互
- **调度器**：通过 `set_user_nice()` 和 `task_nice()` 与核心调度逻辑交互。
- **用户命名空间**：在 UID 比较和能力检查中依赖用户命名空间隔离机制。
- **LSM 框架**：调用 `security_task_setnice()` 允许安全模块（如 SELinux、AppArmor）拦截优先级修改。
- **进程遍历机制**：使用 `for_each_process_thread()` 和 `do_each_pid_thread()` 安全遍历进程列表。

## 5. 使用场景

- **用户空间程序调用 `setpriority()`/`getpriority()`**：如 `nice`、`renice` 命令，或应用程序动态调整自身/子进程 CPU 调度优先级。
- **系统初始化**：`overflowuid`/`overflowgid` 等变量在内核启动时初始化，供 VFS 和 IPC 子系统在处理旧式 16 位 UID/GID 时使用。
- **容器与命名空间环境**：在用户命名空间中，`setpriority` 的权限检查基于目标进程的用户命名空间，确保容器内进程无法越权修改宿主机进程优先级。
- **安全审计与限制**：通过 LSM 钩子，系统可记录或阻止非特权进程提升优先级的行为。
- **跨架构兼容**：为不支持浮点控制、对齐控制等特性的 CPU 架构提供统一的系统调用接口，避免架构特定代码污染通用逻辑。