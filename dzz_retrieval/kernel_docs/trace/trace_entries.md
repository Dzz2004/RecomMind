# trace\trace_entries.h

> 自动生成时间: 2025-10-25 17:16:26
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_entries.h`

---

# `trace/trace_entries.h` 技术文档

## 1. 文件概述

`trace/trace_entries.h` 是 Linux 内核 ftrace（Function Tracer）子系统的核心头文件之一，用于定义写入环形缓冲区（ring buffer）的各类跟踪事件（trace event）的数据结构。该文件通过一组宏（如 `FTRACE_ENTRY`、`FTRACE_ENTRY_PACKED` 等）自动生成结构体定义、事件 ID、格式描述及打印函数，确保事件格式与内核代码同步，并自动更新用户空间可见的 `format` 文件。此机制简化了跟踪事件的维护，避免手动同步结构体与格式描述的错误。

## 2. 核心功能

### 主要跟踪事件结构体（通过宏定义生成）

| 事件名称 | 结构体名 | 事件 ID | 功能说明 |
|--------|--------|--------|--------|
| `function` | `ftrace_entry` | `TRACE_FN` | 记录函数调用：函数地址（`ip`）与调用者地址（`parent_ip`） |
| `funcgraph_entry` | `ftrace_graph_ent_entry` | `TRACE_GRAPH_ENT` | 函数图跟踪入口：记录函数地址与调用深度 |
| `funcgraph_exit` | `ftrace_graph_ret_entry` | `TRACE_GRAPH_RET` | 函数图跟踪返回：记录函数地址、返回值（可选）、调用/返回时间、深度、溢出计数等 |
| `context_switch` | `ctx_switch_entry` | `TRACE_CTX` | 上下文切换事件：记录切换前后任务的 PID、优先级、状态及目标 CPU |
| `wakeup` | （复用 `ctx_switch_entry`） | `TRACE_WAKE` | 任务唤醒事件：与上下文切换共享结构，仅打印格式不同 |
| `kernel_stack` | `stack_entry` | `TRACE_STACK` | 内核栈回溯：记录最多 8 层调用地址 |
| `user_stack` | `userstack_entry` | `TRACE_USER_STACK` | 用户栈回溯：记录用户空间调用栈（固定 8 层） |
| `bprint` | `bprint_entry` | `TRACE_BPRINT` | 二进制格式化打印：记录 IP、格式字符串及动态参数缓冲区 |
| `print` | `print_entry` | `TRACE_PRINT` | 普通格式化打印：记录 IP 与动态字符串缓冲区 |
| `raw_data` | `raw_data_entry` | `TRACE_RAW_DATA` | 原始数据记录：带 ID 的任意二进制数据 |
| `bputs` | `bputs_entry` | `TRACE_BPUTS` | 二进制字符串输出：记录 IP 与静态字符串指针 |
| `mmiotrace_rw` | `trace_mmiotrace_rw` | `TRACE_MMIO_RW` | MMIO 读写操作跟踪 |
| `mmiotrace_map` | `trace_mmiotrace_map` | `TRACE_MMIO_MAP` | MMIO 映射操作跟踪 |

### 关键宏定义

- `FTRACE_ENTRY(name, struct_name, id, structure, print)`：定义标准跟踪事件。
- `FTRACE_ENTRY_PACKED(...)`：用于包含嵌套结构体的事件，使用 `__field_packed` 描述内部字段。
- `FTRACE_ENTRY_DUP(name, struct_name, id, structure, print)`：复用已有结构体，仅生成新的事件 ID 和格式文件。
- `__field(type, item)`：定义普通字段。
- `__array(type, item, size)`：定义固定大小数组。
- `__dynamic_array(type, item)`：定义动态大小数组（实际存储在结构体末尾）。
- `__stack_array(type, item, max, size_field)`：专用于栈回溯的动态数组。
- `__field_struct(type, item)`：声明嵌套结构体字段（不在格式文件中展开）。
- `__field_desc(type, container, item)` / `__array_desc(...)`：描述嵌套结构体中的字段。

## 3. 关键实现

### 宏驱动的结构体生成
所有跟踪事件结构体均由宏展开生成，确保：
- 结构体内存布局与环形缓冲区写入一致；
- `format` 文件内容（字段类型、偏移、大小）自动同步；
- 编译时检查嵌套结构体描述与实际定义的一致性（若不一致将导致编译错误）。

### 嵌套结构体处理
对于如 `ftrace_graph_ent`、`mmiotrace_rw` 等内核内部结构体，使用 `__field_struct` 声明容器字段，并通过 `__field_packed`（或 `__field_desc`）逐字段描述其内容。这种方式既保留了原始结构语义，又使跟踪系统能正确解析字段。

### 动态数组支持
`__dynamic_array` 允许事件携带变长数据（如 `print_entry` 的字符串），实际存储时结构体末尾附加数据，长度由写入时决定。`__stack_array` 是其特化形式，用于栈回溯，通过 `size` 字段记录实际层数。

### 条件编译支持
`funcgraph_exit` 事件根据 `CONFIG_FUNCTION_GRAPH_RETVAL` 配置决定是否包含 `retval` 字段，体现内核配置对跟踪数据粒度的影响。

### 事件复用机制
`wakeup` 事件通过 `FTRACE_ENTRY_DUP` 复用 `ctx_switch_entry` 结构体，仅改变事件 ID 和打印格式，避免重复定义，节省内存并保持数据一致性。

## 4. 依赖关系

- **依赖头文件**：  
  - `linux/tracepoint.h`（隐式，通过 `ftrace.h` 等包含）  
  - `linux/perf_event.h`（用于 `perf_ftrace_event_register` 回调）  
  - `linux/mm.h`（`mmiotrace` 相关类型如 `resource_size_t`）  
  - `trace.h` / `ftrace.h`（提供 `FTRACE_ENTRY` 等宏定义及事件 ID 枚举）

- **被依赖模块**：  
  - **ftrace 核心**（`kernel/trace/ftrace.c`）：使用这些结构体写入环形缓冲区。  
  - **跟踪事件系统**（`kernel/trace/trace.c`）：解析事件 ID，调用对应打印函数。  
  - **perf 工具**：通过 `perf_ftrace_event_register` 注册回调，支持 perf 与 ftrace 交互。  
  - **MMIO 跟踪模块**（`drivers/char/mmtimer.c` 等）：使用 `mmiotrace_rw/map` 事件。

## 5. 使用场景

- **函数跟踪**：通过 `function`、`funcgraph_entry/exit` 事件实现函数调用图分析，用于性能剖析或调试。
- **调度分析**：`context_switch` 和 `wakeup` 事件用于分析任务切换、延迟及调度器行为。
- **栈回溯**：`kernel_stack`/`user_stack` 用于在特定事件（如中断、系统调用）时捕获调用栈。
- **调试输出**：`print`/`bprint`/`bputs` 支持内核开发者使用 `trace_printk()` 输出调试信息到跟踪缓冲区。
- **硬件访问跟踪**：`mmiotrace` 事件用于监控设备 MMIO 读写和映射操作，辅助设备驱动调试。
- **原始数据记录**：`raw_data` 用于自定义二进制数据记录，适用于特定子系统（如安全监控、硬件状态快照）。