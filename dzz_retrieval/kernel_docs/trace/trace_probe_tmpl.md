# trace\trace_probe_tmpl.h

> 自动生成时间: 2025-10-25 17:34:21
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_probe_tmpl.h`

---

# `trace/trace_probe_tmpl.h` 技术文档

## 1. 文件概述

`trace/trace_probe_tmpl.h` 是 Linux 内核动态追踪（ftrace/kprobe/uprobe）子系统中的一个内联函数模板头文件，主要用于实现 **trace probe 参数提取（fetch）机制**。该文件提供了一系列内联函数，用于从内核或用户空间中提取、转换、存储探针（probe）触发时的参数值（如寄存器值、内存内容、字符串、符号名等），并支持动态数据（如字符串）的处理和位域操作。这些函数被 `kprobe` 和 `uprobe` 的 trace event 实现所复用，是构建动态追踪事件参数处理逻辑的核心组件。

## 2. 核心功能

### 主要内联函数

- **`fetch_store_raw`**  
  根据指令指定的大小（1/2/4/8 字节或默认 `unsigned long`），将原始数值写入目标缓冲区。

- **`fetch_apply_bitfield`**  
  对已存储的值应用位域操作（左移 `lshift` 后右移 `rshift`），用于提取结构体中的位字段。

- **`process_common_fetch_insn`**  
  处理第一阶段的 fetch 指令（立即数、当前进程名、数据指针）。

- **`process_fetch_insn_bottom`**  
  **核心函数**：实现完整的四阶段参数提取流程（解引用、存储、位域修改、数组循环）。

- **`fetch_store_string` / `fetch_store_string_user`**  
  从内核/用户空间读取以 null 结尾的字符串并存储。

- **`fetch_store_strlen` / `fetch_store_strlen_user`**  
  计算内核/用户空间字符串长度（不含终止符）。

- **`fetch_store_symstring` / `fetch_store_symstrlen`**  
  将地址转换为符号名（如 `func+0x10/0x100`）并存储或计算其长度。

- **`__get_data_size`**  
  遍历所有动态参数（如字符串），计算所需动态数据区总大小。

- **`store_trace_args`**  
  遍历所有参数，调用 `process_fetch_insn` 提取并存储到 trace 记录中。

### 关键数据结构（隐式依赖）

- **`struct fetch_insn`**  
  fetch 指令结构体，包含操作码（`op`）、偏移量（`offset`）、大小（`size`）、立即数（`immediate`）等字段，用于描述如何提取参数。

- **`struct trace_probe`**  
  trace probe 描述符，包含参数数量（`nr_args`）、参数数组（`args`）等。

- **`struct probe_arg`**  
  单个参数描述，包含 fetch 指令链（`code`）、偏移（`offset`）、是否为动态类型（`dynamic`）等。

## 3. 关键实现

### 四阶段参数提取流程（`process_fetch_insn_bottom`）

1. **第一阶段（由调用者处理）**：  
   通过 `process_common_fetch_insn` 获取初始值（如寄存器值、立即数等）。

2. **第二阶段（解引用）**：  
   循环处理 `FETCH_OP_DEREF`（内核空间）或 `FETCH_OP_UDEREF`（用户空间）指令，从地址读取指针值，支持多级解引用。

3. **第三阶段（存储）**：  
   根据操作码将值存入缓冲区：
   - `ST_RAW`：直接存储原始值
   - `ST_MEM`/`ST_UMEM`：从内存读取固定大小数据
   - `ST_STRING`/`ST_USTRING`/`ST_SYMSTR`：处理动态字符串（使用 data location 机制）

4. **第四阶段（位域修改）**：  
   若存在 `FETCH_OP_MOD_BF` 指令，对存储值应用位域掩码。

5. **数组处理**：  
   若存在 `FETCH_OP_LP_ARRAY` 指令，循环处理数组元素，动态更新目标地址和值地址。

### 动态数据处理机制

- **Data Location 机制**：  
  动态数据（如字符串）不直接存入主记录，而是在主记录中存储一个 32 位的 **data location** 值（高 16 位为长度，低 16 位为相对于 base 的偏移）。
- **两阶段处理**：  
  1. **预计算阶段**（`dest == NULL`）：调用 `process_fetch_insn` 仅计算所需动态数据大小
  2. **存储阶段**：分配动态数据区，实际存储字符串内容

### 内存安全访问

- 使用 `probe_mem_read` 和 `probe_mem_read_user` 安全读取内核/用户内存，避免因无效地址导致系统崩溃。
- 所有函数标记为 `nokprobe_inline`，确保可在 kprobe 上下文中安全执行。

## 4. 依赖关系

- **依赖头文件**：
  - `<linux/kernel.h>`：基础内核 API
  - `<linux/uaccess.h>`：用户空间内存访问（`probe_mem_read_user`）
  - `<linux/kallsyms.h>`：符号解析（`sprint_symbol`）
  - `trace_probe.h`：`struct trace_probe`、`struct probe_arg`、`struct fetch_insn` 等定义
  - `trace.h`：trace event 相关宏和函数

- **被依赖模块**：
  - `kernel/trace/trace_kprobe.c`：kprobe trace event 实现
  - `kernel/trace/trace_uprobe.c`：uprobe trace event 实现
  - 其他基于 trace probe 的动态追踪模块

## 5. 使用场景

- **动态追踪事件参数捕获**：  
  当用户通过 ftrace 接口（如 `/sys/kernel/debug/tracing/kprobe_events`）定义带有参数的 kprobe/uprobe 事件时，内核使用此文件中的函数提取指定参数值。

- **复杂参数类型支持**：  
  支持提取结构体成员（通过偏移和解引用）、位域、字符串、符号地址等复杂数据类型。

- **用户空间和内核空间统一处理**：  
  通过 `*_user` 系列函数，统一处理内核探针和用户空间探针（uprobe）的参数提取逻辑。

- **高效内存管理**：  
  通过 data location 机制和两阶段处理，高效管理变长数据（如字符串）的存储，避免 trace buffer 浪费。