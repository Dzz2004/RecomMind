# dma\direct.c

> 自动生成时间: 2025-10-25 13:12:42
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `dma\direct.c`

---

# `dma/direct.c` 技术文档

## 1. 文件概述

`dma/direct.c` 实现了 Linux 内核中 **DMA 直接映射操作（DMA direct mapping）** 的核心逻辑。该文件提供了一套不依赖 IOMMU 的 DMA 内存分配与映射机制，适用于物理地址可直接被设备访问的平台（如 x86、ARM64 等无 IOMMU 或 IOMMU 被禁用的场景）。其核心思想是将物理内存地址直接转换为设备可见的 DMA 地址，避免复杂的地址转换开销。

该实现支持多种内存分配策略，包括：
- 连续物理内存分配（CMA 或 buddy allocator）
- SWIOTLB 回退机制（用于处理高地址设备无法访问的情况）
- 原子池分配（用于不可阻塞上下文）
- 高端内存重映射
- 内存加密/解密（如 AMD SEV、Intel TDX 等安全特性）

## 2. 核心功能

### 全局变量
- `zone_dma_bits`：定义 ZONE_DMA 的地址位宽（默认 24 位，即 16MB），可由架构代码覆盖。

### 主要函数
| 函数名 | 功能描述 |
|--------|--------|
| `phys_to_dma_direct()` | 将物理地址转换为 DMA 地址，支持强制解密场景 |
| `dma_direct_to_page()` | 通过 DMA 地址反查对应的 `struct page` |
| `dma_direct_get_required_mask()` | 计算设备所需的 DMA 地址掩码（基于系统最大物理地址）|
| `dma_coherent_ok()` | 检查给定物理地址范围是否在设备的 DMA 地址能力范围内 |
| `dma_direct_alloc()` | **主入口函数**：为设备分配 DMA 内存，支持多种属性和回退策略 |
| `__dma_direct_alloc_pages()` | 底层页面分配函数，尝试最优内存区域并回退到低地址区域 |
| `dma_direct_alloc_from_pool()` | 从原子池分配不可阻塞的 DMA 内存 |
| `dma_direct_alloc_no_mapping()` | 分配无内核虚拟映射的 DMA 内存（返回 `struct page*`）|
| `dma_set_decrypted()` / `dma_set_encrypted()` | 设置内存页为解密/加密状态（用于安全虚拟化）|

### 辅助函数
- `dma_direct_optimal_gfp_mask()`：根据设备 DMA 限制选择最优的 GFP 标志（GFP_DMA / GFP_DMA32）
- `__dma_direct_free_pages()`：释放通过直接分配获得的页面（优先尝试 SWIOTLB 释放）

## 3. 关键实现

### 3.1 DMA 地址空间约束处理
- 使用 `dev->coherent_dma_mask` 和 `dev->bus_dma_limit` 确定设备可寻址的物理地址上限。
- 通过 `dma_coherent_ok()` 验证分配的物理内存是否在设备可访问范围内。
- 若分配的内存超出范围，则回退到更低地址区域（先尝试 GFP_DMA32，再尝试 GFP_DMA）。

### 3.2 多层次内存分配策略
1. **首选 CMA 连续内存**：通过 `dma_alloc_contiguous()` 分配。
2. **回退到 buddy allocator**：使用 `alloc_pages_node()`。
3. **SWIOTLB 支持**：当设备无法访问高地址时，通过 `swiotlb_alloc()` 分配 bounce buffer。
4. **原子上下文支持**：在不可阻塞场景下使用 `dma_direct_alloc_from_pool()` 从预分配池中获取内存。

### 3.3 非一致性缓存与内存属性处理
- 对于非一致性缓存架构（`!dev_is_dma_coherent()`）：
  - 优先使用全局一致性内存池（`CONFIG_DMA_GLOBAL_POOL`）
  - 或启用重映射（`CONFIG_DMA_DIRECT_REMAP`）创建 uncached 映射
  - 或调用架构特定的 `arch_dma_alloc()`
- 调用 `arch_dma_prep_coherent()` 清理内核别名的脏缓存行。

### 3.4 安全内存处理（加密/解密）
- 当 `force_dma_unencrypted(dev)` 为真（如 SEV 环境），分配的内存需标记为解密。
- 使用 `set_memory_decrypted()` / `set_memory_encrypted()` 修改页表属性。
- 解密操作可能阻塞，因此在原子上下文中需使用内存池。

### 3.5 高端内存（HighMem）处理
- 若分配的页面位于高端内存（`PageHighMem`），则必须通过 `dma_common_contiguous_remap()` 创建内核虚拟地址映射。
- 重映射时应用设备特定的页保护属性（`dma_pgprot()`）并处理解密需求。

## 4. 依赖关系

### 内核头文件依赖
- `<linux/memblock.h>`：获取 `max_pfn` 系统最大页帧号
- `<linux/dma-map-ops.h>`：DMA 映射操作抽象接口
- `<linux/scatterlist.h>`：SG 表支持（间接依赖）
- `<linux/set_memory.h>`：内存加密/解密操作（`set_memory_decrypted` 等）
- `<linux/vmalloc.h>`：高端内存重映射支持
- `"direct.h"`：本地 DMA direct 实现的私有头文件

### 配置选项依赖
- `CONFIG_SWIOTLB`：SWIOTLB bounce buffer 支持
- `CONFIG_DMA_COHERENT_POOL`：原子上下文 DMA 内存池
- `CONFIG_DMA_GLOBAL_POOL`：全局一致性 DMA 内存池
- `CONFIG_DMA_DIRECT_REMAP`：非一致性设备的重映射支持
- `CONFIG_ZONE_DMA` / `CONFIG_ZONE_DMA32`：低地址内存区域支持
- `CONFIG_ARCH_HAS_DMA_SET_UNCACHED`：架构特定 uncached 映射支持

### 架构相关依赖
- `phys_to_dma()` / `dma_to_phys()`：架构提供的物理地址与 DMA 地址转换函数
- `arch_dma_prep_coherent()`：架构特定的缓存一致性准备
- `arch_dma_alloc()`：架构特定的 DMA 分配回退路径

## 5. 使用场景

### 5.1 设备驱动 DMA 分配
- 驱动调用 `dma_alloc_coherent()` 或 `dma_alloc_attrs()` 时，若系统未启用 IOMMU，则最终由 `dma_direct_alloc()` 处理。
- 适用于大多数无 IOMMU 的嵌入式系统、传统 PC 平台或 IOMMU 被显式禁用的场景。

### 5.2 安全虚拟化环境
- 在 AMD SEV 或 Intel TDX 等机密计算环境中，DMA 内存需标记为“解密”，该文件通过 `force_dma_unencrypted()` 机制实现。

### 5.3 资源受限或实时系统
- 通过 `DMA_ATTR_NO_KERNEL_MAPPING` 属性分配无内核映射的 DMA 内存，减少 TLB 压力。
- 在中断上下文等不可阻塞场景中，自动使用原子内存池分配。

### 5.4 老旧设备兼容
- 对仅支持 32 位或 24 位 DMA 地址的设备，自动分配低地址内存（通过 GFP_DMA32/GFP_DMA）并验证地址范围。

### 5.5 高端内存平台
- 在 32 位系统或内存大于直接映射区域的平台上，自动处理高端内存的重映射，确保返回有效的内核虚拟地址。