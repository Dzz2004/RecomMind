# kasan\report_tags.c

> 自动生成时间: 2025-12-07 16:20:26
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\report_tags.c`

---

# kasan/report_tags.c 技术文档

## 1. 文件概述

`kasan/report_tags.c` 是 Linux 内核中 KASAN（Kernel Address Sanitizer）模块的一部分，专门用于 **基于硬件内存标签（Hardware Tag-Based KASAN）** 的错误报告增强。该文件的主要作用是在检测到内存访问违规时，通过查询一个环形栈追踪缓冲区（stack ring buffer），尝试还原出与问题对象相关的分配（alloc）和释放（free）调用栈信息，并据此推断更精确的错误类型（如 use-after-free 或 out-of-bounds），从而提升调试信息的可读性和准确性。

## 2. 核心功能

### 主要函数

- `get_common_bug_type(struct kasan_report_info *info)`  
  根据访问地址和访问大小判断通用的错误类型。若 `access_addr + access_size < access_addr`（即发生整数溢出），则判定为 "out-of-bounds"；否则返回 "invalid-access"。

- `kasan_complete_mode_report_info(struct kasan_report_info *info)`  
  核心函数，负责填充 `kasan_report_info` 结构体中的分配/释放追踪信息（`alloc_track` / `free_track`）并确定具体的 bug 类型（如 slab-use-after-free、slab-out-of-bounds 等）。

### 关键外部数据结构

- `struct kasan_stack_ring stack_ring`（外部声明）  
  全局环形缓冲区，用于记录近期 slab 对象的分配/释放事件及其对应的调用栈、PID 和指针（含内存标签）。

- `struct kasan_report_info`  
  包含当前内存错误的上下文信息，如访问地址、对象地址、缓存信息、bug 类型及追踪记录等。

## 3. 关键实现

### 环形栈缓冲区遍历策略
- 函数从 `stack_ring.pos - 1` 开始**逆序遍历**最多 `stack_ring.size` 个条目，以查找与当前错误对象匹配的记录。
- 匹配条件包括：
  - 去除内存标签后的指针地址等于 `info->object`
  - 指针的内存标签等于 `info->access_addr` 的标签
- 使用 `smp_load_acquire()` 保证与 `save_stack_info()` 中 `smp_store_release()` 的内存顺序一致性。

### Bug 类型推断逻辑
- **优先级规则**：
  - 若先找到 **free 条目**，则推断为 `"slab-use-after-free"`（UAF）
  - 若先找到 **alloc 条目**，则推断为 `"slab-out-of-bounds"`（OOB）
- **终止条件**：
  - 已同时找到 alloc 和 free 条目
  - 遇到同一类型的第二条记录（表明对象已被重用，历史不可靠）
- 若未找到任何相关条目，则回退到 `get_common_bug_type()` 提供的通用类型。

### 并发安全
- 整个遍历过程在 `write_lock_irqsave()` 保护下进行，防止在读取环形缓冲区时被写入操作干扰，确保数据一致性。

## 4. 依赖关系

- **内部依赖**：
  - `kasan.h`：提供 KASAN 相关的数据结构（如 `kasan_report_info`、`kasan_stack_ring_entry`）、辅助宏（`kasan_reset_tag`、`get_tag`）及全局变量声明。
  - `linux/atomic.h`：用于原子读取 `stack_ring.pos`。
- **外部依赖**：
  - `depot_stack_handle_t`（来自 lockdep 或 stack depot 子系统）：用于高效存储和检索调用栈。
  - SMP 内存屏障原语（`smp_load_acquire` / `smp_store_release`）：确保多核环境下栈记录的可见性。

## 5. 使用场景

该文件在以下场景中被调用：

- 当 **Hardware Tag-Based KASAN** 检测到非法内存访问（如访问已释放对象、越界访问）并触发报告流程时。
- 在生成最终错误报告前，由 KASAN 的报告机制调用 `kasan_complete_mode_report_info()`，以丰富错误上下文：
  - 填充分配/释放时的 PID 和调用栈
  - 精确识别 bug 类型（UAF vs OOB）
- 特别适用于启用了 `CONFIG_KASAN_HW_TAGS` 的 ARM64 系统，利用 MTE（Memory Tagging Extension）硬件特性进行内存安全检测。