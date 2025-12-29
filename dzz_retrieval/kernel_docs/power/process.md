# power\process.c

> 自动生成时间: 2025-10-25 15:23:48
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `power\process.c`

---

# `power/process.c` 技术文档

## 1. 文件概述

`power/process.c` 是 Linux 内核电源管理子系统中的关键文件，负责在系统挂起（suspend）过程中冻结（freeze）和解冻（thaw）用户空间进程及可冻结的内核线程。该机制确保在系统进入低功耗状态前，所有可冻结任务已暂停执行，避免在挂起期间发生不一致状态或资源竞争；在恢复时再安全地唤醒这些任务。此功能最初源自 swsusp（Software Suspend）项目，现已成为通用冻结框架的一部分。

## 2. 核心功能

### 全局变量
- `freeze_timeout_msecs`：冻结任务的超时时间（默认 20 秒），标记为 `__read_mostly` 以优化缓存。

### 主要函数
- `try_to_freeze_tasks(bool user_only)`：尝试冻结指定范围内的任务（仅用户进程或包括内核线程）。
- `freeze_processes(void)`：冻结所有用户空间进程，并禁用用户模式辅助程序（usermodehelper）和 OOM killer。
- `freeze_kernel_threads(void)`：冻结所有可冻结的内核线程（在用户进程已冻结后调用）。
- `thaw_processes(void)`：解冻所有任务（包括用户进程和内核线程），并重新启用 OOM killer 和 usermodehelper。
- `thaw_kernel_threads(void)`：仅解冻内核线程（用于错误恢复或分阶段解冻）。

### 辅助机制
- 使用 `PF_SUSPEND_TASK` 标志标记当前执行冻结操作的进程，防止其自身被冻结。
- 通过 `freezer_active` 静态分支优化冻结状态的判断性能。
- 集成 tracepoint（`trace_suspend_resume`）用于跟踪冻结/解冻事件。

## 3. 关键实现

### 冻结流程 (`try_to_freeze_tasks`)
1. **初始化**：记录开始时间，设置超时阈值（基于 `freeze_timeout_msecs`）。
2. **工作队列冻结**：若 `user_only=false`，调用 `freeze_workqueues_begin()` 开始冻结工作队列。
3. **遍历任务**：通过 `for_each_process_thread` 遍历所有进程和线程，对每个非当前任务调用 `freeze_task()` 发送冻结信号。
4. **重试与退避**：若仍有任务未冻结且未超时，使用指数退避策略（1ms → 2ms → 4ms → 8ms）进行短暂休眠后重试。
5. **中断处理**：若在冻结过程中检测到唤醒事件（`pm_wakeup_pending()`），立即中止冻结。
6. **错误诊断**：冻结失败时，打印未冻结任务列表（通过 `sched_show_task`）和繁忙的工作队列信息（`show_freezable_workqueues`）。

### 用户进程冻结 (`freeze_processes`)
- 禁用 `usermodehelper`（防止挂起期间加载内核模块）。
- 设置当前任务 `PF_SUSPEND_TASK` 标志以豁免自身。
- 激活全局冻结状态（`pm_freezing = true`）。
- 冻结用户进程后，禁用 OOM killer（防止其在冻结期间杀死任务导致状态不一致）。
- 若冻结失败，自动调用 `thaw_processes` 回滚状态。

### 内核线程冻结 (`freeze_kernel_threads`)
- 设置 `pm_nosig_freezing = true` 表示进入无信号冻结阶段（仅影响内核线程）。
- 调用 `try_to_freeze_tasks(false)` 冻结剩余可冻结任务（包括内核线程和工作队列）。
- 失败时仅解冻内核线程（`thaw_kernel_threads`），由调用者负责后续用户进程解冻。

### 解冻流程 (`thaw_processes`)
- 清除全局冻结标志，重新启用 OOM killer 和 usermodehelper。
- 遍历所有任务，调用 `__thaw_task` 清除冻结状态。
- 显式调用 `schedule()` 触发调度，确保解冻任务能及时运行。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/freezer.h>`：提供 `freeze_task`、`__thaw_task` 等冻结核心接口。
  - `<linux/suspend.h>`：定义 `pm_freezing`、`pm_wakeup_pending` 等电源管理状态变量。
  - `<linux/oom.h>`：提供 OOM killer 启用/禁用接口。
  - `<linux/workqueue.h>`：提供工作队列冻结/解冻支持。
  - `<trace/events/power.h>`：提供 suspend/resume 跟踪点。
- **模块交互**：
  - 与 **OOM killer** 协同：冻结期间禁用 OOM，防止干扰冻结任务。
  - 与 **usermodehelper** 协同：冻结期间禁用用户模式辅助程序，避免挂起时执行外部命令。
  - 与 **工作队列子系统** 协同：通过 `freeze_workqueues_begin`/`thaw_workqueues` 管理工作项执行。
  - 与 **调度器** 协同：通过 `sched_show_task` 诊断冻结失败任务。

## 5. 使用场景

- **系统挂起（Suspend-to-RAM/Disk）**：
  1. `freeze_processes()` 冻结用户空间进程。
  2. `freeze_kernel_threads()` 冻结内核线程。
  3. 系统进入低功耗状态。
  4. 唤醒后，`thaw_processes()` 解冻所有任务。
- **休眠（Hibernation）**：在保存内存镜像前冻结所有任务，确保系统状态一致性。
- **错误恢复**：若冻结过程因超时或唤醒事件失败，自动回滚解冻状态，保证系统可用性。
- **调试支持**：通过 `pm_debug_messages_on` 控制冻结失败时的详细任务信息输出，辅助诊断冻结问题。