# entry\common.c

> 自动生成时间: 2025-10-25 13:19:03
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `entry\common.c`

---

# entry\common.c 技术文档

## 文件概述

`entry\common.c` 是 Linux 内核中处理系统调用入口/出口以及中断入口/出口路径的通用逻辑实现文件。该文件提供了一套架构无关的通用函数，用于在用户态与内核态之间切换时执行必要的上下文跟踪、审计、跟踪点、安全检查（如 seccomp）、信号处理、调度等工作。其目标是统一不同架构在系统调用和中断处理路径上的共性逻辑，减少重复代码。

## 核心功能

### 主要函数

| 函数名 | 功能描述 |
|--------|--------|
| `syscall_trace_enter()` | 系统调用进入时的通用处理函数，依次处理用户态分发、ptrace 跟踪、seccomp 安全检查、tracepoint 和审计 |
| `syscall_enter_from_user_mode_prepare()` | 从用户模式进入系统调用前的准备，启用中断并进入内核上下文 |
| `exit_to_user_mode_loop()` | 在返回用户空间前循环处理所有待办工作项（如调度、信号、uprobe、livepatch 等） |
| `syscall_exit_work()` | 系统调用退出时的通用处理，包括审计、tracepoint、ptrace 退出报告等 |
| `irqentry_enter()` / `irqentry_exit()` | 中断入口/出口的通用处理，管理 RCU、上下文跟踪、KMSAN、lockdep 等 |
| `irqentry_enter_from_user_mode()` / `irqentry_exit_to_user_mode()` | 从中断上下文进入/退出用户模式的专用路径 |
| `raw_irqentry_exit_cond_resched()` | 中断退出时的条件调度检查（仅在非抢占计数为 0 时） |

### 关键数据结构

- `irqentry_state_t`：记录中断入口状态，主要用于判断是否需要在退出时执行 RCU 相关操作。
- `SYSCALL_WORK_*` 和 `_TIF_*` 标志位：用于标识待处理的工作类型（如 trace、seccomp、信号、调度等）。

## 关键实现

### 系统调用入口处理流程（`syscall_trace_enter`）

1. **Syscall User Dispatch 优先处理**：若设置了 `SYSCALL_WORK_SYSCALL_USER_DISPATCH`，调用 `syscall_user_dispatch()`，若返回 true 则直接终止系统调用（返回 `-1`），因为此时 ABI 可能无效。
2. **Ptrace 跟踪**：若设置了 `SYSCALL_WORK_SYSCALL_TRACE` 或 `SYSCALL_WORK_SYSCALL_EMU`，调用 `ptrace_report_syscall_entry()`。若 tracer 修改了行为或启用了 `SYSCALL_EMU`，则终止系统调用。
3. **Seccomp 安全检查**：在 ptrace 之后执行，以捕获 tracer 可能引入的变更。调用 `__secure_computing()`，若返回 `-1` 则拒绝系统调用。
4. **重新获取系统调用号**：上述步骤可能修改了系统调用号，需重新通过 `syscall_get_nr()` 获取。
5. **Tracepoint 触发**：若启用 `SYSCALL_WORK_SYSCALL_TRACEPOINT`，触发 `trace_sys_enter`，并再次重新获取系统调用号（因 BPF 或 kprobe 可能修改）。
6. **审计日志**：调用 `syscall_enter_audit()` 记录审计事件。
7. **返回最终系统调用号或错误码**。

### 返回用户空间前的工作循环（`exit_to_user_mode_loop`）

- 使用 `while (ti_work & EXIT_TO_USER_MODE_WORK)` 循环处理所有待办工作，确保在返回用户态前完成：
  - 调度（`_TIF_NEED_RESCHED`）
  - Uprobe 通知（`_TIF_UPROBE`）
  - Livepatch 状态更新（`_TIF_PATCH_PENDING`）
  - 信号处理（`_TIF_SIGPENDING | _TIF_NOTIFY_SIGNAL`）
  - 用户态恢复工作（`_TIF_NOTIFY_RESUME`）
  - 架构特定工作（`arch_exit_to_user_mode_work`）
- 每次循环启用中断（`local_irq_enable_exit_to_user`），处理完后再关闭中断并重新读取线程标志（`read_thread_flags()`），以应对处理过程中新产生的工作项。
- 最后调用 `tick_nohz_user_enter_prepare()` 处理 NO_HZ 模式下的 tick 准备。

### 中断入口/出口的 RCU 与上下文管理

- **从中断进入用户态**：调用 `enter_from_user_mode()`，启用中断。
- **从内核态中断入口**：
  - 若当前是 idle 任务且非 `TINY_RCU`，无条件调用 `ct_irq_enter()` 以确保 RCU 状态一致（避免嵌套中断导致 grace period 错误结束）。
  - 否则调用 `rcu_irq_enter_check_tick()`。
- 所有路径均正确处理 `lockdep`、`KMSAN`（解除寄存器毒化）和 `trace_hardirqs_off` 的顺序，确保调试和安全工具正常工作。

### 条件调度支持（Preemption）

- `raw_irqentry_exit_cond_resched()` 在中断退出且 `preempt_count() == 0` 时检查是否需要调度。
- 支持动态抢占（`CONFIG_PREEMPT_DYNAMIC`），通过 `static_call` 或 `static_key` 实现运行时切换，避免编译时硬编码。

## 依赖关系

### 头文件依赖
- `<linux/context_tracking.h>`：上下文跟踪（用户/内核态切换）
- `<linux/resume_user_mode.h>`：用户态恢复工作
- `<linux/seccomp.h>`（隐式通过 `__secure_computing`）：系统调用过滤
- `<linux/audit.h>`：审计子系统
- `<linux/ptrace.h>`（隐式）：ptrace 跟踪
- `<linux/livepatch.h>`：内核热补丁
- `<linux/uprobes.h>`（隐式）：用户态探针
- `<linux/rcupdate.h>`：RCU 机制
- `<linux/kmsan.h>`：Kernel Memory Sanitizer 支持
- `<trace/events/syscalls.h>`：系统调用跟踪点

### 架构依赖
- 依赖架构特定实现：
  - `syscall_get_arguments()` / `syscall_get_nr()` / `syscall_get_return_value()`
  - `user_mode()` / `regs_irqs_disabled()`
  - `arch_do_signal_or_restart()`（弱符号，默认空实现）
  - `arch_exit_to_user_mode_work()`

### 子系统交互
- **RCU**：管理中断和用户态切换时的宽限期
- **Scheduler**：处理 `need_resched()` 和 `schedule()`
- **Security**：seccomp、audit
- **Tracing**：ftrace、kprobe、uprobe、BPF
- **Livepatch**：动态补丁状态更新

## 使用场景

1. **系统调用入口路径**：  
   当用户程序执行 `syscall` 指令（或其他系统调用机制）进入内核时，架构代码调用 `syscall_trace_enter()` 执行通用预处理。

2. **系统调用出口路径**：  
   系统调用返回前，若存在待处理工作（如审计、tracepoint），调用 `syscall_exit_work()`。

3. **中断处理返回用户空间**：  
   中断处理完成后，若返回用户态，调用 `irqentry_exit_to_user_mode()`，进而触发 `exit_to_user_mode_loop()` 处理所有 pending work。

4. **中断嵌套与 idle 任务处理**：  
   在 idle 任务中发生中断时，确保 RCU 正确进入 IRQ 上下文，防止 grace period 错误终止。

5. **动态抢占支持**：  
   在支持动态抢占的系统中，中断退出时根据运行时配置决定是否执行条件调度。

6. **调试与安全工具集成**：  
   为 KMSAN、Lockdep、ftrace、audit、seccomp 等子系统提供统一的入口/出口钩子，确保工具链在系统调用和中断路径上正常工作。