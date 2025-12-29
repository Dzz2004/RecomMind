# signal.c

> 自动生成时间: 2025-10-25 16:24:03
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `signal.c`

---

# signal.c 技术文档

## 1. 文件概述

`signal.c` 是 Linux 内核中信号子系统的核心实现文件，负责管理进程间信号的发送、接收、排队、处理以及相关状态的维护。该文件实现了 POSIX 信号语义，包括标准信号和实时信号（通过 sigqueue），并处理信号的阻塞、忽略、默认行为及用户自定义处理函数的调用逻辑。它还集成了对 ptrace 调试、作业控制（job control）、冻结（freezer）和 cgroup 等子系统的支持。

## 2. 核心功能

### 主要数据结构
- `sigqueue_cachep`：用于分配 `sigqueue` 结构的 slab 缓存，支持可靠信号排队。
- `task_struct::pending`：每个任务私有的挂起信号队列。
- `signal_struct::shared_pending`：线程组共享的挂起信号队列。
- `task_struct::blocked` / `real_blocked`：信号阻塞掩码。
- `task_struct::jobctl`：作业控制相关状态位（如停止、陷阱等）。

### 主要函数
- `sig_handler()`：获取指定信号的处理函数指针。
- `sig_handler_ignored()`：判断信号是否被显式或隐式忽略。
- `sig_task_ignored()` / `sig_ignored()`：判断任务是否忽略某信号（考虑 init、kthread、ptrace 等特殊情况）。
- `has_pending_signals()`：检查在给定阻塞掩码下是否存在可投递的挂起信号。
- `recalc_sigpending_tsk()` / `recalc_sigpending()` / `recalc_sigpending_and_wake()`：重新计算并设置 `TIF_SIGPENDING` 线程标志。
- `next_signal()`：从挂起信号中选择下一个应被处理的信号，优先处理同步信号（如 SIGSEGV、SIGILL 等）。
- `task_set_jobctl_pending()`：设置任务的作业控制挂起状态（如停止请求）。
- `task_clear_jobctl_trapping()`：清除作业控制陷阱状态并唤醒跟踪者（ptracer）。
- `print_dropped_signal()`：当日志开启且达到 `RLIMIT_SIGPENDING` 限制时，记录被丢弃的信号。

## 3. 关键实现

### 信号忽略逻辑
信号是否被忽略不仅取决于处理函数是否为 `SIG_IGN` 或默认且内核定义为可忽略（`sig_kernel_ignore()`），还需考虑：
- 全局 init 进程不能接收 `SIGKILL`/`SIGSTOP`。
- `SIGNAL_UNKILLABLE` 任务对默认处理的内核信号有特殊豁免。
- 内核线程（`PF_KTHREAD`）仅响应强制（`force=true`）的内核信号。
- 若任务被 ptrace 跟踪，除 `SIGKILL` 外，即使信号被忽略也需通知调试器。

### 挂起信号检测优化
`has_pending_signals()` 使用位运算高效检查 `signal & ~blocked` 是否非零，并针对 `_NSIG_WORDS` 的常见值（1、2、4）进行展开优化，避免循环开销。

### 信号选择策略
`next_signal()` 优先处理同步信号（定义在 `SYNCHRONOUS_MASK` 中），确保如段错误、非法指令等异常能被及时响应，符合 POSIX 对同步信号“立即投递”的要求。

### TIF_SIGPENDING 标志管理
- `recalc_sigpending_tsk()` 综合检查私有/共享挂起信号、作业控制状态和 cgroup 冻结状态，决定是否设置 `TIF_SIGPENDING`。
- 为避免竞态，**不清除**该标志，仅由明确知道安全的调用者（如 `recalc_sigpending()`）在适当上下文中清除。
- `recalc_sigpending_and_wake()` 在设置标志后主动唤醒任务，确保其能及时处理信号。

### 作业控制集成
通过 `jobctl` 字段和 `JOBCTL_*` 位掩码，支持 ptrace 和作业控制的复杂状态机（如停止、陷阱、信号消费），并在 `siglock` 保护下安全更新。

## 4. 依赖关系

- **调度子系统**：依赖 `task_struct`、`thread_info` 标志（如 `TIF_SIGPENDING`）、`PF_EXITING` 等。
- **内存管理**：使用 slab 分配器（`kmem_cache`）管理 `sigqueue`。
- **进程管理**：与 `fork`/`exec`/`exit` 流程交互（如 `calculate_sigpending` 在 fork 后调用）。
- **ptrace**：通过 `ptrace` 字段和 `JOBCTL_TRAPPING` 支持调试器信号拦截。
- **cgroup/freezer**：检查 `cgroup_task_frozen()` 状态影响信号挂起判断。
- **安全模块**：通过 `security_task_kill()` 等钩子（虽未在片段中体现，但完整文件包含）。
- **tracepoint**：定义 `trace/events/signal.h` 中的跟踪点用于调试。
- **架构相关代码**：依赖 `asm/siginfo.h`、`uaccess.h` 等处理用户空间信号帧。

## 5. 使用场景

- **系统调用处理**：`kill()`、`tkill()`、`rt_sigqueueinfo()` 等信号发送系统调用最终调用本文件逻辑。
- **异常处理**：CPU 异常（如页错误、除零）触发同步信号（SIGSEGV、SIGFPE），由本文件选择并准备投递。
- **进程生命周期管理**：在 `do_exit()`、`flush_old_exec()` 等路径中清理或重置信号状态。
- **调试器支持**：ptrace 在注入信号或单步执行时依赖作业控制状态和信号忽略逻辑。
- **资源限制**：当信号队列达到 `RLIMIT_SIGPENDING` 限制时，调用 `print_dropped_signal()` 记录丢弃事件。
- **冻结/恢复**：cgroup freezer 或 suspend 流程通过 `cgroup_task_frozen()` 影响信号挂起状态，确保任务在冻结期间不处理信号。