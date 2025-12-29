# trace\trace_functions_graph.c

> 自动生成时间: 2025-10-25 17:25:32
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_functions_graph.c`

---

# `trace/trace_functions_graph.c` 技术文档

## 1. 文件概述

`trace_functions_graph.c` 是 Linux 内核函数图追踪器（Function Graph Tracer）的核心实现文件。该追踪器用于记录函数调用的进入（entry）和返回（return）事件，并以树状结构（缩进形式）展示函数调用关系，支持深度控制、中断过滤、执行耗时统计、进程信息显示等功能。相比简单的函数追踪器（function tracer），函数图追踪器能提供更完整的调用上下文，适用于性能分析、延迟调试和代码路径可视化等场景。

## 2. 核心功能

### 主要数据结构

- **`struct fgraph_cpu_data`**  
  每 CPU 的函数图追踪状态数据，包含：
  - `last_pid`：上次追踪的进程 PID
  - `depth`：当前调用深度
  - `depth_irq`：中断上下文中的调用深度
  - `ignore`：是否忽略当前追踪
  - `enter_funcs`：记录已进入但未返回的函数地址栈（最大深度为 `FTRACE_RETFUNC_DEPTH`）

- **`struct fgraph_data`**  
  全局函数图追踪数据结构，包含 per-CPU 数据指针、临时缓存的 entry/ret 条目及失败状态等。

- **`tracer_flags` 与 `trace_opts`**  
  定义函数图追踪器的可配置选项，如是否显示 CPU、进程名、执行耗时、中断标记、绝对时间、返回值（需 `CONFIG_FUNCTION_GRAPH_RETVAL`）等。

### 主要函数

- **`__trace_graph_entry()` / `__trace_graph_return()`**  
  底层函数，负责将函数进入/返回事件写入 ring buffer。

- **`trace_graph_entry()` / `trace_graph_return()`**  
  高层回调函数，由 ftrace 框架在函数进入/返回时调用，执行过滤、上下文检查、中断判断等逻辑后调用底层写入函数。

- **`trace_graph_thresh_return()`**  
  支持阈值过滤的返回处理函数：仅当函数执行时间超过 `tracing_thresh` 时才记录返回事件。

- **`ftrace_graph_ignore_irqs()`**  
  判断是否应忽略中断上下文中的函数调用（由 `ftrace_graph_skip_irqs` 控制）。

- **`trace_graph_function()`**  
  用于直接追踪单个函数调用（无嵌套），常用于调试或特殊追踪场景。

- **`allocate_fgraph_ops()`**  
  为指定的 `trace_array` 分配并初始化 `fgraph_ops` 结构体（代码片段中未完整展示）。

## 3. 关键实现

### 调用图构建机制
函数图追踪器通过 hook 函数的进入和返回点，记录每个函数的调用深度和执行时间。进入时记录 `calltime` 和深度，返回时记录 `rettime`，两者之差即为函数执行耗时。通过 per-CPU 的 `enter_funcs` 栈维护调用关系，确保嵌套调用的正确匹配。

### 中断与过滤处理
- 若 `ftrace_graph_skip_irqs` 为真且当前处于硬中断上下文，则跳过追踪。
- 支持通过 `set_graph_notrace` 排除特定函数，使用 `TRACE_GRAPH_NOTRACE_BIT` 标记任务变量以临时禁用追踪，并在返回时恢复。
- 支持基于执行时间阈值（`tracing_thresh`）的过滤：仅记录耗时超过阈值的函数。

### 输出格式控制
通过 `tracer_flags` 动态控制输出内容，包括：
- 缩进（每层 2 空格）
- 是否显示 CPU、进程名、执行耗时、绝对时间
- 中断标记（如 `!` 表示中断发生）
- 函数返回值（需配置支持）
- 睡眠时间（调度出的时间）是否计入总耗时

### 并发与中断安全
使用 `local_irq_save/restore` 禁用本地中断，并通过 `atomic_inc_return(&data->disabled)` 实现 per-CPU 缓冲区的嵌套保护，确保在中断或 NMI 上下文中不会破坏 ring buffer 的一致性。

## 4. 依赖关系

- **`<linux/ftrace.h>`**：提供 ftrace 核心 API，如 `ftrace_graph_ent`、`ftrace_graph_ret`、`ftrace_ops` 等。
- **`"trace.h"` / `"trace_output.h"`**：内核追踪子系统内部头文件，定义 `trace_array`、`ring_buffer` 操作及事件输出格式。
- **`CONFIG_FUNCTION_GRAPH_TRACER`**：必须启用此配置选项。
- **`CONFIG_FUNCTION_GRAPH_RETVAL`（可选）**：启用函数返回值追踪。
- **`CONFIG_FUNCTION_PROFILER`（可选）**：启用嵌套函数时间统计。

## 5. 使用场景

- **性能分析**：通过函数调用图识别热点路径和长延迟函数。
- **延迟调试**：结合 `tracing_thresh` 过滤，聚焦于执行时间异常的函数。
- **中断行为分析**：通过 `funcgraph-irqs` 选项观察中断对正常执行流的影响。
- **代码路径验证**：确认特定功能的调用栈是否符合预期。
- **系统启动/关机追踪**：在早期启动阶段启用，分析初始化流程。

该追踪器可通过 `/sys/kernel/debug/tracing/` 接口配置和读取，是 Linux 内核动态追踪基础设施的重要组成部分。