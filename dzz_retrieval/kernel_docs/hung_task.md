# hung_task.c

> 自动生成时间: 2025-10-25 13:44:48
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `hung_task.c`

---

# hung_task.c 技术文档

## 1. 文件概述

`hung_task.c` 是 Linux 内核中用于检测“挂起任务”（Hung Task）的核心模块。该模块通过一个名为 `khungtaskd` 的内核线程周期性地扫描系统中处于不可中断睡眠状态（`TASK_UNINTERRUPTIBLE`，即 D 状态）且长时间未被调度的任务。若任务挂起时间超过设定阈值（默认 120 秒），内核将打印警告信息、任务堆栈、锁信息，甚至在配置启用时触发系统 panic，以帮助开发者诊断系统卡死问题。

## 2. 核心功能

### 主要全局变量（sysctl 可调参数）

- `sysctl_hung_task_timeout_secs`：检测挂起任务的超时阈值（秒），0 表示禁用检测。
- `sysctl_hung_task_check_count`：每次扫描最多检查的任务数量，默认为 `PID_MAX_LIMIT`。
- `sysctl_hung_task_warnings`：最多打印警告信息的次数（默认 10 次），之后抑制输出。
- `sysctl_hung_task_panic`：检测到挂起任务时是否触发 panic。
- `sysctl_hung_task_all_cpu_backtrace`（仅 SMP）：是否在检测到挂起任务时打印所有 CPU 的 backtrace。
- `sysctl_hung_task_check_interval_secs`：检查间隔（秒），0 表示使用 `timeout_secs` 作为间隔。
- `sysctl_hung_task_detect_count`：自系统启动以来检测到的挂起任务总数。

### 主要函数

- `check_hung_task(struct task_struct *t, unsigned long timeout)`  
  检查单个任务是否挂起超时，若满足条件则打印诊断信息。

- `check_hung_uninterruptible_tasks(unsigned long timeout)`  
  遍历所有进程线程，调用 `check_hung_task` 检测挂起任务，并处理锁和 backtrace 输出。

- `rcu_lock_break(struct task_struct *g, struct task_struct *t)`  
  在长时间 RCU 读临界区内主动释放 RCU 锁并调度，避免延长 RCU grace period。

- `debug_show_blocker(struct task_struct *task)`（条件编译）  
  在 `CONFIG_DETECT_HUNG_TASK_BLOCKER` 启用时，尝试识别并打印阻塞当前挂起任务的锁持有者。

- `hung_task_panic(struct notifier_block *this, ...)`  
  panic 通知回调，用于标记系统已 panic，避免重复报告。

## 3. 关键实现

### 挂起任务判定逻辑

任务被判定为“挂起”需同时满足以下条件：
- 处于 `TASK_UNINTERRUPTIBLE` 状态；
- **不**包含 `TASK_WAKEKILL`（即可被致命信号唤醒）；
- **不**包含 `TASK_NOLOAD`（非负载任务，如 idle）；
- **未被冻结**（非 suspend/freeze 场景）；
- 自上次上下文切换以来的时间超过 `timeout * HZ`；
- 上下文切换计数（`nvcsw + nivcsw`）非零（排除刚创建未调度的任务）。

### RCU 与可抢占性控制

为避免在遍历所有任务时长时间持有 RCU 读锁导致 RCU grace period 过长，代码引入 `HUNG_TASK_LOCK_BREAK = HZ/10`（约 100ms）的间隔。每经过该时间，调用 `rcu_lock_break()` 主动释放 RCU 锁、执行 `cond_resched()` 让出 CPU，再重新获取 RCU 锁继续扫描，保证系统响应性。

### 诊断信息增强

- **锁信息**：若 `hung_task_show_lock` 被置位（如触发 panic 或首次警告），调用 `debug_show_all_locks()` 打印系统锁依赖图。
- **阻塞者识别**：在 `CONFIG_DETECT_HUNG_TASK_BLOCKER` 下，通过 `task->blocker` 字段尝试解析 mutex 或 semaphore 的持有者，并打印其任务信息。
- **全 CPU backtrace**：若 `sysctl_hung_task_all_cpu_backtrace` 启用，则调用 `trigger_all_cpu_backtrace()` 打印所有 CPU 的调用栈。

### Panic 与抑制机制

- 若 `sysctl_hung_task_panic` 为真，则首次检测到挂起任务即触发 `panic()`。
- 警告信息最多打印 `sysctl_hung_task_warnings` 次（默认 10），之后抑制输出，避免日志刷屏。
- 系统已 panic 或标记 `TAINT_DIE` 时，直接跳过检测，防止在崩溃恢复阶段产生干扰。

## 4. 依赖关系

- **调度子系统**：依赖 `sched/` 中的 `sched_show_task()`、`for_each_process_thread()`、任务状态（`__state`）、上下文切换计数等。
- **RCU 子系统**：使用 `rcu_read_lock/unlock()` 安全遍历进程链表。
- **锁调试**：依赖 `lockdep` 和 `debug_show_all_locks()` 提供锁状态信息。
- **NMI/Watchdog**：调用 `touch_nmi_watchdog()` 防止 NMI watchdog 误报。
- **sysctl**：通过 `kernel/sysctl.c` 暴露可调参数供用户空间配置。
- **tracepoint**：使用 `trace_sched_process_hang()` 事件供 ftrace 跟踪。
- **SMP 支持**：`trigger_all_cpu_backtrace()` 仅在 `CONFIG_SMP` 下有效。

## 5. 使用场景

- **系统卡死诊断**：当系统因 I/O、硬件或驱动问题导致进程长期处于 D 状态时，自动触发警告，帮助定位问题根源。
- **生产环境监控**：运维可通过 `/proc/sys/kernel/hung_task_timeout_secs` 动态启用/禁用检测，或设置 panic 行为实现自动重启。
- **内核开发调试**：开发者可结合 `hung_task_all_cpu_backtrace` 和锁信息，分析死锁或资源竞争问题。
- **自动化测试**：在 CI/CD 测试中启用 hung task panic，可快速暴露长时间阻塞的回归问题。