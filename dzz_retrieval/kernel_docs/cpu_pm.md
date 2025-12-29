# cpu_pm.c

> 自动生成时间: 2025-10-25 12:55:54
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cpu_pm.c`

---

# cpu_pm.c 技术文档

## 1. 文件概述

`cpu_pm.c` 实现了 Linux 内核中 CPU 电源管理（CPU PM）的通知机制，用于在 CPU 或 CPU 集群进入/退出低功耗状态时通知相关驱动程序。该机制允许驱动程序在 CPU 电源状态变化前后执行必要的上下文保存与恢复操作（如 VFP 协处理器、中断控制器、本地定时器等），以确保系统在低功耗状态切换后仍能正常运行。该文件特别考虑了实时内核（PREEMPT_RT）下的锁行为，使用 `raw_spinlock_t` 保证在中断禁用上下文中安全执行。

## 2. 核心功能

### 主要数据结构
- `cpu_pm_notifier`：包含一个 `raw_notifier_head` 通知链和一个 `raw_spinlock_t` 锁，用于管理 CPU PM 事件的通知。

### 主要函数
- `cpu_pm_register_notifier(struct notifier_block *nb)`  
  注册一个 CPU PM 事件通知回调。
- `cpu_pm_unregister_notifier(struct notifier_block *nb)`  
  注销一个已注册的 CPU PM 事件通知回调。
- `cpu_pm_enter(void)`  
  通知所有监听者：当前 CPU 即将进入可能导致同电源域硬件复位的低功耗状态。
- `cpu_pm_exit(void)`  
  通知所有监听者：当前 CPU 正在退出低功耗状态。
- `cpu_cluster_pm_enter(void)`  
  通知所有监听者：整个 CPU 集群（电源域）即将进入低功耗状态。
- `cpu_cluster_pm_exit(void)`  
  通知所有监听者：整个 CPU 集群正在退出低功耗状态。

### 内部辅助函数
- `cpu_pm_notify(enum cpu_pm_event event)`  
  调用通知链，适用于单向事件（如 EXIT）。
- `cpu_pm_notify_robust(enum cpu_pm_event event_up, enum cpu_pm_event event_down)`  
  调用健壮通知链（robust notifier），在通知失败时可回滚，适用于 ENTER 类操作。

## 3. 关键实现

### 使用 raw_spinlock 而非 spinlock
由于在 PREEMPT_RT 内核中，普通 `spinlock_t` 可能导致睡眠，而 CPU PM 通知由 idle 任务在中断禁用上下文中调用，不能阻塞。因此，该模块使用 `raw_spinlock_t` 保证在任何配置下都能在原子上下文中安全执行。

### 健壮通知机制（Robust Notification）
- `cpu_pm_enter()` 和 `cpu_cluster_pm_enter()` 使用 `raw_notifier_call_chain_robust()`：
  - 先按顺序发送 `*_ENTER` 事件；
  - 若任一回调失败，则反向发送 `*_ENTER_FAILED` 事件，允许已成功执行的驱动回滚操作。
- `cpu_pm_exit()` 和 `cpu_cluster_pm_exit()` 使用普通通知链，因为退出操作通常不可逆，无需回滚。

### 中断上下文要求
所有 `cpu_pm_*` 和 `cpu_cluster_pm_*` 函数**必须在中断禁用的上下文中调用**，因为：
- 被通知的驱动可能操作不能被中断的硬件（如本地定时器、VFP 协处理器）；
- 防止在上下文保存/恢复过程中被抢占或中断，导致状态不一致。

### 系统核心电源管理集成（CONFIG_PM）
当启用 `CONFIG_PM` 时：
- 注册 `syscore_ops` 回调，在系统挂起到 RAM（suspend-to-RAM）期间自动调用 `cpu_pm_suspend()` 和 `cpu_pm_resume()`；
- `cpu_pm_suspend()` 依次调用 `cpu_pm_enter()` 和 `cpu_cluster_pm_enter()`；
- `cpu_pm_resume()` 依次调用 `cpu_cluster_pm_exit()` 和 `cpu_pm_exit()`；
- 通过 `core_initcall` 在内核初始化早期注册该机制。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/cpu_pm.h>`：定义 `cpu_pm_event` 枚举和通知函数原型；
  - `<linux/notifier.h>`：提供通知链基础设施；
  - `<linux/spinlock.h>`：提供 `raw_spinlock_t` 支持；
  - `<linux/syscore_ops.h>`：用于系统 suspend/resume 集成；
  - `<linux/rcupdate.h>`（隐式）：`rcu_read_lock/unlock` 用于安全遍历通知链。

- **内核配置依赖**：
  - `CONFIG_PM`：启用系统级 suspend/resume 集成；
  - `CONFIG_PREEMPT_RT`：影响锁的选择逻辑（虽不直接依赖，但设计考虑了其实现差异）。

- **被依赖模块**：
  - 需要保存/恢复 CPU 相关硬件上下文的驱动（如 ARM 架构的 VFP、GIC 中断控制器、arch-timer 等）会调用注册/注销接口。

## 5. 使用场景

1. **CPU 热插拔或 idle 深度睡眠**  
   当 CPU 进入 `WFI`/`WFE` 或更深度的 idle 状态（如 ARM 的 `cpuidle` 驱动）时，调用 `cpu_pm_enter()`/`cpu_pm_exit()` 通知驱动保存/恢复上下文。

2. **CPU 集群电源门控（Cluster Power Gating）**  
   在 big.LITTLE 或多簇 ARM 系统中，当整个 CPU 集群断电时，先对每个 CPU 调用 `cpu_pm_enter()`，再调用 `cpu_cluster_pm_enter()`；唤醒时顺序相反。

3. **系统挂起（Suspend-to-RAM）**  
   通过 `syscore_ops` 集成，在 `suspend` 过程中自动触发 CPU 和集群 PM 通知，确保系统 resume 后 CPU 相关硬件状态正确。

4. **实时系统（PREEMPT_RT）兼容性**  
   在 RT 内核中，确保 CPU PM 通知路径不会因锁而阻塞，维持 idle 路径的确定性。