# percpu-internal.h

> 自动生成时间: 2025-12-07 17:08:49
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `percpu-internal.h`

---

# percpu-internal.h 技术文档

## 1. 文件概述

`percpu-internal.h` 是 Linux 内核中 per-CPU（每个 CPU）内存分配器的内部头文件，定义了 per-CPU 内存管理所需的核心数据结构、辅助函数和全局变量。该文件主要用于支持内核中按 CPU 分配和管理内存的机制，提供高效的本地化内存访问能力，并集成内存控制组（memcg）、内存分配分析（profiling）以及统计信息等功能。

## 2. 核心功能

### 主要数据结构

- **`struct pcpu_block_md`**  
  每个位图块（bitmap block）的元数据结构，用于快速查找连续空闲区域：
  - `scan_hint` / `scan_hint_start`：扫描提示及其起始位置
  - `contig_hint` / `contig_hint_start`：最大连续空闲区域提示
  - `left_free` / `right_free`：左右边界空闲大小
  - `first_free`：第一个空闲位的位置
  - `nr_bits`：该块管理的总位数

- **`struct pcpuobj_ext`**  
  每个 per-CPU 对象的扩展元数据，用于支持：
  - `CONFIG_MEMCG`：记录对象所属的 `obj_cgroup`
  - `CONFIG_MEM_ALLOC_PROFILING`：记录分配来源的代码标签（codetag）

- **`struct pcpu_chunk`**  
  per-CPU 内存块（chunk）的核心结构，代表一个物理内存区域：
  - `list`：链接到 per-CPU 槽（slot）链表
  - `free_bytes`：空闲字节数
  - `base_addr`：对齐后的基地址（避免 false sharing）
  - `alloc_map` / `bound_map`：分配位图和边界位图
  - `md_blocks`：指向所有 `pcpu_block_md` 元数据数组
  - `data`：实际数据区域指针
  - `populated[]`：动态数组，记录已填充的页面位图
  - 支持不可变（`immutable`）、隔离（`isolated`）等状态
  - 包含页对齐所需的偏移量（`start_offset`, `end_offset`）

- **`struct percpu_stats`**（仅当 `CONFIG_PERCPU_STATS` 启用）  
  全局 per-CPU 分配统计信息，包括分配/释放次数、当前/最大活跃分配数、chunk 数量、最小/最大分配大小等。

### 主要辅助函数（内联函数）

- **位图与页转换**
  - `pcpu_chunk_nr_blocks()`：将 chunk 的页数转换为元数据块数量
  - `pcpu_nr_pages_to_map_bits()` / `pcpu_chunk_map_bits()`：将页数转换为位图所需位数

- **对象大小计算**
  - `pcpu_obj_full_size()`：计算带 memcg 扩展信息的对象总大小（考虑所有 CPU）

- **统计信息更新**（条件编译）
  - `pcpu_stats_area_alloc()` / `pcpu_stats_area_dealloc()`：更新区域分配统计
  - `pcpu_stats_chunk_alloc()` / `pcpu_stats_chunk_dealloc()`：更新 chunk 生命周期统计
  - `pcpu_stats_save_ai()`：保存初始分配信息

- **配置判断**
  - `need_pcpuobj_ext()`：判断是否需要 `pcpuobj_ext` 扩展结构

### 全局变量

- `pcpu_lock`：保护 per-CPU 分配器的自旋锁
- `pcpu_chunk_lists`：指向 per-CPU chunk 槽链表数组
- `pcpu_nr_slots`、`pcpu_sidelined_slot`、`pcpu_to_depopulate_slot`：槽管理相关参数
- `pcpu_first_chunk`、`pcpu_reserved_chunk`：初始和保留 chunk 指针
- `pcpu_nr_empty_pop_pages`：空但已填充页面计数
- `pcpu_stats`、`pcpu_stats_ai`：统计信息结构体（条件编译）

## 3. 关键实现

### 元数据块（`pcpu_block_md`）设计

- 采用“提示”（hint）机制加速连续空闲空间查找：
  - `contig_hint` 记录当前已知的最大连续空闲长度
  - `scan_hint` 用于在向前扫描时避免重复检查已知非优区域
- 维护不变式：`scan_hint_start > contig_hint_start` 当且仅当 `scan_hint == contig_hint`，确保扫描逻辑正确性
- 同时维护左右边界空闲（`left_free`/`right_free`）和首个空闲位（`first_free`），支持多种分配策略

### 内存布局优化

- `base_addr` 使用 `____cacheline_aligned_in_smp` 对齐，避免与 `free_bytes` 和 `chunk_md` 共享缓存行，减少 false sharing

### 扩展支持机制

- 通过 `NEED_PCPUOBJ_EXT` 宏条件编译 `pcpuobj_ext` 字段，仅在启用 memcg 或分配分析时包含
- `pcpu_obj_full_size()` 动态计算每个对象所需额外空间（如 `obj_cgroup*` 指针数组）

### 统计信息收集

- 在 `CONFIG_PERCPU_STATS` 下，所有分配/释放操作均更新全局和 chunk 级统计
- 使用 `lockdep_assert_held(&pcpu_lock)` 确保统计更新在锁保护下进行
- chunk 级统计（如 `nr_alloc`）用于局部调试，全局统计用于系统级监控

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/types.h>`：基础类型定义
  - `<linux/percpu.h>`：per-CPU 基础接口
  - `<linux/memcontrol.h>`：内存控制组（memcg）支持

- **配置选项依赖**：
  - `CONFIG_MEMCG`：启用基于 cgroup 的内存记账
  - `CONFIG_MEM_ALLOC_PROFILING`：启用分配来源追踪
  - `CONFIG_PERCPU_STATS`：启用详细分配统计

- **与其他模块交互**：
  - 与 `mm/percpu.c` 紧密耦合，提供内部数据结构和辅助函数
  - 依赖内存管理子系统（如 page allocator）进行底层页面分配
  - 与 cgroup 子系统交互以实现 per-object 内存记账

## 5. 使用场景

- **内核初始化阶段**：`pcpu_first_chunk` 和 `pcpu_reserved_chunk` 用于早期 per-CPU 变量分配
- **运行时动态分配**：通过 `pcpu_chunk` 管理动态创建的 per-CPU 内存区域，支持模块加载等场景
- **内存压力回收**：利用 `populated[]` 位图和 `nr_empty_pop_pages` 跟踪可回收页面
- **资源控制**：在容器化环境中，通过 `obj_cgroup` 实现 per-CPU 内存的 cgroup 限制
- **性能分析**：通过分配分析和统计信息定位内存使用热点或泄漏
- **NUMA 优化**：per-CPU 分配天然适配 NUMA 架构，减少远程内存访问