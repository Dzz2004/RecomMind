# trace\bpf_trace.c

> 自动生成时间: 2025-10-25 17:00:33
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\bpf_trace.c`

---

# `trace/bpf_trace.c` 技术文档

## 1. 文件概述

`trace/bpf_trace.c` 是 Linux 内核中 BPF（Berkeley Packet Filter）子系统与跟踪（tracing）基础设施集成的核心实现文件。该文件主要负责：

- 提供 BPF 程序在 tracepoint、kprobe、uprobe 等动态跟踪点上执行的通用调用机制
- 实现 BPF 程序可调用的辅助函数（helpers），用于安全地从用户空间或内核空间读取内存
- 支持 BPF 程序对函数返回值的覆盖（override）功能（需配置 `CONFIG_BPF_KPROBE_OVERRIDE`）
- 管理模块中定义的原始跟踪点（raw tracepoint）的查找与引用
- 为 BPF 程序提供上下文信息（如栈信息、cookie、入口地址等）

该文件是 BPF tracing 功能的关键桥梁，连接了 BPF 执行引擎与内核的动态跟踪子系统。

## 2. 核心功能

### 主要函数

| 函数 | 功能描述 |
|------|--------|
| `trace_call_bpf()` | 在指定 tracepoint 上执行关联的 BPF 程序数组，返回过滤结果 |
| `bpf_probe_read_user()` | BPF 辅助函数：从用户空间安全读取任意内存 |
| `bpf_probe_read_user_str()` | BPF 辅助函数：从用户空间安全读取以 null 结尾的字符串 |
| `bpf_probe_read_kernel()` | BPF 辅助函数：从内核空间安全读取任意内存 |
| `bpf_probe_read_kernel_str()` | BPF 辅助函数：从内核空间安全读取以 null 结尾的字符串 |
| `bpf_override_return()` | BPF 辅助函数：覆盖被探测函数的返回值（仅限 kprobe） |
| `bpf_get_raw_tracepoint_module()` | 在已加载内核模块中查找指定名称的原始跟踪点 |

### 主要数据结构

- `bpf_trace_module`：用于跟踪已注册 BPF 原始跟踪点的内核模块
- `bpf_func_proto` 实例（如 `bpf_probe_read_user_proto`）：定义 BPF 辅助函数的类型签名和权限

### 宏与常量

- `MAX_UPROBE_MULTI_CNT` / `MAX_KPROBE_MULTI_CNT`：限制 multi-uprobe/kprobe 的最大数量（1M）
- `bpf_event_rcu_dereference()`：带锁依赖检查的 RCU 解引用宏
- `CREATE_TRACE_POINTS`：触发 `bpf_trace.h` 中跟踪点的实例化

## 3. 关键实现

### BPF 程序执行机制 (`trace_call_bpf`)

- 使用 per-CPU 计数器 `bpf_prog_active` 防止 BPF 程序递归执行（避免死锁或栈溢出）
- 通过 RCU 机制安全访问 `call->prog_array`（BPF 程序数组）
- 若已有 BPF 程序在当前 CPU 上运行，则跳过执行并增加 miss 计数器
- 返回值语义：`0` 表示过滤事件，非 `0` 表示保留事件（通常为 `1`）

### 安全内存读取

- **用户空间读取**：使用 `copy_from_user_nofault()` 和 `strncpy_from_user_nofault()`，即使地址无效也不会导致 oops
- **内核空间读取**：使用 `probe_kernel_read()` 或 `strncpy_from_kernel_nofault()`（未在片段中显示但被调用）
- **错误处理**：读取失败时清零目标缓冲区，防止信息泄露
- **字符串处理**：特别注意 `strncpy_*_nofault` 不会自动清零缓冲区剩余部分，依赖调用者处理

### 模块跟踪点管理

- 在 `CONFIG_MODULES` 启用时，维护全局链表 `bpf_trace_modules`
- 通过 `mutex` 保护模块列表遍历
- 使用 `try_module_get()` 增加模块引用计数，防止卸载时访问非法内存

### BPF 辅助函数注册

- 所有 `bpf_probe_read_*` 函数标记为 `GPL-only`（`gpl_only = true`）
- 参数类型严格校验：
  - `ARG_PTR_TO_UNINIT_MEM`：目标缓冲区（BPF verifier 会验证大小）
  - `ARG_CONST_SIZE_OR_ZERO`：读取大小（编译时常量或零）
  - `ARG_ANYTHING`：源地址（由运行时检查有效性）

## 4. 依赖关系

### 内核子系统依赖

- **BPF 核心**：`<linux/bpf.h>`, `bpf_prog_run_array()`, `bpf_prog_active`
- **跟踪子系统**：`trace_event_call`, `trace_probe.h`, `trace.h`
- **内存管理**：`copy_from_user_nofault`, `probe_kernel_read`
- **模块系统**：`struct module`, `try_module_get`（条件编译）
- **RCU 机制**：用于无锁访问 BPF 程序数组
- **Kprobe/Uprobe**：`<linux/kprobes.h>`, `override_function_with_return`
- **BTF（BPF Type Format）**：用于类型安全的内存访问（`bpf_btf_printf_prepare`）

### 头文件依赖

- 内核内部头文件：`trace_probe.h`, `trace.h`, `bpf_trace.h`
- UAPI 头文件：`<uapi/linux/bpf.h>`, `<uapi/linux/btf.h>`
- 架构相关：`<asm/tlb.h>`（可能用于内存屏障）

## 5. 使用场景

### BPF 程序开发

- 用户通过 `bpf()` 系统调用加载 BPF 程序，并将其附加到：
  - **Tracepoints**：通过 `BPF_PROG_TYPE_TRACEPOINT`
  - **Kprobes/Uprobes**：通过 `BPF_PROG_TYPE_KPROBE`
  - **Raw Tracepoints**：通过 `BPF_PROG_TYPE_RAW_TRACEPOINT`
- 程序中调用 `bpf_probe_read_*` 安全访问进程内存或内核数据结构

### 动态追踪

- **性能分析**：在函数入口/出口收集栈信息、参数、返回值
- **安全监控**：拦截敏感系统调用（如 `execve`）并检查参数
- **故障注入**：使用 `bpf_override_return` 模拟错误返回（需 `CONFIG_BPF_KPROBE_OVERRIDE`）

### 内核模块扩展

- 第三方内核模块可通过 `EXPORT_BPF_RAW_TRACEPOINT()` 导出原始跟踪点
- BPF 程序可在模块加载后动态附加到这些跟踪点

### 调试与可观测性

- 结合 `bpf_get_stackid()` / `bpf_get_stack()` 获取调用栈
- 通过 `bpf_perf_event_output()` 将读取的数据发送到用户空间环形缓冲区