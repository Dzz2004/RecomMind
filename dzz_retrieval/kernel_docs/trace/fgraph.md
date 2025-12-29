# trace\fgraph.c

> 自动生成时间: 2025-10-25 17:01:31
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\fgraph.c`

---

# `trace/fgraph.c` 技术文档

## 1. 文件概述

`trace/fgraph.c` 是 Linux 内核函数图跟踪（Function Graph Tracer）的核心实现文件，负责管理函数调用与返回的追踪基础设施。该模块通过在函数入口和返回点插入钩子，记录调用栈信息，支持内核函数执行路径的可视化分析。其核心机制依赖于一个“影子栈”（shadow stack），用于在不干扰正常栈结构的前提下，高效存储函数返回地址及相关元数据。

## 2. 核心功能

### 主要数据结构

- **`struct ftrace_ret_stack`**  
  表示函数调用帧的元数据结构，存储被替换的原始返回地址等信息。

- **`fgraph_array[FGRAPH_ARRAY_SIZE]`**  
  全局数组，用于注册多个 `fgraph_ops`（函数图操作集），每个元素对应一个追踪器实例。

- **`fgraph_lru_table[]`、`fgraph_lru_next`、`fgraph_lru_last`**  
  实现 LRU（Least Recently Used）策略的索引分配机制，用于动态管理 `fgraph_array` 中的可用槽位。

- **`fgraph_array_bitmask`**  
  位图，标记 `fgraph_array` 中哪些索引已被占用。

### 关键宏定义

- **`FGRAPH_FRAME_SIZE` / `FGRAPH_FRAME_OFFSET`**  
  定义 `ftrace_ret_stack` 结构体在影子栈中占用的字节数和 `long` 字长数。

- **影子栈布局相关宏**  
  - `SHADOW_STACK_SIZE`：影子栈总大小（1 页 = 4KB）
  - `SHADOW_STACK_OFFSET`：影子栈以 `long` 为单位的总长度
  - `SHADOW_STACK_MAX_OFFSET`：允许压入新帧的最大偏移（预留缓冲区）

- **元数据编码宏**  
  定义影子栈顶部控制字的位域布局：
  - `FGRAPH_FRAME_OFFSET_MASK`（位 0–9）：到前一个 `ftrace_ret_stack` 的偏移
  - `FGRAPH_TYPE`（位 10–11）：元数据类型（`BITMAP` 或 `DATA`）
  - `FGRAPH_INDEX`（位 12–27）：在 `BITMAP` 类型下表示哪些 `fgraph_ops` 需要回调
  - `FGRAPH_DATA`（位 12–17）与 `FGRAPH_DATA_INDEX`（位 18–23）：在 `DATA` 类型下分别表示附加数据大小和所属 `fgraph_ops` 索引

### 主要函数

- **`fgraph_lru_init()`**  
  初始化 LRU 索引表，将所有索引标记为可用。

- **`fgraph_lru_alloc_index()`**  
  从 LRU 表中分配一个未使用的 `fgraph_array` 索引。

- **`fgraph_lru_release_index(int idx)`**  
  释放指定索引回 LRU 表，并清除位图标记。

- **`__get_offset(unsigned long val)`**  
  从影子栈控制字中提取 `ftrace_ret_stack` 偏移量。

### 全局变量

- **`kill_ftrace_graph`**  
  静态跳转键（static key），用于在禁用函数图追踪时快速绕过相关逻辑。

- **`ftrace_graph_active`**  
  标记当前是否有活跃的函数图追踪器。

## 3. 关键实现

### 影子栈元数据编码机制

函数图追踪器在每次函数入口（`function_graph_enter()`）时，向当前任务的影子栈压入一个复合结构：

1. **`ftrace_ret_stack` 结构体**：保存原始返回地址。
2. **控制字（control word）**：位于结构体上方，编码以下信息：
   - 到前一个帧的偏移（用于栈回溯）
   - 类型标识（`BITMAP` 或 `DATA`）
   - 若为 `BITMAP` 类型，则包含一个 16 位掩码，指示 `fgraph_array` 中哪些追踪器需要在其返回时调用回调函数。
   - 若为 `DATA` 类型，则包含附加数据的大小（1–32 个 `long`）及其所属追踪器索引。

此设计允许多个追踪器共用同一影子栈，通过位图或专用数据区高效协作。

### LRU 索引管理

由于 `fgraph_array` 大小固定（16 项），系统使用 LRU 策略动态分配和回收索引：
- 初始化时，所有索引按顺序填入 `fgraph_lru_table`。
- 分配时从 `fgraph_lru_next` 取出索引并标记为 `-1`（已用）。
- 释放时将索引追加到 `fgraph_lru_last` 位置。
- 配合位图 `fgraph_array_bitmask` 快速判断索引状态。

该机制确保在追踪器频繁注册/注销时高效复用槽位。

### 安全边界控制

影子栈大小固定为一页（4KB），通过 `SHADOW_STACK_MAX_OFFSET` 预留缓冲区，防止帧压入时溢出。最大支持帧数受此限制，避免栈溢出风险。

## 4. 依赖关系

- **`<linux/ftrace.h>`**：提供函数追踪基础框架，包括 `ftrace_ops`、`fgraph_ops` 等接口。
- **`"ftrace_internal.h"` / `"trace.h"`**：内核追踪子系统内部头文件，定义共享数据结构和辅助函数。
- **`<trace/events/sched.h>`**：可能用于与调度事件集成（如任务切换时的追踪状态保存）。
- **`<linux/static_call.h>` / `<linux/jump_label.h>`**：支持运行时动态启用/禁用追踪逻辑，提升性能。
- **`<linux/slab.h>`**：用于动态内存分配（虽当前片段未直接使用，但追踪器注册可能涉及）。

## 5. 使用场景

- **内核函数执行流分析**：通过 `function_graph` tracer 可视化函数调用树，用于性能剖析或调试。
- **动态追踪工具支持**：为 `ftrace`、`perf` 等工具提供底层函数图追踪能力。
- **多追踪器协同**：允许多个子系统（如调度器、内存管理器）同时注册自己的 `fgraph_ops`，在函数返回时执行特定回调（如记录时间戳、采集上下文）。
- **低开销追踪**：利用静态跳转键（`kill_ftrace_graph`）在未启用时几乎零开销，启用后通过影子栈避免修改真实栈，保证系统稳定性。