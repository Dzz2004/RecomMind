# trace\kprobe_event_gen_test.c

> 自动生成时间: 2025-10-25 17:04:09
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\kprobe_event_gen_test.c`

---

# `trace/kprobe_event_gen_test.c` 技术文档

## 1. 文件概述

`kprobe_event_gen_test.c` 是一个 Linux 内核测试模块，用于验证内核中动态创建 kprobe 和 kretprobe 跟踪事件的 API 功能。该模块在初始化时通过编程方式创建两个动态跟踪事件：
- 一个 **kprobe 事件**（`gen_kprobe_test`），在函数入口处触发，用于捕获函数参数；
- 一个 **kretprobe 事件**（`gen_kretprobe_test`），在函数返回时触发，用于捕获返回值。

模块通过调用 `kprobe_event_gen_cmd_start()`、`kprobe_event_add_fields()` 和 `kprobe_event_gen_cmd_end()` 等接口动态构建并注册事件，并在退出时正确清理资源。该测试模块主要用于验证内核中“动态事件生成”（dynamic event generation）机制的正确性和稳定性。

## 2. 核心功能

### 主要函数

| 函数名 | 功能描述 |
|--------|--------|
| `test_gen_kprobe_cmd()` | 动态创建一个 kprobe 事件，指定目标函数和多个参数字段，并启用该事件 |
| `test_gen_kretprobe_cmd()` | 动态创建一个 kretprobe 事件，捕获目标函数的返回值，并启用该事件 |
| `kprobe_event_gen_test_init()` | 模块初始化入口，依次调用上述两个测试函数 |
| `kprobe_event_gen_test_exit()` | 模块退出处理，禁用并删除已创建的事件，释放资源 |
| `trace_event_file_is_valid()` | 辅助函数，用于安全判断 `trace_event_file` 指针是否有效 |

### 全局变量

| 变量名 | 类型 | 用途 |
|--------|------|------|
| `gen_kprobe_test` | `struct trace_event_file *` | 指向动态创建的 kprobe 事件的文件对象，用于后续启用/禁用和释放 |
| `gen_kretprobe_test` | `struct trace_event_file *` | 指向动态创建的 kretprobe 事件的文件对象 |

### 宏定义

- `KPROBE_GEN_TEST_FUNC`：统一指定被探测的目标函数为 `"do_sys_open"`（旧版系统调用入口）。
- `KPROBE_GEN_TEST_ARG0~ARG3`：根据不同的 CPU 架构（x86、ARM64、ARM、RISC-V 等）定义寄存器名称，用于从 CPU 寄存器或栈中提取函数参数。

## 3. 关键实现

### 动态事件创建流程

1. **缓冲区分配**：使用 `kzalloc(MAX_DYNEVENT_CMD_LEN, GFP_KERNEL)` 分配命令缓冲区。
2. **命令初始化**：调用 `kprobe_event_cmd_init()` 初始化 `dynevent_cmd` 结构。
3. **事件定义**：
   - 对于 kprobe：先通过 `kprobe_event_gen_cmd_start()` 设置事件名、目标函数和前两个参数，再通过 `kprobe_event_add_fields()` 添加剩余参数。
   - 对于 kretprobe：直接通过 `kretprobe_event_gen_cmd_start()` 设置事件名、目标函数和 `$retval`（返回值）。
4. **事件注册**：调用 `*_gen_cmd_end()` 实际在内核中注册事件。
5. **事件启用**：
   - 使用 `trace_get_event_file()` 获取事件文件句柄（增加引用计数防止被意外删除）。
   - 调用 `trace_array_set_clr_event(..., true)` 启用事件，使其开始记录到 trace 缓冲区。

### 架构适配

模块通过条件编译（`#if defined(CONFIG_X86_64)...`）为不同架构定义正确的寄存器名称，确保参数提取语法符合 ftrace/kprobe 的要求：
- x86 使用 `%ax`, `%dx` 等 AT&T 语法；
- ARM64 使用 `%x0`–`%x3`；
- ARM 使用 `%r0`–`%r3`；
- RISC-V 使用 `%a0`–`%a3`（遵循 ABI 参数寄存器命名）。

### 资源管理与错误处理

- 所有分配的内存（`buf`）在函数末尾通过 `kfree()` 释放。
- 若事件创建失败，调用 `kprobe_event_delete()` 删除已部分创建的事件。
- 模块退出时，**必须先禁用事件**（`trace_array_set_clr_event(..., false)`），否则无法删除事件。
- 使用 `trace_put_event_file()` 释放对事件文件的引用。

## 4. 依赖关系

- **内核配置依赖**：
  - `CONFIG_KPROBES`：kprobe 基础支持
  - `CONFIG_TRACING`：ftrace 跟踪框架
  - `CONFIG_KPROBE_EVENTS`：用户态 kprobe 事件支持（动态事件生成基于此）
  - `CONFIG_KPROBE_EVENT_GEN_TEST`：本测试模块的编译开关
- **头文件依赖**：
  - `<linux/module.h>`：模块加载/卸载基础
  - `<linux/trace_events.h>`：提供 `trace_get_event_file`、`trace_array_set_clr_event` 等跟踪事件管理接口
- **函数依赖**：
  - `kprobe_event_gen_cmd_start/add_fields/end`
  - `kretprobe_event_gen_cmd_start/end`
  - `kprobe_event_delete`
  - `trace_get_event_file` / `trace_put_event_file`

## 5. 使用场景

该文件**仅用于内核开发和测试**，典型使用流程如下：

1. **编译**：在内核配置中启用 `CONFIG_KPROBE_EVENT_GEN_TEST=m`，编译生成 `kprobe_event_gen_test.ko`。
2. **加载**：
   ```bash
   insmod kernel/trace/kprobe_event_gen_test.ko
   ```
   模块加载后自动创建并启用两个动态事件。
3. **验证**：
   ```bash
   cat /sys/kernel/tracing/trace
   ```
   可观察到大量 `gen_kprobe_test` 和 `gen_kretprobe_test` 事件记录，内容包含 `do_sys_open` 的参数和返回值。
4. **卸载**：
   ```bash
   rmmod kprobe_event_gen_test
   ```
   模块自动禁用并删除事件，释放所有资源。

该测试模块验证了内核中“从内核代码动态创建跟踪事件”的能力，为 eBPF、perf、或其他内核子系统需要程序化创建 kprobe 事件提供了基础保障。