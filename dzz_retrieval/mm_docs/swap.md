# swap.c

> 自动生成时间: 2025-12-07 17:25:49
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `swap.c`

---

# swap.c 技术文档

## 1. 文件概述

`swap.c` 是 Linux 内核内存管理子系统（MM）中的核心文件之一，主要负责页面回收（page reclaim）、LRU（Least Recently Used）链表管理、页面释放以及与交换（swap）机制相关的底层支持逻辑。尽管文件名为 `swap.c`，但其功能不仅限于交换，而是涵盖了通用的页面生命周期管理、LRU 链表操作、页面引用计数释放、可回收性判断等关键内存管理任务。该文件为页面缓存（page cache）、匿名页（anonymous pages）和大页（huge pages）提供统一的释放与 LRU 管理接口。

## 2. 核心功能

### 主要全局变量
- `page_cluster`：控制一次 I/O 操作中尝试换入/换出的页面数量（以 2 的幂表示），默认值由系统配置决定。
- `page_cluster_max`：`page_cluster` 的最大允许值（31，即最多 2^31 页，实际受架构限制）。

### 主要数据结构
- `struct lru_rotate`：每个 CPU 私有的结构，用于在中断禁用上下文中批量处理需移至 LRU 链表尾部的页面（如 `folio_rotate_reclaimable` 场景）。
- `struct cpu_fbatches`：每个 CPU 私有的 folio 批处理结构，包含多个 folio_batch，用于高效地向 LRU 链表添加、停用或激活页面，避免频繁获取 LRU 锁。

### 主要函数
- `__folio_put()`：释放一个 folio 的核心函数，根据 folio 类型（设备内存、大页、普通页）调用相应的释放路径。
- `put_pages_list()`：批量释放通过 `lru` 字段链接的页面列表，常用于网络子系统或 compound page 释放。
- `lru_add_fn()`：将 folio 添加到对应 LRU 链表的回调函数，处理可回收性（evictable/unevictable）状态转换和统计计数。
- `folio_batch_move_lru()`：批量执行 LRU 操作（如添加、移动），在持有 LRU 锁期间完成所有 folio 的处理。
- `folio_rotate_reclaimable()`：在写回完成后，若页面仍可回收，则将其移至 inactive LRU 链表尾部，以延迟其被回收的时间。
- `lru_note_cost()`：记录 LRU 扫描过程中的 I/O 和旋转（rotation）成本，用于后续调整 anon/file LRU 的扫描比例。

## 3. 关键实现

### LRU 批处理机制
为减少 LRU 锁竞争，内核采用 per-CPU 批处理（`folio_batch`）方式暂存待处理的 folio。当批处理满或遇到大页（`folio_test_large`）时，才批量获取 LRU 锁并执行操作（如 `lru_add_fn`）。这显著提升了高并发场景下的性能。

### 可回收性管理
页面是否可回收由 `folio_evictable()` 判断，主要依据是否被 mlock 锁定。在添加到 LRU 时：
- 若页面变为可回收（原为 unevictable），则增加 `UNEVICTABLE_PGRESCUED` 统计；
- 若页面不可回收，则清除 active 标志，设置 unevictable 标志，并重置 `mlock_count`，同时增加 `UNEVICTABLE_PGCULLED` 统计。

### 页面释放路径
`__folio_put()` 是 folio 引用计数归零后的释放入口：
1. 设备内存 folio 调用 `free_zone_device_folio()`
2. 大页 folio 调用 `free_huge_folio()`
3. 普通 folio 先从 LRU 移除（若在 LRU 上），然后解绑内存控制组（memcg），最后调用 `free_unref_page()` 释放到伙伴系统。

### LRU 旋转优化
`folio_rotate_reclaimable()` 在写回结束时，若页面干净且未锁定，则将其移至 inactive LRU 尾部。此操作通过 per-CPU 的 `lru_rotate` 批处理完成，仅在必要时获取 LRU 锁，避免影响写回关键路径性能。

### 成本跟踪
`lru_note_cost()` 通过累加 `nr_io * SWAP_CLUSTER_MAX + nr_rotated` 来量化扫描成本，用于动态调整匿名页与文件页 LRU 的扫描比例，优化内存回收效率。

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`、`<linux/pagevec.h>`、`"internal.h"` 等，使用伙伴系统、LRU 框架、内存控制组（memcg）等基础组件。
- **交换子系统**：虽不直接实现 swap read/write，但为 `vmscan.c` 中的页面回收提供 LRU 操作接口，是 swap 机制的支撑模块。
- **大页支持**：通过 `hugetlb.h` 与大页子系统交互，特殊处理大页释放。
- **设备内存**：通过 `memremap.h` 支持持久内存（pmem）等 zone device 页面的释放。
- **跟踪与统计**：使用 tracepoint（`trace/events/pagemap.h`）和 VM 统计（`kernel_stat.h`）进行性能分析。
- **SMP 支持**：大量使用 per-CPU 变量（`DEFINE_PER_CPU`）和本地锁（`local_lock_t`）优化多核性能。

## 5. 使用场景

- **页面回收（Reclaim）**：当内存压力触发 kswapd 或 direct reclaim 时，`vmscan.c` 调用本文件的 LRU 操作函数来隔离、释放页面。
- **页面缓存释放**：文件系统或网络子系统在释放 page cache 页面时，通过 `__folio_put()` 或 `put_pages_list()` 触发 LRU 移除和内存释放。
- **写回完成处理**：块设备或文件系统在完成脏页写回后，调用 `folio_rotate_reclaimable()` 更新页面在 LRU 中的位置。
- **内存控制组（cgroup）**：memcg 回收内存时，复用本文件的 LRU 批处理和 folio 释放逻辑。
- **大页与设备内存管理**：透明大页（THP）或持久内存应用释放页面时，通过统一的 `__folio_put()` 接口分发到专用释放函数。
- **系统调优**：管理员通过 `/proc/sys/vm/page-cluster` 调整 `page_cluster` 值，影响 swap 和 page cache 的 I/O 批量大小。