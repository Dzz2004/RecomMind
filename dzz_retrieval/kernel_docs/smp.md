# smp.c

> 自动生成时间: 2025-10-25 16:24:56
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `smp.c`

---

# smp.c 技术文档

## 文件概述

`smp.c` 是 Linux 内核中用于实现 **对称多处理（SMP）** 架构下 **跨 CPU 核心函数调用（IPI，Inter-Processor Interrupt）** 的通用辅助模块。该文件提供了在多个 CPU 之间安全、高效地调度和执行函数调用的基础设施，是 SMP 系统中 CPU 间通信的核心组件之一。其主要功能包括：

- 管理 per-CPU 的调用队列（call_single_queue）
- 实现 `smp_call_function()` 及相关 API 的底层支持
- 处理 CPU 热插拔（hotplug）过程中的 IPI 清理
- 支持同步/异步 CSD（Call Single Data）调用
- 提供 CSD 锁等待超时调试机制（可选）

## 核心功能

### 主要数据结构

| 数据结构 | 说明 |
|--------|------|
| `struct call_function_data` | 每个 CPU 私有的调用函数数据结构，包含：<br>• `csd`：per-CPU 的 `call_single_data_t` 数组<br>• `cpumask` / `cpumask_ipi`：用于 IPI 目标 CPU 掩码 |
| `call_single_queue` | per-CPU 的无锁链表（`llist_head`），用于排队待处理的单次调用请求 |
| `trigger_backtrace` | per-CPU 原子变量，用于控制是否在 CSD 卡死时触发目标 CPU 的堆栈回溯 |
| `cur_csd`, `cur_csd_func`, `cur_csd_info` | （调试模式下）记录当前 CPU 正在处理的 CSD 请求信息 |

### 主要函数

| 函数 | 功能 |
|------|------|
| `smpcfd_prepare_cpu()` | 为指定 CPU 初始化 `call_function_data` 所需内存（cpumask 和 percpu csd） |
| `smpcfd_dead_cpu()` | 释放指定 CPU 的 `call_function_data` 资源 |
| `smpcfd_dying_cpu()` | 在 CPU 下线前显式刷新 IPI 队列，防止遗留工作 |
| `call_function_init()` | 初始化所有可能 CPU 的 `call_single_queue`，并为 boot CPU 准备资源 |
| `send_call_function_single_ipi()` | 向单个 CPU 发送函数调用 IPI |
| `send_call_function_ipi_mask()` | 向掩码指定的多个 CPU 发送函数调用 IPI |
| `csd_do_func()` | 执行实际的回调函数，并插入 tracepoint |
| `__flush_smp_call_function_queue()` | 处理当前 CPU 的 `call_single_queue` 中所有待处理项（内部函数） |
| `csd_lock_wait_toolong()` | （调试）检测 CSD 锁等待是否超时，并输出诊断信息 |

## 关键实现

### 1. Per-CPU 调用队列管理
- 使用 `llist_head`（无锁链表）实现 per-CPU 的 `call_single_queue`，允许多个 CPU 并发地向目标 CPU 提交调用请求。
- IPI 中断处理函数（如 `generic_smp_call_function_single_interrupt`）会调用 `__flush_smp_call_function_queue()` 来消费队列。

### 2. CSD（Call Single Data）类型与标志
- CSD 结构体中的 `u_flags` 字段包含类型信息（`CSD_FLAG_TYPE_MASK`），区分同步（`CSD_TYPE_SYNC`）、异步（`CSD_TYPE_ASYNC`）等调用类型。
- 同步调用会设置 `CSD_FLAG_LOCK`，调用方需等待目标 CPU 执行完毕并清除该标志。

### 3. CPU 热插拔安全
- 在 `smpcfd_dying_cpu()` 中，CPU 下线前会主动调用 `__flush_smp_call_function_queue(false)` 和 `irq_work_run()`，确保所有已排队但未处理的 IPI 被执行，避免资源泄漏或死锁。

### 4. CSD 锁等待调试（CONFIG_CSD_LOCK_WAIT_DEBUG）
- 通过 `csdlock_debug=` 内核参数启用/禁用调试。
- 记录当前 CPU 正在处理的 CSD 请求（`cur_csd` 等 per-CPU 变量）。
- 若等待 CSD 锁超过 `csd_lock_timeout`（默认 5 秒），则打印警告；若超过 `panic_on_ipistall`（默认 0，即不 panic），则触发 `BUG_ON()`。
- 自动触发目标 CPU 的任务堆栈回溯（`dump_cpu_task()`）以辅助诊断。

### 5. 跟踪点（Tracepoints）
- 集成 `trace/events/ipi.h` 和 `trace/events/csd.h`，提供 IPI 发送和 CSD 函数执行的跟踪能力，便于性能分析和调试。

## 依赖关系

### 头文件依赖
- **架构相关**：`<asm/cputype.h>`（仅 ARM64）、`arch_send_call_function_*_ipi()`（由各架构实现）
- **核心子系统**：
  - `smp.h`：SMP 基础 API
  - `percpu.h`：Per-CPU 变量支持
  - `rcupdate.h` / `rculist.h`：RCU 同步机制
  - `irq_work.h`：IRQ 工作队列
  - `cpumask.h`：CPU 掩码操作
  - `sched/` 相关头文件：调度器集成
- **调试支持**：`nmi.h`、`sched/debug.h`、`jump_label.h`

### 模块依赖
- **底层**：依赖各 CPU 架构提供的 `arch_send_call_function_ipi_mask()` 和 `arch_send_call_function_single_ipi()` 实现。
- **上层**：被 `kernel/smp.c`、`kernel/sched/`、以及其他需要跨 CPU 执行函数的子系统（如 RCU、热插拔、电源管理）所调用。
- **内部**：包含本地头文件 `"smpboot.h"` 和 `"sched/smp.h"`。

## 使用场景

1. **内核同步原语**：RCU、锁、内存屏障等机制在需要跨 CPU 同步时，会使用 `smp_call_function()` 系列 API。
2. **CPU 热插拔**：在线/离线 CPU 时，需确保无遗留 IPI 工作，通过 `smpcfd_dying_cpu()` 安全清理。
3. **中断上下文任务迁移**：将工作从一个 CPU 的中断上下文迁移到另一个 CPU 执行。
4. **系统调试与诊断**：当启用 `csdlock_debug` 时，用于检测和诊断 IPI 处理卡死问题。
5. **调度器负载均衡**：SMP 调度器在迁移任务或平衡负载时，可能触发跨 CPU 函数调用。
6. **虚拟化与 Hypervisor 交互**：在虚拟化环境中，可能通过 IPI 通知其他 vCPU 执行特定操作。