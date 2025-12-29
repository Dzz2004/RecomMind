# trace\ftrace_internal.h

> 自动生成时间: 2025-10-25 17:03:34
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\ftrace_internal.h`

---

# `trace/ftrace_internal.h` 技术文档

## 1. 文件概述

`ftrace_internal.h` 是 Linux 内核 ftrace（Function Tracer）子系统的核心内部头文件，定义了 ftrace 功能模块间共享的内部接口、数据结构和辅助函数。该文件主要用于协调动态函数追踪（`CONFIG_DYNAMIC_FTRACE`）、函数图追踪（`CONFIG_FUNCTION_GRAPH_TRACER`）等子系统的内部操作，提供统一的注册/注销机制和状态管理接口，**不对外暴露给普通内核模块使用**。

## 2. 核心功能

### 函数接口

- `__register_ftrace_function(struct ftrace_ops *ops)`  
  内部注册 ftrace 操作集，供 ftrace 框架调用。
  
- `__unregister_ftrace_function(struct ftrace_ops *ops)`  
  内部注销 ftrace 操作集。

- `ftrace_startup(struct ftrace_ops *ops, int command)`  
  启用指定的 ftrace 操作集，根据是否启用 `CONFIG_DYNAMIC_FTRACE` 有不同的实现。

- `ftrace_shutdown(struct ftrace_ops *ops, int command)`  
  停用指定的 ftrace 操作集。

- `ftrace_ops_test(struct ftrace_ops *ops, unsigned long ip, void *regs)`  
  测试当前 ftrace 操作集是否应处理指定指令指针（IP）处的函数调用。

- `ftrace_startup_subops / ftrace_shutdown_subops`  
  用于管理嵌套或子 ftrace 操作集的启停（仅在动态 ftrace 启用时有效）。

- `fgraph_update_pid_func(void)`  
  更新函数图追踪中与当前进程 PID 相关的过滤逻辑。

### 全局变量

- `ftrace_lock`（`mutex` 类型）  
  保护 ftrace 全局状态的互斥锁，防止并发修改。

- `global_ops`（`struct ftrace_ops` 类型）  
  全局默认的 ftrace 操作集，通常用于基础追踪功能。

- `ftrace_graph_active`（`int` 类型）  
  标志位，表示函数图追踪（function graph tracer）是否处于激活状态。

## 3. 关键实现

- **条件编译支持**：  
  文件大量使用 `#ifdef CONFIG_*` 宏，根据内核配置动态包含或排除代码。例如：
  - 若未启用 `CONFIG_DYNAMIC_FTRACE`，`ftrace_startup/shutdown` 被实现为宏，直接调用注册/注销函数并更新 `FTRACE_OPS_FL_ENABLED` 标志。
  - 若启用 `CONFIG_DYNAMIC_FTRACE`，则提供完整的函数实现，支持更复杂的动态插桩逻辑。

- **ftrace_ops_test 的简化处理**：  
  在非动态 ftrace 模式下，`ftrace_ops_test` 直接返回 `1`，表示所有函数调用均应被追踪，因为此时无法进行细粒度过滤。

- **子操作集（subops）支持**：  
  在动态 ftrace 模式下，支持对主 `ftrace_ops` 下挂载的子操作集进行独立启停控制，用于实现如 per-CPU 或 per-task 的追踪策略。

- **函数图追踪集成**：  
  通过 `ftrace_graph_active` 和 `fgraph_update_pid_func` 实现与函数图追踪器的联动，确保在启用图追踪时能正确更新 PID 过滤逻辑。

## 4. 依赖关系

- **依赖配置选项**：
  - `CONFIG_FUNCTION_TRACER`：基础函数追踪支持。
  - `CONFIG_DYNAMIC_FTRACE`：动态函数追踪（运行时修改函数入口）。
  - `CONFIG_FUNCTION_GRAPH_TRACER`：函数调用图追踪（记录函数进入/返回）。

- **依赖头文件/模块**：
  - 依赖 `ftrace.h` 中定义的 `struct ftrace_ops` 和相关标志（如 `FTRACE_OPS_FL_ENABLED`）。
  - 与 `kernel/trace/ftrace.c` 紧密耦合，该文件实现了上述声明的函数。
  - 函数图追踪相关逻辑依赖 `kernel/trace/fgraph.c`。

- **被调用方**：
  - 主要被 ftrace 核心代码（如 `ftrace.c`、`trace.c`）及特定 tracer（如 function tracer、graph tracer）内部使用。

## 5. 使用场景

- **ftrace 框架初始化/销毁**：  
  在 tracer 注册或取消注册时，通过 `ftrace_startup/shutdown` 启停追踪逻辑。

- **动态追踪控制**：  
  当用户通过 debugfs 接口（如 `/sys/kernel/debug/tracing/`）启用/禁用特定追踪器时，内核调用这些内部接口更新追踪状态。

- **函数图追踪激活**：  
  当启用函数图追踪时，`fgraph_update_pid_func` 被调用以同步 PID 过滤设置，确保仅追踪目标进程。

- **多操作集管理**：  
  在复杂追踪场景（如同时启用多个 tracer 或使用 eBPF fentry/fexit）中，通过 `subops` 机制管理不同追踪上下文的生命周期。