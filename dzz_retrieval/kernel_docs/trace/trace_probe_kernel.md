# trace\trace_probe_kernel.h

> 自动生成时间: 2025-10-25 17:33:44
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_probe_kernel.h`

---

# `trace/trace_probe_kernel.h` 技术文档

## 1. 文件概述

`trace_probe_kernel.h` 是 Linux 内核动态追踪子系统中的一个辅助头文件，主要用于提供在内核探针（如 kprobe、eprobe）上下文中安全地从内核或用户空间读取字符串和内存数据的通用内联函数。该文件特别关注在探针处理路径（probe context）中避免触发递归探针（通过 `nokprobe_inline` 限定），并支持跨地址空间（内核/用户）的数据读取，同时处理地址空间重叠架构与非重叠架构的差异。

## 2. 核心功能

文件中定义了以下主要内联函数：

- **字符串长度获取**：
  - `fetch_store_strlen_user()`：从用户空间安全读取以 null 结尾的字符串长度（含终止符）。
  - `fetch_store_strlen()`：自动判断地址空间，从内核或用户空间读取字符串长度。

- **字符串内容读取**：
  - `fetch_store_string_user()`：从用户空间安全拷贝 null-terminated 字符串到目标缓冲区。
  - `fetch_store_string()`：自动判断地址空间，从内核或用户空间拷贝字符串。

- **通用内存读取**：
  - `probe_mem_read_user()`：从用户空间安全读取任意内存块。
  - `probe_mem_read()`：自动判断地址空间，安全读取内核或用户空间内存。

- **辅助函数**：
  - `set_data_loc()`：根据读取结果设置动态追踪中的“数据位置”（data location）字段，用于支持变长数据（如字符串）在追踪事件中的高效存储。

> 所有函数均使用 `nokprobe_inline` 修饰，确保不会在探针上下文中被再次探测。

## 3. 关键实现

### 地址空间自动识别
通过 `CONFIG_ARCH_HAS_NON_OVERLAPPING_ADDRESS_SPACE` 宏判断当前架构是否具有非重叠的内核/用户地址空间（如 x86_64）。若定义该宏且地址小于 `TASK_SIZE`，则视为用户空间地址，调用用户空间专用读取函数（如 `strnlen_user_nofault`、`strncpy_from_user_nofault`）；否则视为内核地址，使用内核空间安全读取函数（如 `copy_from_kernel_nofault`）。

### 安全内存访问
所有内存读取操作均使用 `_nofault` 系列函数（如 `copy_from_kernel_nofault`、`strncpy_from_user_nofault`），这些函数在访问非法或不可用地址时不会导致内核 oops，而是返回错误码，确保探针执行的健壮性。

### 动态数据位置编码
字符串等变长数据在追踪事件中不直接内联存储，而是采用“数据位置”（data location）机制：
- 使用 `get_loc_len()` 从 `u32` 字段中提取预分配的最大长度。
- 使用 `get_loc_data()` 计算实际数据存储地址（相对于事件记录基地址 `base` 的偏移）。
- 通过 `make_data_loc(len, offset)` 将长度和偏移编码回 `u32` 字段，供后续解析使用。
- `set_data_loc()` 封装了该逻辑，并处理读取失败（`ret < 0`）时将长度置零。

### 字符串读取容错
`fetch_store_string()` 在读取内核字符串时注释指出“字符串可能在探测过程中被修改”，因此使用 `strncpy_from_kernel_nofault` 而非简单 `strncpy`，以容忍并发修改导致的不一致，避免崩溃。

## 4. 依赖关系

- **前置头文件依赖**：  
  本文件**不能直接包含** `trace_probe.h`，但其功能依赖于该头文件中定义的宏和函数（如 `get_loc_len`、`get_loc_data`、`make_data_loc`、`MAX_STRING_SIZE`）。因此，任何包含本文件的源文件**必须先包含 `trace_probe.h`**。

- **架构依赖**：  
  依赖 `CONFIG_ARCH_HAS_NON_OVERLAPPING_ADDRESS_SPACE` 配置选项，该选项在具有分离用户/内核地址空间的架构（如 x86、ARM64）上定义，在重叠地址空间架构（如某些 32 位 ARM）上未定义。

- **内核 API 依赖**：  
  依赖以下内核安全访问函数：
  - `strnlen_user_nofault()`
  - `strncpy_from_user_nofault()`
  - `copy_from_user_nofault()`
  - `copy_from_kernel_nofault()`
  - `strncpy_from_kernel_nofault()`

- **使用模块**：  
  主要被 `trace_kprobe.c` 和 `trace_eprobe.c` 通过 `trace_probe_tmpl.h` 模板机制间接使用，为 kprobe 和 eprobe 提供统一的数据获取接口。

## 5. 使用场景

该头文件主要用于 Linux 内核的 **ftrace 动态事件追踪系统** 中，具体场景包括：

- **Kprobe 事件定义**：当用户通过 `echo 'p:myprobe kernel_func +0(%di):string' > /sys/kernel/debug/tracing/kprobe_events` 定义一个捕获字符串参数的 kprobe 时，内核在触发探针时会调用 `fetch_store_string()` 从寄存器指向的地址（可能是内核或用户空间）安全读取字符串。

- **Eprobe（Event Probe）事件**：类似 kprobe，用于附加到 tracepoint 或 ftrace function 事件上，并提取其参数中的字符串。

- **用户空间参数追踪**：当被探测的内核函数接收用户空间指针（如系统调用参数）时，探针需通过 `_user` 系列函数安全访问用户内存。

- **内核数据结构字段提取**：探针可读取内核数据结构中的字符串字段（如 `task_struct->comm`），此时调用非 `_user` 版本函数。

所有操作均在中断上下文或 NMI 安全的探针处理路径中执行，因此必须避免睡眠、页错误和递归探针，本文件的设计完全满足这些约束。