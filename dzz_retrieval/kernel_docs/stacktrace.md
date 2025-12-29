# stacktrace.c

> 自动生成时间: 2025-10-25 16:28:02
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `stacktrace.c`

---

# stacktrace.c 技术文档

## 1. 文件概述

`stacktrace.c` 是 Linux 内核中用于管理和操作栈回溯（stack trace）的核心实现文件。该文件提供了一套统一的接口，用于捕获、存储和打印内核栈跟踪信息。它支持从当前执行上下文、指定任务（task）、寄存器状态（pt_regs）以及用户空间获取栈回溯，并根据架构是否支持 `CONFIG_ARCH_STACKWALK` 提供两种不同的实现路径：现代基于 `arch_stack_walk()` 的实现和传统的基于 `save_stack_trace()` 的弱符号兼容实现。

## 2. 核心功能

### 主要函数

- **`stack_trace_print`**  
  将栈回溯条目以可读形式打印到内核日志（`printk`），支持前导空格缩进。

- **`stack_trace_snprint`**  
  将栈回溯条目格式化输出到指定缓冲区，返回实际写入的字节数。

- **`stack_trace_save`**  
  捕获当前执行上下文的内核栈回溯，保存到用户提供的数组中，可跳过指定数量的顶层条目。

- **`stack_trace_save_tsk`**  
  捕获指定任务（`task_struct`）的内核栈回溯，适用于调试或分析其他任务的调用栈。

- **`stack_trace_save_regs`**  
  基于给定的 `pt_regs`（处理器寄存器状态）捕获栈回溯，常用于异常或中断处理上下文。

- **`stack_trace_save_user`**（仅当 `CONFIG_USER_STACKTRACE_SUPPORT` 启用）  
  捕获当前任务的用户空间栈回溯（仅适用于非内核线程）。

- **`stack_trace_save_tsk_reliable`**（仅当 `CONFIG_HAVE_RELIABLE_STACKTRACE` 启用）  
  捕获指定任务的栈回溯，并验证其可靠性（如无中断、无损坏帧等），若不可靠则返回错误码。

### 数据结构

- **`struct stacktrace_cookie`**  
  用于在栈遍历回调中传递上下文信息，包含存储数组、大小、跳过计数和已记录条目数。

- **回调函数类型 `stack_trace_consume_fn`**  
  定义栈遍历过程中每遇到一个返回地址时的处理函数原型。

### 辅助函数（内部使用）

- **`stack_trace_consume_entry`**  
  标准回调函数，将地址存入 `stacktrace_cookie`，支持跳过机制。

- **`stack_trace_consume_entry_nosched`**  
  专用于任务栈回溯的回调，自动过滤调度器内部函数（通过 `in_sched_functions()` 判断）。

## 3. 关键实现

### 双路径架构支持

文件根据是否定义 `CONFIG_ARCH_STACKWALK` 分为两个实现分支：

- **现代架构路径（启用 `CONFIG_ARCH_STACKWALK`）**  
  使用 `arch_stack_walk()` 及其变体（如 `arch_stack_walk_user`、`arch_stack_walk_reliable`）进行栈遍历。这些函数由具体架构（如 x86、ARM64）实现，提供更灵活、高效和可靠的栈展开能力。遍历过程通过回调函数 `stack_trace_consume_fn` 逐帧处理返回地址。

- **传统兼容路径（未启用 `CONFIG_ARCH_STACKWALK`）**  
  依赖旧式 `save_stack_trace()` 系列函数（如 `save_stack_trace_tsk`）。若架构未实现这些函数，则链接器会使用 `__weak` 定义的桩函数，并在运行时打印警告。此路径主要用于尚未迁移到新栈遍历框架的架构。

### 跳过机制

所有 `stack_trace_save*` 函数均支持 `skipnr` 参数，用于忽略栈顶的若干帧（通常用于跳过回溯函数自身及其调用者）。例如：
- `stack_trace_save` 默认跳过 1 帧（+1）以排除自身。
- `stack_trace_save_tsk` 在追踪当前任务时额外跳过 1 帧。

### 可靠性检查

在支持 `CONFIG_HAVE_RELIABLE_STACKTRACE` 的架构上，`stack_trace_save_tsk_reliable` 调用 `arch_stack_walk_reliable()`，该函数在遍历过程中验证栈帧的完整性（如检查帧指针有效性、中断上下文一致性等）。若检测到不可靠特征（如被中断破坏的栈），则返回负错误码而非部分结果。

### 用户栈支持

当启用 `CONFIG_USER_STACKTRACE_SUPPORT` 时，`stack_trace_save_user` 利用 `arch_stack_walk_user()` 从 `task_pt_regs(current)` 开始遍历用户空间栈，仅适用于非内核线程（`PF_KTHREAD` 未设置）。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/stacktrace.h>`：定义核心接口和数据结构。
  - `<linux/sched.h>`、`<linux/sched/task_stack.h>`：访问任务结构和栈管理。
  - `<linux/kallsyms.h>`：支持 `%pS` 格式化符号解析。
  - `<linux/interrupt.h>`：用于 `in_sched_functions()` 判断。
  - `<linux/kernel.h>`、`<linux/export.h>`：基础内核功能和符号导出。

- **架构依赖**：
  - 若启用 `CONFIG_ARCH_STACKWALK`，依赖架构特定的 `asm/stacktrace.h` 中定义的 `arch_stack_walk*` 系列函数。
  - 若未启用，则依赖旧式 `save_stack_trace*` 函数（通常在 `arch/*/kernel/stacktrace.c` 中实现）。

- **配置依赖**：
  - `CONFIG_HAVE_RELIABLE_STACKTRACE`：启用可靠性验证功能。
  - `CONFIG_USER_STACKTRACE_SUPPORT`：启用用户空间栈回溯支持。

## 5. 使用场景

- **内核调试与诊断**：  
  通过 `dump_stack()` 或 `WARN()` 等机制打印当前调用栈，辅助定位死锁、内存错误等问题。

- **性能分析与跟踪**：  
  在 perf、ftrace 等子系统中捕获函数调用链，用于性能剖析或事件溯源。

- **任务状态检查**：  
  在进程管理、OOM killer 或 hung task detector 中分析目标任务的阻塞位置。

- **异常处理**：  
  在 page fault、oops 或 panic 处理流程中，基于 `pt_regs` 重建故障发生时的调用栈。

- **安全审计**：  
  验证关键路径（如系统调用入口）的调用合法性，或检测栈溢出等异常。

- **用户空间调试支持**：  
  通过 `/proc/<pid>/stack` 等接口向用户空间暴露内核栈信息（需特权），或在 ptrace 场景中辅助调试。