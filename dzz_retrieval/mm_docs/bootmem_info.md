# bootmem_info.c

> 自动生成时间: 2025-12-07 15:41:59
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bootmem_info.c`

---

# bootmem_info.c 技术文档

## 1. 文件概述

`bootmem_info.c` 是 Linux 内核中用于管理启动阶段保留内存（bootmem）元数据的辅助模块。该文件主要负责在系统初始化期间，为与内存热插拔（memory hotplug）相关的内核数据结构（如 `pglist_data`、`mem_section` 的 memmap 和 usage 结构）所占用的物理页面打上特殊的标记，并通过引用计数机制跟踪这些页面的生命周期。当这些页面不再被需要时（例如在内存热移除过程中），可安全地释放回 buddy allocator。

该机制确保了在内存热插拔操作中，用于描述内存布局的关键元数据页面不会被意外释放或重用，同时支持在适当时候回收这些保留页面以提高内存利用率。

## 2. 核心功能

### 主要函数

- **`get_page_bootmem(unsigned long info, struct page *page, unsigned long type)`**  
  为指定的 `struct page` 设置 bootmem 标记：  
  - 将 `page->index` 设为类型 `type`  
  - 设置 `PG_private` 标志  
  - 将 `page->private` 设为附加信息 `info`  
  - 增加页面引用计数

- **`put_page_bootmem(struct page *page)`**  
  减少 bootmem 页面的引用计数；若引用计数降至 1（表示仅剩 bootmem 引用），则清除标记并释放该页面：  
  - 验证 `type` 在合法范围内（`MEMORY_HOTPLUG_MIN/MAX_BOOTMEM_TYPE`）  
  - 清除 `PG_private` 标志和 `private` 字段  
  - 初始化 `lru` 链表头  
  - 调用 `kmemleak_free_part_phys()` 通知内存泄漏检测器  
  - 调用 `free_reserved_page()` 将页面归还给伙伴系统

- **`register_page_bootmem_info_section(unsigned long start_pfn)`**  
  （`__init` 函数）为指定 PFN 所属内存 section 的以下结构注册 bootmem 信息：  
  - `mem_section` 对应的 `memmap`（即 `struct page` 数组）  
  - `mem_section_usage` 结构  
  根据是否启用 `CONFIG_SPARSEMEM_VMEMMAP`，对 `memmap` 的处理方式不同

- **`register_page_bootmem_info_node(struct pglist_data *pgdat)`**  
  （`__init` 函数）为指定 NUMA 节点的以下结构注册 bootmem 信息：  
  - `pglist_data`（即 `node` 描述符）本身  
  - 该节点包含的所有有效内存 section 的 memmap 和 usage 结构

### 关键数据结构依赖

- `struct page`：通过其 `index`、`private` 字段和 `PG_private` 标志存储 bootmem 元数据
- `struct pglist_data`：NUMA 节点内存描述符
- `struct mem_section`：稀疏内存模型中的内存段描述符
- `struct mem_section_usage`：内存段使用状态位图

## 3. 关键实现

### Bootmem 页面标记机制
- 利用 `struct page` 中未在普通页面中使用的字段：
  - `index` 存储页面类型（`NODE_INFO`、`SECTION_INFO` 或 `MIX_SECTION_INFO`）
  - `private` 存储附加信息（如节点 ID 或 section 编号）
- 通过 `SetPagePrivate()` 标记页面为“私有”，表明其受特殊管理
- 引用计数用于跟踪页面是否仍被 bootmem 系统或其他子系统使用

### 稀疏内存模型适配
- **非 `VMEMMAP` 模式**（`!CONFIG_SPARSEMEM_VMEMMAP`）：  
  `memmap` 是动态分配的虚拟地址，需手动遍历其对应的物理页面并逐个调用 `get_page_bootmem()`
- **`VMEMMAP` 模式**：  
  `memmap` 是线性映射，通过专用函数 `register_page_bootmem_memmap()` 处理（定义在其他文件中）

### 节点与 Section 注册逻辑
- `register_page_bootmem_info_node()` 遍历节点内所有 PFN，按 `PAGES_PER_SECTION` 步进
- 使用 `early_pfn_to_nid()` 确保 PFN 仅在其所属节点注册，避免多节点平台上的重复注册
- 仅对 `pfn_valid(pfn)` 有效的 PFN 进行处理

### 安全释放机制
- `put_page_bootmem()` 中的 `BUG_ON()` 确保类型值在预定义范围内，防止非法操作
- 引用计数检查 (`page_ref_dec_return() == 1`) 确保只有最后一个引用释放时才真正归还页面
- 调用 `kmemleak_free_part_phys()` 避免内存泄漏检测器误报

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/mm.h>`：核心内存管理定义
  - `<linux/memblock.h>`：早期内存分配器
  - `<linux/bootmem_info.h>`：本模块的公共接口声明（含类型常量和函数原型）
  - `<linux/memory_hotplug.h>`：内存热插拔相关定义（如 `MEMORY_HOTPLUG_MIN/MAX_BOOTMEM_TYPE`）
  - `<linux/kmemleak.h>`：内存泄漏检测接口

- **功能依赖**：
  - 稀疏内存模型（`CONFIG_SPARSEMEM`）：`register_page_bootmem_info_section` 的实现依赖于 sparse memory 架构
  - 内存热插拔子系统：bootmem 类型常量和释放逻辑服务于热插拔场景
  - 伙伴分配器（buddy allocator）：通过 `free_reserved_page()` 归还页面

- **外部调用**：
  - `register_page_bootmem_memmap()`（仅在 `VMEMMAP` 模式下）：由 `mm/sparse-vmemmap.c` 提供
  - `free_reserved_page()`：由 `mm/page_alloc.c` 提供

## 5. 使用场景

- **系统初始化阶段**：  
  在 `mm_init()` 或类似初始化路径中，通过 `register_page_bootmem_info_node()` 为每个 NUMA 节点的元数据页面注册 bootmem 信息

- **内存热移除（Memory Hot-Unplug）**：  
  当某个内存 section 被移除时，相关代码（如 `memory_block_release()`）会调用 `put_page_bootmem()` 释放之前保留的 memmap 和 usage 页面

- **内存热添加（Memory Hot-Add）的逆向操作**：  
  在热添加过程中分配的元数据页面，在后续移除时通过此机制安全回收

- **调试与内存泄漏检测**：  
  通过 `kmemleak` 集成，确保 bootmem 页面在释放时被正确跟踪，避免误报内存泄漏

该文件是内存热插拔基础设施的重要组成部分，确保内核元数据页面的生命周期得到精确管理，从而支持动态内存配置的可靠性。