# kasan\shadow.c

> 自动生成时间: 2025-12-07 16:21:25
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\shadow.c`

---

# kasan/shadow.c 技术文档

## 1. 文件概述

`kasan/shadow.c` 是 Linux 内核中 KASAN（Kernel Address SANitizer）子系统的核心运行时文件之一，主要负责管理 KASAN 的影子内存（shadow memory）。该文件同时支持 **通用 KASAN 模式**（CONFIG_KASAN_GENERIC）和 **软件标签 KASAN 模式**（CONFIG_KASAN_SW_TAGS）。其核心职责包括：

- 提供内存访问检查的入口函数（读/写）
- 实现对标准内存操作函数（如 `memset`、`memcpy`、`memmove`）的 KASAN 仪器化包装
- 提供影子内存的毒化（poisoning）与解毒（unpoisoning）接口
- 支持内存热插拔场景下的影子内存动态映射与释放

## 2. 核心功能

### 主要函数

| 函数名 | 功能说明 |
|--------|--------|
| `__kasan_check_read` / `__kasan_check_write` | KASAN 编译器插桩调用的运行时检查入口，分别用于读/写访问验证 |
| `memset` / `memcpy` / `memmove` | 在不支持编译器内置 KASAN 内存函数时，提供带边界检查的 C 库函数重定义 |
| `__asan_memset` / `__asan_memcpy` / `__asan_memmove` | 编译器生成的 ASan 仪器化代码调用的标准接口，执行内存范围检查后调用底层实现 |
| `__hwasan_*` 系列函数 | 软件标签模式下的别名函数，指向对应的 `__asan_*` 实现 |
| `kasan_poison` | 将指定内存区域对应的影子内存设置为特定毒化值（如 0xFF 表示不可访问） |
| `kasan_unpoison` | 解除指定内存区域的毒化状态，使其可被合法访问 |
| `kasan_poison_last_granule` | （仅通用模式）对对象末尾未对齐部分进行精确毒化，用于检测越界访问 |
| `kasan_mem_notifier` | 内存热插拔通知回调，动态分配或释放新增/移除物理内存对应的影子内存 |

### 关键宏与配置

- `CONFIG_CC_HAS_KASAN_MEMINTRINSIC_PREFIX`：指示编译器是否能生成 `__asan_mem*` 内建函数
- `CONFIG_GENERIC_ENTRY`：影响是否覆盖标准 `mem*` 函数
- `CONFIG_KASAN_SW_TAGS`：启用软件标签模式支持
- `CONFIG_MEMORY_HOTPLUG`：启用内存热插拔下的影子内存管理

## 3. 关键实现

### 影子内存毒化机制

- **地址去标签处理**：在 `kasan_poison` 和 `kasan_unpoison` 中，通过 `kasan_reset_tag()` 去除指针的 Top Byte Ignore (TBI) 标签，确保影子地址计算基于真实物理地址。
- **粒度对齐检查**：使用 `KASAN_GRANULE_MASK` 验证传入地址和大小是否按 KASAN 粒度（通常为 8 字节）对齐，避免非法影子操作。
- **KFENCE 兼容**：显式跳过 KFENCE 分配的内存区域，防止与 KFENCE 的边界检查机制冲突。
- **通用模式末尾毒化**：`kasan_poison_last_granule` 在对象末尾非对齐字节对应的影子字节中写入偏移量，使越界访问触发精确错误。

### 内存操作函数仪器化

- 当编译器不支持自动仪器化 `mem*` 函数时（即未定义 `CONFIG_CC_HAS_KASAN_MEMINTRINSIC_PREFIX` 且非 `CONFIG_GENERIC_ENTRY`），文件通过 `#undef` 重定义标准库函数，在调用实际实现前插入 KASAN 范围检查。
- 所有 `__asan_*` 和 `__hwasan_*` 函数均导出为符号（`EXPORT_SYMBOL`），供编译器生成的仪器化代码调用。

### 内存热插拔支持

- `shadow_mapped()`：遍历内核页表，判断指定影子地址是否已映射。
- `kasan_mem_notifier()`：
  - **MEM_GOING_ONLINE**：若影子未映射，则通过 `__vmalloc_node_range()` 动态分配并映射影子页，使用 `kmemleak_ignore` 避免内存泄漏误报。
  - **MEM_OFFLINE / MEM_CANCEL_ONLINE**：通过 `find_vm_area()` 判断影子是否由 `vmalloc` 分配，若是则调用 `vfree()` 释放；启动时静态映射的影子暂不支持释放（存在内存泄漏）。

## 4. 依赖关系

- **架构相关头文件**：依赖 `<asm/cacheflush.h>` 和 `<asm/tlbflush.h>` 进行缓存/TLB 维护（虽未直接调用，但为潜在需求预留）。
- **内存管理子系统**：重度依赖 `mm/` 中的 `vmalloc`、`memory_hotplug`、`page_alloc` 等机制。
- **KASAN 内部模块**：包含本地头文件 `"kasan.h"`，调用 `kasan_check_range()`、`kasan_mem_to_shadow()` 等核心函数。
- **KFENCE 子系统**：通过 `is_kfence_address()` 与 KFENCE 协同工作，避免双重检查。
- **kmemleak**：在热插拔影子分配时调用 `kmemleak_ignore()` 防止误报。

## 5. 使用场景

- **内核构建时**：当启用 `CONFIG_KASAN` 时，该文件被编译进内核，为所有内存访问提供运行时检查基础。
- **运行时内存访问**：任何被 KASAN 仪器化的内核代码在访问内存前会调用 `__kasan_check_read/write`。
- **内核内存分配器**（slab/slub/slob） 在分配/释放对象时调用 `kasan_unpoison`/`kasan_poison` 标记内存状态。
- **内存热插拔事件**：当系统在线/离线内存区域时，通过 `kasan_mem_notifier` 动态维护对应影子内存的生命周期。
- **调试与错误检测**：配合 KASAN 报告机制，精准捕获越界访问、使用已释放内存等错误。