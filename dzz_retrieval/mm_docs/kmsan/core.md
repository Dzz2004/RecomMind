# kmsan\core.c

> 自动生成时间: 2025-12-07 16:28:12
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kmsan\core.c`

---

# `kmsan/core.c` 技术文档

## 1. 文件概述

`kmsan/core.c` 是 Linux 内核内存 sanitizer（KMSAN）运行时库的核心实现文件。KMSAN 是一种用于检测内核中未初始化内存使用（use-of-uninitialized-memory）的动态分析工具。该文件提供了 KMSAN 的基础运行时支持，包括元数据（shadow 和 origin）的管理、内存污染（poisoning）与解污染（unpoisoning）、堆栈追踪记录、任务上下文初始化以及内存拷贝时元数据的同步等关键功能。

## 2. 核心功能

### 全局变量
- `kmsan_enabled`：全局开关，控制 KMSAN 是否启用（`__read_mostly` 优化读取性能）。
- `kmsan_percpu_ctx`：每个 CPU 的 KMSAN 上下文结构，用于在中断上下文中替代不可用的 `current->kmsan_ctx`。

### 主要函数
- `kmsan_internal_task_create()`：为新创建的任务初始化 KMSAN 上下文，并对当前线程信息结构进行解污染。
- `kmsan_internal_poison_memory()`：将指定内存区域标记为“污染”（即未初始化），并记录污染来源的堆栈信息。
- `kmsan_internal_unpoison_memory()`：将指定内存区域标记为“已初始化”（解污染）。
- `kmsan_save_stack_with_flags()`：保存当前调用栈到 stack depot，并附加额外信息（如是否为释放后使用 UAF）。
- `kmsan_internal_memmove_metadata()`：在执行 `memmove` 类操作时，同步复制源地址到目标地址的 shadow 和 origin 元数据，处理内存对齐边界情况。
- `kmsan_internal_chain_origin()`：对 origin 进行链式追踪，记录多次内存拷贝/赋值的历史路径，防止无限增长并保留关键信息。
- `kmsan_internal_set_shadow_origin()`：底层函数，用于设置指定内存区域的 shadow 值和 origin 句柄（代码截断，但功能明确）。

## 3. 关键实现

### 元数据管理
KMSAN 为每字节用户内存维护两份元数据：
- **Shadow**：指示该字节是否已初始化（0 表示已初始化，非 0 表示未初始化）。
- **Origin**：一个 `depot_stack_handle_t` 句柄，指向 stack depot 中记录该未初始化值最初来源的调用栈。

### 内存对齐与 Origin 槽位处理
在 `kmsan_internal_memmove_metadata()` 中，由于 origin 元数据按 `KMSAN_ORIGIN_SIZE`（通常为 4 字节）对齐存储，而实际内存操作可能跨多个 origin 槽位，因此需：
- 计算源和目标区域覆盖的 origin 槽位数（`src_slots`, `dst_slots`）。
- 处理首尾槽位的部分字节（通过位掩码 `skip_bits` 忽略未涉及的字节）。
- 在 `dst_slots > src_slots` 时（因对齐差异），根据拷贝方向（`backwards`）复制相邻槽位的 origin 值以填充额外槽位。

### Origin 链式追踪
`kmsan_internal_chain_origin()` 实现了 origin 的链式记录机制：
- 每次传播未初始化值时，生成一个新的 stack depot 条目，包含魔术值 `KMSAN_CHAIN_MAGIC_ORIGIN`、当前调用栈和前一个 origin。
- 使用 extra bits 存储链深度（`depth`）和 UAF 标志（`uaf`）。
- 当链深度达到 `KMSAN_MAX_ORIGIN_DEPTH` 时停止扩展，避免资源耗尽。

### 中断上下文支持
通过 `DEFINE_PER_CPU(struct kmsan_ctx, kmsan_percpu_ctx)` 提供 per-CPU 上下文，在中断或不可调度上下文中使用，避免依赖 `current` 指针。

### 堆栈保存优化
`kmsan_save_stack_with_flags()` 在保存堆栈时清除可能导致睡眠的 GFP 标志（`__GFP_DIRECT_RECLAIM | __GFP_KSWAPD_RECLAIM`），确保在原子上下文中安全调用。

## 4. 依赖关系

- **内存管理子系统**：依赖 `<linux/mm.h>`, `<linux/slab.h>`, `<linux/vmalloc.h>` 等，用于获取内存布局和分配信息。
- **Stack Depot**：通过 `<linux/stackdepot.h>` 使用内核的堆栈存储机制，高效压缩和复用调用栈。
- **KMSAN 内部头文件**：依赖 `"kmsan.h"` 和 `<linux/kmsan_types.h>` 定义的数据结构和常量。
- **体系结构相关**：包含 `<asm/page.h>` 获取页大小等架构细节。
- **Slab 分配器**：包含 `"../slab.h"` 以集成 slab 对象的 KMSAN 支持。

## 5. 使用场景

- **任务创建**：在 `copy_process()` 等路径中调用 `kmsan_internal_task_create()` 初始化新进程的 KMSAN 上下文。
- **内存分配/释放**：在 kmalloc/kfree、页面分配等路径中调用 `kmsan_internal_poison_memory()` 标记未初始化或释放的内存。
- **内存拷贝操作**：在 `memcpy`, `memmove`, `copy_to_user` 等函数的 KMSAN 插桩中调用 `kmsan_internal_memmove_metadata()` 同步元数据。
- **错误报告**：当检测到未初始化内存使用时，通过 origin 链回溯污染源头，辅助开发者定位 bug。
- **中断处理**：在硬中断或软中断中，使用 per-CPU 上下文 `kmsan_percpu_ctx` 执行 KMSAN 检查。