# kfence\report.c

> 自动生成时间: 2025-12-07 16:25:50
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kfence\report.c`

---

# `kfence/report.c` 技术文档

## 1. 文件概述

`kfence/report.c` 是 Linux 内核中 **KFENCE（Kernel Electric Fence）** 内存错误检测机制的报告模块。该文件负责在检测到内存访问违规（如越界访问、释放后使用等）时，生成结构化、可读性强的错误诊断信息，包括堆栈跟踪、对象状态、时间戳以及内存内容差异等，便于开发者定位和调试内存安全问题。

## 2. 核心功能

### 主要函数

- **`seq_con_printf()`**  
  辅助函数，根据传入的 `seq_file` 指针决定将格式化字符串输出到序列文件或内核控制台（`vprintk`）。

- **`get_stack_skipnr()`**  
  分析堆栈回溯记录，跳过 KFENCE 和 slab 分配器内部函数（如 `kfence_*`, `kfree`, `__kmalloc` 等），返回应从哪一层开始向用户展示调用栈，以聚焦于用户代码路径。

- **`kfence_print_stack()`**  
  打印指定对象的分配或释放堆栈信息，包含任务 PID、CPU、时间戳（绝对时间和距今时间），并跳过内部函数。

- **`kfence_print_object()`**  
  完整打印 KFENCE 对象元数据信息，包括对象 ID、地址范围、大小、所属缓存名称，以及分配/释放堆栈（若已释放）。

- **`print_diff_canary()`**  
  打印指定地址附近与预期 **canary 值** 不符的字节内容，用于显示内存破坏区域；在非调试构建中隐藏实际内存值以避免信息泄露。

- **`kfence_report_error()`**  
  **核心错误报告入口**。根据错误类型（越界、UAF、损坏等）生成标准化的 `BUG` 报告，包含错误类型、访问地址、方向、对象 ID、触发点函数及完整上下文信息，并通过 `tracepoint` 上报。

### 关键数据结构（引用）

- `struct kfence_metadata`：KFENCE 对象的元数据，包含地址、大小、状态、分配/释放追踪信息等。
- `enum kfence_error_type`：定义错误类型（`KFENCE_ERROR_OOB`, `KFENCE_ERROR_UAF`, `KFENCE_ERROR_CORRUPTION`, `KFENCE_ERROR_INVALID_FREE`, `KFENCE_ERROR_INVALID`）。

## 3. 关键实现

- **堆栈净化（Stack Skipping）**  
  通过 `get_stack_skipnr()` 动态识别并跳过 KFENCE 和 slab allocator 的内部函数帧，确保报告中的堆栈从用户调用点开始，提升可读性。支持架构前缀（`ARCH_FUNC_PREFIX`）适配不同平台的符号命名。

- **安全输出机制**  
  使用 `seq_con_printf()` 统一处理输出目标（`seq_file` 或 `printk`），便于在 `/sys/kernel/debug/kfence/objects` 等 debugfs 接口和内核日志中复用相同格式。

- **内存内容安全显示**  
  在 `print_diff_canary()` 中，若 `no_hash_pointers` 未启用（即非调试模式），对非 canary 字节仅显示 `!` 而非实际值，防止内核内存布局泄露。

- **时间戳格式化**  
  使用 `local_clock()` 获取高精度时间，并格式化为 `秒.微秒` 形式，与 `printk` 时间戳风格一致，便于日志关联分析。

- **死锁风险规避**  
  在 `kfence_report_error()` 中主动调用 `lockdep_off()`，因错误可能发生在调度器等敏感路径，避免 `printk` 触发死锁，优先保证错误信息输出。

- **错误上下文完整性**  
  支持从 `pt_regs`（页错误上下文）或当前执行上下文获取堆栈，并根据错误类型调整堆栈跳过逻辑（如 OOB/UAF 直接使用故障点，而 CORRUPTION 需跳过释放路径）。

## 4. 依赖关系

- **KFENCE 核心**：依赖 `kfence.h` 中定义的元数据结构、状态枚举和全局变量（如 `kfence_metadata`）。
- **内核基础组件**：
  - `stacktrace.h`：堆栈回溯保存（`stack_trace_save`, `stack_trace_save_regs`）
  - `printk.h` / `seq_file.h`：日志与序列文件输出
  - `sched/clock.h`：高精度时间戳（`local_clock`）
  - `trace/events/error_report.h`：通过 tracepoint 上报错误事件
  - `asm/kfence.h`：架构特定配置（如 `ARCH_FUNC_PREFIX`）
- **内存子系统**：与 slab allocator（`kmem_cache`, `kfree`, `kmalloc`）紧密集成，解析其函数符号以净化堆栈。

## 5. 使用场景

- **内存错误检测触发**：当 KFENCE 捕获到非法内存访问（如访问 guard page）时，由 `kfence_handle_page_fault()` 调用 `kfence_report_error()` 生成详细报告。
- **DebugFS 接口查询**：通过 `kfence_print_object()` 向 `/sys/kernel/debug/kfence/objects` 提供每个 KFENCE 对象的当前状态和历史操作堆栈。
- **内核崩溃诊断**：在发生 use-after-free、out-of-bounds write 等严重内存错误时，提供可追溯的调用链、对象生命周期信息和破坏位置，辅助根因分析。
- **运行时监控**：结合 ftrace 或其他 tracing 机制，通过 `error_report` tracepoint 实时捕获 KFENCE 错误事件。