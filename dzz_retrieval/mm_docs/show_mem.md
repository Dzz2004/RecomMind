# show_mem.c

> 自动生成时间: 2025-12-07 17:18:59
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `show_mem.c`

---

# show_mem.c 技术文档

## 1. 文件概述

`show_mem.c` 是 Linux 内核中用于提供内存状态信息查询和展示功能的核心实现文件。该文件实现了通用的 `show_mem()` 相关接口，用于在系统调试、内存压力分析或 OOM（Out-Of-Memory）诊断等场景下，输出当前系统的内存使用状况，包括各内存区域（zone）的空闲页数、活跃/非活跃匿名页与文件页、可回收内存、高内存统计等关键指标。此外，还提供了用户空间可通过 `/proc/meminfo` 等接口间接调用的内存信息获取函数。

## 2. 核心功能

### 全局变量
- `atomic_long_t _totalram_pages`：系统总物理内存页数（以页为单位），标记为 `__read_mostly` 优化缓存局部性。
- `unsigned long totalreserve_pages`：系统保留内存页数，用于保障关键内核操作。
- `unsigned long totalcma_pages`：CMA（Contiguous Memory Allocator）区域总页数。

### 主要函数
- `si_mem_available(void)`：估算当前可用于用户空间分配而不触发交换或 OOM 的内存页数。
- `si_meminfo(struct sysinfo *val)`：填充 `sysinfo` 结构体，提供全局内存统计信息（如总内存、空闲内存、共享内存等）。
- `si_meminfo_node(struct sysinfo *val, int nid)`（仅当 `CONFIG_NUMA` 启用时）：为指定 NUMA 节点填充内存信息。
- `show_free_areas(unsigned int filter, nodemask_t *nodemask, int max_zone_idx)`：打印详细的内存使用和空闲区域信息，支持按 NUMA 节点过滤。
- `show_mem_node_skip(...)`：根据传入标志和 cpuset 策略判断是否跳过显示某 NUMA 节点。
- `show_migration_types(...)`：将页面迁移类型位图转换为可读字符（如 'U' 表示不可移动，'M' 表示可移动等）。
- `node_has_managed_zones(...)`：判断指定节点在给定最大 zone 索引范围内是否存在受管内存。

## 3. 关键实现

### 内存可用性估算 (`si_mem_available`)
该函数通过以下步骤估算“安全可用”内存：
1. **基础可用内存** = 全局空闲页数 - 系统保留页数。
2. **可释放的 Page Cache**：取活跃/非活跃文件页之和，减去其一半与所有 zone 低水位线总和中的较小值（防止过度回收导致 thrashing）。
3. **可回收内核内存**：包括可回收 slab 和其他可回收内核内存，同样减去其一半与低水位线的较小值。
4. 最终结果不低于 0。

此算法旨在提供一个保守但实用的“不会引发交换或 OOM”的可用内存估计值，被 `/proc/meminfo` 中的 `MemAvailable` 字段使用。

### NUMA 感知的内存信息展示
- 在 `CONFIG_NUMA` 配置下，`show_free_areas` 和 `si_meminfo_node` 按节点分别统计内存。
- 通过 `show_mem_node_skip` 函数结合 `SHOW_MEM_FILTER_NODES` 标志和当前进程的 `cpuset_current_mems_allowed`，实现仅显示当前任务允许访问的 NUMA 节点内存信息，提升诊断相关性。

### 内存统计项输出
`show_free_areas` 输出两类信息：
- **全局统计**：包括各类 LRU 链表页数、脏页、回写页、slab、页表、bounce buffer、free_pcp（每 CPU 页面缓存）、CMA 空闲页等。
- **按节点统计**：每个在线且有受管内存的节点单独一行，包含 kB 单位的各项内存使用量，并标注节点是否“all_unreclaimable”。

### 迁移类型可视化
`show_migration_types` 将 buddy allocator 中的迁移类型位图（如 `MIGRATE_UNMOVABLE`, `MIGRATE_MOVABLE`, `MIGRATE_CMA` 等）映射为单字符标识，便于在调试输出中快速识别内存碎片特性。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/mm.h>`, `<linux/mmzone.h>`：核心内存管理数据结构和宏定义。
  - `<linux/vmstat.h>`：提供 `global_node_page_state()` 等全局内存计数器访问接口。
  - `<linux/cma.h>`, `<linux/hugetlb.h>`：CMA 和大页支持。
  - `<linux/cpuset.h>`：NUMA 节点过滤依赖 cpuset 的内存策略。
  - `"internal.h"`, `"swap.h"`：内核 MM 子系统内部头文件。

- **配置选项依赖**：
  - `CONFIG_NUMA`：启用 NUMA 相关函数和节点过滤逻辑。
  - `CONFIG_HIGHMEM`：高内存统计支持。
  - `CONFIG_CMA` / `CONFIG_MEMORY_ISOLATION`：影响迁移类型字符映射。
  - `CONFIG_TRANSPARENT_HUGEPAGE`：在节点统计中增加透明大页相关字段。

- **导出符号**：
  - `_totalram_pages`（GPL 例外）
  - `si_mem_available()`（GPL）
  - `si_meminfo()`（GPL）

供其他内核模块（如 procfs、OOM killer、内存热插拔等）使用。

## 5. 使用场景

- **系统调试与监控**：通过 `/proc/meminfo`、`/proc/zoneinfo` 或内核日志（如 OOM 日志）查看详细内存分布。
- **OOM Killer 触发时**：`show_free_areas()` 被调用以打印完整的内存状态快照，辅助分析内存耗尽原因。
- **内存压力评估**：`si_mem_available()` 为用户空间提供可靠的可用内存估计，避免应用因错误判断空闲内存而崩溃。
- **NUMA 系统调优**：在多节点系统中，按节点展示内存使用情况，帮助识别内存不平衡或局部耗尽问题。
- **内核开发与测试**：开发者可通过手动触发内存信息打印（如通过 SysRq）验证内存分配、回收行为是否符合预期。