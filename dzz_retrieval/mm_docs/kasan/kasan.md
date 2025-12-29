# kasan\kasan.h

> 自动生成时间: 2025-12-07 16:15:42
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\kasan.h`

---

# `kasan/kasan.h` 技术文档

## 1. 文件概述

`kasan/kasan.h` 是 Linux 内核中 **Kernel Address Sanitizer (KASAN)** 子系统的核心头文件，用于定义 KASAN 的通用接口、数据结构和配置宏。该文件为三种 KASAN 模式（Generic、Software Tagging、Hardware Tagging）提供统一的抽象层，并根据编译配置条件性地启用特定功能。其主要作用包括：

- 定义 KASAN 元数据布局和内存粒度
- 提供堆栈跟踪、采样分配、故障模式判断等运行时辅助函数
- 声明通用报告结构体和全局变量元数据格式
- 实现不同 KASAN 模式下的行为差异（如是否需要元数据、影子内存映射等）

## 2. 核心功能

### 主要函数

| 函数 | 功能说明 |
|------|--------|
| `kasan_stack_collection_enabled()` | 判断是否启用堆栈跟踪收集（受 `kasan.stacktrace` 启动参数控制） |
| `kasan_vmalloc_enabled()` | （仅 HW_TAGS）判断是否对 vmalloc 区域启用 KASAN |
| `kasan_async_fault_possible()` / `kasan_sync_fault_possible()` | 判断当前 KASAN 模式是否可能触发异步/同步错误报告 |
| `kasan_sample_page_alloc(unsigned int order)` | （仅 HW_TAGS）基于采样率决定是否对指定阶数的页面分配进行检测 |
| `kasan_requires_meta()` | 判断当前 KASAN 模式是否需要为每个对象存储元数据 |
| `kasan_shadow_to_mem(const void *shadow_addr)` | 将影子内存地址转换回对应的原始内存地址 |
| `addr_has_metadata(const void *addr)` | 判断给定地址是否位于具有 KASAN 元数据覆盖的内存区域 |

### 主要数据结构

| 结构体 | 用途 |
|-------|------|
| `struct kasan_track` | 记录内存分配/释放时的 PID 和调用栈（通过 stackdepot 存储） |
| `struct kasan_report_info` | 统一的错误报告上下文，包含访问信息、对象元数据、错误类型等 |
| `struct kasan_source_location` | 编译器生成的全局变量源码位置信息（ABI 兼容） |
| `struct kasan_global` | 描述全局变量的 KASAN 元数据（由编译器插桩生成） |
| `struct kasan_alloc_meta` / `struct kasan_free_meta` | （仅 GENERIC）存储 slab 对象的分配/释放元数据 |
| `struct kasan_stack_ring_entry` / `struct kasan_stack_ring` | （SW/HW_TAGS）用于记录近期内存操作的环形缓冲区 |

### 关键宏定义

| 宏 | 说明 |
|----|------|
| `KASAN_GRANULE_SIZE` | KASAN 检测的基本内存粒度（Generic/SW_TAGS 为 8 字节，HW_TAGS 为 MTE 粒度） |
| `KASAN_PAGE_FREE`, `KASAN_SLAB_REDZONE` 等 | 影子内存中的特殊标记值，表示不同类型的无效/红区内存 |
| `KASAN_STACK_*`, `KASAN_ALLOCA_*` | （仅 GENERIC）栈和 alloca 红区的影子值（编译器 ABI） |
| `META_*` 系列宏 | 定义元数据在调试输出中的显示格式（每行块数、字节数等） |

## 3. 关键实现

### 多模式支持机制
文件通过 `#ifdef CONFIG_KASAN_*` 条件编译区分三种 KASAN 模式：
- **Generic**：使用影子内存 + 每对象元数据，支持精确错误定位
- **SW_TAGS**：使用软件生成的 8-bit 标签，无每对象元数据
- **HW_TAGS**：利用 ARM MTE 硬件标签，依赖 CPU 特性

### 堆栈跟踪控制
通过 `static_key` 优化性能：
```c
DECLARE_STATIC_KEY_TRUE(kasan_flag_stacktrace);
```
默认启用堆栈收集，但可通过启动参数 `kasan.stacktrace=off` 动态关闭，减少运行时开销。

### 页面分配采样（HW_TAGS 特有）
为平衡性能与覆盖率，HW_TAGS 模式引入概率采样：
- 小于 `kasan_page_alloc_sample_order` 的分配总是检测
- 更大分配按 `1/kasan_page_alloc_sample` 概率检测
- 使用 per-CPU 计数器 `kasan_page_alloc_skip` 实现无锁采样

### 元数据管理差异
- **Generic 模式**：在对象前后或 quarantine 中存储 `kasan_alloc_meta`/`free_meta`
- **Tag-based 模式**：不使用每对象元数据，改用环形缓冲区 `kasan_stack_ring` 记录近期操作

### 影子内存映射
通过 `kasan_shadow_to_mem()` 实现影子地址到原始地址的转换，公式为：
```
原始地址 = (影子地址 - KASAN_SHADOW_OFFSET) << KASAN_SHADOW_SCALE_SHIFT
```

## 4. 依赖关系

| 依赖模块 | 用途 |
|---------|------|
| `<linux/kasan.h>` | KASAN 公共 API（如 `kasan_enable/disable_current()`） |
| `<linux/kasan-tags.h>` | 标签操作辅助函数（如 `kasan_reset_tag()`） |
| `<linux/stackdepot.h>` | 调用栈压缩存储（`depot_stack_handle_t`） |
| `<asm/mte-kasan.h>` | （HW_TAGS）ARM MTE 架构相关定义 |
| `<linux/slab.h>` | （HW_TAGS）slab 分配器集成 |
| `<linux/static_key.h>` | 静态分支优化（堆栈跟踪开关） |
| `<linux/kfence.h>` | 与 KFENCE 内存检测器协同工作 |

## 5. 使用场景

1. **内存错误检测**  
   在内核内存访问（读/写）时，KASAN 运行时通过此头文件定义的接口检查影子内存状态，捕获越界、释放后使用等错误。

2. **错误报告生成**  
   当检测到非法访问时，`kasan_report_info` 结构体被填充，结合 `kasan_track` 中的堆栈信息生成详细错误报告。

3. **编译器插桩支持**  
   Clang/GCC 在编译时生成对 `__asan_load*/store*` 的调用，这些函数内部使用本文件定义的宏（如 `KASAN_GRANULE_SIZE`）和地址转换逻辑。

4. **全局变量保护**  
   编译器为全局变量生成 `kasan_global` 结构体数组，在初始化阶段通过 `kasan_register_globals()` 注册红区。

5. **动态配置调整**  
   通过 `kasan.stacktrace`、`kasan.vmalloc` 等启动参数，可在运行时调整 KASAN 行为（如关闭堆栈收集以提升性能）。

6. **硬件加速集成**  
   在 ARM64 平台上，HW_TAGS 模式利用 MTE 指令自动验证内存标签，本文件提供与硬件特性的抽象层对接。