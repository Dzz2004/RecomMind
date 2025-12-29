# dma\mapping.c

> 自动生成时间: 2025-10-25 13:14:22
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `dma\mapping.c`

---

# `dma/mapping.c` 技术文档

## 1. 文件概述

`dma/mapping.c` 是 Linux 内核中与架构无关的 DMA（Direct Memory Access）映射核心实现文件。该文件提供了统一的、可管理的 DMA 内存分配与映射接口，屏蔽了底层硬件（如 IOMMU、直接映射等）的差异，为驱动开发者提供一致的 DMA 操作抽象。同时，它支持“资源管理”（Managed DMA）机制，确保在设备卸载时自动释放 DMA 资源，防止内存泄漏。

## 2. 核心功能

### 主要数据结构
- **`struct dma_devres`**  
  用于实现“Managed DMA”资源管理的私有结构体，包含：
  - `size`：分配的内存大小
  - `vaddr`：内核虚拟地址
  - `dma_handle`：设备可见的 DMA 地址
  - `attrs`：DMA 属性标志（如 `DMA_ATTR_*`）

### 主要函数
- **Managed DMA 接口**
  - `dmam_alloc_attrs()`：分配受管理的 DMA 内存（自动释放）
  - `dmam_free_coherent()`：显式释放受管理的 coherent DMA 内存（通常由 devres 自动调用）

- **DMA 映射/解映射接口**
  - `dma_map_page_attrs()`：将单个页面映射为 DMA 地址
  - `dma_unmap_page_attrs()`：解映射单个页面的 DMA 地址
  - `dma_map_sg_attrs()`：映射 scatterlist 缓冲区（返回成功映射的条目数）
  - `dma_map_sgtable()`：映射 `sg_table` 结构描述的缓冲区（返回错误码）

- **内部辅助函数**
  - `dma_go_direct()` / `dma_alloc_direct()` / `dma_map_direct()`：判断是否可绕过 IOMMU 使用直接映射
  - `__dma_map_sg_attrs()`：`dma_map_sg_attrs()` 和 `dma_map_sgtable()` 的公共实现

## 3. 关键实现

### Managed DMA 资源管理机制
- 使用 `devres`（Device Resource Management）框架实现自动资源回收。
- `dmam_alloc_attrs()` 在分配 DMA 内存后，将 `dma_devres` 结构注册到设备的资源链表中。
- 设备卸载时，`devres` 框架自动调用 `dmam_release()`，进而调用 `dma_free_attrs()` 释放内存。
- `dmam_match()` 用于在显式释放时匹配资源条目，确保一致性。

### 直接映射（Direct Mapping）优化
- 通过 `dma_go_direct()` 判断是否可跳过 IOMMU 操作：
  - 若设备无自定义 `dma_map_ops`，默认使用直接映射。
  - 若启用 `CONFIG_DMA_OPS_BYPASS` 且设备设置 `dma_ops_bypass`，且 DMA 掩码足够大（覆盖物理地址空间），则使用直接映射。
- 直接映射路径调用 `dma_direct_*` 系列函数（定义在 `direct.h` 中），避免 IOMMU 开销。

### 错误处理与调试支持
- 所有映射函数均校验 DMA 方向（`valid_dma_direction`）和设备 DMA 掩码。
- 集成 `KMSAN`（Kernel Memory Sanitizer）支持，通过 `kmsan_handle_dma*` 标记 DMA 访问区域。
- 启用 `DMA_API_DEBUG` 时，调用 `debug_dma_*` 函数记录映射操作，用于检测错误使用（如未映射即访问）。

### Scatterlist 映射语义
- `dma_map_sg_attrs()` 返回实际映射成功的条目数（可能 ≤ `nents`），但**解映射必须使用原始 `nents`**。
- `dma_map_sgtable()` 返回标准错误码（如 `-ENOMEM`, `-EINVAL`），便于错误分类和重试逻辑。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/dma-map-ops.h>`：DMA 操作集抽象（`dma_map_ops`）
  - `<linux/devres.h>`（隐式）：设备资源管理框架
  - `"direct.h"`：直接映射实现（`dma_direct_map_page` 等）
  - `"debug.h"`：DMA 调试接口
- **配置依赖**：
  - `CONFIG_ARCH_HAS_SYNC_DMA_*`：决定是否定义 `dma_default_coherent`
  - `CONFIG_DMA_OPS_BYPASS`：启用 DMA 操作绕过优化
  - `CONFIG_ARCH_DMA_DEFAULT_COHERENT`：设置默认一致性属性
- **底层依赖**：
  - 架构特定的 `arch_dma_*_direct()` 函数（用于判断直接映射可行性）
  - IOMMU 驱动提供的 `dma_map_ops` 实现（当不使用直接映射时）

## 5. 使用场景

- **驱动开发**：
  - 使用 `dmam_alloc_attrs()` 分配 DMA 缓冲区，避免手动释放。
  - 使用 `dma_map_page_attrs()` 或 `dma_map_sg_attrs()` 映射数据缓冲区供设备访问。
- **IOMMU 子系统**：
  - IOMMU 驱动通过注册 `dma_map_ops` 拦截映射请求，实现地址转换和权限控制。
  - 当设备 DMA 能力足够时（如 64 位 DMA 掩码），自动切换至直接映射以提升性能。
- **内存调试**：
  - 与 KMSAN 集成，在 DMA 操作前后标记内存状态，检测 CPU/DMA 访问冲突。
  - 通过 `DMA_API_DEBUG` 捕获驱动错误（如重复映射、方向错误等）。