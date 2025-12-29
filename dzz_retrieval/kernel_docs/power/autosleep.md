# power\autosleep.c

> 自动生成时间: 2025-10-25 15:18:31
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `power\autosleep.c`

---

# `kernel/power/autosleep.c` 技术文档

## 1. 文件概述

`autosleep.c` 实现了 Linux 内核中的 **自动睡眠（autosleep）** 功能，属于“机会性睡眠”（Opportunistic sleep）机制。该机制在系统空闲且无活跃唤醒源（wakeup source）时，自动将系统转入指定的低功耗状态（如 suspend 或 hibernate）。此功能通常通过用户空间接口（如 `/sys/power/autosleep`）控制，用于在嵌入式设备或移动系统中实现智能电源管理。

## 2. 核心功能

### 主要全局变量
- `autosleep_state`：当前自动睡眠目标状态（`suspend_state_t` 类型），`PM_SUSPEND_ON` 表示禁用自动睡眠。
- `autosleep_wq`：专用于自动睡眠的有序工作队列（`workqueue_struct`）。
- `autosleep_lock`：保护 `autosleep_state` 和相关操作的互斥锁。
- `autosleep_ws`：用于防止在状态切换过程中系统意外休眠的唤醒源（`wakeup_source`）。

### 主要函数
- `try_to_suspend(struct work_struct *work)`：核心工作函数，尝试进入睡眠状态。
- `queue_up_suspend_work(void)`：在启用自动睡眠时调度 `try_to_suspend` 工作。
- `pm_autosleep_state(void)`：返回当前自动睡眠状态。
- `pm_autosleep_lock(void)` / `pm_autosleep_unlock(void)`：提供对 `autosleep_lock` 的可中断加锁接口。
- `pm_autosleep_set_state(suspend_state_t state)`：设置自动睡眠目标状态，并触发相应行为。
- `pm_autosleep_init(void)`：模块初始化函数，注册唤醒源并创建工作队列。

## 3. 关键实现

### 自动睡眠触发机制
- 当 `autosleep_state` 被设为非 `PM_SUSPEND_ON` 状态时，系统会调用 `queue_up_suspend_work()`，将 `try_to_suspend` 工作加入 `autosleep_wq`。
- `try_to_suspend` 函数首先通过 `pm_get_wakeup_count()` 获取当前唤醒计数（`initial_count`），确保在检查期间无新唤醒事件。
- 若系统处于 `SYSTEM_RUNNING` 状态且唤醒计数未变，则根据 `autosleep_state` 的值调用 `pm_suspend()` 或 `hibernate()`。
- 唤醒后再次获取唤醒计数（`final_count`）。若计数未变（即无明确唤醒源），则休眠 0.5 秒以避免频繁休眠/唤醒的“抖动”（tight loop）。

### 死锁预防
- 注释明确指出：**只有在有活跃唤醒源时才能安全地使用 `mutex_lock(&autosleep_lock)`**，否则可能与 `try_to_suspend()` 中的冻结进程操作死锁。
- 因此，对外提供的加锁接口为 `pm_autosleep_lock()`，使用 `mutex_lock_interruptible()`，可在进程冻结时中断返回。

### 唤醒源管理
- 在设置新状态前，通过 `__pm_stay_awake(autosleep_ws)` 激活内部唤醒源，防止在状态切换过程中系统意外进入睡眠。
- 设置完成后调用 `__pm_relax(autosleep_ws)` 释放该唤醒源。
- 同时通过 `pm_wakep_autosleep_enabled()` 通知 wakeup source 子系统自动睡眠是否启用，影响 wakeup count 的行为。

### 初始化
- `pm_autosleep_init()` 在内核启动时注册名为 `"autosleep"` 的唤醒源，并创建同名的有序工作队列，确保 `try_to_suspend` 工作串行执行。

## 4. 依赖关系

- **`<linux/pm_wakeup.h>`**：提供 wakeup source 和 wakeup count 相关 API（如 `pm_get_wakeup_count`, `__pm_stay_awake`）。
- **`power.h`**：内核电源管理内部头文件，定义 `suspend_state_t`、`pm_suspend()`、`hibernate()` 等接口。
- **`<linux/workqueue.h>`**（隐式）：通过 `DECLARE_WORK` 和 `alloc_ordered_workqueue` 使用工作队列机制。
- **`CONFIG_HIBERNATION`**：若未配置休眠支持，则禁止设置 `>= PM_SUSPEND_MAX` 的状态。

## 5. 使用场景

- **用户空间控制**：通过写入 `/sys/power/autosleep`（如 `"mem"`、`"disk"` 或 `"off"`）触发 `pm_autosleep_set_state()`，启用或禁用自动睡眠。
- **系统空闲管理**：在无用户交互、无网络活动、无后台任务等场景下，系统自动进入低功耗状态以节省电量。
- **嵌入式/移动设备**：常用于 Android 或 IoT 设备，在屏幕关闭后自动 suspend。
- **避免频繁唤醒**：通过 `schedule_timeout_uninterruptible(HZ / 2)` 防止因硬件误触发导致的休眠-唤醒震荡。