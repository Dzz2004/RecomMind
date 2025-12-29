# trace\trace_sched_switch.c

> 自动生成时间: 2025-10-25 17:35:27
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_sched_switch.c`

---

# trace_sched_switch.c 技术文档

## 1. 文件概述

`trace_sched_switch.c` 是 Linux 内核 ftrace 框架中的一个核心组件，用于在任务调度上下文切换（context switch）和任务唤醒（wakeup）事件发生时，记录相关任务的辅助信息（如命令行名称和线程组 ID）。该文件通过注册到内核调度器的 tracepoint（`sched_switch`、`sched_wakeup` 和 `sched_wakeup_new`），在调度事件触发时动态捕获并缓存任务元数据，供后续跟踪系统（如 latency tracing、function tracer 等）使用。

## 2. 核心功能

### 主要函数

- `probe_sched_switch()`：`sched_switch` tracepoint 的回调函数，在任务切换时被调用。
- `probe_sched_wakeup()`：`sched_wakeup` 和 `sched_wakeup_new` tracepoint 的回调函数，在任务被唤醒时被调用。
- `tracing_sched_register()`：注册所有相关的调度 tracepoint 探针。
- `tracing_sched_unregister()`：注销所有已注册的调度 tracepoint 探针。
- `tracing_start_sched_switch()` / `tracing_stop_sched_switch()`：内部辅助函数，用于根据引用计数控制探针的启用/禁用。
- `tracing_start_cmdline_record()` / `tracing_stop_cmdline_record()`：对外接口，用于启用/禁用命令行名称记录。
- `tracing_start_tgid_record()` / `tracing_stop_tgid_record()`：对外接口，用于启用/禁用线程组 ID（TGID）记录。

### 关键数据结构与变量

- `sched_cmdline_ref`：记录请求启用命令行记录的引用计数。
- `sched_tgid_ref`：记录请求启用 TGID 记录的引用计数。
- `sched_register_mutex`：互斥锁，保护引用计数和探针注册状态的并发访问。
- `RECORD_CMDLINE` / `RECORD_TGID`：标志位，分别表示是否需要记录命令行和 TGID。

## 3. 关键实现

- **引用计数机制**：通过 `sched_cmdline_ref` 和 `sched_tgid_ref` 两个引用计数变量，允许多个跟踪子系统（如 latency tracer、wakeup tracer 等）独立请求记录任务信息，避免重复注册或过早注销探针。
  
- **动态探针注册**：仅当至少有一个记录请求（命令行或 TGID）存在时，才调用 `tracing_sched_register()` 注册 tracepoint 探针；当所有请求都被释放后，自动注销探针以减少运行时开销。

- **统一任务信息记录接口**：两个探针函数（`probe_sched_switch` 和 `probe_sched_wakeup`）均调用 `tracing_record_taskinfo_sched_switch()`，传入当前任务和目标任务以及记录标志，由底层统一处理任务元数据的缓存。

- **错误回滚机制**：在 `tracing_sched_register()` 中，若任一 tracepoint 注册失败，则按顺序回滚已成功注册的探针，确保系统状态一致性。

- **唤醒事件处理**：`probe_sched_wakeup` 使用 `current` 作为“前一个任务”，`wakee` 作为“下一个任务”，模拟上下文切换场景，确保被唤醒任务的信息也能被正确记录。

## 4. 依赖关系

- **Tracepoint 子系统**：依赖 `<trace/events/sched.h>` 中定义的 `sched_switch`、`sched_wakeup` 和 `sched_wakeup_new` tracepoint。
- **Ftrace 框架**：通过 `#include <linux/ftrace.h>` 和 `"trace.h"` 与 ftrace 核心集成。
- **任务信息记录接口**：调用 `tracing_record_taskinfo_sched_switch()`，该函数定义在 `kernel/trace/trace.c` 中，负责实际缓存任务的 cmdline 和 TGID。
- **内核基础模块**：使用 `mutex`、`pr_info`、`register_trace_*` 等通用内核原语。

## 5. 使用场景

- **延迟跟踪（Latency Tracing）**：在分析调度延迟时，需要知道切换任务的名称和所属进程，便于定位性能瓶颈。
- **唤醒路径分析（Wakeup Tracer）**：追踪哪个任务唤醒了目标任务，需记录唤醒者和被唤醒者的身份信息。
- **函数图跟踪（Function Graph Tracer）**：结合任务上下文，提供更清晰的调用栈归属。
- **动态调试与性能分析工具**：如 `perf`、`trace-cmd` 等用户态工具依赖此机制获取可读的任务标识信息。

该模块本身不直接输出跟踪数据，而是作为基础设施，为其他跟踪器提供任务元数据支持，提升跟踪结果的可读性和诊断价值。