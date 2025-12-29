# dma\coherent.c

> 自动生成时间: 2025-10-25 13:10:06
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `dma\coherent.c`

---

# `dma/coherent.c` 技术文档

## 1. 文件概述

`dma/coherent.c` 实现了 Linux 内核中**设备专属一致性 DMA 内存池**（per-device coherent DMA memory pool）的管理机制。该机制允许平台代码（如设备树解析代码）为特定设备预分配一块物理连续、CPU 与设备均可高效访问的内存区域，并通过标准的 `dma_alloc_coherent()` 接口从该内存池中分配内存，从而避免通用 DMA 分配器的开销或满足硬件对 DMA 地址范围的特殊要求。

## 2. 核心功能

### 数据结构

- **`struct dma_coherent_mem`**  
  描述一个设备专属的一致性 DMA 内存池：
  - `virt_base`：CPU 虚拟地址（通过 `memremap()` 映射）
  - `device_base`：设备视角的起始 DMA 地址
  - `pfn_base`：物理内存起始页帧号（PFN）
  - `size`：内存池大小（以页为单位）
  - `bitmap`：位图，用于跟踪已分配/空闲页面
  - `spinlock`：保护位图操作的自旋锁
  - `use_dev_dma_pfn_offset`：是否使用设备特定的 PFN 偏移转换 DMA 地址

### 主要函数

- **`dma_declare_coherent_memory()`**  
  由平台代码调用，为设备注册一个一致性 DMA 内存池。
  
- **`dma_release_coherent_memory()`**  
  释放设备关联的一致性内存池资源。

- **`dma_alloc_from_dev_coherent()`**  
  供架构相关 `dma_alloc_coherent()` 实现调用，尝试从设备专属内存池分配内存。

- **`dma_release_from_dev_coherent()`**  
  供架构相关 `dma_free_coherent()` 实现调用，尝试释放内存到设备专属内存池。

- **`dma_mmap_from_dev_coherent()`**  
  供 `dma_mmap_coherent()` 实现调用，将设备专属内存映射到用户空间。

- **内部辅助函数**  
  - `dma_init_coherent_memory()`：初始化内存池结构
  - `_dma_release_coherent_memory()`：释放内存池资源
  - `dma_assign_coherent_memory()`：将内存池绑定到设备
  - `__dma_alloc_from_coherent()` / `__dma_release_from_coherent()` / `__dma_mmap_from_coherent()`：核心分配/释放/映射逻辑

## 3. 关键实现

### 内存池初始化
- 使用 `memremap(phys_addr, size, MEMREMAP_WC)` 将指定物理地址映射为 CPU 可访问的虚拟地址（通常使用写合并 WC 属性）。
- 通过 `bitmap_zalloc()` 分配位图，用于管理页级别的内存分配。
- 支持两种 DMA 地址计算方式：
  - 直接使用传入的 `device_addr`
  - 通过 `phys_to_dma()` 转换物理地址（当 `use_dev_dma_pfn_offset=true` 时）

### 内存分配算法
- 使用 `bitmap_find_free_region()` 在位图中查找连续的空闲页面块（按 2 的幂对齐）。
- 分配成功后返回虚拟地址和对应的设备 DMA 地址。
- 分配的内存会被 `memset()` 清零。

### 线程安全
- 所有位图操作（分配/释放）均通过 `spinlock` 保护，确保 SMP 环境下的安全性。
- 使用 `spin_lock_irqsave()`/`spin_unlock_irqrestore()` 禁用本地中断，防止死锁。

### 地址验证
- 释放和 mmap 操作前会验证虚拟地址是否落在设备内存池范围内，确保操作的安全性。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/io.h>`：提供 `memremap()`/`memunmap()`
  - `<linux/slab.h>`：提供 `kzalloc()`/`kfree()`
  - `<linux/dma-direct.h>`：提供 `phys_to_dma()`
  - `<linux/dma-map-ops.h>`：DMA 映射操作接口
  - `<linux/bitmap.h>`：位图操作（隐式包含）

- **架构依赖**：
  - 依赖架构特定的 `dma_alloc_coherent()` 实现调用 `dma_alloc_from_dev_coherent()` 等接口。
  - 依赖 `phys_to_dma()` 的正确实现（在 `dma-direct.c` 中定义）。

- **配置依赖**：
  - `CONFIG_DMA_GLOBAL_POOL`：文件末尾有未完成的条件编译代码（可能用于全局 DMA 池扩展）。

## 5. 使用场景

1. **嵌入式/SoC 平台**  
   当设备（如 GPU、DSP、网络控制器）要求 DMA 内存位于特定物理地址范围（如 DDR 的保留区域）时，平台代码通过设备树解析调用 `dma_declare_coherent_memory()` 预注册内存池。

2. **性能敏感场景**  
   避免通用 DMA 分配器（如 CMA）的运行时开销，为高频 DMA 操作提供快速、确定性的内存分配。

3. **IOMMU 旁路场景**  
   在无 IOMMU 或 IOMMU 被绕过的系统中，确保设备能直接访问物理连续内存。

4. **用户空间映射**  
   通过 `dma_mmap_from_dev_coherent()` 支持将设备专属 DMA 缓冲区直接映射到用户空间（如 V4L2、DRM 驱动）。