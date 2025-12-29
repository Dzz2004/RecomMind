# reboot.c

> 自动生成时间: 2025-10-25 15:51:14
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `reboot.c`

---

# reboot.c 技术文档

## 1. 文件概述

`reboot.c` 是 Linux 内核中负责系统重启、关机和紧急重启逻辑的核心实现文件。它提供了统一的接口用于注册重启通知器、处理重启准备流程、执行系统重启，并支持多种重启模式（如硬重启、软重启、kexec 等）。该文件协调设备关闭、用户空间辅助进程禁用、CPU 迁移等关键步骤，确保系统在重启前处于安全状态，并为架构无关代码提供标准化的重启抽象。

## 2. 核心功能

### 主要全局变量
- `C_A_D`：控制是否允许通过 Ctrl+Alt+Del 组合键触发重启（默认启用）。
- `cad_pid`：指向处理 Ctrl+Alt+Del 信号的进程 PID（导出供其他模块使用）。
- `reboot_mode`：当前系统重启模式（如 `REBOOT_HARD`、`REBOOT_SOFT` 等），ARM 架构默认为硬重启。
- `panic_reboot_mode`：内核 panic 时使用的重启模式。
- `reboot_default`：标识 `reboot=` 内核参数是否被显式设置，用于控制 DMI 重启 quirks 的启用。
- `reboot_cpu` / `reboot_type` / `reboot_force`：控制重启目标 CPU、重启方式（如 ACPI、EFI 等）及是否强制重启。
- `pm_power_off`：弱符号函数指针，作为遗留关机接口的临时占位符。

### 主要函数
- `emergency_restart()`：在紧急情况下（如死锁、严重错误）立即重启系统，可在中断上下文调用。
- `kernel_restart_prepare()`：执行重启前的标准准备流程（通知链、设备关闭等）。
- `kernel_restart()`：执行完整的系统重启流程，包括迁移至指定 CPU、关闭 syscore、调用底层 `machine_restart()`。
- `register_reboot_notifier()` / `unregister_reboot_notifier()`：注册/注销重启通知器（阻塞型）。
- `devm_register_reboot_notifier()`：基于设备资源管理的重启通知器注册。
- `register_restart_handler()` / `unregister_restart_handler()`：注册/注销重启处理器（原子型，高优先级）。
- `do_kernel_restart()`：调用已注册的重启处理器链，尝试执行架构无关的重启。
- `migrate_to_reboot_cpu()`：将当前任务迁移到指定的重启 CPU（默认为 CPU 0 或首个在线 CPU）。
- `do_kernel_restart_prepare()`：调用重启准备通知链，用于预处理。

### 通知链
- `reboot_notifier_list`（阻塞）：用于常规重启前的通知。
- `restart_handler_list`（原子）：用于实际执行重启操作的高优先级处理器。
- `restart_prep_handler_list`（阻塞）：用于重启前的额外准备步骤。

## 3. 关键实现

### 重启流程控制
- **标准重启** (`kernel_restart`)：依次执行通知链 → 设备关闭 → 用户空间 helper 禁用 → 迁移到指定 CPU → syscore 关闭 → 调用架构相关 `machine_restart()`。
- **紧急重启** (`emergency_restart`)：跳过大部分清理步骤，直接调用 `machine_emergency_restart()`，适用于系统已不稳定的情况。
- **重启处理器机制**：通过 `register_restart_handler()` 注册的处理器（如 watchdog 驱动）可在 `machine_restart()` 中被调用（若其实现调用了 `do_kernel_restart()`），实现架构无关的重启能力。

### CPU 迁移策略
- `migrate_to_reboot_cpu()` 确保重启操作在指定 CPU（`reboot_cpu`）上执行，若该 CPU 离线则回退到首个在线 CPU。
- 设置 `PF_NO_SETAFFINITY` 标志防止其他任务修改当前任务的 CPU 亲和性，保证迁移的可靠性。

### 重启模式与参数
- `reboot_mode` 允许内核或用户空间指定重启类型（硬/软/kexec），影响底层硬件操作方式。
- `reboot_default` 变量用于判断是否通过内核命令行显式设置了 `reboot=` 参数，从而决定是否跳过 DMI 重启 quirks 扫描，便于覆盖错误的固件行为。

### 资源管理
- `devm_register_reboot_notifier()` 使用设备资源管理（devres）自动注销通知器，避免资源泄漏。

## 4. 依赖关系

- **架构相关代码**：依赖 `machine_restart()` 和 `machine_emergency_restart()` 的架构特定实现（位于 `arch/*/kernel/reboot.c` 等）。
- **设备模型**：调用 `device_shutdown()` 关闭设备，依赖驱动模型。
- **电源管理**：与 `suspend.h` 和遗留的 `pm_power_off` 接口交互。
- **kexec**：支持通过 `kexec` 实现快速重启，依赖 `kexec.h`。
- **内核通知机制**：使用 `notifier.h` 提供的阻塞和原子通知链。
- **用户空间交互**：通过 `syscalls.h` 暴露系统调用接口（如 `reboot()` 系统调用）。
- **日志系统**：使用 `kmsg_dump()` 在重启前转储内核日志。

## 5. 使用场景

- **系统调用处理**：`sys_reboot()` 系统调用最终调用 `kernel_restart()` 或 `kernel_halt()` 等函数。
- **内核 Panic**：当配置了 panic 后自动重启时，调用 `emergency_restart()` 或 `kernel_restart()`。
- **硬件驱动**：Watchdog 或电源管理芯片驱动通过 `register_restart_handler()` 注册硬件级重启能力。
- **用户空间工具**：`reboot`、`shutdown` 等命令通过系统调用触发内核重启流程。
- **kexec 快速启动**：配合 kexec 实现无需固件介入的内核切换。
- **调试与恢复**：在系统卡死时通过 Magic SysRq 或硬件看门狗触发紧急重启。