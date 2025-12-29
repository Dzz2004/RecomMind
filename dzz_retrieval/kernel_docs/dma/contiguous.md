# dma\contiguous.c

> 自动生成时间: 2025-10-25 13:10:56
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `dma\contiguous.c`

---

# `dma/contiguous.c` 技术文档

## 1. 文件概述

`dma/contiguous.c` 是 Linux 内核中实现 **连续内存分配器**（Contiguous Memory Allocator, CMA）的核心文件之一，专为 DMA（Direct Memory Access）映射框架服务。该文件负责在系统启动早期阶段预留物理上连续的大块内存区域，供后续设备驱动在需要连续物理内存时使用（如摄像头、视频编解码器等无 scatter-gather 能力的硬件设备）。CMA 的核心优势在于：预留的内存区域在未被设备使用时可被内核用于页缓存（page cache），当设备请求时通过页迁移（page migration）机制释放出连续内存，从而兼顾内存利用率与设备需求。

## 2. 核心功能

### 主要全局变量
- `dma_contiguous_default_area`：指向默认全局 CMA 区域的 `struct cma` 指针。
- `size_cmdline`, `base_cmdline`, `limit_cmdline`：解析内核启动参数 `cma=` 得到的用户自定义 CMA 区域配置。
- `numa_cma_size[]`, `dma_contiguous_numa_area[]`, `dma_contiguous_pernuma_area[]`（仅当 `CONFIG_DMA_NUMA_CMA` 启用）：用于 NUMA 架构下按节点配置 CMA 区域。

### 主要函数
- `early_cma(char *p)`：解析内核启动参数 `cma=`，设置全局 CMA 区域的大小、基地址和上限。
- `early_numa_cma(char *p)`（仅当 `CONFIG_DMA_NUMA_CMA` 启用）：解析 `numa_cma=` 参数，为指定 NUMA 节点设置 CMA 大小。
- `early_cma_pernuma(char *p)`（仅当 `CONFIG_DMA_NUMA_CMA` 启用）：解析 `cma_pernuma=` 参数，为所有在线 NUMA 节点设置统一的 CMA 大小。
- `dma_contiguous_reserve(phys_addr_t limit)`：主入口函数，在系统启动早期预留默认全局 CMA 区域（及 NUMA CMA 区域）。
- `dma_contiguous_reserve_area(phys_addr_t size, phys_addr_t base, phys_addr_t limit, struct cma **res_cma, bool fixed)`：预留自定义 CMA 区域的通用接口。
- `dma_contiguous_early_fixup(phys_addr_t base, unsigned long size)`：架构相关的 CMA 内存区域修正钩子（弱符号，默认为空）。

### 辅助函数
- `cma_early_percent_memory(void)`：根据 `CONFIG_CMA_SIZE_PERCENTAGE` 计算基于系统总内存百分比的 CMA 大小。

## 3. 关键实现

### CMA 区域预留时机与机制
- CMA 区域必须在 **早期内存分配器**（如 `memblock`）激活后、其他子系统大量分配内存前预留，以确保能获得足够大的连续物理内存块。
- 预留通过调用 `cma_declare_contiguous()` 或 `cma_declare_contiguous_nid()` 实现，这些函数最终将内存区域标记为 CMA 专用，并初始化 `struct cma` 管理结构。

### 配置优先级
CMA 默认区域大小的确定遵循以下优先级：
1. **内核命令行参数 `cma=`**：最高优先级，可指定大小、基地址和上限（格式：`size[@base][-limit]`）。
2. **编译时配置**（`.config`）：
   - `CONFIG_CMA_SIZE_MBYTES`：固定大小（MB）。
   - `CONFIG_CMA_SIZE_PERCENTAGE`：系统总内存的百分比。
   - `CONFIG_CMA_SIZE_SEL_*`：决定如何组合上述两个值（取 MB 值、百分比值、最小值或最大值）。

### NUMA 支持
- 当启用 `CONFIG_DMA_NUMA_CMA` 时，支持为每个 NUMA 节点独立预留 CMA 区域：
  - `numa_cma=`：为指定节点设置特定大小。
  - `cma_pernuma=`：为所有在线节点设置统一大小。
- 通过 `for_each_node()` 遍历节点，调用 `cma_declare_contiguous_nid()` 在对应节点内存范围内预留。

### 架构适配
- `dma_contiguous_early_fixup()` 为架构提供钩子，可在 CMA 区域预留后进行特定修正（如调整内存属性）。
- 特定平台（如兆芯 KH40000）可通过条件编译跳过 CMA 预留。

### 内存区域约束
- `limit` 参数限制 CMA 区域的最高物理地址，确保与设备 DMA 地址能力兼容。
- `fixed` 标志控制是否严格在指定 `base` 地址预留（`true`）或在 `[base, limit]` 范围内灵活选择（`false`）。

## 4. 依赖关系

- **核心依赖**：
  - `<linux/cma.h>`：CMA 核心 API（`cma_declare_contiguous*` 等）。
  - `<linux/memblock.h>`：早期内存管理。
  - `<linux/dma-map-ops.h>`：DMA 映射框架。
- **配置依赖**：
  - `CONFIG_CMA`：CMA 功能总开关。
  - `CONFIG_DMA_CMA`：启用 DMA 框架对 CMA 的支持。
  - `CONFIG_DMA_NUMA_CMA`：启用 NUMA 感知的 CMA。
  - `CONFIG_CMA_SIZE_*`：编译时 CMA 大小配置选项。
- **架构依赖**：
  - 依赖架构提供的 `dma_contiguous_early_fixup()` 实现（若需要）。
  - 依赖 `is_zhaoxin_kh40000()` 等平台检测函数（特定平台）。

## 5. 使用场景

1. **嵌入式设备驱动**：摄像头、GPU、视频编解码器等需要大块连续物理内存的设备驱动，通过 `dma_alloc_coherent()` 等接口分配 CMA 内存。
2. **系统启动配置**：
   - 发行版内核通过 `.config` 设置默认 CMA 大小，适配多数硬件。
   - 用户通过内核参数 `cma=`、`numa_cma=`、`cma_pernuma=` 精确控制 CMA 布局。
3. **NUMA 系统优化**：在 NUMA 架构中，为每个节点预留本地 CMA 区域，减少跨节点内存访问开销。
4. **内存高效利用**：CMA 区域在空闲时作为可移动页（movable pages）参与内存管理，提升整体内存利用率。