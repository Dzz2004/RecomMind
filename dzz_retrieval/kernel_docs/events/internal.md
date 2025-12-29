# events\internal.h

> 自动生成时间: 2025-10-25 13:24:29
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `events\internal.h`

---

# `events/internal.h` 技术文档

## 1. 文件概述

`events/internal.h` 是 Linux 内核性能事件子系统（perf events）的内部头文件，定义了用于管理 perf 环形缓冲区（ring buffer）和辅助缓冲区（AUX buffer）的核心数据结构、辅助函数和内存操作接口。该文件为 perf 事件的采样数据记录、用户空间 mmap 映射、缓冲区分配与释放、跨页数据拷贝等关键功能提供底层支持，仅供内核 perf 子系统内部使用，不对外暴露给其他模块。

## 2. 核心功能

### 主要数据结构

- **`struct perf_buffer`**  
  表示 perf 事件的主数据环形缓冲区，包含：
  - 引用计数（`refcount`）和 RCU 回收机制（`rcu_head`）
  - 缓冲区页面管理（`nr_pages`, `page_order`, `data_pages[]`）
  - 写入控制（`head`, `paused`, `overwrite`, `nest`）
  - 唤醒机制（`poll`, `watermark`, `wakeup`）
  - 事件丢失统计（`lost`）
  - 用户空间 mmap 相关字段（`mmap_count`, `mmap_user`, `user_page`）
  - AUX 辅助缓冲区支持（`aux_*` 字段，用于如 Intel PT 等硬件追踪）

### 主要函数/宏

- **缓冲区生命周期管理**
  - `rb_alloc()` / `rb_free()`：分配/释放主环形缓冲区
  - `rb_alloc_aux()` / `rb_free_aux()`：分配/释放 AUX 辅助缓冲区
  - `ring_buffer_get()` / `ring_buffer_put()`：引用计数管理

- **缓冲区操作**
  - `rb_toggle_paused()`：暂停/恢复写入
  - `rb_has_aux()`：判断是否启用 AUX 缓冲区
  - `perf_event_wakeup()`：唤醒等待 perf 事件的用户进程
  - `perf_event_aux_event()`：记录 AUX 相关事件

- **内存拷贝与输出**
  - `__output_copy()` / `__output_copy_user()` / `__output_skip()`：跨页安全的数据拷贝接口
  - `__DEFINE_OUTPUT_COPY_BODY`：通用跨页拷贝宏模板
  - `perf_mmap_to_page()`：将 mmap 偏移转换为物理页

- **辅助功能**
  - `get_recursion_context()` / `put_recursion_context()`：中断上下文递归保护
  - `arch_perf_have_user_stack_dump()` / `perf_user_stack_pointer()`：用户栈转储支持

## 3. 关键实现

### 环形缓冲区跨页写入机制
通过 `__DEFINE_OUTPUT_COPY_BODY` 宏实现通用的跨页写入逻辑：
- 自动处理缓冲区写入指针（`handle->addr`）跨越页面边界的情况
- 支持多种拷贝后端（内核内存拷贝、用户空间拷贝、跳过模式）
- 利用 `handle->page` 和 `handle->size` 跟踪当前页面和剩余空间
- 页面大小支持通过 `page_order` 扩展（`CONFIG_PERF_USE_VMALLOC`）

### 用户空间安全拷贝
- `arch_perf_out_copy_user` 默认使用 `__copy_from_user_inatomic()`，并在拷贝期间禁用页错误（`pagefault_disable()`），确保在原子上下文中安全访问用户内存

### 递归写入保护
- 使用 `recursion` 数组按中断上下文级别（`interrupt_context_level()`）跟踪写入状态，防止同一上下文多次进入 perf 写入路径导致死锁或数据损坏

### AUX 缓冲区支持
- 独立于主数据缓冲区，通过 `aux_pages` 和 `aux_priv` 管理硬件追踪数据（如 Intel Processor Trace）
- 提供独立的 watermark、overwrite 和 mmap 控制

### 内存分配策略
- 默认使用连续物理页（`kmalloc` + `alloc_pages`）
- 在存在 d-cache 别名问题的架构上（如某些 ARM），启用 `CONFIG_PERF_USE_VMALLOC` 使用 vmalloc 分配虚拟连续内存

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/hardirq.h>`：提供中断上下文判断（`interrupt_context_level()`）
  - `<linux/uaccess.h>`：提供用户空间内存访问函数（`__copy_from_user_inatomic`）
  - `<linux/refcount.h>`：提供引用计数操作

- **内核配置依赖**：
  - `CONFIG_PERF_EVENTS`：perf 事件子系统基础
  - `CONFIG_PERF_USE_VMALLOC`：控制缓冲区内存分配策略
  - `CONFIG_HAVE_PERF_USER_STACK_DUMP`：控制用户栈转储功能

- **关联模块**：
  - `kernel/events/core.c`：perf 事件核心实现，使用本文件定义的缓冲区接口
  - `kernel/events/ring_buffer.c`：环形缓冲区具体实现（`rb_alloc`, `rb_free` 等）
  - 架构特定代码（如 x86, ARM）：可能重写 `arch_perf_out_copy_user` 或提供 `user_stack_pointer`

## 5. 使用场景

- **性能采样数据记录**：当 perf 事件触发采样（如周期性时钟中断、硬件性能计数器溢出）时，内核通过 `__output_copy` 系列函数将采样数据（如 IP、栈帧、上下文信息）写入环形缓冲区
- **用户空间 mmap 映射**：用户程序通过 `mmap()` 映射 perf 事件文件描述符，直接读取 `perf_buffer` 中的 `data_pages` 和 `user_page`（包含 head/tail 指针）
- **硬件追踪数据收集**：在启用 Intel PT 等特性时，CPU 生成的追踪数据通过 AUX 缓冲区机制写入 `aux_pages`，由用户空间工具（如 `perf`）解析
- **低延迟事件通知**：当缓冲区数据量达到 `watermark` 时，通过 `perf_event_wakeup` 唤醒阻塞在 `poll()`/`select()` 上的用户进程
- **中断/软中断上下文安全写入**：通过递归保护机制，确保在 NMI、IRQ 等高优先级上下文中也能安全记录 perf 事件