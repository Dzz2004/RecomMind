# cma.c

> 自动生成时间: 2025-12-07 15:42:51
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cma.c`

---

# cma.c 技术文档

## 1. 文件概述

`cma.c` 是 Linux 内核中 **Contiguous Memory Allocator**（CMA，连续内存分配器）的核心实现文件。该模块用于在系统启动早期预留大块物理连续的内存区域，并在运行时按需分配和释放这些内存，以满足设备驱动（如 GPU、多媒体硬件等）对大块连续物理内存的需求。CMA 在保证系统整体内存碎片可控的前提下，提供了一种高效管理连续内存的机制。

## 2. 核心功能

### 主要数据结构
- `struct cma`：表示一个 CMA 区域，包含基地址（`base_pfn`）、页数（`count`）、位图粒度（`order_per_bit`）、名称（`name`）、位图（`bitmap`）及自旋锁等。
- `cma_areas_data[MAX_CMA_AREAS]`：静态数组，用于存储最多 `MAX_CMA_AREAS` 个 CMA 区域。
- `cma_areas`：指向当前使用的 CMA 区域数组（可动态扩展）。
- `cma_area_count`：已注册的 CMA 区域数量。
- `cma_mutex`：保护 CMA 区域注册过程的互斥锁。

### 主要函数
- `cma_get_base()` / `cma_get_size()` / `cma_get_name()`：获取 CMA 区域的基地址、大小和名称。
- `cma_bitmap_aligned_mask()` / `cma_bitmap_aligned_offset()` / `cma_bitmap_pages_to_bits()`：辅助函数，用于处理位图对齐和单位转换。
- `cma_clear_bitmap()`：在 CMA 位图中标记指定范围为“空闲”。
- `cma_activate_area()`：激活一个已预留的 CMA 区域，初始化其位图并验证区域有效性。
- `cma_init_reserved_areas()`：在内核初始化阶段（`core_initcall`）激活所有已声明的 CMA 区域。
- `cma_reserve_pages_on_error()`：设置标志，指示在激活失败时是否保留页面不释放回 buddy 系统。
- `cma_alloc_areas()`：动态扩展 CMA 区域数组容量。
- `cma_init_reserved_mem()`：从**已通过 memblock 预留的内存区域**创建 CMA 区域。
- `cma_declare_contiguous_nid()`：**直接通过 memblock 预留内存并创建 CMA 区域**（支持 NUMA 节点指定）。

## 3. 关键实现

### 位图管理
- CMA 使用位图（`bitmap`）跟踪区域内页面的分配状态。
- 每个位可代表 `2^order_per_bit` 个页面（即 `1 << order_per_bit` 页），以减少位图内存开销。
- 对齐分配通过 `cma_bitmap_aligned_mask()` 和 `cma_bitmap_aligned_offset()` 计算位图中的对齐偏移，确保分配起始地址满足对齐要求。

### 区域激活与验证
- `cma_activate_area()` 在内核 slab 分配器可用后执行：
  - 分配位图内存（`bitmap_zalloc`）。
  - **强制要求整个 CMA 区域位于同一内存 zone**（如 DMA、Normal），因为后续的 `alloc_contig_range()` 要求如此。
  - 调用 `init_cma_reserved_pageblock()` 将页面块标记为 MIGRATE_CMA 类型，使其可被 CMA 分配器迁移/回收。
- 若区域跨 zone 或位图分配失败，则根据 `reserve_pages_on_error` 标志决定是否将页面释放回 buddy 系统。

### 内存预留方式
- **方式一**（`cma_init_reserved_mem`）：由平台代码先调用 `memblock_reserve()` 预留内存，再通过此函数将其注册为 CMA 区域。
- **方式二**（`cma_declare_contiguous_nid`）：直接在此函数内部调用 memblock 接口预留内存（支持指定 base/limit/alignment/fixed/NUMA node），是更常用的接口。

### 初始化流程
- CMA 区域在早期启动阶段通过上述两个函数之一注册（仅记录元数据）。
- 所有区域在 `core_initcall` 阶段统一通过 `cma_init_reserved_areas()` 激活，此时内存子系统已基本就绪。

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`、`<linux/memblock.h>`、`internal.h` 等，使用 page、zone、buddy allocator、migration 等机制。
- **同步原语**：使用 `mutex`（`cma_mutex`）和 `spinlock`（`cma->lock`）保证并发安全。
- **调试支持**：集成 `CONFIG_CMA_DEBUG`、`CONFIG_CMA_DEBUGFS`、`trace/events/cma.h` 提供调试信息和运行时监控。
- **架构相关**：依赖 `PFN_PHYS`、`__pa()` 等宏，需架构提供正确实现。
- **NUMA 支持**：通过 `nid` 参数支持多节点系统（需 `CONFIG_NUMA`）。

## 5. 使用场景

- **设备驱动**：GPU、视频编解码器、DMA 引擎等需要大块连续物理内存的驱动通过 `dma_alloc_coherent()` 等接口间接使用 CMA。
- **系统启动配置**：通过内核命令行参数（如 `cma=64M@0-0xffffffff`）或设备树（`reserved-memory` 节点）声明 CMA 区域，最终由 `cma_declare_contiguous_nid()` 处理。
- **平台特定预留**：SoC 厂商在板级初始化代码中调用 `cma_init_reserved_mem()` 将特定物理地址范围注册为 CMA。
- **内存热插拔/休眠**：CMA 区域在系统休眠前需释放所有分配，在恢复后重新激活（依赖底层内存管理支持）。