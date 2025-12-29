# ptrace.c

> 自动生成时间: 2025-10-25 15:37:14
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `ptrace.c`

---

# ptrace.c 技术文档

## 1. 文件概述

`ptrace.c` 是 Linux 内核中实现 **ptrace**（进程跟踪）机制的核心通用代码文件。该文件提供了跨架构的 ptrace 公共接口和基础功能，避免在每个体系结构中重复实现相同逻辑。ptrace 机制允许一个进程（tracer，通常是调试器）观察和控制另一个进程（tracee）的执行，包括读写其内存、寄存器状态、拦截系统调用等，是调试器（如 GDB）、系统调用追踪工具（如 strace）和安全监控工具的基础。

## 2. 核心功能

### 主要函数

- **`ptrace_access_vm()`**  
  安全地访问被跟踪进程（tracee）的虚拟内存空间，用于读写其内存内容。

- **`__ptrace_link()`**  
  将被跟踪进程链接到跟踪进程（tracer）的 `ptraced` 链表中，并设置其父进程为 tracer。

- **`ptrace_link()`**  
  封装 `__ptrace_link()`，使用当前进程的凭证建立跟踪关系。

- **`__ptrace_unlink()`**  
  解除跟踪关系：将被跟踪进程从 tracer 的链表中移除，恢复其原始父进程，并根据进程组停止状态调整其任务状态（如从 `TASK_TRACED` 转为 `TASK_STOPPED` 或唤醒）。

- **`ptrace_freeze_traced()`** / **`ptrace_unfreeze_traced()`**  
  在执行 ptrace 操作期间临时冻结被跟踪进程，防止其被意外唤醒（即使是 SIGKILL），确保操作的原子性和一致性。

- **`ptrace_check_attach()`**  
  验证当前进程是否有权对目标进程执行 ptrace 操作，并确保目标进程处于合适的跟踪状态（可选）。

- **`looks_like_a_spurious_pid()`**  
  辅助函数，用于检测因线程组 leader 更换（如 `de_thread()`）导致的“虚假”ptrace 事件，避免对已销毁进程的误操作。

### 关键数据结构字段（在 `task_struct` 中）

- `ptrace`：标志位，表示进程是否被跟踪。
- `parent` / `real_parent`：分别表示当前父进程（通常是 tracer）和原始父进程。
- `ptraced`：链表头，包含所有被当前进程跟踪的子进程。
- `ptrace_entry`：链表节点，用于加入 tracer 的 `ptraced` 链表。
- `ptracer_cred`：跟踪进程的凭证（credentials），用于权限检查。
- `jobctl`：任务控制标志，包含 `JOBCTL_PTRACE_FROZEN`、`JOBCTL_TRACED`、`JOBCTL_STOP_PENDING` 等 ptrace 相关状态。

## 3. 关键实现

### 安全内存访问 (`ptrace_access_vm`)
- 通过 `get_task_mm()` 获取目标进程的内存描述符 `mm_struct`。
- 执行严格的权限检查：
  - 目标进程必须正在被跟踪（`tsk->ptrace` 非零）。
  - 当前进程必须是目标进程的直接父进程（`current == tsk->parent`）。
  - 或者当前进程在目标进程的用户命名空间中具有 `CAP_SYS_PTRACE` 能力（通过 `ptracer_capable()` 检查）。
- 使用 `__access_remote_vm()` 安全地读写目标进程内存，避免直接遍历页表。

### 跟踪关系管理
- **链接**：`ptrace_link()` 在持有 `tasklist_lock` 写锁时调用 `__ptrace_link()`，将 tracee 加入 tracer 的 `ptraced` 链表，并保存 tracer 的凭证。
- **解链接**：`__ptrace_unlink()` 在 detach 或 tracer 退出时调用：
  - 清除 syscall trace/emu 标志。
  - 恢复 `real_parent`。
  - 清除 `ptrace` 标志和 jobctl 中的 trap 相关位。
  - 根据进程组停止状态决定是否设置 `JOBCTL_STOP_PENDING` 并唤醒进程（`ptrace_signal_wake_up()`）。

### 进程状态冻结机制
- 在执行 ptrace 操作前调用 `ptrace_freeze_traced()`：
  - 若 tracee 处于 `TASK_TRACED` 且无致命信号待处理，则设置 `JOBCTL_PTRACE_FROZEN` 标志，使其无法被唤醒。
- 操作完成后调用 `ptrace_unfreeze_traced()`：
  - 清除冻结标志。
  - 若存在致命信号（如 SIGKILL），则清除 `JOBCTL_TRACED` 并唤醒进程以处理信号。

### 权限与状态验证 (`ptrace_check_attach`)
- 在 `tasklist_lock` 读锁保护下验证：
  - 目标进程确由当前进程跟踪（`child->ptrace && child->parent == current`）。
  - 若 `ignore_state=false`，则进一步冻结 tracee 以确保其处于稳定状态。

## 4. 依赖关系

- **调度子系统**：依赖 `task_struct`、`mm_struct`、`sighand_struct` 等核心数据结构，以及 `wake_up_state()`、`task_is_traced()` 等调度状态管理函数。
- **内存管理**：通过 `get_task_mm()`、`mmput()` 和 `__access_remote_vm()` 访问远程进程内存。
- **信号处理**：大量使用 `siglock`、`jobctl`、`signal_struct` 等信号相关机制管理进程状态转换。
- **安全模块**：集成 LSM（Linux Security Module）钩子（`security_ptrace_access_check`）和能力检查（`capable()`）。
- **审计与通知**：与 `audit` 和 `cn_proc`（进程事件连接器）交互，记录 ptrace 事件。
- **体系结构相关代码**：依赖 `asm/syscall.h` 提供的 `syscall_get_*` 接口获取系统调用信息。
- **硬件断点**：通过 `hw_breakpoint.h` 支持硬件断点调试功能。

## 5. 使用场景

- **调试器（如 GDB）**：attach 到目标进程，读取/修改寄存器和内存，设置断点，单步执行。
- **系统调用追踪（如 strace）**：拦截并记录目标进程的所有系统调用及其参数和返回值。
- **安全监控工具**：监控可疑进程的行为，如检测恶意代码注入或提权操作。
- **容器与沙箱**：在用户命名空间中实现进程隔离和监控。
- **内核测试**：用于内核自检和调试，验证进程行为和系统调用处理。
- **进程注入与热补丁**：通过修改运行中进程的内存和寄存器状态实现代码注入或修复。