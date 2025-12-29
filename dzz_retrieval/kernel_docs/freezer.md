# freezer.c

> 自动生成时间: 2025-10-25 13:30:57
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `freezer.c`

---

# freezer.c 技术文档

## 文件概述

`freezer.c` 是 Linux 内核中实现任务冻结（freezing）机制的核心文件，用于在系统挂起（suspend）、休眠（hibernation）或 cgroup freezer 控制等场景下，将用户空间进程和部分内核线程临时挂起（冻结），使其进入 `TASK_FROZEN` 状态，从而确保系统状态一致性。该机制允许内核在不终止进程的情况下暂停其执行，并在系统恢复时安全地唤醒它们。

## 核心功能

### 全局变量
- `freezer_active`：静态键（static key），表示当前是否有冻结条件生效，用于快速路径判断。
- `pm_freezing`：布尔值，表示电源管理（PM）冻结是否生效（受 `system_transition_mutex` 保护）。
- `pm_nosig_freezing`：布尔值，表示是否启用无信号冻结模式（通常用于 cgroup freezer）。
- `freezer_lock`：自旋锁，保护冻结/解冻状态转换的原子性。

### 主要函数
- `freezing_slow_path(struct task_struct *p)`：冻结慢路径判断函数，决定任务是否应被冻结。
- `frozen(struct task_struct *p)`：检查任务是否已处于冻结状态。
- `__refrigerator(bool check_kthr_stop)`：任务进入“冰箱”（冻结等待循环）的主函数。
- `__set_task_frozen(struct task_struct *p, void *arg)`：将可冻结任务的状态切换为 `TASK_FROZEN`。
- `__freeze_task(struct task_struct *p)`：尝试冻结指定任务。
- `freeze_task(struct task_struct *p)`：向任务发送冻结请求，必要时唤醒以进入冻结状态。
- `__restore_freezer_state(struct task_struct *p, void *arg)`：恢复任务冻结前的状态。
- `__thaw_task(struct task_struct *p)`：解冻指定任务。
- `set_freezable(void)`：将当前任务标记为可冻结，并尝试立即冻结。

## 关键实现

### 冻结判断逻辑
`freezing_slow_path()` 是冻结判断的核心逻辑：
- 排除设置了 `PF_NOFREEZE`（不可冻结）或 `PF_SUSPEND_TASK`（挂起专用任务）的进程。
- 排除正在处理内存回收（`TIF_MEMDIE`）的任务。
- 若 `pm_nosig_freezing` 为真（如 cgroup freezer 场景）或任务属于冻结 cgroup，则应冻结。
- 若 `pm_freezing` 为真且任务不是内核线程（`PF_KTHREAD`），则应冻结。

### 冻结状态管理
- 任务状态通过 `task_struct->__state` 字段管理，冻结状态为 `TASK_FROZEN`。
- `saved_state` 字段用于保存冻结前的原始状态，以便解冻时恢复。
- 使用 `WRITE_ONCE()` 和 `READ_ONCE()` 确保状态读写的原子性和内存序。

### 冻结唤醒机制
- 用户空间任务通过 `fake_signal_wake_up()` 发送伪信号（调用 `signal_wake_up()`）促使其进入冻结。
- 内核线程通过 `wake_up_state(p, TASK_NORMAL)` 唤醒，使其在调度循环中检测冻结条件并进入 `__refrigerator()`。

### 冻结安全检查
- 在 `__set_task_frozen()` 中，通过 `WARN_ON_ONCE()` 检查：
  - 只有 `TASK_NORMAL` 状态的任务可被标记为 `TASK_FREEZABLE`。
  - 若启用了 `CONFIG_LOCKDEP`，则警告在持有锁的情况下冻结任务（可能导致死锁）。

### 冻结/解冻原子性
- 所有状态转换均在 `freezer_lock` 保护下进行，确保并发安全。
- `__thaw_task()` 在解冻时先尝试恢复原始状态，若失败（如任务已在运行）则显式唤醒 `TASK_FROZEN` 状态的任务。

## 依赖关系

- **头文件依赖**：
  - `<linux/freezer.h>`：提供冻结相关的宏和函数声明。
  - `<linux/suspend.h>`：与电源管理挂起机制集成。
  - `<linux/cgroup.h>`（隐式）：通过 `cgroup_freezing()` 与 cgroup freezer 子系统交互。
  - `<linux/kthread.h>`：处理内核线程的特殊冻结逻辑（如 `kthread_should_stop()`）。
- **内核子系统**：
  - **电源管理（PM）**：系统挂起/休眠时触发全局冻结。
  - **cgroup freezer**：通过 cgroup 接口对任务组进行冻结控制。
  - **调度器（Scheduler）**：依赖 `task_call_func()`、`wake_up_state()` 等调度接口操作任务状态。
  - **信号子系统**：通过 `signal_wake_up()` 唤醒用户空间任务。

## 使用场景

1. **系统挂起/休眠**：
   - 在进入 suspend/hibernation 前，内核设置 `pm_freezing = true` 并冻结所有用户空间进程，确保系统状态一致。
   - 恢复时调用 `__thaw_task()` 解冻任务。

2. **cgroup freezer 控制**：
   - 用户通过写入 cgroup 的 `freezer.state` 文件冻结/解冻任务组。
   - 触发 `pm_nosig_freezing = true`，使用无信号方式冻结任务。

3. **内核线程协作冻结**：
   - 可冻结的内核线程需定期调用 `try_to_freeze()` 或 `set_freezable()`。
   - 在 `__refrigerator()` 中循环等待冻结条件解除。

4. **内存回收（OOM）保护**：
   - 正在处理 OOM 的任务（`TIF_MEMDIE`）被排除在冻结之外，避免干扰关键内存回收流程。

5. **驱动/子系统集成**：
   - 驱动在 suspend 回调中可依赖冻结机制确保用户空间无活动 I/O。
   - 文件系统、网络栈等子系统在冻结期间暂停用户请求处理。