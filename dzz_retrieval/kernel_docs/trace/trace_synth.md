# trace\trace_synth.h

> 自动生成时间: 2025-10-25 17:38:50
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_synth.h`

---

# `trace/trace_synth.h` 技术文档

## 1. 文件概述

`trace/trace_synth.h` 是 Linux 内核动态追踪子系统中的头文件，用于定义合成事件（synthetic events）相关的数据结构和接口。合成事件是一种用户可动态创建的追踪事件，允许将多个现有追踪事件字段组合成新的虚拟事件，用于高级追踪、过滤和分析场景。该文件为合成事件的定义、管理和使用提供基础支持。

## 2. 核心功能

### 宏定义
- `SYNTH_SYSTEM`：定义合成事件所属的事件系统名称，固定为 `"synthetic"`。
- `SYNTH_FIELDS_MAX`：限制单个合成事件中最多可包含的字段数量（64 个）。
- `STR_VAR_LEN_MAX`：定义字符串类型字段的最大长度，其值等于 `MAX_FILTER_STR_VAL`，且必须是 `sizeof(u64)` 的整数倍，以保证内存对齐。

### 数据结构
- `struct synth_field`：描述合成事件中的单个字段。
  - `type`：字段的 C 类型字符串（如 `"int"`、`"char *"`）。
  - `name`：字段名称。
  - `size`：字段在内存中的字节大小。
  - `offset`：该字段在事件数据结构中的偏移量。
  - `field_pos`：字段在字段数组中的位置索引。
  - `is_signed`：指示该字段是否为有符号类型。
  - `is_string`：指示该字段是否为字符串类型。
  - `is_dynamic`：指示该字段是否为动态分配类型（如动态字符串）。
  - `is_stack`：指示该字段是否来自内核栈追踪信息。

- `struct synth_event`：表示一个完整的合成事件。
  - `devent`：嵌入的动态事件结构，用于统一管理动态事件（如 kprobe、uprobe、synth 等）。
  - `ref`：引用计数，用于生命周期管理。
  - `name`：合成事件的名称。
  - `fields`：指向所有字段指针的数组。
  - `n_fields`：字段总数。
  - `dynamic_fields`：仅包含动态字段（如字符串）的子数组。
  - `n_dynamic_fields`：动态字段数量。
  - `n_u64`：事件数据所需 `u64` 单元的数量（用于对齐和分配）。
  - `class`：关联的 `trace_event_class`，用于事件格式描述。
  - `call`：关联的 `trace_event_call`，用于注册到追踪系统。
  - `tp`：对应的 `tracepoint` 结构，用于触发事件。
  - `mod`：指向创建该事件的内核模块（若由模块创建）。

### 外部函数声明
- `find_synth_event(const char *name)`：根据名称查找已注册的合成事件，返回对应的 `struct synth_event *` 指针，若未找到则返回 `NULL`。

## 3. 关键实现

- **字段对齐与内存布局**：合成事件的数据结构在运行时动态构建，字段按 `u64` 对齐。字符串字段虽逻辑上为变长，但实际存储时通过固定长度缓冲区（`STR_VAR_LEN_MAX`）实现，并要求长度为 `u64` 的倍数，以确保事件记录在 ring buffer 中正确对齐。
  
- **动态字段处理**：`is_dynamic` 字段用于标识需要特殊处理的字段（如字符串），这些字段在事件触发时需额外分配或复制数据。`dynamic_fields` 数组便于在事件生成时快速遍历和处理动态内容。

- **事件生命周期管理**：通过 `ref` 引用计数与 `dyn_event` 机制集成，支持动态创建和销毁合成事件，避免内存泄漏。

- **与 trace_event 集成**：每个 `synth_event` 内嵌 `trace_event_class` 和 `trace_event_call`，使其能无缝接入内核的通用追踪事件框架（如 ftrace、perf），支持通过 `/sys/kernel/debug/tracing/` 接口进行配置和读取。

## 4. 依赖关系

- **`trace_dynevent.h`**：提供 `struct dyn_event` 定义，使合成事件能作为动态事件的一种类型被统一管理。
- **追踪子系统核心组件**：依赖 `trace_events`、`tracepoint` 等机制，用于事件注册、触发和输出。
- **内存管理**：依赖内核通用内存分配器（如 `kmalloc`）进行字段和事件结构的动态分配。
- **字符串过滤支持**：`STR_VAR_LEN_MAX` 依赖 `MAX_FILTER_STR_VAL`，该值在过滤子系统中定义，用于限制字符串比较的最大长度。

## 5. 使用场景

- **动态追踪脚本**：用户可通过 `synthetic` 事件系统，在运行时组合多个现有追踪点的字段（如从 `sched_switch` 和 `sys_enter` 中提取 PID、comm、syscall 号等），创建自定义的复合事件，用于复杂场景分析。
  
- **性能分析工具集成**：perf、ftrace 等工具可利用合成事件减少原始事件数量，提升分析效率。例如，将多个低层事件聚合为高层语义事件。

- **内核调试与监控**：开发人员可在不修改内核代码的前提下，通过合成事件快速构建特定监控逻辑，用于调试竞态条件、资源泄漏等问题。

- **安全审计**：结合动态字段（如路径名、命令行参数），合成事件可用于构建细粒度的安全审计规则，监控敏感系统调用序列。