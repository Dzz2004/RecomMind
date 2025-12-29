# kasan\report_generic.c

> 自动生成时间: 2025-12-07 16:18:57
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\report_generic.c`

---

# kasan/report_generic.c 技术文档

## 1. 文件概述

`kasan/report_generic.c` 是 Linux 内核中 KASAN（Kernel Address SANitizer）子系统的核心错误报告模块，负责通用的内存安全违规检测与诊断信息生成。该文件实现了对各类非法内存访问（如越界访问、释放后使用等）的识别、分类和辅助调试信息提取功能，为开发者提供详细的错误上下文，便于定位和修复内核中的内存安全问题。

## 2. 核心功能

### 主要函数

- **`kasan_find_first_bad_addr(const void *addr, size_t size)`**  
  在指定内存区域 `[addr, addr + size)` 中查找第一个被 KASAN 标记为无效（即影子内存非零）的地址。

- **`kasan_get_alloc_size(void *object, struct kmem_cache *cache)`**  
  根据对象的影子内存状态，推断其原始分配大小（仅适用于 slab 分配的对象）。

- **`get_shadow_bug_type(struct kasan_report_info *info)`**  
  基于影子内存值判断内存错误的具体类型（如 slab-out-of-bounds、use-after-free 等）。

- **`get_wild_bug_type(struct kasan_report_info *info)`**  
  对无影子内存覆盖的“野指针”访问进行分类（如 null-ptr-deref、user-memory-access 等）。

- **`get_bug_type(struct kasan_report_info *info)`**  
  综合判断内存错误类型：先检查是否为整数溢出导致的越界，再根据是否有影子元数据选择调用 `get_shadow_bug_type` 或 `get_wild_bug_type`。

- **`kasan_complete_mode_report_info(struct kasan_report_info *info)`**  
  补全错误报告信息，包括填充分配/释放时的调用栈（track）信息。

- **`kasan_metadata_fetch_row(char *buffer, void *row)`**  
  从指定内存行对应的影子内存区域复制元数据到缓冲区。

- **`kasan_print_aux_stacks(struct kmem_cache *cache, const void *object)`**  
  打印与对象相关的辅助调用栈（如 workqueue 创建栈），用于复杂场景的调试。

- **`print_decoded_frame_descr(const char *frame_descr)`**  
  （仅在 `CONFIG_KASAN_STACK` 启用时）解析并打印栈帧中局部变量的布局描述。

- **`get_address_stack_frame_info(const void *addr, ...)`**  
  （仅在 `CONFIG_KASAN_STACK` 启用时）判断地址是否位于当前任务栈，并提取相关栈帧信息。

### 关键数据结构

- **`struct kasan_report_info`**  
  封装一次 KASAN 错误报告所需的所有信息，包括访问地址、大小、对象指针、缓存、错误类型及分配/释放轨迹等。

## 3. 关键实现

### 影子内存解析机制
KASAN 使用影子内存（shadow memory）映射主内存状态。每个 `KASAN_GRANULE_SIZE`（通常为 8 字节）的主内存对应一个字节的影子值：
- `0`：完全可访问；
- `1–7`：部分可访问（表示前 N 字节有效）；
- 特殊值（如 `KASAN_SLAB_FREE`, `KASAN_GLOBAL_REDZONE` 等）：表示不同类型的红区或已释放区域。

`kasan_find_first_bad_addr()` 和 `kasan_get_alloc_size()` 利用此机制遍历影子内存，分别用于定位首个非法访问点和还原分配大小。

### 错误类型判定逻辑
`get_bug_type()` 首先通过 `access_addr + access_size < access_addr` 检测因负数转换导致的超大访问尺寸（视为越界）。随后依据 `addr_has_metadata()` 判断地址是否属于 KASAN 监控区域：
- 若是，则通过 `get_shadow_bug_type()` 解析影子值确定具体错误类别；
- 若否，则调用 `get_wild_bug_type()` 根据地址范围判断是否为空指针解引用、用户空间访问或完全非法的野指针访问。

### 调试信息增强
`kasan_complete_mode_report_info()` 从对象的 `alloc_meta` 和 `free_meta` 中提取分配/释放时的调用栈（通过 `stack_depot` 存储），极大提升 UAF（Use-After-Free）等问题的可追溯性。`kasan_print_aux_stacks()` 进一步提供 workqueue 等异步上下文的创建栈，辅助并发问题调试。

### 栈变量元数据支持（`CONFIG_KASAN_STACK`）
当启用栈检测时，编译器会为每个栈帧注入描述局部变量布局的字符串（`frame_descr`）。`print_decoded_frame_descr()` 解析该字符串，输出各变量的偏移、大小和名称，帮助定位栈越界的具体变量。

## 4. 依赖关系

- **KASAN 核心模块**：依赖 `kasan.h` 提供的影子内存映射接口（如 `kasan_mem_to_shadow()`）、元数据结构定义及常量（如 `KASAN_GRANULE_SIZE`、各类红区标记值）。
- **内存管理子系统**：使用 `slab.h` 中的 slab 缓存信息（`struct kmem_cache`）及对象元数据访问函数（`kasan_get_alloc_meta()` 等）。
- **调试基础设施**：
  - `stackdepot.h`：用于存储和检索压缩的调用栈；
  - `stacktrace.h`：提供栈回溯能力；
  - `printk.h`：输出错误日志。
- **体系结构相关**：包含 `<asm/sections.h>` 获取内核段信息，并假设栈向下增长（`BUILD_BUG_ON(IS_ENABLED(CONFIG_STACK_GROWSUP))`）。

## 5. 使用场景

- **内存错误检测**：在 KASAN 拦截到非法内存访问（读/写）时，由报告入口（如 `kasan_report_invalid_access()`）调用本文件函数生成详细诊断信息。
- **调试信息输出**：配合 `kasan_report()` 流程，将错误类型、访问地址、对象信息、分配/释放栈等打印至内核日志，供开发者分析。
- **动态分析支持**：为内核测试（如 KUnit、LKDTM）和模糊测试（如 syzkaller）提供精准的内存安全违规反馈。
- **栈保护增强**：在启用 `CONFIG_KASAN_STACK` 时，辅助定位栈缓冲区溢出的具体变量，提升栈保护的有效性。