# trace\trace_sched_wakeup.c

> 自动生成时间: 2025-10-25 17:35:56
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_sched_wakeup.c`

---

# `trace_sched_wakeup.c` 技术文档

## 1. 文件概述

`trace_sched_wakeup.c` 是 Linux 内核中用于追踪任务唤醒延迟（wakeup latency）的关键调度器跟踪模块。该文件实现了 **wakeup tracer**，用于记录从一个高优先级任务被唤醒（例如通过 `wake_up_process()`）到它实际获得 CPU 执行之间的时间延迟。该 tracer 主要用于实时系统性能分析和调度延迟调试，是内核 ftrace 框架的一部分。

## 2. 核心功能

### 主要全局变量
- `wakeup_trace`：指向当前 wakeup tracer 实例的 `struct trace_array`。
- `tracer_enabled`：标记 tracer 是否启用。
- `wakeup_task`：当前被追踪唤醒的目标任务。
- `wakeup_cpu` / `wakeup_current_cpu`：记录目标任务所在 CPU 和当前执行 CPU。
- `wakeup_prio`：目标任务的优先级（初始为 -1 表示无效）。
- `wakeup_rt` / `wakeup_dl` / `tracing_dl`：标志位，分别表示是否为实时任务（RT）、截止时间任务（Deadline）以及是否正在追踪 Deadline 任务。
- `wakeup_lock`：用于保护关键数据结构的自旋锁。

### 主要函数
- `func_prolog_preempt_disable()`：函数追踪的前置处理，用于判断是否应记录当前函数调用，并禁用抢占。
- `wakeup_tracer_call()`：函数追踪回调函数，记录函数调用事件。
- `wakeup_graph_entry()` / `wakeup_graph_return()`：函数图追踪（function graph tracer）的入口和返回钩子。
- `register_wakeup_function()` / `unregister_wakeup_function()`：注册/注销函数追踪回调。
- `wakeup_function_set()`：处理 `TRACE_ITER_FUNCTION` 标志变更。
- `wakeup_flag_changed()`：处理 tracer 标志变化（如启用函数追踪或函数图追踪）。
- `wakeup_print_line()` / `wakeup_print_header()`：格式化输出追踪结果。
- `wakeup_trace_open()` / `wakeup_trace_close()`：追踪迭代器的打开/关闭回调。

### 回调结构体
- `fgraph_wakeup_ops`：定义了用于函数图追踪的入口和返回回调函数。

## 3. 关键实现

### 唤醒追踪机制
- 当一个高优先级任务被唤醒时，wakeup tracer 会记录该任务信息（`wakeup_task`、`wakeup_prio`、CPU 等）。
- 在后续调度过程中，tracer 会追踪从唤醒点到该任务实际运行之间的所有函数调用（如果启用了函数追踪）。
- 通过比较时间戳，可计算出唤醒延迟（latency），并记录最大延迟值（`tr->max_latency`）。

### 函数追踪集成
- 若启用 `CONFIG_FUNCTION_TRACER`，tracer 会注册 `wakeup_tracer_call` 作为函数追踪回调。
- 若同时启用 `CONFIG_FUNCTION_GRAPH_TRACER`，则使用 `fgraph_wakeup_ops` 实现函数调用图追踪，记录完整的调用栈。
- 使用 `func_prolog_preempt_disable()` 确保只在追踪目标 CPU 上记录，并通过 `data->disabled` 原子计数防止嵌套追踪。

### 并发与抢占控制
- 使用 `preempt_disable_notrace()` 禁用抢占以保证追踪上下文一致性。
- 使用 `local_irq_save/restore()` 保护关键追踪路径。
- 通过 `arch_spinlock_t wakeup_lock` 保护共享状态（虽在代码片段中未直接使用，但为全局同步预留）。

### 动态追踪模式切换
- 支持在运行时切换普通函数追踪与函数图追踪模式（通过 `TRACE_ITER_DISPLAY_GRAPH` 标志）。
- 切换时会重置追踪状态（`wakeup_reset`）并重新注册对应的追踪回调。

## 4. 依赖关系

- **ftrace 框架**：依赖 `ftrace.h` 提供的函数追踪基础设施。
- **调度子系统**：通过 `trace/events/sched.h` 接收任务唤醒事件（如 `sched_wakeup`、`sched_wakeup_new`）。
- **实时调度类**：包含对 `SCHED_FIFO`/`SCHED_RR`（RT）和 `SCHED_DEADLINE` 调度策略的特殊处理。
- **函数图追踪**：若启用 `CONFIG_FUNCTION_GRAPH_TRACER`，依赖其回调机制和栈管理。
- **内核符号解析**：通过 `kallsyms.h` 支持函数名解析（间接依赖）。

## 5. 使用场景

- **实时系统延迟分析**：用于测量高优先级 RT 或 Deadline 任务从唤醒到执行的延迟，验证系统是否满足实时性要求。
- **调度器调试**：帮助开发者分析调度延迟来源，如中断处理、锁竞争、低优先级任务占用 CPU 等。
- **性能调优**：结合函数追踪或函数图追踪，定位导致唤醒延迟的具体代码路径。
- **内核测试**：作为 `ftrace` 的标准 tracer 之一，可通过 `/sys/kernel/debug/tracing/current_tracer` 设置为 `wakeup` 或 `wakeup_rt` 进行测试。