# memblock.c

> 自动生成时间: 2025-12-07 16:38:16
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `memblock.c`

---

# memblock.c 技术文档

## 1. 文件概述

`memblock.c` 实现了 Linux 内核早期启动阶段的内存管理机制——**memblock**。该机制用于在常规内存分配器（如 buddy allocator）尚未初始化之前，对物理内存进行粗粒度的区域管理。它将系统内存抽象为若干连续的内存区域（regions），支持“可用内存”（memory）、“保留内存”（reserved）和“物理内存”（physmem，部分架构支持）三种类型，为内核早期初始化提供内存添加、查询和分配能力。

## 2. 核心功能

### 主要数据结构
- `struct memblock_region`：表示一个连续的物理内存区域，包含基地址（base）、大小（size）、NUMA 节点 ID 和属性标志。
- `struct memblock_type`：管理一类内存区域的集合，包含区域数组、当前数量（cnt）、最大容量（max）和名称。
- `struct memblock`：全局 memblock 管理结构，包含 `memory` 和 `reserved` 两种类型的 `memblock_type`，以及分配方向（bottom_up）和当前分配上限（current_limit）。
- `physmem`（条件编译）：描述不受 `mem=` 参数限制的实际物理内存布局。

### 主要函数与变量
- `memblock_add()` / `memblock_add_node()`：向 memblock 添加可用内存区域。
- `memblock_reserve()`：标记内存区域为保留（不可用于动态分配）。
- `memblock_phys_alloc*()` / `memblock_alloc*()`：分配物理或虚拟地址的内存。
- `memblock_overlaps_region()`：判断指定区域是否与某类 memblock 区域重叠。
- `__memblock_find_range_bottom_up()`：从低地址向高地址查找满足条件的空闲内存范围。
- 全局变量 `memblock`：静态初始化的主 memblock 结构体。
- `max_low_pfn`, `min_low_pfn`, `max_pfn`, `max_possible_pfn`：记录 PFN（页帧号）边界信息。

### 配置宏
- `INIT_MEMBLOCK_REGIONS`：初始内存/保留区域数组大小（默认 128）。
- `CONFIG_HAVE_MEMBLOCK_PHYS_MAP`：启用 `physmem` 类型支持。
- `CONFIG_MEMBLOCK_KHO_SCRATCH`：支持仅从特定标记（KHO_SCRATCH）区域分配内存。
- `CONFIG_ARCH_KEEP_MEMBLOCK`：决定是否在初始化完成后保留 memblock 数据结构。

## 3. 关键实现

### 初始化与存储
- `memblock` 结构体在编译时静态初始化，其 `memory` 和 `reserved` 的区域数组分别使用 `memblock_memory_init_regions` 和 `memblock_reserved_init_regions`，初始容量由 `INIT_MEMBLOCK_*_REGIONS` 定义。
- 每个 `memblock_type` 的 `cnt` 初始设为 1，但实际第一个条目为空的占位符，有效区域从索引 1 开始（后续代码处理）。
- 支持通过 `memblock_allow_resize()` 动态扩容区域数组，但需谨慎避免与 initrd 等关键区域冲突。

### 内存区域管理
- 使用 `for_each_memblock_type` 宏遍历指定类型的区域。
- `memblock_addrs_overlap()` 通过比较区间端点判断两个物理内存区域是否重叠。
- `memblock_overlaps_region()` 封装了对某类所有区域的重叠检测。

### 分配策略
- 默认采用 **top-down**（从高地址向低地址）分配策略，可通过 `memblock_set_bottom_up(true)` 切换为 **bottom-up**。
- 分配时受 `current_limit` 限制（默认 `MEMBLOCK_ALLOC_ANYWHERE` 表示无限制）。
- 支持基于 NUMA 节点、对齐要求、内存属性（如 `MEMBLOCK_MIRROR`、`MEMBLOCK_KHO_SCRATCH`）的精细控制。
- `choose_memblock_flags()` 根据 `kho_scratch_only` 和镜像内存存在性动态选择分配标志。

### 安全与调试
- `memblock_cap_size()` 防止地址计算溢出（确保 `base + size <= PHYS_ADDR_MAX`）。
- 条件编译的 `memblock_dbg()` 宏用于调试输出（需开启 `memblock_debug`）。
- 使用 `__initdata_memblock` 属性标记仅在初始化阶段使用的数据，便于后续释放。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/memblock.h>`：定义 memblock API 和数据结构。
  - `<linux/kernel.h>`, `<linux/init.h>`：提供基础内核功能和初始化宏。
  - `<linux/pfn.h>`：PFN 相关操作。
  - `<asm/sections.h>`：访问内核链接段信息。
  - 架构相关头文件（如 `internal.h`）。
- **配置依赖**：
  - `CONFIG_NUMA`：影响 `contig_page_data` 的定义。
  - `CONFIG_KEXEC_HANDOVER`：引入 kexec 相关头文件。
  - `CONFIG_HAVE_MEMBLOCK_PHYS_MAP`：启用 `physmem` 支持。
- **后续移交**：在 `mem_init()` 中，memblock 管理的内存会被释放给 buddy allocator，完成内存管理权移交。

## 5. 使用场景

- **内核早期初始化**：在 `start_kernel()` 初期，架构代码（如 `setup_arch()`）调用 `memblock_add()` 注册可用物理内存，调用 `memblock_reserve()` 保留内核镜像、设备树、initrd 等关键区域。
- **早期内存分配**：在 slab/buddy 分配器就绪前，使用 `memblock_alloc()` 分配大块连续内存（如页表、中断向量表、ACPI 表解析缓冲区）。
- **内存布局查询**：通过 `for_each_memblock()` 等宏遍历内存区域，用于构建 e820 表、EFI 内存映射或 NUMA 拓扑。
- **特殊分配需求**：支持从镜像内存（`MEMBLOCK_MIRROR`）或 KHO scratch 区域分配，满足安全启动或崩溃转储等场景。
- **调试与分析**：通过 debugfs 接口（未在片段中体现）导出 memblock 布局，辅助内存问题诊断。