# percpu-km.c

> 自动生成时间: 2025-12-07 17:09:21
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `percpu-km.c`

---

# percpu-km.c 技术文档

## 1. 文件概述

`percpu-km.c` 是 Linux 内核中用于在 **无 MMU（nommu）架构** 上实现 per-CPU 变量分配的内存管理模块。该文件提供了一种基于连续内核内存（通过 `alloc_pages()` 分配）的 per-CPU chunk 分配机制，称为 **percpu-km**（kernel memory based per-CPU allocation）。由于 nommu 架构无法使用基于虚拟地址重映射的 per-CPU 分配方式（如 `EMBED_FIRST_CHUNK` 或 `PAGE_FIRST_CHUNK`），因此需要这种直接分配物理连续内存的方式。

该实现要求所有 CPU 的 per-CPU 数据必须位于同一个内存组（group）中，且不支持 NUMA 架构。

## 2. 核心功能

### 主要函数

| 函数名 | 功能说明 |
|--------|---------|
| `pcpu_post_unmap_tlb_flush` | TLB 刷新回调（空实现，因 nommu 无 TLB） |
| `pcpu_populate_chunk` | 填充 chunk 页面（空实现，因一次性分配全部内存） |
| `pcpu_depopulate_chunk` | 释放 chunk 页面（空实现） |
| `pcpu_create_chunk` | 创建一个新的 per-CPU chunk，通过 `alloc_pages()` 分配连续物理内存 |
| `pcpu_destroy_chunk` | 销毁指定的 per-CPU chunk，释放其占用的页面 |
| `pcpu_addr_to_page` | 将虚拟地址转换为对应的 `struct page`（使用 `virt_to_page`） |
| `pcpu_verify_alloc_info` | 验证 per-CPU 分配信息是否符合 percpu-km 的限制条件 |
| `pcpu_should_reclaim_chunk` | 判断是否应回收 chunk（始终返回 `false`，不支持动态回收） |

### 关键数据结构依赖

- `struct pcpu_chunk`：per-CPU 内存块描述符
- `struct pcpu_alloc_info`：per-CPU 内存布局分配信息
- `pcpu_group_sizes[]`：每组的大小（以字节为单位）
- 全局锁 `pcpu_lock`：保护 per-CPU chunk 状态变更

## 3. 关键实现

### 内存分配策略
- 每个 per-CPU chunk 作为一个 **物理连续的内存块** 分配，使用 `alloc_pages(gfp, order)`。
- 分配大小为 `pcpu_group_sizes[0]`（即第一组的总大小），向上对齐到 2 的幂次页数（`order_base_2(nr_pages)`）。
- 若实际所需页数不是 2 的幂，则会 **浪费部分内存**，内核会发出警告。

### 初始化与验证
- 在 `pcpu_verify_alloc_info()` 中强制要求：
  - 仅允许 **一个内存组**（`ai->nr_groups == 1`）
  - 所有 CPU 必须属于同一组（隐含要求）
- 不兼容 `CONFIG_NEED_PER_CPU_PAGE_FIRST_CHUNK`，编译时通过 `#error` 检查。

### 空操作回调
- `pcpu_populate_chunk` / `pcpu_depopulate_chunk` / `pcpu_post_unmap_tlb_flush` 均为空实现：
  - 因内存一次性分配完成，无需按需填充或释放页面
  - nommu 架构无 TLB，无需刷新

### 地址转换
- 使用 `page_address(pages)` 获取连续页面的内核虚拟地址作为 `chunk->base_addr`
- `pcpu_addr_to_page()` 直接调用 `virt_to_page()`，依赖内核线性映射

### 资源统计与追踪
- 调用 `pcpu_stats_chunk_alloc/dealloc()` 更新 per-CPU 内存统计
- 使用 `trace_percpu_create/destroy_chunk` 提供 ftrace 跟踪点

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/log2.h>`：用于 `order_base_2()` 计算分配阶数
- **内核配置依赖**：
  - 必须定义 `CONFIG_NEED_PER_CPU_KM`（由架构 Kconfig 设置）
  - 禁止同时定义 `CONFIG_NEED_PER_CPU_PAGE_FIRST_CHUNK`
- **核心 per-CPU 子系统依赖**：
  - 依赖 `mm/percpu.c` 提供的通用接口（如 `pcpu_alloc_chunk`, `pcpu_free_chunk`, `pcpu_set_page_chunk` 等）
  - 使用全局 per-CPU 锁 `pcpu_lock`
- **内存管理子系统**：
  - 依赖 `alloc_pages()` / `__free_pages()` 进行底层内存分配
  - 依赖 `virt_to_page()` / `page_address()` 进行地址转换

## 5. 使用场景

- **目标架构**：专用于 **无 MMU（nommu）的嵌入式或特殊架构**（如某些 ARM、Blackfin、OpenRISC 等）
- **启动阶段**：在内核初始化早期设置 per-CPU 第一块内存（first chunk）
- **内存模型限制**：
  - 适用于所有 CPU 共享统一内存空间的 SMP 或 UP 系统
  - **不支持 NUMA**：要求所有 CPU 距离为 `LOCAL_DISTANCE`
- **典型配置组合**：
  - `CONFIG_SMP=y` + `CONFIG_NEED_PER_CPU_KM=y`
  - 通常配合 `CONFIG_HAVE_SETUP_PER_CPU_AREA` 使用，由架构代码提供 per-CPU 布局信息
- **性能特点**：
  - 分配简单，但可能浪费内存（因页数需 2 的幂对齐）
  - 无运行时页面填充开销，适合资源受限环境