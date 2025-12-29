# trace\trace_stack.c

> 自动生成时间: 2025-10-25 17:37:38
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_stack.c`

---

# `trace/trace_stack.c` 技术文档

## 1. 文件概述

`trace/trace_stack.c` 实现了 Linux 内核中的**栈追踪器**（stack tracer）功能，用于动态监控并记录内核执行路径中**最大栈使用深度**。该功能基于 ftrace 框架，在每次函数调用时检查当前栈使用量，若超过历史最大值，则保存完整的调用栈信息，包括每个函数帧的大小和位置。主要用于调试栈溢出风险、分析内核栈使用模式，对系统稳定性与安全性具有重要意义。

## 2. 核心功能

### 主要全局变量
- `stack_dump_trace[]`：存储最大栈深度时的返回地址（函数指针），最多 `STACK_TRACE_ENTRIES`（500）项。
- `stack_trace_index[]`：对应每个返回地址在栈中的偏移量（从栈顶开始计算的字节数）。
- `stack_trace_nr_entries`：当前记录的有效栈帧数量。
- `stack_trace_max_size`：历史记录的最大栈使用字节数。
- `stack_trace_max_lock`：保护最大栈数据的自旋锁（`arch_spinlock_t`）。
- `disable_stack_tracer`（per-CPU）：用于临时禁用当前 CPU 上的栈追踪。
- `stack_tracer_enabled`：全局开关，控制栈追踪器是否启用。
- `stack_sysctl_mutex`：保护 sysctl 接口的互斥锁。

### 主要函数
- `print_max_stack()`：以人类可读格式打印当前记录的最大栈使用情况，包括深度、各帧大小及函数符号。
- `check_stack(unsigned long ip, unsigned long *stack)`：核心回调函数，由 ftrace 触发，用于检测并更新最大栈使用记录。

## 3. 关键实现

### 栈大小计算
- 通过传入的局部变量地址 `stack` 计算当前栈使用量：  
  `this_size = THREAD_SIZE - ((unsigned long)stack & (THREAD_SIZE - 1))`
- 减去追踪器自身帧开销（`tracer_frame`），避免污染测量结果。

### 最大栈更新逻辑
1. 若当前栈使用量 ≤ 已记录最大值，直接返回。
2. 若栈不在当前任务栈空间（如中断栈），则跳过（暂不支持）。
3. 禁用本地中断并获取自旋锁，确保更新原子性。
4. 调用 `stack_trace_save()` 获取当前调用栈的返回地址列表。
5. **跳过追踪器自身帧**：在栈回溯结果中查找触发回调的指令指针 `ip`，忽略其之上的帧。
6. **地址到栈偏移映射**：
   - 从栈底向栈顶扫描，匹配返回地址。
   - 记录每个匹配地址距离栈顶的偏移（字节数）到 `stack_trace_index[]`。
   - 使用 `READ_ONCE_NOCHECK` 避免 KASAN 误报栈越界。

### 架构适配说明
- 文档注释详细解释了不同 CPU 架构（如 x86 与 ARM）在栈帧布局上的差异：
  - **x86 风格**：返回地址位于局部变量**之前**，偏移直接对应函数帧起始。
  - **ARM 风格**（`ARCH_RET_ADDR_AFTER_LOCAL_VARS`）：返回地址（LR）保存在局部变量**之后**，需调整偏移计算逻辑（代码中通过条件编译处理，但当前片段未展示完整实现）。

## 4. 依赖关系

- **ftrace 框架**：通过 `ftrace` 注册回调函数 `check_stack`，在每次函数入口触发。
- **栈回溯接口**：依赖 `stack_trace_save()`（来自 `<linux/stacktrace.h>`）获取调用栈。
- **内核符号解析**：使用 `kallsyms`（`%pS` 格式化）将地址转换为函数名。
- **内存与任务管理**：依赖 `task_stack.h` 判断栈边界（`object_is_on_stack`）。
- **同步原语**：使用 `arch_spinlock_t` 和 `mutex` 保证多核/多线程安全。
- **安全模块**：包含 `<linux/security.h>`，可能用于权限检查（如 sysctl 访问控制）。

## 5. 使用场景

- **内核调试**：通过 `/sys/kernel/debug/tracing/stack_max_size` 和 `/sys/kernel/debug/tracing/stack_trace` 接口查看最大栈使用情况，定位潜在栈溢出风险。
- **性能分析**：评估内核路径的栈消耗，优化深层调用链。
- **安全审计**：监控异常栈增长，辅助检测栈溢出类漏洞。
- **系统稳定性保障**：在开发和测试阶段启用，确保关键路径不会超出 `THREAD_SIZE`（通常 8KB 或 16KB）限制。
- **架构验证**：验证不同 CPU 架构下栈布局假设的正确性。