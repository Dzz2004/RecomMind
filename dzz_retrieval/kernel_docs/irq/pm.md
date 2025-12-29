# irq\pm.c

> 自动生成时间: 2025-10-25 14:05:54
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\pm.c`

---

# `irq/pm.c` 技术文档

## 1. 文件概述

`irq/pm.c` 是 Linux 内核中断子系统中与电源管理（Power Management, PM）紧密相关的模块。该文件实现了在系统挂起（suspend）和恢复（resume）过程中对中断的特殊处理逻辑，包括：

- 在系统挂起期间禁用非唤醒中断；
- 识别并配置可作为唤醒源的中断；
- 在系统恢复阶段正确地重新启用中断；
- 支持早期恢复（early resume）和强制恢复（force resume）等特殊中断行为。

其核心目标是在保证系统低功耗状态的同时，确保指定的中断能够唤醒系统，并在恢复后正确还原中断状态。

## 2. 核心功能

### 主要函数

| 函数名 | 功能描述 |
|--------|---------|
| `irq_pm_check_wakeup()` | 检查中断是否为已武装的唤醒源，若是则执行挂起处理并通知 PM 子系统发生唤醒事件 |
| `irq_pm_install_action()` | 在注册中断处理函数时，更新描述符中与电源管理相关的计数器（如 `no_suspend_depth`、`force_resume_depth` 等） |
| `irq_pm_remove_action()` | 在注销中断处理函数时，相应减少电源管理相关计数器 |
| `suspend_device_irq()` | 对单个中断描述符执行挂起操作：禁用中断、设置 `IRQS_SUSPENDED` 状态，或为唤醒中断做特殊准备 |
| `suspend_device_irqs()` | 遍历所有中断，调用 `suspend_device_irq()` 执行系统级中断挂起 |
| `resume_irq()` | 恢复单个中断的状态，包括清除挂起标志、还原启用/禁用状态 |
| `resume_irqs()` | 遍历中断并根据 `want_early` 参数决定是否仅恢复带 `IRQF_EARLY_RESUME` 标志的中断 |
| `rearm_wake_irq()` | 重新武装一个唤醒中断（通常在唤醒事件被处理后调用，以便再次唤醒） |
| `irq_pm_syscore_resume()` | 作为 syscore 回调，在系统早期恢复阶段启用 `IRQF_EARLY_RESUME` 中断 |
| `resume_device_irqs()` | 恢复所有非早期中断（即未设置 `IRQF_EARLY_RESUME` 的中断） |

### 关键数据结构字段（位于 `struct irq_desc`）

- `nr_actions`：当前注册的中断处理函数数量
- `no_suspend_depth`：标记为 `IRQF_NO_SUSPEND` 的处理函数数量（不可挂起）
- `cond_suspend_depth`：标记为 `IRQF_COND_SUSPEND` 的处理函数数量
- `force_resume_depth`：标记为 `IRQF_FORCE_RESUME` 的处理函数数量（强制恢复）
- `istate`：中断状态位，包含 `IRQS_SUSPENDED` 和 `IRQS_PENDING` 等标志

### 全局变量

- `irq_pm_syscore_ops`：注册到 syscore 框架的恢复操作集，用于早期中断恢复

## 3. 关键实现

### 中断挂起逻辑（`suspend_device_irqs`）

1. 遍历所有中断描述符；
2. 跳过嵌套线程中断（`IRQF_ONESHOT` 相关）；
3. 对每个中断加锁后调用 `suspend_device_irq()`；
4. 若该函数返回 `true`（通常是因为是唤醒中断），则调用 `synchronize_irq()` 确保状态变更全局可见。

### 唤醒中断处理

- 若中断设置了 `IRQD_WAKEUP_SET`（通过 `irq_set_irq_wake()`），则：
  - 设置 `IRQD_WAKEUP_ARMED` 标志；
  - 若中断当前被禁用且 irqchip 支持 `IRQCHIP_ENABLE_WAKEUP_ON_SUSPEND`，则临时启用中断（设置 `IRQD_IRQ_ENABLED_ON_SUSPEND`）；
  - 返回 `true` 触发 `synchronize_irq()`，确保唤醒路径安全。

### 中断恢复策略

- **早期恢复**：通过 `syscore_ops` 在系统恢复早期阶段启用带 `IRQF_EARLY_RESUME` 的中断（如控制台、调试串口）；
- **常规恢复**：在 `resume_device_irqs()` 中恢复其余中断；
- **强制恢复**：即使中断未被挂起（如因 `IRQF_NO_SUSPEND`），若存在 `IRQF_FORCE_RESUME` 处理函数，仍会模拟“挂起-恢复”流程以确保状态一致。

### 状态一致性保障

- 使用 `desc->lock` 保护所有状态变更；
- 通过 `synchronize_irq()` 确保 `IRQD_WAKEUP_ARMED` 对中断处理路径可见；
- 利用 `istate` 中的 `IRQS_SUSPENDED` 标志跟踪中断是否处于挂起状态。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/irq.h>`、`<linux/interrupt.h>`：中断核心 API
  - `<linux/suspend.h>`：电源管理挂起/恢复接口
  - `<linux/syscore_ops.h>`：系统核心操作注册机制
  - `"internals.h"`：中断子系统内部实现细节

- **与其他子系统交互**：
  - **PM Core**：通过 `pm_system_irq_wakeup()` 通知唤醒事件；
  - **IRQ Core**：依赖 `__enable_irq()`、`__disable_irq()`、`mask_irq()` 等底层操作；
  - **Syscore Framework**：注册早期恢复回调，确保关键中断在设备驱动恢复前可用。

- **编译依赖**：作为 `GENERIC_IRQ_PM` 功能的一部分，通常在支持通用中断和电源管理的架构中启用。

## 5. 使用场景

1. **系统挂起（Suspend-to-RAM / Hibernate）**：
   - 调用 `suspend_device_irqs()` 禁用非唤醒中断；
   - 唤醒中断保持可触发状态，触发时调用 `irq_pm_check_wakeup()` 通知 PM 子系统。

2. **系统恢复（Resume）**：
   - 早期阶段：通过 `syscore_ops` 恢复 `IRQF_EARLY_RESUME` 中断（如串口、定时器）；
   - 后期阶段：调用 `resume_device_irqs()` 恢复其余中断。

3. **设备驱动注册/注销中断**：
   - 驱动使用 `IRQF_NO_SUSPEND`、`IRQF_FORCE_RESUME` 等标志时，自动更新中断描述符的电源管理计数器。

4. **重复唤醒支持**：
   - 在处理完一次唤醒事件后，驱动可调用 `rearm_wake_irq()` 重新武装中断，使其能再次唤醒系统。

该模块是 Linux 电源管理与中断子系统协同工作的关键桥梁，确保系统在低功耗状态下仍能响应关键事件，并在恢复后维持中断状态的一致性。