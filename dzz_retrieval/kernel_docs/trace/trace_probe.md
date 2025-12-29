# trace\trace_probe.c

> 自动生成时间: 2025-10-25 17:33:07
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_probe.c`

---

# trace_probe.c 技术文档

## 文件概述

`trace/trace_probe.c` 是 Linux 内核中用于实现基于探针（probe-based）动态事件（Dynamic events）的通用核心代码。该文件为 kprobe 和 uprobe 等动态追踪机制提供共享的基础设施，包括参数类型解析、数据提取、格式化输出、错误日志记录以及事件名称解析等功能。其目标是抽象出 probe 事件处理中的共性逻辑，避免在不同 probe 类型（如 kprobe/uprobe）中重复实现。

## 核心功能

### 主要数据结构

- **`probe_fetch_types[]`**：定义了所有支持的数据提取类型（fetch types），包括基本整型（u8/s32 等）、十六进制表示（x8/x64）、字符串（string/ustring/symstr）和符号地址（symbol）等。
- **`trace_probe_log`**：用于在解析动态事件命令时记录上下文（子系统名、参数列表、当前处理索引），以便在出错时生成带位置信息的错误日志。
- **`reserved_field_names[]`**：列出在动态事件中保留的关键字段名（如 `common_pid`、`common_type` 等），防止用户自定义字段与之冲突。

### 主要函数

- **`find_fetch_type()`**：根据类型字符串（如 "u32"、"string"）查找对应的 `fetch_type` 描述符，支持位域（bitfield）语法（如 `b8/32`）。
- **`traceprobe_split_symbol_offset()`**：将形如 `"func+0x10"` 的符号字符串拆分为函数名和偏移量。
- **`traceprobe_parse_event_name()`**：解析事件名称字符串（如 `"group/event"` 或 `"event"`），提取组名和事件名，并进行合法性校验。
- **`trace_probe_log_*()` 系列函数**：初始化、清除、设置索引和记录错误日志，用于动态事件命令解析过程中的错误定位。
- **`PRINT_TYPE_FUNC_NAME()` 宏生成的打印函数**：如 `print_u32()`、`print_string()` 等，用于将提取的数据按指定格式输出到 trace buffer。
- **`parse_trace_event_arg()`**：在已注册的 trace event 字段中查找匹配的参数名，用于支持从已有事件中引用字段。

## 关键实现

### 类型系统与数据提取

- 通过 `probe_fetch_types` 数组统一管理所有支持的数据类型，每种类型包含：
  - 名称（如 "u32"）
  - 对应的打印函数指针
  - 格式字符串
  - 存储大小
  - 是否为符号类型
  - 是否使用 `__data_loc`（用于变长数据如字符串）
- 字符串类型（`string`/`ustring`/`symstr`）使用 `__data_loc` 机制：实际数据不直接存放在事件记录中，而是存储偏移量，通过 `get_loc_data()` 在打印时动态定位。
- 位域类型（如 `b8/32`）在解析时被映射到对应的无符号整型（u8/u16/u32/u64）。

### 错误日志与用户反馈

- 使用 `trace_probe_log` 全局结构体在解析动态事件命令（如 `echo 'p:mygroup/myevent func arg1=%ax' > /sys/kernel/debug/tracing/kprobe_events`）时记录参数上下文。
- 当解析失败时，`__trace_probe_log_err()` 会重组原始命令字符串，并根据当前处理位置（`index` + `offset`）高亮错误位置，调用 `tracing_log_err()` 向用户空间返回带位置指示的错误信息。

### 事件命名规范

- 事件名格式支持 `group/event` 或纯 `event`。
- 组名和事件名均需通过 `is_good_system_name()` 和 `is_good_name()` 校验（仅允许字母、数字、下划线，且不能以数字开头）。
- 长度限制为 `MAX_EVENT_NAME_LEN`（通常为 64 字节）。

### 符号解析限制

- 在用户态探针（uprobes）上下文中，禁止使用 `symbol` 和 `symstr` 类型，因为内核无法直接解析用户空间符号。

## 依赖关系

- **头文件依赖**：
  - `trace_probe.h`：定义核心数据结构（如 `fetch_type`、`traceprobe_parse_context`）和宏。
  - `trace_btf.h`：提供 BTF（BPF Type Format）相关支持（用于高级参数类型推断）。
  - `linux/bpf.h`：BPF 子系统接口（可能用于 future 扩展）。
- **内核子系统依赖**：
  - **ftrace**：依赖 ftrace 的事件字段管理（`trace_get_fields()`）和序列化输出（`trace_seq_*`）。
  - **动态事件框架**：与 `dyn_event` 框架集成，受 `dyn_event_ops_mutex` 互斥锁保护。
  - **kprobe/uprobe**：作为底层探针机制的通用后端，被 `trace_kprobe.c` 和 `trace_uprobe.c` 调用。

## 使用场景

- **动态追踪事件注册**：当用户通过 debugfs 接口（如 `/sys/kernel/debug/tracing/kprobe_events`）添加 kprobe/uprobe 事件时，该文件负责解析事件定义中的参数类型、名称和提取规则。
- **事件数据格式化**：在追踪事件触发时，使用对应的打印函数（如 `print_u64()`）将捕获的数据转换为人类可读的字符串，写入 trace buffer。
- **错误诊断**：在用户输入非法事件定义时，提供精确的语法错误位置和类型提示，提升调试体验。
- **BTF 集成**（条件编译）：当启用 `CONFIG_PROBE_EVENTS_BTF_ARGS` 时，可利用 BTF 信息自动推断函数参数类型，简化事件定义。