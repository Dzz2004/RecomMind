# trace\ftrace.c

> 自动生成时间: 2025-10-25 17:03:00
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\ftrace.c`

---

# `trace/ftrace.c` 技术文档

## 1. 文件概述

`trace/ftrace.c` 是 Linux 内核中 **ftrace（Function Tracer）** 子系统的核心实现文件之一，负责提供函数跟踪的基础架构。该文件实现了基于 GCC `-pg` 插桩机制的函数调用跟踪能力，支持动态启用/禁用函数跟踪、多跟踪操作（`ftrace_ops`）管理、PID 过滤、安全控制等功能。它是内核运行时性能分析、延迟追踪和调试的关键组件。

## 2. 核心功能

### 主要数据结构

- **`struct ftrace_ops`**  
  表示一个函数跟踪操作对象，包含回调函数 `func`、标志位 `flags`、私有数据 `private`、哈希过滤器 `func_hash` 等，用于定制跟踪行为。

- **`ftrace_ops_list`**  
  全局 RCU 保护的 `ftrace_ops` 链表头，所有注册的跟踪操作都链接在此链表中。

- **`ftrace_trace_function`**  
  全局函数指针，指向当前实际执行的跟踪回调函数（如 `ftrace_stub`、`ftrace_ops_list_func` 等）。

- **`function_trace_op`**  
  当前生效的 `ftrace_ops` 实例指针，供汇编层 trampoline 使用。

- **`ftrace_list_end`**  
  链表终止哨兵节点，其 `func` 为 `ftrace_stub`（空操作）。

- **`global_ops`**  
  全局默认的 `ftrace_ops` 实例。

### 主要函数

- **`update_ftrace_function()`**  
  核心调度函数，根据当前注册的 `ftrace_ops` 数量和属性，动态选择最优的跟踪回调路径（直接调用 or 列表遍历）。

- **`ftrace_pid_func()`**  
  PID 过滤包装函数，仅当当前进程 PID 匹配配置时才调用原始跟踪回调。

- **`ftrace_ops_get_list_func()`**  
  根据 `ops` 的标志位决定是否必须使用 `ftrace_ops_list_func`（支持动态/RCU/强制列表模式）。

- **`ftrace_pids_enabled()`**  
  检查指定 `ftrace_ops` 是否启用了 PID 过滤功能。

- **`ftrace_ops_init()`**  
  初始化 `ftrace_ops` 的内部结构（如哈希锁、子操作链表）。

- **`add_ftrace_ops()`**（部分实现）  
  将新的 `ftrace_ops` 安全地插入到全局链表中（使用 RCU）。

- **`ftrace_kill()`**  
  在检测到严重异常时禁用 ftrace（通过设置 `ftrace_disabled`）。

## 3. 关键实现

### 动态函数跟踪调度机制

- 当无 `ftrace_ops` 注册时，使用 `ftrace_stub`（空函数）。
- 当仅有一个非动态、非 RCU、支持直接调用的 `ftrace_ops` 时，直接跳转其回调函数以提升性能。
- 否则统一使用 `ftrace_ops_list_func` 遍历所有注册的 `ops` 并依次调用。

### 安全与一致性保障

- 使用 **RCU** 保护 `ftrace_ops_list` 的读取，确保遍历安全。
- 使用 **`ftrace_lock` 互斥锁** 保护链表修改和状态更新。
- 在 **非动态跟踪（`!CONFIG_DYNAMIC_FTRACE`）** 模式下，通过 `synchronize_rcu_tasks_rude()` 和 `smp_call_function()` 确保所有 CPU 同步切换跟踪函数，避免竞态。

### PID 过滤机制

- 通过 `ftrace_ops` 的 `private` 字段关联 `trace_array`。
- 在 `ftrace_pid_func` 中检查当前 CPU 的 `ftrace_ignore_pid` 状态：
  - `FTRACE_PID_IGNORE`：跳过跟踪。
  - `FTRACE_PID_TRACE`：跟踪所有进程。
  - 其他值：仅跟踪指定 PID 的进程。

### 错误处理

- 定义 `FTRACE_WARN_ON()` 和 `FTRACE_WARN_ON_ONCE()` 宏，在触发 `WARN_ON` 时自动调用 `ftrace_kill()` 禁用 ftrace，防止系统崩溃。

### 构建时配置支持

- **`CONFIG_DYNAMIC_FTRACE`**：启用动态修改调用点指令（如将 `mcount` 替换为 NOP）。
- **`CONFIG_DYNAMIC_FTRACE_WITH_CALL_OPS`**：支持在调用点直接传递 `ftrace_ops`，避免额外 trampoline。
- 提供 `ftrace_list_ops` 和 `ftrace_nop_ops` 作为特殊 stub，用于列表调用和禁用状态。

## 4. 依赖关系

- **架构相关代码**：依赖 `asm/sections.h`、`asm/setup.h` 及架构特定的 trampoline（如 `ftrace_caller`）。
- **内核基础组件**：
  - RCU（`rcupdate.h`）
  - 调度器（`sched/task.h`）
  - 内存管理（`slab.h`）
  - 模块系统（`module.h`）
  - 安全框架（`security.h`）
- **跟踪子系统**：
  - `tracefs`（提供用户空间接口）
  - `trace_output.h`、`trace_stat.h`（跟踪输出与统计）
  - `ftrace_internal.h`（内部辅助函数）
- **事件跟踪**：集成 `trace/events/sched.h` 事件。

## 5. 使用场景

- **内核性能分析**：通过 `/sys/kernel/tracing/` 接口启用函数跟踪，分析函数调用开销。
- **延迟调试**：结合 `wakeup`、`irqsoff` 等 tracer 定位调度或中断延迟。
- **安全监控**：通过 `ftrace_ops` 注册自定义回调，监控敏感函数调用。
- **动态插桩**：在运行时启用/禁用特定函数的跟踪，无需重启系统。
- **PID 过滤跟踪**：仅跟踪特定进程的函数调用路径，用于应用行为分析。
- **内核开发调试**：开发者通过 `ftrace` 快速验证函数执行流和时序。