# power\poweroff.c

> 自动生成时间: 2025-10-25 15:23:05
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `power\poweroff.c`

---

# power/poweroff.c 技术文档

## 1. 文件概述

`power/poweroff.c` 是 Linux 内核中实现 SysRq（Magic SysRq）功能的一个模块，用于响应用户通过 SysRq 键（通常是 `Alt+SysRq+o`）触发的关机请求。该文件注册了一个 SysRq 处理函数，当用户按下指定组合键时，内核会调度一个工作队列任务，在引导 CPU 上安全地执行关机操作，从而实现对系统的优雅断电。

## 2. 核心功能

### 主要函数

- **`do_poweroff(struct work_struct *dummy)`**  
  工作队列回调函数，实际调用 `kernel_power_off()` 执行关机操作。

- **`handle_poweroff(u8 key)`**  
  SysRq 键处理函数，负责将关机任务调度到在线 CPU 中的第一个（通常是引导 CPU）上执行。

- **`pm_sysrq_init(void)`**  
  模块初始化函数，用于向 SysRq 子系统注册 `'o'` 键对应的关机操作。

### 主要数据结构

- **`poweroff_work`**  
  使用 `DECLARE_WORK` 宏静态声明的工作项，绑定到 `do_poweroff` 函数。

- **`sysrq_poweroff_op`**  
  `sysrq_key_op` 类型的结构体，定义了 `'o'` 键的行为，包括处理函数、帮助信息、动作提示和启用掩码。

## 3. 关键实现

- **工作队列机制**：  
  关机操作通过工作队列异步执行，避免在中断上下文或原子上下文中直接调用可能阻塞的 `kernel_power_off()`。使用 `schedule_work_on()` 确保任务在 `cpumask_first(cpu_online_mask)`（即第一个在线 CPU，通常是 CPU 0）上运行，这是关机操作的安全执行环境。

- **SysRq 集成**：  
  通过 `register_sysrq_key('o', &sysrq_poweroff_op)` 将 `'o'` 键与关机操作绑定。该操作仅在 `SYSRQ_ENABLE_BOOT` 权限下启用，通常在系统引导阶段允许使用，防止运行时被意外触发。

- **优雅关机**：  
  最终调用 `kernel_power_off()`，该函数会执行平台相关的断电流程（如 ACPI 关机、设备电源管理等），确保系统状态一致后再切断电源。

## 4. 依赖关系

- **`<linux/sysrq.h>`**：提供 SysRq 键注册和操作结构体定义。
- **`<linux/workqueue.h>`**：提供工作队列调度接口（`DECLARE_WORK`, `schedule_work_on`）。
- **`<linux/pm.h>` 和 `<linux/reboot.h>`**：提供 `kernel_power_off()` 函数声明，该函数由电源管理子系统实现。
- **`<linux/cpumask.h>`**：用于获取第一个在线 CPU 的 ID。
- **电源管理（PM）子系统**：实际关机逻辑依赖于平台特定的 PM 实现（如 ACPI、设备树等）。

## 5. 使用场景

- **紧急关机**：在系统无法正常响应（如死锁、严重错误）但仍能处理中断时，管理员可通过 SysRq 组合键 `Alt+SysRq+o` 安全关机，避免直接断电导致的数据损坏。
- **调试与恢复**：在内核调试或系统恢复过程中，作为最后手段优雅关闭系统。
- **嵌入式或无图形界面环境**：在没有用户空间关机命令可用的场景下，提供底层关机能力。

> 注意：SysRq 功能需在内核配置中启用（`CONFIG_MAGIC_SYSRQ`），且 `'o'` 键操作默认仅在引导阶段启用（由 `SYSRQ_ENABLE_BOOT` 控制），生产环境中可能被限制。