# kfence\kfence.h

> 自动生成时间: 2025-12-07 16:24:13
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kfence\kfence.h`

---

# `kfence/kfence.h` 技术文档

## 1. 文件概述

`kfence/kfence.h` 是 Linux 内核中 **Kernel Electric-Fence (KFENCE)** 内存安全调试机制的核心头文件。KFENCE 是一种轻量级、低开销的内存错误检测工具，用于在运行时捕获以下类型的内存错误：

- 越界访问（Out-of-Bounds, OOB）
- 释放后使用（Use-After-Free, UAF）
- 内存破坏（Corruption）
- 非法释放（Invalid Free）

该头文件定义了 KFENCE 所需的数据结构、宏、枚举和函数声明，为 KFENCE 的内存分配、元数据管理、错误检测与报告提供基础支持。

---

## 2. 核心功能

### 主要数据结构

| 结构体/枚举 | 说明 |
|------------|------|
| `enum kfence_object_state` | 描述 KFENCE 对象的生命周期状态：未使用、已分配、RCU 释放中、已释放 |
| `struct kfence_track` | 记录一次分配或释放操作的上下文信息，包括 PID、CPU、时间戳和调用栈 |
| `struct kfence_metadata` | 每个受保护对象的元数据，包含地址、大小、状态、分配/释放跟踪信息等 |
| `enum kfence_error_type` | 定义 KFENCE 可检测的错误类型 |

### 关键宏定义

| 宏 | 说明 |
|----|------|
| `KFENCE_CANARY_PATTERN_U8(addr)` | 基于地址低 3 位生成字节级 canary 值，用于检测内存破坏 |
| `KFENCE_CANARY_PATTERN_U64` | 8 字节对齐的 canary 模式，支持 64 位批量填充与校验，提升性能 |
| `KFENCE_STACK_DEPTH` | 调用栈最大深度（64 层） |
| `KFENCE_METADATA_SIZE` | 所有元数据所需内存大小（按页对齐） |

### 主要函数声明

| 函数 | 功能 |
|------|------|
| `kfence_report_error()` | 生成并输出详细的内存错误报告 |
| `kfence_print_object()` | 在 `/sys/kernel/debug/kfence/objects` 等调试接口中打印对象信息 |
| `addr_to_metadata()` | （内联函数）根据虚拟地址快速定位对应的 `kfence_metadata` |

---

## 3. 关键实现

### 地址到元数据的映射机制

KFENCE 使用特殊的内存布局：每个受保护对象被放置在两个相邻的保护页之间（一个只读，一个不可访问）。对象实际位于中间的“数据页”。

- 所有 KFENCE 对象池起始于 `__kfence_pool`
- 每个对象占用 **2 个页面**（一个数据页 + 一个保护页）
- 元数据数组 `kfence_metadata[]` 与对象一一对应
- `addr_to_metadata()` 通过地址偏移计算索引：
  ```c
  index = (addr - __kfence_pool) / (PAGE_SIZE * 2) - 1;
  ```
  此设计确保即使访问到保护页边界，也能正确或安全地返回 `NULL`。

### Canary 保护机制

- **字节级 canary**：`KFENCE_CANARY_PATTERN_U8(addr)` 使用地址低 3 位异或 `0xaa`，使相邻字节 canary 不同，提高检测概率。
- **64 位优化**：`KFENCE_CANARY_PATTERN_U64` 预计算 8 字节 canary 模式，允许一次性写入/校验 8 字节，减少循环开销。

### 并发安全

- 每个 `kfence_metadata` 包含一个 `raw_spinlock_t lock`，保护其内部状态（如 `state`、`addr`、`size` 等）。
- 该锁确保 `__kfence_alloc()`、`__kfence_free()` 和页错误处理函数 `kfence_handle_page_fault()` 对同一对象的操作互斥。
- 元数据空闲链表操作受全局 `kfence_freelist_lock` 保护。

### RCU 延迟释放支持

- 对象释放可能通过 RCU 机制延迟执行（如 SLAB_TYPESAFE_BY_RCU）
- 状态 `KFENCE_OBJECT_RCU_FREEING` 表示对象正在 RCU 回调中等待释放
- `rcu_head` 字段用于注册 RCU 回调

### 内存控制组（memcg）支持

- 若启用 `CONFIG_MEMCG`，元数据中嵌入 `struct slabobj_ext obj_exts`，用于关联 memcg 信息

---

## 4. 依赖关系

| 依赖项 | 说明 |
|--------|------|
| `<linux/mm.h>` | 提供内存管理基础类型和函数（如 `is_kfence_address()`） |
| `<linux/slab.h>` | 提供 SLAB 分配器接口 |
| `"../slab.h"` | 引入 `struct kmem_cache` 定义，用于记录分配来源 |
| `CONFIG_KFENCE_NUM_OBJECTS` | 编译时配置项，决定 KFENCE 池中对象数量 |
| `__kfence_pool` | 外部符号，由 `kfence/core.c` 定义，指向 KFENCE 内存池起始地址 |
| `kfence_metadata` | 全局元数据数组指针，由 `kfence/core.c` 初始化 |

---

## 5. 使用场景

1. **内核开发与调试**  
   开启 `CONFIG_KFENCE` 后，KFENCE 自动拦截部分 `kmalloc`/`kfree` 调用，将对象分配到受保护区域，用于检测驱动或子系统中的内存错误。

2. **生产环境轻量监控**  
   相比 KASAN，KFENCE 运行时开销极低（<1%），适合在生产内核中长期启用，用于捕获偶发性内存错误。

3. **错误报告与分析**  
   当发生非法内存访问触发页错误时，KFENCE 页错误处理程序调用 `kfence_report_error()`，输出包含：
   - 错误类型（OOB/UAF 等）
   - 访问地址与读写方向
   - 寄存器状态（`pt_regs`）
   - 分配/释放调用栈
   - 对象大小与所属 `kmem_cache`

4. **调试接口集成**  
   `kfence_print_object()` 被用于 `/sys/kernel/debug/kfence/objects` 接口，允许用户空间查看当前所有 KFENCE 对象的状态，辅助离线分析。