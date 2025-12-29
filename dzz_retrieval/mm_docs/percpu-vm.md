# percpu-vm.c

> 自动生成时间: 2025-12-07 17:10:25
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `percpu-vm.c`

---

# percpu-vm.c 技术文档

## 1. 文件概述

`percpu-vm.c` 是 Linux 内核中 per-CPU（每 CPU）内存管理子系统的核心实现文件之一，负责基于 **vmalloc 虚拟地址空间** 的 per-CPU chunk（块）分配器。该文件实现了将物理页面动态映射到 per-CPU 虚拟地址区域的功能，是 per-CPU 子系统的默认 chunk 分配器。

其核心思想是：为每个 CPU 单元在 vmalloc 区域中预留连续的虚拟地址空间，但底层物理页面按需分配和映射，从而支持灵活、可扩展的 per-CPU 内存布局。

## 2. 核心功能

### 主要函数

| 函数名 | 功能描述 |
|--------|--------|
| `pcpu_chunk_page()` | 通过虚拟地址反查对应 struct page（仅用于非 immutable chunk） |
| `pcpu_get_pages()` | 获取全局临时 pages 数组，用于暂存待分配/释放的页面指针 |
| `pcpu_alloc_pages()` | 为所有 CPU 单元分配指定范围的物理页面 |
| `pcpu_free_pages()` | 释放指定范围内的物理页面 |
| `pcpu_map_pages()` | 将物理页面映射到 per-CPU chunk 的虚拟地址，并建立反向映射（page → chunk） |
| `pcpu_unmap_pages()` | 解除虚拟地址到物理页面的映射，并记录页面指针供后续释放 |
| `pcpu_pre_unmap_flush()` | 在解映射前执行 cache flush（针对整个区域） |
| `pcpu_post_unmap_tlb_flush()` | 解映射后执行 TLB 刷新（针对整个区域） |
| `pcpu_post_map_flush()` | 映射完成后执行 cache flush（针对整个区域） |

### 关键辅助函数
- `__pcpu_map_pages()`：调用 `vmap_pages_range_noflush()` 执行实际映射
- `__pcpu_unmap_pages()`：调用 `vunmap_range_noflush()` 执行实际解映射

## 3. 关键实现

### 3.1 页面索引机制
- 使用 `pcpu_page_idx(cpu, page_idx)` 宏将二维坐标 `(cpu, page_idx)` 映射为一维数组索引。
- 全局临时数组 `pages[]` 由 `pcpu_get_pages()` 提供，大小为 `pcpu_nr_units * pcpu_unit_pages`，受 `pcpu_alloc_mutex` 保护。

### 3.2 内存分配策略
- 调用 `alloc_pages_node(cpu_to_node(cpu), gfp | __GFP_HIGHMEM, 0)` 为每个 CPU 在其本地 NUMA 节点分配单页。
- 支持 HIGHMEM 页面，提高内存利用率。

### 3.3 批量缓存与 TLB 管理
- **避免逐 CPU 刷新**：所有 flush 操作（cache 和 TLB）均作用于 **整个 per-CPU 区域**，从 `pcpu_low_unit_cpu` 到 `pcpu_high_unit_cpu`。
- 使用 `noflush` 版本的 vmap/vunmap 函数（如 `vmap_pages_range_noflush`），由调用者统一控制刷新时机，减少开销。

### 3.4 错误处理与回滚
- `pcpu_alloc_pages()` 和 `pcpu_map_pages()` 在失败时会回滚已分配/映射的资源，确保状态一致性。
- 回滚逻辑按 CPU 顺序释放，避免遗漏。

### 3.5 反向映射支持
- `pcpu_map_pages()` 中调用 `pcpu_set_page_chunk(page, chunk)`，建立物理页面到所属 chunk 的关联，用于后续内存追踪和调试。

## 4. 依赖关系

- **内部依赖**：
  - `mm/internal.h`：包含 per-CPU 内存管理的内部定义
  - `pcpu_*` 系列宏和函数（如 `pcpu_chunk_addr`, `pcpu_page_idx`, `pcpu_set_page_chunk`）
  - 全局变量：`pcpu_alloc_mutex`, `pcpu_nr_units`, `pcpu_unit_pages`, `pcpu_low_unit_cpu`, `pcpu_high_unit_cpu`

- **外部依赖**：
  - **vmalloc 子系统**：使用 `vmalloc_to_page()`, `vmap_pages_range_noflush()`, `vunmap_range_noflush()` 等接口
  - **内存管理子系统**：依赖 `alloc_pages_node()`, `__free_page()` 等页面分配器
  - **体系结构相关**：依赖 `flush_cache_vmap()`, `flush_cache_vunmap()`, `flush_tlb_kernel_range()` 等架构特定的缓存/TLB 操作

## 5. 使用场景

- **Per-CPU 内存初始化**：系统启动时为 per-CPU 变量分配初始内存块。
- **动态扩展**：当现有 per-CPU chunk 空间不足时，分配新的 chunk 并映射物理页面。
- **内存热插拔**：在 CPU 热插拔过程中，为新上线 CPU 分配 per-CPU 内存。
- **模块加载**：内核模块使用 `DEFINE_PER_CPU` 定义变量时，可能触发新的 per-CPU 内存分配。
- **内存回收**：当 chunk 被释放时，解映射并释放其占用的物理页面。

该文件作为 per-CPU 子系统的默认分配器，在大多数架构（尤其是 x86、ARM64 等）上被广泛使用，提供了高效、可扩展的 per-CPU 内存管理能力。