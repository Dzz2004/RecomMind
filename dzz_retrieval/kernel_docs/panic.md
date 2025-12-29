# panic.c

> 自动生成时间: 2025-10-25 15:14:29
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `panic.c`

---

# panic.c 技术文档

## 文件概述

`panic.c` 是 Linux 内核中实现系统崩溃（panic）处理机制的核心文件。当内核检测到无法恢复的严重错误（如内存损坏、死锁、硬件异常等）时，会调用 `panic()` 函数终止系统运行，并输出诊断信息。该文件负责协调崩溃流程中的关键操作，包括打印错误信息、通知注册的回调、停止其他 CPU、触发 kdump/kexec 崩溃转储、以及最终系统停机或重启。它还提供了对 WARN() 警告的限流和自动 panic 支持，并支持通过 sysctl 和 sysfs 暴露控制接口。

## 核心功能

### 主要函数
- **`panic(const char *fmt, ...)`**：内核 panic 的主入口函数，格式化输出错误信息，执行清理和停机流程，永不返回。
- **`nmi_panic(struct pt_regs *regs, const char *msg)`**：在 NMI（不可屏蔽中断）上下文中安全地触发 panic，避免多 CPU 同时 panic。
- **`nmi_panic_self_stop(struct pt_regs *regs)`**：当其他 CPU 已 panic 时，当前 CPU 在 NMI 上下文中自旋等待，可被架构代码覆盖以保存寄存器状态。
- **`panic_smp_self_stop(void)`**：panic 的 CPU 在停止其他 CPU 后自旋等待，可被架构代码覆盖。
- **`crash_smp_send_stop(void)`**：向其他 CPU 发送停止信号，用于崩溃转储前的准备，可被架构代码覆盖以保存 CPU 状态。
- **`check_panic_on_warn(const char *origin)`**：检查是否因 WARN() 触发 panic（基于 `panic_on_warn` 或 `warn_limit`）。
- **`panic_other_cpus_shutdown(bool crash_kexec)`**：辅助函数，根据 `panic_print` 设置决定是否触发所有 CPU 的 backtrace，然后停止其他 CPU。
- **`panic_print_sys_info(bool console_flush)`**：根据 `panic_print` 位掩码打印各类系统诊断信息（任务、内存、锁、ftrace 等）。

### 关键数据结构与变量
- **`panic_notifier_list`**：原子通知链，允许其他子系统注册 panic 事件回调。
- **`panic_timeout`**：panic 后自动重启/关机的超时时间（秒），0 表示无限等待，负值表示立即关机。
- **`panic_print`**：位掩码，控制 panic 时打印哪些额外的系统信息（任务状态、内存、锁等）。
- **`panic_on_oops`**：若置位，内核 oops（严重错误但非致命）将升级为 panic。
- **`panic_on_warn`**：若置位，任何 `WARN()` 调用将触发 panic。
- **`warn_limit` / `warn_count`**：限制 `WARN()` 调用次数，超过阈值则触发 panic。
- **`panic_cpu`**：原子变量，记录当前触发 panic 的 CPU ID，防止多 CPU 同时 panic。
- **`panic_blink`**：函数指针，用于在 panic 时通过 LED 闪烁指示状态（如键盘 Caps Lock）。
- **`sysctl_oops_all_cpu_backtrace`**（SMP）：控制 oops 时是否打印所有 CPU 的 backtrace。
- **`crash_kexec_post_notifiers`**：控制是否在通知链和 kmsg_dump 之后再执行 crash_kexec。

## 关键实现

### Panic 流程控制
1. **单点进入**：通过 `panic_cpu` 原子变量确保只有一个 CPU 执行完整的 panic 流程，其他 CPU 调用 `nmi_panic_self_stop()` 自旋。
2. **中断禁用**：panic CPU 禁用本地中断，防止在自旋等待时被中断打断。
3. **信息输出**：格式化 panic 消息，根据 `panic_print` 位掩码选择性输出系统状态（任务、内存、锁、ftrace、阻塞任务等）。
4. **通知与转储**：
   - 若 `crash_kexec_post_notifiers` 为假，则先尝试执行 crash_kexec（崩溃转储）。
   - 调用 `atomic_notifier_call_chain()` 通知所有 panic 回调。
   - 调用 `kmsg_dump(KMSG_DUMP_PANIC)` 转储内核日志。
   - 若 `crash_kexec_post_notifiers` 为真，则在此之后执行 crash_kexec。
5. **多 CPU 停止**：
   - 根据 `panic_print & PANIC_PRINT_ALL_CPU_BT` 决定是否先触发所有 CPU 的 NMI backtrace。
   - 调用 `crash_smp_send_stop()`（用于崩溃转储）或 `smp_send_stop()` 停止其他 CPU。
6. **最终停机**：
   - 若 `panic_timeout > 0`，启动定时器并在超时后重启/关机。
   - 启用 `panic_blink`（如键盘 LED 闪烁）提供视觉指示。
   - 调用 `panic_smp_self_stop()` 进入无限循环。

### NMI 安全 Panic
- `nmi_panic()` 专为 NMI 上下文设计，通过 `panic_cpu` 检查避免竞争。
- 若当前 CPU 非首个 panic CPU，则调用 `nmi_panic_self_stop()`，允许架构代码在此保存寄存器状态用于崩溃分析。

### 警告限流与自动 Panic
- `check_panic_on_warn()` 被 `WARN()` 宏调用，检查 `panic_on_warn` 或 `warn_count` 是否超过 `warn_limit`，若是则触发 panic。
- `warn_count` 通过原子操作计数，并通过 sysfs (`/sys/kernel/warn_count`) 暴露。

### 可配置性
- **Sysctl 接口**：`/proc/sys/kernel/oops_all_cpu_backtrace`（SMP）、`/proc/sys/kernel/warn_limit`。
- **Sysfs 接口**：`/sys/kernel/warn_count`。
- **内核参数**：`panic=`, `panic_on_oops=`, `panic_on_warn=`, `warn_limit=`, `panic_print=` 等。

## 依赖关系

- **架构相关代码**：依赖 `asm/sections.h` 和弱符号函数（`panic_smp_self_stop`, `nmi_panic_self_stop`, `crash_smp_send_stop`），由各架构实现提供崩溃转储支持。
- **调度器**：使用 `show_state()`, `show_state_filter()` 打印任务信息。
- **内存管理**：调用 `show_mem()` 输出内存状态。
- **锁调试**：集成 `debug_show_all_locks()` 检测死锁。
- **ftrace**：通过 `ftrace_dump()` 输出函数跟踪信息。
- **kexec/kdump**：与 `linux/kexec.h` 协作执行崩溃内核加载。
- **通知机制**：使用 `linux/notifier.h` 的原子通知链。
- **控制台**：通过 `console_flush_on_panic()` 刷新日志。
- **SysRq**：调用 `sysrq_timer_list_show()` 打印定时器信息。
- **调试支持**：集成 `kgdb`, `kmsg_dump`, `bug.h`（WARN 处理）等。

## 使用场景

1. **内核严重错误处理**：当内核遇到不可恢复错误（如空指针解引用、死锁、内存破坏）时，通过 `panic()` 终止系统，防止数据损坏。
2. **Oops 升级为 Panic**：当 `panic_on_oops=1` 时，普通 oops（如页错误）会触发完整 panic 流程。
3. **调试辅助**：开发人员通过 `panic_print` 位掩码在 panic 时自动收集系统状态（如所有 CPU backtrace、锁状态），加速问题定位。
4. **自动崩溃转储**：结合 kexec/kdump，在 panic 时自动保存内存镜像供离线分析。
5. **生产环境防护**：通过 `warn_limit` 限制内核警告频率，避免因频繁警告导致系统不稳定，超限时自动 panic 触发高可用切换。
6. **NMI 错误处理**：硬件错误（如 MCE）在 NMI 上下文中通过 `nmi_panic()` 安全触发 panic。
7. **系统监控**：通过 sysfs 的 `warn_count` 监控内核警告发生次数，评估系统健康度。