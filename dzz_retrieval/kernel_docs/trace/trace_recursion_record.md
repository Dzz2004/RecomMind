# trace\trace_recursion_record.c

> 自动生成时间: 2025-10-25 17:34:54
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_recursion_record.c`

---

# `trace_recursion_record.c` 技术文档

## 1. 文件概述

`trace_recursion_record.c` 是 Linux 内核 ftrace（Function Tracer）子系统中的一个辅助模块，用于记录在函数追踪过程中检测到的递归调用（recursion）。当 ftrace 检测到某个函数在追踪上下文中被递归调用时，会调用本模块提供的 `ftrace_record_recursion()` 函数，将该函数及其调用者（parent）的地址记录下来，以供后续调试和分析使用。

该模块通过在 `tracefs` 文件系统中创建名为 `recursed_functions` 的文件，允许用户空间读取已记录的递归函数信息，或通过写入（截断）操作清空记录。

## 2. 核心功能

### 数据结构

- **`struct recursed_functions`**  
  表示一条递归记录，包含：
  - `ip`：发生递归的函数地址（instruction pointer）
  - `parent_ip`：调用该函数的父函数地址

- **全局静态变量**
  - `recursed_functions[]`：大小为 `CONFIG_FTRACE_RECORD_RECURSION_SIZE` 的数组，用于存储递归记录
  - `nr_records`：原子变量，记录当前有效记录数量；值为 `-1` 时表示正在清空记录
  - `cached_function`：缓存最近一次记录的函数地址，用于快速去重

### 主要函数

- **`ftrace_record_recursion(unsigned long ip, unsigned long parent_ip)`**  
  核心记录函数，由 ftrace 在检测到递归时调用。负责去重、并发安全地将新递归函数加入记录数组。

- **`recursed_function_open()` / `recursed_function_release()`**  
  文件操作回调，处理 `recursed_functions` 文件的打开与释放。若以写模式打开并带 `O_TRUNC` 标志，则清空所有记录。

- **`recursed_function_write()`**  
  空实现的写回调，仅返回写入字节数，实际清空操作在 `open` 中完成。

- **`recursed_function_seq_*` 系列函数**  
  实现 `seq_file` 接口，用于按行输出递归记录，格式为：`<parent_symbol>:<function_symbol>`。

- **`create_recursed_functions()`**  
  初始化函数，在 `fs_initcall` 阶段注册 `recursed_functions` 文件到 `tracefs`。

## 3. 关键实现

### 并发安全的记录机制

- 使用 `cmpxchg()` 原子操作尝试将函数地址写入 `recursed_functions[index].ip`，若目标位置非零（已被占用），则尝试下一个索引。
- 通过 `cached_function` 快速跳过重复记录，虽存在竞态但可接受（注释中说明“内存缓存本身也是竞态的”）。
- `nr_records` 使用原子操作管理记录数量，并在值为 `-1` 时表示正在清空，此时新记录被丢弃。

### 防死锁设计

- 当多个 CPU 同时尝试记录递归时，若因竞态导致 `index >= nr_records`，不会无限重试，而是直接使用 `index = i`（当前记录数）作为写入位置，避免因等待其他 CPU 更新 `nr_records` 而造成死锁（尤其在中断被禁用的情况下）。

### 安全清空机制

- 清空操作通过三步完成：
  1. 设置 `nr_records = -1`（禁止新记录）
  2. `memset` 清零数组
  3. 设置 `nr_records = 0`（重新启用记录）
- 使用内存屏障（`smp_mb__after_atomic()` 和 `smp_wmb()`）确保操作顺序对其他 CPU 可见。
- 即使在清空过程中有 CPU 成功写入记录，后续也会通过 `cmpxchg(..., ip, 0)` 尝试清除“残留”记录。

### seq_file 输出格式

- 每行输出格式为：`<parent_symbol>:<function_symbol>`，例如：  
  `do_sys_open:__fput`
- 使用 `trace_seq_print_sym()` 解析地址为符号名（支持 kallsyms）。

## 4. 依赖关系

- **`<linux/ftrace.h>`**：提供 ftrace 核心接口，`ftrace_record_recursion` 被 ftrace 递归检测逻辑调用。
- **`<linux/seq_file.h>` / `<linux/fs.h>`**：实现 `seq_file` 和文件操作接口。
- **`<linux/kallsyms.h>`**：用于将函数地址转换为可读符号名。
- **`"trace_output.h"`**：提供 `trace_seq_*` 系列辅助函数。
- **`tracefs` 子系统**：通过 `trace_create_file()` 在 `tracefs` 中创建 `recursed_functions` 文件。
- **配置选项**：依赖 `CONFIG_FTRACE_RECORD_RECURSION_SIZE` 定义记录数组大小。

## 5. 使用场景

- **调试 ftrace 递归问题**：当 ftrace 自身在追踪过程中意外触发递归（如追踪函数内部又调用被追踪函数），该模块记录相关函数对，帮助开发者定位问题根源。
- **内核稳定性分析**：在系统出现 soft lockup 或死锁时，检查 `recursed_functions` 文件可判断是否由 ftrace 递归引起。
- **动态清空记录**：用户可通过 `echo > /sys/kernel/tracing/recursed_functions` 清空历史记录，便于复现和隔离问题。
- **开发与测试**：内核开发者在启用 `CONFIG_FUNCTION_TRACER` 时，可利用此接口验证递归保护机制是否正常工作。