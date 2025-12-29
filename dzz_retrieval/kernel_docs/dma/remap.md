# dma\remap.c

> 自动生成时间: 2025-10-25 13:16:22
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `dma\remap.c`

---

# `dma/remap.c` 技术文档

## 1. 文件概述

`dma/remap.c` 是 Linux 内核中用于 DMA（Direct Memory Access）一致性内存管理的辅助实现文件。该文件提供了一组通用函数，用于将物理页面（`struct page`）重新映射到内核虚拟地址空间中，并标记为 DMA 一致性映射区域（`VM_DMA_COHERENT`）。这些函数主要用于支持架构无关的 DMA 映射操作，特别是在需要将非连续物理页或连续物理内存块映射为连续虚拟地址的场景中。

## 2. 核心功能

### 主要函数：

- **`dma_common_find_pages(void *cpu_addr)`**  
  根据给定的内核虚拟地址 `cpu_addr`，查找其对应的 `struct page` 数组。该地址必须是由 `dma_common_*_remap` 系列函数创建的、标记为 `VM_DMA_COHERENT` 的 vmalloc 区域。

- **`dma_common_pages_remap(struct page **pages, size_t size, pgprot_t prot, const void *caller)`**  
  将一组非连续的物理页面（由 `pages` 数组指定）重新映射为一个连续的内核虚拟地址区域，并标记为 `VM_DMA_COHERENT`。该函数不可在原子上下文（如中断处理程序）中调用。

- **`dma_common_contiguous_remap(struct page *page, size_t size, pgprot_t prot, const void *caller)`**  
  将一段物理上连续的内存区域（起始于 `page`，长度为 `size`）重新映射为连续的内核虚拟地址，并标记为 `VM_DMA_COHERENT`。内部会临时分配一个 `struct page *` 数组来描述每一页。

- **`dma_common_free_remap(void *cpu_addr, size_t size)`**  
  释放由上述 `remap` 函数创建的虚拟映射区域。会验证该区域是否为有效的 `VM_DMA_COHERENT` 类型，若无效则触发警告。

### 数据结构：
- 无显式定义新数据结构，但依赖于内核已有的：
  - `struct page`
  - `struct vm_struct`
  - `pgprot_t`

## 3. 关键实现

- **VM 区域标识**：所有通过 `dma_common_*_remap` 创建的映射区域均使用 `VM_DMA_COHERENT` 标志，以便后续可通过 `find_vm_area()` 识别其为 DMA 一致性映射区域。
  
- **页面数组管理**：
  - `dma_common_pages_remap` 直接使用传入的 `pages` 数组，并在成功 `vmap` 后将其保存到 `vm_struct->pages` 字段中，供 `dma_common_find_pages` 查询。
  - `dma_common_contiguous_remap` 针对连续物理内存，动态构建 `pages` 数组（使用 `kvmalloc_array`），调用 `vmap` 后立即释放该临时数组，但 `vmap` 内部会复制页面指针。

- **内存分配与映射**：
  - 使用 `vmap()` 将物理页面映射到 vmalloc 区域，确保返回的虚拟地址在内核空间连续。
  - 使用 `kvmalloc_array`/`kvfree` 进行临时内存分配，兼顾大内存分配的可靠性（可回退到 vmalloc）。

- **错误处理与调试**：
  - `dma_common_free_remap` 中包含 `WARN(1, ...)`，用于检测非法释放操作，提升调试能力。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/dma-map-ops.h>`：提供 DMA 映射操作相关的类型和接口。
  - `<linux/slab.h>`：提供 `kvmalloc_array`/`kvfree` 等内存分配接口。
  - `<linux/vmalloc.h>`：提供 `vmap`、`vunmap`、`find_vm_area` 等 vmalloc 区域管理函数。

- **内核子系统依赖**：
  - **VMALLOC 子系统**：依赖 `vmap`/`vunmap` 实现虚拟地址映射。
  - **内存管理子系统（MM）**：依赖 `struct page` 和页面操作函数（如 `nth_page`）。
  - **DMA 子系统**：作为 `dma_map_ops` 的底层支持，被架构特定的 DMA 实现（如 ARM、ARM64）调用。

## 5. 使用场景

- **DMA 一致性内存分配**：当设备驱动需要分配大块 DMA 一致性内存，且底层无法直接提供连续虚拟地址时，可通过此模块将物理页重新映射为连续虚拟地址。
  
- **IOMMU 或非一致性缓存架构支持**：在缓存不一致的系统（如某些 ARM 平台）上，为保证 CPU 与设备对内存视图一致，需使用特殊页表属性（`pgprot_t`）进行映射，本模块提供通用封装。

- **通用 DMA 映射框架后端**：作为 `dma_map_ops` 中 `alloc`/`free` 等操作的辅助实现，被 `dma-direct.c`、`arm_dma_alloc.c` 等架构相关代码调用。

- **调试与验证**：通过 `VM_DMA_COHERENT` 标志和 `WARN` 机制，帮助检测非法的 DMA 内存释放操作，提升系统稳定性。