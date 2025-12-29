# watchdog_perf.c

> 自动生成时间: 2025-10-25 17:52:30
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `watchdog_perf.c`

---

# watchdog_perf.c 技术文档

## 1. 文件概述

`watchdog_perf.c` 是 Linux 内核中用于实现**硬锁死（hard lockup）检测机制**的核心文件。它基于 **perf 事件子系统**，通过在每个 CPU 上创建一个周期性溢出的硬件性能计数器（通常监控 CPU 周期），在非屏蔽中断（NMI）上下文中触发回调，从而检测 CPU 是否因长时间禁用中断或陷入死循环而无法响应。该机制是 NMI watchdog 的现代实现，替代了早期架构相关的实现方式，具有更好的可移植性和灵活性。

## 2. 核心功能

### 主要数据结构

- `wd_hw_attr` / `fallback_wd_hw_attr`：`struct perf_event_attr` 类型，定义用于硬锁死检测的 perf 事件属性（默认监控 `PERF_COUNT_HW_CPU_CYCLES`）。
- `watchdog_ev`：每 CPU 变量，指向当前 CPU 上创建的 perf 事件对象。
- `watchdog_cpus`：原子变量，记录当前已启用硬锁死检测的 CPU 数量。
- （条件编译）`last_timestamp`：每 CPU 变量，记录上次 NMI 触发的时间戳（用于防误报）。
- （条件编译）`nmi_rearmed`：每 CPU 变量，记录连续未满足时间阈值的 NMI 次数。
- （条件编译）`watchdog_hrtimer_sample_threshold`：全局阈值，用于判断 NMI 采样间隔是否合理。

### 主要函数

- `watchdog_overflow_callback()`：perf 事件溢出时的回调函数，在 NMI 上下文中执行，负责调用硬锁死检查逻辑。
- `hardlockup_detector_event_create()`：为当前 CPU 创建并初始化 perf 事件。
- `watchdog_hardlockup_enable(cpu)`：启用指定 CPU 的硬锁死检测。
- `watchdog_hardlockup_disable(cpu)`：禁用指定 CPU 的硬锁死检测。
- `hardlockup_detector_perf_stop()` / `hardlockup_detector_perf_restart()`：全局暂停/恢复所有 CPU 的 watchdog 事件（用于处理 x86 超线程 bug）。
- `watchdog_hardlockup_probe()`：探测当前系统是否支持基于 perf 的 NMI watchdog。
- `hardlockup_config_perf_event(str)`：允许通过内核启动参数自定义 perf 事件的原始配置。
- （条件编译）`watchdog_check_timestamp()`：检查 NMI 触发间隔是否过短，防止因 Turbo Boost 等导致的误报。
- （条件编译）`watchdog_init_timestamp()`：初始化每 CPU 的时间戳。

## 3. 关键实现

### 硬锁死检测原理
- 每个在线 CPU 启动一个 **pinned、disabled** 的 perf 事件，监控硬件 CPU 周期计数器。
- 事件配置为在达到 `hw_nmi_get_sample_period(watchdog_thresh)` 周期后溢出，触发 NMI。
- 在 NMI 回调 `watchdog_overflow_callback()` 中：
  - 重置事件中断计数（防止被 perf 子系统节流）。
  - （若启用 `CONFIG_HARDLOCKUP_CHECK_TIMESTAMP`）检查自上次 NMI 以来是否已过去足够时间（避免因 CPU 频率动态调整导致的过快触发）。
  - 调用通用硬锁死检查函数 `watchdog_hardlockup_check()`。

### 防误报机制 (`CONFIG_HARDLOCKUP_CHECK_TIMESTAMP`)
- 引入 `watchdog_hrtimer_sample_threshold`（设为 `watchdog_thresh * 2` 纳秒）。
- 若两次 NMI 间隔小于该阈值，则认为可能是因 CPU Turbo Boost 导致周期计数过快，暂时忽略此次触发。
- 连续 10 次过快触发后强制通过检查，防止因系统时钟停滞（如 jiffies 停滞）导致 watchdog 失效。

### 事件创建与回退
- 优先使用 `wd_hw_attr` 创建事件。
- 若失败（如硬件 PMU 资源不足），尝试使用相同的 `fallback_wd_hw_attr`（当前实现中两者相同，但保留扩展性）。
- 创建失败则打印调试信息并返回错误。

### 架构适配
- 通过弱符号 `arch_perf_nmi_is_available()` 允许架构层声明是否支持 perf-based NMI。
- 提供 `hardlockup_config_perf_event()` 接口，允许用户通过 `nmi_watchdog=` 内核参数指定原始 perf 事件编码，用于调试或适配特殊硬件。

### 全局控制接口
- `hardlockup_detector_perf_stop/restart` 用于在特定场景（如 x86 超线程 bug 修复）下临时全局禁用/启用所有 watchdog 事件，要求调用时持有 CPU hotplug 锁。

## 4. 依赖关系

- **perf_event 子系统**：核心依赖，用于创建和管理硬件性能计数器事件。
- **NMI 子系统**：perf 事件溢出通过 NMI 触发回调，依赖 `linux/nmi.h`。
- **调度器调试功能**：调用 `watchdog_hardlockup_check()`（定义在 `kernel/watchdog.c`），该函数会打印 CPU 状态和堆栈。
- **架构特定代码**：
  - `hw_nmi_get_sample_period()`：由架构提供，根据 `watchdog_thresh` 计算 perf 采样周期。
  - `arch_perf_nmi_is_available()`：架构可覆盖此函数以禁用 perf watchdog。
- **内核配置选项**：依赖 `CONFIG_HARDLOCKUP_DETECTOR` 和 `CONFIG_PERF_EVENTS`，可选依赖 `CONFIG_HARDLOCKUP_CHECK_TIMESTAMP`。

## 5. 使用场景

- **系统稳定性监控**：在生产环境中持续监控 CPU 是否发生硬锁死（即 CPU 长时间无法处理中断）。
- **内核调试**：当系统无响应时，若 watchdog 触发，会打印出故障 CPU 的寄存器状态和调用栈，辅助定位死锁或无限循环问题。
- **架构无关的 watchdog 实现**：作为通用框架，替代旧的 x86-specific NMI watchdog，便于在 ARM64、RISC-V 等架构上实现统一的硬锁死检测。
- **动态配置**：通过内核参数（如 `nmi_watchdog=...`）允许用户指定特定的 perf 事件，用于在标准 CPU 周期计数器不可靠的平台上进行调试。
- **与软锁死检测协同**：硬锁死检测（基于 NMI）与软锁死检测（基于高精度定时器）共同构成完整的内核 watchdog 机制，分别检测中断禁用和进程调度层面的锁死。