# power\suspend.c

> 自动生成时间: 2025-10-25 15:26:21
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `power\suspend.c`

---

# `power/suspend.c` 技术文档

## 1. 文件概述

`power/suspend.c` 是 Linux 内核电源管理（Power Management, PM）子系统的核心文件之一，主要负责实现 **系统挂起（Suspend）** 功能，包括：

- **Suspend-to-RAM（挂起到内存，即 `mem` 状态）**
- **Suspend-to-idle（挂起到空闲，即 `freeze` 或 `s2idle` 状态）**
- **Standby（待机，即 `standby` 状态）**

该文件提供了挂起状态的注册、验证、进入与恢复的通用框架，并协调平台特定的挂起操作（通过 `platform_suspend_ops` 和 `platform_s2idle_ops` 接口），同时管理挂起状态的可见性（如 `/sys/power/state` 中的状态列表）。

## 2. 核心功能

### 主要全局变量

| 变量名 | 类型 | 说明 |
|--------|------|------|
| `pm_labels[]` | `const char * const[]` | 用户空间可见的挂起状态名称：`"freeze"`、`"standby"`、`"mem"` |
| `mem_sleep_labels[]` | `const char * const[]` | `/sys/power/mem_sleep` 中使用的内部状态标签：`"s2idle"`、`"shallow"`、`"deep"` |
| `mem_sleep_states[]` | `const char *[]` | 当前系统支持的 `mem_sleep` 状态列表（动态填充） |
| `pm_states[]` | `const char *[]` | 当前系统支持的 `/sys/power/state` 状态列表 |
| `mem_sleep_current` | `suspend_state_t` | 当前生效的内存挂起深度（默认为 `PM_SUSPEND_TO_IDLE`） |
| `mem_sleep_default` | `suspend_state_t` | 通过内核参数 `mem_sleep_default=` 设置的默认挂起深度 |
| `pm_suspend_target_state` | `suspend_state_t` | 当前挂起操作的目标状态（导出供其他模块使用） |
| `pm_suspend_global_flags` | `unsigned int` | 全局挂起标志位（导出） |
| `suspend_ops` | `const struct platform_suspend_ops *` | 平台提供的 Suspend-to-RAM 操作集 |
| `s2idle_ops` | `const struct platform_s2idle_ops *` | 平台提供的 Suspend-to-idle 操作集 |

### 主要函数

| 函数 | 说明 |
|------|------|
| `pm_suspend_default_s2idle()` | 判断当前默认挂起方式是否为 suspend-to-idle |
| `s2idle_set_ops()` | 注册平台特定的 s2idle 操作集 |
| `s2idle_begin()` | s2idle 流程初始化 |
| `s2idle_enter()` | 执行 suspend-to-idle 的核心逻辑：使所有 CPU 进入 idle |
| `s2idle_loop()` | s2idle 主循环，持续检查唤醒事件并进入 idle |
| `s2idle_wake()` | 唤醒正在 s2idle 中等待的 CPU（由中断或唤醒源调用） |
| `pm_states_init()` | 初始化基础挂起状态（`mem` 和 `freeze` 始终可用） |
| `suspend_set_ops()` | 注册平台 suspend 操作集，并更新支持的状态列表 |
| `suspend_valid_only_mem()` | 通用的 `.valid()` 回调，仅允许 `PM_SUSPEND_MEM` |
| `sleep_state_supported()` | 判断指定挂起状态是否被系统支持 |
| `platform_suspend_prepare*()` / `platform_resume*()` | 封装平台挂起/恢复各阶段的回调调用 |

## 3. 关键实现

### 3.1 挂起状态管理

- 系统支持三种挂起状态：
  - `PM_SUSPEND_TO_IDLE`（freeze/s2idle）：冻结进程、挂起设备、CPU 进入 idle，**不依赖平台固件**，纯软件实现。
  - `PM_SUSPEND_STANDBY`（standby/shallow）：轻量级挂起，依赖平台支持。
  - `PM_SUSPEND_MEM`（mem/deep）：挂起到内存，需平台固件（如 ACPI S3）支持。
- `pm_states[]` 控制 `/sys/power/state` 中可见的状态。
- `mem_sleep_states[]` 控制 `/sys/power/mem_sleep` 中可配置的深度，用于选择默认挂起方式。

### 3.2 Suspend-to-Idle (s2idle) 实现

- **核心机制**：通过 `swait_event_exclusive()` 使主 CPU 等待，同时调用 `wake_up_all_idle_cpus()` 触发所有 CPU（包括主 CPU）进入 idle。
- **唤醒处理**：外部中断或唤醒事件调用 `s2idle_wake()`，设置状态并唤醒等待队列，打破 idle 循环。
- **平台回调**：通过 `s2idle_ops` 提供 `prepare`、`check`、`begin`、`restore` 等钩子，允许平台在 s2idle 各阶段执行特定操作。

### 3.3 平台操作抽象

- 使用 `suspend_ops`（Suspend-to-RAM）和 `s2idle_ops`（Suspend-to-idle）将平台相关操作解耦。
- `valid_state()` 验证平台是否支持某挂起状态（需 `.valid()` 和 `.enter()` 回调存在）。
- 挂起流程各阶段（prepare、prepare_late、enter、wake、restore、finish）均通过封装函数统一调用平台回调。

### 3.4 默认挂起深度配置

- 通过内核启动参数 `mem_sleep_default=<label>`（如 `s2idle`、`shallow`、`deep`）设置默认挂起方式。
- `mem_sleep_current` 动态反映当前生效的挂起深度，影响 `/sys/power/mem_sleep` 的默认值。

## 4. 依赖关系

### 头文件依赖
- `<linux/suspend.h>`：挂起核心 API 和数据结构定义
- `<linux/cpuidle.h>`、`<linux/cpu.h>`：CPU idle 和热插拔管理
- `<linux/console.h>`：控制台冻结/解冻
- `<trace/events/power.h>`：电源管理事件追踪
- `"power.h"`：本地私有头文件（含 `lock_system_sleep()` 等）

### 内核子系统依赖
- **设备驱动模型**：设备挂起/恢复通过 `dpm_suspend()`/`dpm_resume()` 实现（在其他文件中）
- **CPU 空闲管理（cpuidle）**：s2idle 依赖 cpuidle 驱动使 CPU 进入深度 idle
- **唤醒源（wakeup source）**：通过 `pm_wakeup_pending()` 检测挂起期间的唤醒事件
- **ACPI / 平台固件**：`suspend_ops` 通常由 ACPI 或 SoC 平台驱动提供（如 `arch/x86/kernel/acpi/sleep.c`）

### 导出符号（供其他模块使用）
- `pm_suspend_target_state`
- `pm_suspend_global_flags`
- `pm_suspend_default_s2idle()`
- `s2idle_wake()`
- `suspend_set_ops()`
- `suspend_valid_only_mem()`

## 5. 使用场景

1. **用户空间触发挂起**：
   - 向 `/sys/power/state` 写入 `mem`、`standby` 或 `freeze` 触发对应挂起流程。
   - 向 `/sys/power/mem_sleep` 写入 `s2idle`/`shallow`/`deep` 切换默认挂起深度。

2. **系统集成**：
   - **ACPI 系统**：ACPI 驱动注册 `suspend_ops` 实现 S3（mem）挂起。
   - **ARM/嵌入式平台**：SoC 电源管理驱动注册 `suspend_ops` 或 `s2idle_ops`。
   - **通用 PC/服务器**：通常支持 `mem`（需 BIOS 支持）和 `freeze`（始终可用）。

3. **低功耗场景**：
   - **笔记本合盖**：通常配置为 `mem`（S3）。
   - **无 ACPI 的嵌入式设备**：使用 `freeze`（s2idle）实现软件挂起。
   - **现代 Intel/AMD 平台**：结合 `s2idle` 与 Modern Standby（S0ix）实现快速唤醒。

4. **内核调试与追踪**：
   - 通过 `ftrace` 的 `power:power_start`/`power_end` 事件追踪挂起/恢复流程。
   - `PM: ` 前缀的日志用于调试挂起过程中的问题。