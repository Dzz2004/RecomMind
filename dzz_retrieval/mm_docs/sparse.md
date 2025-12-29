# sparse.c

> 自动生成时间: 2025-12-07 17:25:01
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sparse.c`

---

# sparse.c 技术文档

## 1. 文件概述

`sparse.c` 是 Linux 内核中实现 **SPARSEMEM（稀疏内存模型）** 的核心文件，用于管理物理内存的稀疏映射。该模型将整个物理地址空间划分为固定大小的“内存段”（memory sections），仅对实际存在的内存段分配 `mem_map`（页描述符数组），从而在支持大物理地址空间的同时节省内存开销。此文件负责内存段的初始化、节点关联、存在性标记以及与内存热插拔和 vmemmap 相关的功能。

## 2. 核心功能

### 主要数据结构
- **`mem_section`**: 全局内存段数组，每个元素代表一个内存段，存储该段的 `mem_map` 指针及其他元数据。
  - 在 `CONFIG_SPARSEMEM_EXTREME` 下为二级指针（动态分配根数组）
  - 否则为静态二维数组 `[NR_SECTION_ROOTS][SECTIONS_PER_ROOT]`
- **`section_to_node_table`**: （仅当 `NODE_NOT_IN_PAGE_FLAGS` 时）用于通过内存段号查找所属 NUMA 节点的查找表。
- **`__highest_present_section_nr`**: 记录当前系统中编号最大的已存在内存段，用于优化遍历。

### 主要函数
- **`memory_present()`**: 标记指定 PFN 范围内的内存段为“存在”，并关联到指定 NUMA 节点。
- **`memblocks_present()`**: 遍历所有 memblock 内存区域，调用 `memory_present()` 标记所有系统内存。
- **`sparse_index_init()`**: （仅 `CONFIG_SPARSEMEM_EXTREME`）为指定内存段分配其所在的根数组项。
- **`sparse_encode_mem_map()` / `sparse_decode_mem_map()`**: 编码/解码 `mem_map` 指针，使其能通过段内偏移计算出实际 PFN。
- **`subsection_map_init()`**: （仅 `CONFIG_SPARSEMEM_VMEMMAP`）初始化子段（subsection）位图，用于更细粒度的内存管理。
- **`page_to_nid()`**: （仅 `NODE_NOT_IN_PAGE_FLAGS`）通过页结构获取其所属 NUMA 节点。
- **`mminit_validate_memmodel_limits()`**: 验证传入的 PFN 范围是否超出 SPARSEMEM 模型支持的最大地址。

### 辅助宏与内联函数
- **`for_each_present_section_nr()`**: 高效遍历所有已存在的内存段。
- **`first_present_section_nr()`**: 获取第一个存在的内存段编号。
- **`sparse_encode_early_nid()` / `sparse_early_nid()`**: 在早期启动阶段利用 `section_mem_map` 字段临时存储 NUMA 节点 ID。

## 3. 关键实现

### 内存段管理
- 物理内存被划分为 `PAGES_PER_SECTION` 大小的段（通常 128MB）。
- `mem_section` 数组索引即为段号（section number），通过 `__nr_to_section()` 宏访问。
- 段的存在性通过 `SECTION_MARKED_PRESENT` 位标记，并维护 `__highest_present_section_nr` 以加速遍历。

### NUMA 节点关联
- 若页结构体（`struct page`）中未直接存储节点 ID（`NODE_NOT_IN_PAGE_FLAGS`），则使用 `section_to_node_table` 查找。
- 在 `memory_present()` 中通过 `set_section_nid()` 建立段到节点的映射。

### 动态内存段分配（SPARSEMEM_EXTREME）
- 为减少静态内存占用，`mem_section` 采用二级结构：
  - 一级：`mem_section[]` 指向多个二级数组
  - 二级：每个 `mem_section[root]` 指向 `SECTIONS_PER_ROOT` 个 `struct mem_section`
- `sparse_index_init()` 在需要时动态分配二级数组（使用 `kzalloc_node` 或 `memblock_alloc_node`）。

### 早期启动阶段的优化
- 在 `mem_map` 分配前，复用 `section_mem_map` 字段的高位存储 NUMA 节点 ID（`sparse_encode_early_nid()`）。
- 此信息在分配真实 `mem_map` 前被清除。

### vmemmap 子段支持
- 当启用 `CONFIG_SPARSEMEM_VMEMMAP` 时，每个内存段进一步划分为子段（subsections）。
- `subsection_map_init()` 初始化位图，标记哪些子段包含有效内存，支持更灵活的内存热插拔。

### 地址空间验证
- `mminit_validate_memmodel_limits()` 确保传入的 PFN 范围不超过 `PHYSMEM_END`（SPARSEMEM 模型最大支持地址），防止越界。

## 4. 依赖关系

- **头文件依赖**:
  - `<linux/mm.h>`, `<linux/mmzone.h>`: 内存管理核心定义
  - `<linux/memblock.h>`: 早期内存分配器
  - `<linux/vmalloc.h>`: 用于 vmemmap 映射
  - `<asm/dma.h>`: 架构相关 DMA 定义
  - `"internal.h"`: MM 子系统内部头文件
- **配置选项依赖**:
  - `CONFIG_SPARSEMEM`: 基础稀疏内存模型
  - `CONFIG_SPARSEMEM_EXTREME`: 动态内存段分配
  - `CONFIG_SPARSEMEM_VMEMMAP`: 使用虚拟映射的 mem_map
  - `CONFIG_MEMORY_HOTPLUG`: 内存热插拔支持
  - `NODE_NOT_IN_PAGE_FLAGS`: 页结构体不包含节点 ID
- **与其他模块交互**:
  - **Memory Block (memblock)**: 通过 `for_each_mem_pfn_range()` 获取初始内存布局
  - **Page Allocator**: 提供 `struct page` 数组（mem_map）
  - **NUMA Subsystem**: 通过节点 ID 关联内存与 CPU 拓扑
  - **Memory Hotplug**: 依赖本文件提供的段管理接口进行内存增删

## 5. 使用场景

- **系统启动初始化**:
  - `memblocks_present()` 在 `mm_init()` 阶段被调用，标记所有固件报告的内存区域为“存在”。
- **内存热插拔**:
  - 热添加内存时，调用 `memory_present()` 标记新段；热移除时清理对应段。
  - `sparse_index_init()` 支持动态扩展 `mem_section` 数组。
- **页到节点转换**:
  - 当 `page_to_nid()` 被调用时（如页面迁移、NUMA 调度），通过段查找节点。
- **vmemmap 优化**:
  - 在支持 `SPARSEMEM_VMEMMAP` 的架构（如 x86_64, ARM64）上，`subsection_map_init()` 使内核能按子段粒度映射 `struct page`，减少虚拟地址空间占用。
- **调试与验证**:
  - `mminit_validate_memmodel_limits()` 在开发阶段捕获内存模型配置错误。