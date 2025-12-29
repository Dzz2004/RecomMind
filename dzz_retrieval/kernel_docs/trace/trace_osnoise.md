# trace\trace_osnoise.c

> 自动生成时间: 2025-10-25 17:30:11
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_osnoise.c`

---

# `trace_osnoise.c` 技术文档

## 1. 文件概述

`trace_osnoise.c` 是 Linux 内核中用于实现 **OS Noise Tracer** 和 **Timerlat Tracer** 的核心源文件。  
- **OS Noise Tracer** 用于测量运行线程所遭受的来自操作系统（如中断、软中断、内核线程等）的干扰（即“噪声”），量化系统对实时任务的干扰程度。  
- **Timerlat Tracer** 用于测量从高精度定时器触发中断到用户空间线程被唤醒并执行之间的延迟（wakeup latency），特别适用于评估实时系统的定时响应能力。

该文件基于早期的 `hwlat_detector` 和学术研究（如 ECRTS 2020 的 rtsl tracer）实现，专为实时性分析和调试设计。

## 2. 核心功能

### 主要数据结构

| 结构体 | 说明 |
|--------|------|
| `struct osnoise_instance` | 表示一个已启用的 osnoise/timerlat tracer 实例，关联到 `trace_array` |
| `struct osn_nmi / osn_irq / osn_softirq / osn_thread` | 分别记录 NMI、硬中断、软中断、内核线程在采样期间的计数和时间戳信息 |
| `struct osnoise_variables` | 每 CPU 的运行时状态，包含采样线程、上下文计数器等 |
| `struct timerlat_variables`（条件编译） | 每 CPU 的 timerlat 模式运行时状态，包含高精度定时器、周期、线程标识等 |
| `struct osnoise_sample` | 一次 OS Noise 采样的统计结果，包括总噪声、最大单次噪声、各类干扰事件计数 |
| `struct timerlat_sample`（条件编译） | 一次 Timerlat 采样的结果，包含延迟值、序列号、上下文类型（IRQ/Thread） |

### 主要函数

| 函数 | 功能 |
|------|------|
| `osnoise_has_registered_instances()` | 检查是否存在已注册的 tracer 实例 |
| `osnoise_instance_registered()` | 判断指定 `trace_array` 是否已注册 |
| `osnoise_register_instance()` / `osnoise_unregister_instance()` | 管理 tracer 实例的注册与注销 |
| `this_cpu_osn_var()` / `this_cpu_tmr_var()` | 获取当前 CPU 对应的运行时变量结构 |
| `osn_var_reset()` / `tlat_var_reset()` / `osn_var_reset_all()` | 重置 per-CPU 运行时状态 |
| `trace_osnoise_callback_enabled` | 全局标志，控制 NMI 是否回调 tracer 记录时间戳 |

### 配置与选项

- **默认参数**：
  - `DEFAULT_SAMPLE_PERIOD = 1s`
  - `DEFAULT_SAMPLE_RUNTIME = 1s`
  - `DEFAULT_TIMERLAT_PERIOD = 1ms`
  - `DEFAULT_TIMERLAT_PRIO = 95`（SCHED_FIFO 优先级）
- **运行时选项**（通过 `osnoise/options` 接口控制）：
  - `OSN_WORKLOAD`：启用后台噪声工作负载
  - `PANIC_ON_STOP`：采样异常停止时触发 panic
  - `OSN_PREEMPT_DISABLE` / `OSN_IRQ_DISABLE`：在采样时禁用抢占或 IRQ

## 3. 关键实现

### 实例管理机制
- 使用 RCU 保护的全局链表 `osnoise_instances` 管理所有活跃的 tracer 实例。
- 注册/注销操作由 `trace_types_lock` 串行化，确保线程安全。
- 支持多实例并行运行（每个 `trace_array` 对应一个实例）。

### 每 CPU 状态隔离
- 所有运行时状态（如中断计数、时间戳）均通过 `DEFINE_PER_CPU` 存储，避免跨 CPU 干扰。
- 采样线程绑定到特定 CPU，确保测量结果反映该 CPU 的噪声情况。

### Timerlat 模式（条件编译）
- 依赖 `CONFIG_TIMERLAT_TRACER` 编译选项。
- 每 CPU 启动一个高优先级 `SCHED_FIFO` 内核线程，配合 `hrtimer` 触发精确中断。
- 测量从 `hrtimer` 中断触发到线程实际运行的时间差，区分 **IRQ 上下文** 和 **线程上下文** 延迟。

### 噪声采样逻辑
- 在 `sample_runtime` 时间内持续运行空循环（或工作负载），期间记录所有干扰事件（NMI/IRQ/SoftIRQ/Thread）。
- 通过 `local_t int_counter` 等原子计数器统计事件次数。
- 最终生成 `osnoise_sample`，包含总噪声时间、最大单次干扰、各类事件计数。

### 与 Trace Events 集成
- 包含自定义 tracepoint：`trace/events/osnoise.h`（通过 `CREATE_TRACE_POINTS` 生成）。
- 复用现有 trace events：`irq.h`（硬中断）、`sched.h`（调度事件）。
- 在 x86 平台上可集成 APIC 中断向量追踪（`irq_vectors.h`）。

## 4. 依赖关系

| 依赖模块 | 用途 |
|---------|------|
| `tracefs` | 提供用户空间配置接口（如 `osnoise/options`） |
| `kthread` | 创建 per-CPU 采样线程 |
| `hrtimer`（Timerlat 模式） | 高精度定时器触发 |
| `sched/clock.h` | 获取高精度时间戳 |
| `trace/events/irq.h`, `sched.h` | 捕获中断和调度事件 |
| `asm/trace/irq_vectors.h`（x86） | 追踪本地 APIC 中断向量 |
| `RCU` | 安全遍历实例链表 |

## 5. 使用场景

- **实时系统性能分析**：评估 Linux 内核对实时任务的干扰程度，识别噪声源（如周期性中断、内核线程）。
- **延迟敏感应用调试**：通过 Timerlat 模式测量最坏-case 中断到线程唤醒延迟，验证系统是否满足实时性要求。
- **内核配置调优**：结合 `osnoise` 输出调整 IRQ 亲和性、禁用不必要的内核线程、优化调度策略。
- **自动化测试**：集成到 CI/CD 流程中，监控内核版本升级或配置变更对实时性能的影响。
- **panic 触发机制**：启用 `PANIC_ON_STOP` 可在噪声超标时自动 crash 系统，便于事后分析（如 kdump）。