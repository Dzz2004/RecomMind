# kasan\report_hw_tags.c

> 自动生成时间: 2025-12-07 16:19:27
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\report_hw_tags.c`

---

# kasan/report_hw_tags.c 技术文档

## 1. 文件概述

`kasan/report_hw_tags.c` 是 Linux 内核中硬件标签型 KASAN（Kernel Address Sanitizer）子系统的一部分，专门用于处理基于硬件内存标签（Hardware Tag-Based KASAN）的错误报告逻辑。该文件实现了与硬件辅助内存标签机制相关的地址解析、分配大小计算、元数据提取和标签打印等功能，为 KASAN 在支持 MTE（Memory Tagging Extension）等硬件特性的平台上提供高效的内存错误检测能力。

## 2. 核心功能

### 主要函数：

- **`kasan_find_first_bad_addr(const void *addr, size_t size)`**  
  返回发生内存访问违规的第一个无效地址。在硬件标签模式下，该地址已由硬件精确标识，无需遍历标签。

- **`kasan_get_alloc_size(void *object, struct kmem_cache *cache)`**  
  根据对象的内存标签推断其实际分配大小，通过扫描连续的有效标签粒度（granule）来估算。

- **`kasan_metadata_fetch_row(char *buffer, void *row)`**  
  从指定内存行中提取每个粒度对应的硬件内存标签，并填充到输出缓冲区。

- **`kasan_print_tags(u8 addr_tag, const void *addr)`**  
  打印指针携带的标签（pointer tag）与目标地址处存储的内存标签（memory tag），用于诊断标签不匹配错误。

### 关键常量/宏（来自其他头文件）：
- `KASAN_GRANULE_SIZE`：KASAN 硬件标签模式下的最小内存粒度（通常为 16 字节）。
- `KASAN_TAG_INVALID`：表示无效或已释放内存的特殊标签值。
- `META_BYTES_PER_ROW`：每行元数据包含的标签字节数。
- `hw_get_mem_tag()`：内联函数，用于读取指定地址的硬件内存标签。

## 3. 关键实现

- **精确错误地址定位**：  
  在硬件标签 KASAN 中，CPU 在发生标签不匹配时会直接触发异常，并将出错地址传递给处理函数。因此 `kasan_find_first_bad_addr()` 直接返回经 `kasan_reset_tag()` 清除指针高地址标签后的原始地址，无需像软件 KASAN 那样遍历影子内存。

- **分配大小推断机制**：  
  `kasan_get_alloc_size()` 通过逐粒度（每次偏移 `KASAN_GRANULE_SIZE`）读取内存标签，累加有效标签（非 `KASAN_TAG_INVALID`）所覆盖的长度，直到遇到无效标签或达到缓存对象最大尺寸（`cache->object_size`）。若对象已被释放（所有标签为无效），则返回 0。

- **元数据提取与标签打印**：  
  `kasan_metadata_fetch_row()` 利用 `hw_get_mem_tag()` 从物理内存中直接读取硬件维护的标签位，用于调试信息展示；`kasan_print_tags()` 则对比指针标签与内存标签，帮助开发者快速识别“use-after-free”或“out-of-bounds”等错误的根本原因。

- **跳过元数据存在性检查**：  
  注释明确指出，在硬件标签模式下，相关函数仅作用于 slab 分配器管理的内存区域，这些区域必然具备有效的标签元数据，因此省略了 `addr_has_metadata` 检查以提升性能。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/kasan.h>`：KASAN 公共接口定义
  - `<linux/mm.h>`、`<linux/memory.h>`：内存管理相关结构和函数
  - `"kasan.h"`（本地头文件）：包含硬件标签 KASAN 的内部实现细节，如 `hw_get_mem_tag()`、`KASAN_GRANULE_SIZE` 等

- **架构依赖**：  
  本文件仅在启用 `CONFIG_KASAN_HW_TAGS` 配置选项且运行于支持内存标签扩展（如 ARM64 MTE）的硬件平台上编译使用。

- **与其他 KASAN 模块的关系**：  
  作为 `report.c` 的硬件标签专用替代实现，被 KASAN 错误处理主流程调用，与通用报告逻辑解耦。

## 5. 使用场景

- **内存错误检测**：当内核代码发生越界访问、使用已释放内存等错误时，硬件触发异常，KASAN 调用本文件中的函数精确定位错误地址并生成诊断信息。
- **调试信息输出**：在 KASAN 报告中打印指针标签与内存标签的对比，辅助开发者分析标签不匹配的原因。
- **分配大小估算**：在报告 use-after-free 错误时，尝试恢复原始分配大小以提供更准确的上下文信息。
- **元数据可视化**：配合调试工具（如 `kasan.dump`）提取并显示内存区域的标签布局，用于深入分析内存状态。