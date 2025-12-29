# trace\trace_preemptirq.c

> 自动生成时间: 2025-10-25 17:31:43
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_preemptirq.c`

---

# `trace_preemptirq.c` 技术文档

## 1. 文件概述

`trace_preemptirq.c` 是 Linux 内核中用于跟踪中断（IRQ）和抢占（preemption）状态变化的核心跟踪模块。该文件实现了在中断使能/禁用（`irq_enable`/`irq_disable`）以及抢占使能/禁用（`preempt_enable`/`preempt_disable`）时触发 tracepoint 的机制，主要用于内核延迟分析、死锁检测、实时性调试等场景。该模块通过与 `ftrace`、`lockdep` 和 RCU 子系统协同工作，提供低开销、高精度的上下文切换跟踪能力。

## 2. 核心功能

### 主要函数

- `trace_hardirqs_on_prepare(void)`  
  在中断开启前调用，仅执行跟踪逻辑，不触发 lockdep 检查，用于底层入口代码中对 RCU 顺序敏感的场景。

- `trace_hardirqs_on(void)`  
  完整的中断开启跟踪函数，包含 lockdep 的硬中断开启通知和 tracepoint 触发。

- `trace_hardirqs_off_finish(void)`  
  在中断关闭后调用，仅执行跟踪逻辑，不触发 lockdep 检查，用于底层入口代码。

- `trace_hardirqs_off(void)`  
  完整的中断关闭跟踪函数，先通知 lockdep，再执行跟踪逻辑。

- `trace_preempt_on(unsigned long a0, unsigned long a1)`  
  抢占开启时触发 `preempt_enable` tracepoint 并调用 tracer 回调。

- `trace_preempt_off(unsigned long a0, unsigned long a1)`  
  抢占关闭时触发 `preempt_disable` tracepoint 并调用 tracer 回调。

### 数据结构

- `static DEFINE_PER_CPU(int, tracing_irq_cpu)`  
  每 CPU 变量，用于避免在中断已关闭状态下重复触发 `irq_disable` 跟踪事件，确保跟踪事件的准确性。

### 宏定义

- `trace(point)`  
  根据架构是否支持 `noinstr`（无插桩）特性，选择使用普通 tracepoint（`trace_irq_enable`）或 RCU-idle 安全版本（`trace_irq_enable_rcuidle`），并在非 NMI 上下文中调用。

## 3. 关键实现

### 中断状态去重机制
通过 `tracing_irq_cpu` 每 CPU 变量记录当前 CPU 的中断跟踪状态：
- 当 `tracing_irq_cpu == 1` 表示中断已关闭且尚未跟踪，此时若调用 `trace_hardirqs_on` 则触发 `irq_enable` 事件并重置状态。
- 当 `tracing_irq_cpu == 0` 表示中断已开启或已跟踪，调用 `trace_hardirqs_off` 时才触发 `irq_disable` 事件并置位状态。
该机制防止在中断嵌套或重复开关中断时产生冗余跟踪事件。

### 架构适配策略
通过 `CONFIG_ARCH_WANTS_NO_INSTR` 宏区分新旧架构：
- 支持 `noinstr` 的架构（如 x86_64）可安全使用标准 tracepoint，因其保证在 RCU 使能上下文中调用。
- 旧架构使用 `_rcuidle` 变体，并通过 `in_nmi()` 排除 NMI 上下文（因 `_rcuidle` 不是 NMI-safe）。

### 与 lockdep 的解耦设计
提供 `*_prepare` 和 `*_finish` 版本函数，将跟踪逻辑与 lockdep 的硬中断状态跟踪分离：
- 底层入口代码（如异常/中断处理入口）使用 `trace_hardirqs_on_prepare`/`off_finish`，确保 RCU 与中断状态的正确排序。
- 通用代码路径使用完整版 `trace_hardirqs_on/off`，同时更新 lockdep 状态。

### 抢占跟踪实现
`trace_preempt_on/off` 直接调用 tracepoint 和 tracer 回调，无状态去重逻辑，因为抢占状态由调度器精确控制，通常不会出现冗余调用。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/ftrace.h>`：提供 `tracer_hardirqs_on/off`、`tracer_preempt_on/off` 等 tracer 回调接口。
  - `<trace/events/preemptirq.h>`：定义 `irq_enable`、`irq_disable`、`preempt_enable`、`preempt_disable` 等 tracepoint。
  - `<linux/kprobes.h>`：用于 `NOKPROBE_SYMBOL` 标记，防止 kprobe 在关键路径插入。
  - `<linux/rcupdate.h>`（隐式）：通过 `in_nmi()` 判断 NMI 上下文。

- **配置依赖**：
  - `CONFIG_TRACE_IRQFLAGS`：启用中断状态跟踪功能。
  - `CONFIG_TRACE_PREEMPT_TOGGLE`：启用抢占状态跟踪功能。
  - `CONFIG_ARCH_WANTS_NO_INSTR`：决定使用标准 tracepoint 还是 `_rcuidle` 变体。

- **子系统交互**：
  - **Lockdep**：通过 `lockdep_hardirqs_on/off` 同步硬中断状态。
  - **RCU**：跟踪函数需在 RCU 安全上下文中执行，`_rcuidle` 变体用于 idle 或中断上下文。
  - **Ftrace**：作为底层跟踪引擎，接收 tracepoint 事件并记录到 ring buffer。

## 5. 使用场景

- **中断延迟分析**：通过 `irq_disable`/`irq_enable` 事件计算最长关中断时间，用于实时系统调优。
- **抢占延迟监控**：利用 `preempt_disable`/`preempt_enable` 事件分析内核不可抢占时间段。
- **死锁与锁顺序检测**：lockdep 依赖 `trace_hardirqs_on/off` 获取准确的中断状态，以验证锁的使用是否符合中断安全规则。
- **底层异常处理跟踪**：在系统调用、中断、异常入口/出口处调用 `*_prepare`/`*_finish` 函数，确保在 RCU 初始化前/后正确跟踪中断状态。
- **性能剖析工具支持**：为 `perf`、`ftrace` 等工具提供原始事件数据，用于生成内核执行流图或延迟热力图。