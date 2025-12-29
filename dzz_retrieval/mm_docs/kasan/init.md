# kasan\init.c

> 自动生成时间: 2025-12-07 16:14:56
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\init.c`

---

# kasan/init.c 技术文档

## 1. 文件概述

`kasan/init.c` 是 Linux 内核中 KASAN（Kernel Address Sanitizer）子系统的关键初始化文件，负责在内核启动早期阶段为 KASAN 的影子内存（shadow memory）区域建立初始页表映射。该文件实现了使用特殊预分配的“早期影子页”来填充整个 KASAN 影子区域的机制，确保在完整内存管理子系统（如 slab 分配器）尚未就绪前，KASAN 能够正常工作。此外，这些早期影子页在后期还会被复用为“零影子页”，用于覆盖那些允许访问但 KASAN 不主动监控的内存区域（如 vmalloc、vmemmap 等）。

## 2. 核心功能

### 主要全局数据结构
- `kasan_early_shadow_page[PAGE_SIZE]`: 预分配的单页内存，用作早期影子内存页和后期零影子页。
- `kasan_early_shadow_pte[]`: 预分配的 PTE 页表项数组，所有条目指向 `kasan_early_shadow_page`。
- `kasan_early_shadow_pmd[]` (条件编译): 预分配的 PMD 页表项数组（当 `CONFIG_PGTABLE_LEVELS > 2` 时存在）。
- `kasan_early_shadow_pud[]` (条件编译): 预分配的 PUD 页表项数组（当 `CONFIG_PGTABLE_LEVELS > 3` 时存在）。
- `kasan_early_shadow_p4d[]` (条件编译): 预分配的 P4D 页表项数组（当 `CONFIG_PGTABLE_LEVELS > 4` 时存在）。

### 主要函数
- `early_alloc()`: 在 slab 分配器不可用时，使用 memblock 从物理内存中分配对齐内存。
- `zero_pte_populate()`: 填充 PTE 页表，使其所有条目都指向 `kasan_early_shadow_page`。
- `zero_pmd_populate()`: 填充 PMD 页表，根据对齐情况选择直接映射预分配 PTE 表或动态分配 PTE 表。
- `zero_pud_populate()`: 填充 PUD 页表，逻辑类似 `zero_pmd_populate`。
- `zero_p4d_populate()`: 填充 P4D 页表，逻辑类似 `zero_pmd_populate`。
- `kasan_populate_early_shadow()`: **核心入口函数**，遍历指定的影子内存范围，逐级建立页表映射，全部指向早期影子页。
- `kasan_free_*()` 系列函数 (`kasan_free_pte`, `kasan_free_pmd`, `kasan_free_pud`, `kasan_free_p4d`): 用于在运行时释放不再需要的影子页表（代码片段末尾被截断）。
- `kasan_*_table()` 系列内联函数: 判断给定的页表项是否指向 KASAN 的预分配早期影子表。
- `kernel_pte_init()`, `pmd_init()`, `pud_init()`: 弱符号函数，供架构层实现特定的页表项初始化。

## 3. 关键实现

### 早期影子内存机制
- 在内核启动极早期（slab 分配器不可用），KASAN 无法动态分配影子内存。此时，整个 KASAN 影子区域通过页表映射到同一个物理页 `kasan_early_shadow_page`。
- 该页的内容全为 0，表示对应的主内存区域是完全可访问的（无越界/未初始化访问）。
- 这种“写时复制”式的共享映射极大节省了早期内存开销。

### 多级页表处理
- 代码通过条件编译 (`#if CONFIG_PGTABLE_LEVELS > X`) 适配不同架构的页表层级（2~5 级）。
- 对于每个页表层级（PGD → P4D → PUD → PMD → PTE），提供对应的填充函数 (`zero_*_populate`)。
- 在填充过程中，优先利用大页对齐特性：
  - 如果当前处理的地址范围与页表项大小（如 PGDIR_SIZE, PUD_SIZE）对齐，则直接将该页表项指向下一级的**预分配**影子页表（如 `kasan_early_shadow_p4d`）。
  - 否则，动态分配下一级页表（使用 `early_alloc` 或 slab），并递归填充。

### 动态分配策略
- `early_alloc()`: 使用 `memblock_alloc_try_nid` 在 `MEMBLOCK_ALLOC_ACCESSIBLE` 区域分配内存，失败则 panic。
- 在 slab 可用后 (`slab_is_available() == true`)，改用标准内核页表分配函数（如 `pte_alloc_one_kernel`）。

### 架构适配
- `lm_alias()`: 用于处理某些架构（如 ARM64）中线性映射（linear mapping）与虚拟地址别名的问题，确保页表项指向正确的物理页。
- 弱符号函数（如 `kernel_pte_init`）允许架构代码在分配页表后执行特定初始化。

## 4. 依赖关系

- **内存管理子系统**: 重度依赖 `memblock`（早期分配）、`mm`（页表操作）、`pgalloc`（页表分配）。
- **KASAN 核心**: 依赖 `kasan.h` 中定义的宏和接口，是 KASAN 初始化流程的一部分。
- **体系结构代码**: 依赖 `asm/page.h` 和 `asm/pgalloc.h` 提供的页表操作宏（如 `pgd_offset_k`, `pmd_populate_kernel`）及页表层级常量（`PTRS_PER_P*`）。
- **通用内核头文件**: 使用 `init.h`（`__init`）、`slab.h`（`slab_is_available`）等。

## 5. 使用场景

- **内核启动早期**: 在 `start_kernel()` 流程中，于内存管理子系统（特别是 slab）完全初始化**之前**调用 `kasan_populate_early_shadow()`，为整个内核地址空间的 KASAN 影子区域建立初始映射。
- **KASAN 初始化**: 作为 `kasan_init()` 函数的关键步骤，确保 KASAN 在启用后能立即监控内存访问。
- **运行时影子内存管理**: （由被截断的 `kasan_free_*` 函数暗示）在 KASAN 动态扩展或收缩监控区域时，用于释放不再使用的影子页表内存。
- **特殊内存区域覆盖**: `kasan_early_shadow_page` 在后期被复用为“零影子页”，通过 `kasan_unpoison_vmalloc` 等机制，安全地覆盖 vmalloc、vmemmap 等区域，避免误报。