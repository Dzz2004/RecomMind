# watchdog.c

> 自动生成时间: 2025-10-25 17:51:17
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `watchdog.c`

---

# watchdog.c 技术文档

## 1. 文件概述

`watchdog.c` 是 Linux 内核中实现 **硬锁死（hard lockup）** 和 **软锁死（soft lockup）** 检测机制的核心文件。该机制用于监控系统中 CPU 是否因长时间禁用中断或陷入无限循环而无法响应，从而帮助诊断系统挂死问题。硬锁死指 CPU 完全停止响应中断（包括 NMI），软锁死指内核线程长时间占用 CPU 且未调度其他任务。本文件主要聚焦于硬锁死检测的通用框架和部分实现，软锁死检测逻辑主要在其他文件（如 `softlockup.c`）中实现，但两者共享部分配置和控制逻辑。

## 2. 核心功能

### 主要全局变量
- `watchdog_enabled`：位掩码，表示当前启用的 watchdog 类型（软/硬锁死检测）。
- `watchdog_user_enabled`：用户空间是否启用 watchdog（默认 1）。
- `watchdog_hardlockup_user_enabled`：用户空间是否启用硬锁死检测（默认值取决于架构）。
- `watchdog_softlockup_user_enabled`：用户空间是否启用软锁死检测（默认 1）。
- `watchdog_thresh`：锁死检测阈值（秒，默认 10 秒）。
- `watchdog_cpumask`：参与 watchdog 检测的 CPU 掩码。
- `hardlockup_panic`：硬锁死发生时是否触发内核 panic（默认由 `CONFIG_BOOTPARAM_HARDLOCKUP_PANIC` 决定）。
- `sysctl_hardlockup_all_cpu_backtrace`（SMP）：硬锁死时是否打印所有 CPU 的 backtrace。
- `hardlockup_count`（SYSFS）：记录硬锁死事件发生次数。

### 主要函数
- `hardlockup_detector_disable(void)`：在启动早期禁用硬锁死检测（例如虚拟机环境）。
- `hardlockup_panic_setup(char *str)`：解析内核启动参数 `nmi_watchdog=`，配置硬锁死行为。
- `arch_touch_nmi_watchdog(void)`：架构相关函数，用于在关键路径“触摸”硬 watchdog，防止误报（导出符号）。
- `watchdog_hardlockup_touch_cpu(unsigned int cpu)`：标记指定 CPU 已被“触摸”。
- `is_hardlockup(unsigned int cpu)`：检查指定 CPU 是否发生硬锁死（基于高精度定时器中断计数）。
- `watchdog_hardlockup_kick(void)`：在高精度定时器中断中“踢”硬 watchdog（更新中断计数）。
- `watchdog_hardlockup_check(unsigned int cpu, struct pt_regs *regs)`：执行硬锁死检测逻辑，打印诊断信息并可能触发 panic。
- `watchdog_hardlockup_enable/disable(unsigned int cpu)`：弱符号函数，由具体硬 watchdog 实现（如 perf-based）覆盖，用于启停 per-CPU 检测。
- `watchdog_hardlockup_probe(void)`：弱符号函数，由具体实现提供，用于探测硬 watchdog 硬件/机制是否可用。

### 核心数据结构（Per-CPU）
- `hrtimer_interrupts`：高精度定时器中断计数器（原子变量）。
- `hrtimer_interrupts_saved`：上次保存的中断计数值。
- `watchdog_hardlockup_warned`：是否已为该 CPU 打印过硬锁死警告。
- `watchdog_hardlockup_touched`：该 CPU 是否被“触摸”过（用于豁免检测）。

## 3. 关键实现

### 硬锁死检测机制（基于高精度定时器）
当配置 `CONFIG_HARDLOCKUP_DETECTOR_COUNTS_HRTIMER` 时，硬锁死检测通过监控 **高精度定时器（hrtimer）中断** 的发生频率实现：
1. **计数更新**：每次 hrtimer 中断发生时，调用 `watchdog_hardlockup_kick()` 原子递增 per-CPU 计数器 `hrtimer_interrupts`。
2. **检测逻辑**：在 NMI（不可屏蔽中断）上下文（或其他检测点）调用 `watchdog_hardlockup_check()`：
   - 若 CPU 被“触摸”（`watchdog_hardlockup_touched` 为真），则清除此标记并跳过检测。
   - 否则调用 `is_hardlockup()`：比较当前 `hrtimer_interrupts` 与上次保存值 `hrtimer_interrupts_saved`。若相等，说明在检测周期内无 hrtimer 中断，判定为硬锁死。
3. **告警与处理**：
   - 首次检测到硬锁死时，打印紧急日志（CPU 信息、模块列表、中断跟踪、寄存器状态或栈回溯）。
   - 若启用 `sysctl_hardlockup_all_cpu_backtrace`，触发其他 CPU 的 backtrace。
   - 若 `hardlockup_panic` 为真，调用 `nmi_panic()` 触发内核 panic。
   - 设置 `watchdog_hardlockup_warned` 避免重复告警。

### 启动参数与配置
- **`nmi_watchdog=` 参数**：通过 `__setup` 宏注册，支持以下值：
  - `panic`/`nopanic`：设置 `hardlockup_panic`。
  - `0`/`1`：启用/禁用硬锁死检测。
  - `r...`：传递参数给 perf-based 检测器（`hardlockup_config_perf_event`）。
- **早期禁用**：`hardlockup_detector_disable()` 可在解析命令行前禁用硬检测（如 KVM guest）。

### 架构交互与豁免
- **`arch_touch_nmi_watchdog()`**：允许架构代码或关键内核路径（如 printk）临时豁免硬 watchdog 检测，防止在已知安全的长操作中误报。使用 `raw_cpu_write` 确保在抢占/中断使能环境下安全。

### 弱符号扩展点
- `watchdog_hardlockup_enable/disable/probe` 声明为 `__weak`，允许不同架构或检测方法（如基于 perf event 的 NMI watchdog）提供具体实现，实现检测机制的可插拔。

## 4. 依赖关系

- **内核子系统**：
  - `<linux/nmi.h>`：NMI 处理框架，硬锁死检测通常在 NMI 上下文触发。
  - `<linux/hrtimer.h>`（隐含）：高精度定时器中断作为检测心跳源。
  - `<linux/sched/*.h>`：调度器相关（`print_irqtrace_events`, `dump_stack`）。
  - `<linux/sysctl.h>`：提供 `sysctl_hardlockup_all_cpu_backtrace` 控制接口。
  - `<linux/sysfs.h>`：暴露 `hardlockup_count` 到 sysfs。
  - `<asm/irq_regs.h>`：获取中断上下文寄存器状态（`show_regs`）。
- **配置选项**：
  - `CONFIG_HARDLOCKUP_DETECTOR`：启用硬锁死检测框架。
  - `CONFIG_HARDLOCKUP_DETECTOR_COUNTS_HRTIMER`：使用 hrtimer 中断计数实现检测。
  - `CONFIG_HARDLOCKUP_DETECTOR_SPARC64`：SPARC64 架构默认启用硬检测。
  - `CONFIG_BOOTPARAM_HARDLOCKUP_PANIC`：设置默认 panic 行为。
  - `CONFIG_SMP`：多核支持（`all_cpu_backtrace` 功能）。
  - `CONFIG_SYSFS`：sysfs 接口支持。
- **其他模块**：依赖具体架构的 NMI 实现（如 x86 的 perf-based NMI watchdog）提供检测触发点。

## 5. 使用场景

- **系统稳定性监控**：在生产服务器或嵌入式设备中持续监控 CPU 响应性，及时发现硬件故障、驱动 bug 或内核死锁导致的系统挂死。
- **内核调试**：开发人员通过 watchdog 触发的 backtrace 和寄存器转储，定位导致系统无响应的代码路径。
- **虚拟化环境**：在 hypervisor guest 中可选择性禁用硬 watchdog（因虚拟化开销可能导致误报），通过 `hardlockup_detector_disable()` 或启动参数控制。
- **实时系统**：结合 CPU 隔离（`isolcpus`）和 watchdog 配置，确保关键 CPU 核心的响应性，同时避免在非关键核上产生干扰。
- **panic 策略**：通过 `hardlockup_panic` 配置，使系统在硬锁死时自动重启，提高无人值守系统的可用性。