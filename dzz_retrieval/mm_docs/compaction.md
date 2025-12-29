# compaction.c

> 自动生成时间: 2025-12-07 15:44:52
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `compaction.c`

---

# compaction.c 技术文档

## 1. 文件概述

`compaction.c` 是 Linux 内核内存管理子系统中实现**内存压缩（Memory Compaction）**功能的核心文件。其主要目标是**减少外部碎片（external fragmentation）**，通过迁移可移动页面，将物理内存中的空闲页聚集形成连续的大块内存区域，从而满足高阶（high-order）内存分配请求（如透明大页 THP 或 HugeTLB）。该机制高度依赖页面迁移（page migration）来完成实际的页面移动工作。

## 2. 核心功能

### 主要函数
- **`PageMovable()` / `__SetPageMovable()` / `__ClearPageMovable()`**: 管理页面的可移动性标记，用于标识页面是否可通过注册的 `movable_operations` 进行迁移。
- **`defer_compaction()` / `compaction_deferred()` / `compaction_defer_reset()`**: 实现**压缩延迟（deferred compaction）**机制，避免在压缩失败后频繁重试，提升系统性能。
- **`compaction_restarting()`**: 判断是否因多次失败后重新启动压缩流程。
- **`isolation_suitable()`**: 检查指定 pageblock 是否适合进行页面隔离（用于迁移）。
- **`reset_cached_positions()`**: 重置压缩控制结构中缓存的扫描位置（迁移源和空闲目标页的起始 PFN）。
- **`release_free_list()`**: 将临时空闲页面列表中的页面释放回伙伴系统。
- **`skip_offline_sections()` / `skip_offline_sections_reverse()`**: 在 SPARSEMEM 内存模型下跳过离线内存段。

### 关键数据结构与宏
- **`struct compact_control`**: 压缩操作的控制上下文（定义在 `internal.h` 中），包含扫描范围、迁移/空闲页面列表等。
- **`COMPACTION_HPAGE_ORDER`**: 用于计算节点/区域“碎片分数（fragmentation score）”的参考阶数，通常为透明大页或 HugeTLB 的阶数。
- **`COMPACT_MAX_DEFER_SHIFT`**: 压缩延迟的最大次数（64 次）。
- **`zone->compact_*` 字段**: 包括 `compact_considered`, `compact_defer_shift`, `compact_order_failed`, `compact_cached_*_pfn` 等，用于跟踪压缩状态和优化扫描。

## 3. 关键实现

### 内存压缩流程
1. **扫描阶段**：从区域两端向中间扫描：
   - **迁移源扫描器（migrate scanner）**：从低地址向高地址扫描，寻找可迁移的页面。
   - **空闲目标扫描器（free scanner）**：从高地址向低地址扫描，寻找空闲页面块。
2. **页面隔离**：将找到的可迁移页面加入迁移列表，空闲页面加入空闲列表。
3. **页面迁移**：调用 `migrate_pages()` 将迁移列表中的页面移动到空闲列表提供的目标位置。
4. **结果处理**：迁移成功后，原位置变为空闲，可能形成更大的连续空闲块；失败则回滚。

### 压缩延迟机制（Deferred Compaction）
- 当压缩未能成功分配指定 `order` 的页面时，调用 `defer_compaction()` 增加延迟计数器 `compact_defer_shift`。
- 后续分配请求会通过 `compaction_deferred()` 检查是否应跳过压缩（基于 `compact_considered` 计数和 `defer_limit = 1 << compact_defer_shift`）。
- 若分配成功或预期成功，则通过 `compaction_defer_reset()` 重置延迟状态。
- 当延迟达到最大值（`COMPACT_MAX_DEFER_SHIFT`）且考虑次数足够多时，`compaction_restarting()` 返回 true，强制重启完整压缩流程。

### 碎片分数与主动压缩
- 通过 `COMPACTION_HPAGE_ORDER` 定义的阶数评估区域的外部碎片程度。
- 主动压缩（proactive compaction）定期（`HPAGE_FRAG_CHECK_INTERVAL_MSEC = 500ms`）检查碎片分数，并在需要时触发后台压缩。
- `is_via_compact_memory()` 用于识别通过 `/proc/sys/vm/compact_memory` 等接口发起的全量压缩请求（`order = -1`）。

### 页面可移动性管理
- `__SetPageMovable()` 将 `movable_operations` 指针编码到 `page->mapping` 中，并设置 `PAGE_MAPPING_MOVABLE` 标志。
- `PageMovable()` 验证页面是否被正确标记为可移动，并确保其操作集有效。

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`, `internal.h`, `mm_inline.h` 提供的伙伴系统、页面分配/释放、zone 管理等基础功能。
- **页面迁移**：紧密集成 `<linux/migrate.h>`，压缩的核心操作由 `migrate_pages()` 完成。
- **内存模型**：针对 `CONFIG_SPARSEMEM` 提供离线内存段跳过逻辑。
- **大页支持**：根据 `CONFIG_TRANSPARENT_HUGEPAGE` 或 `CONFIG_HUGETLBFS` 确定 `COMPACTION_HPAGE_ORDER`。
- **调试与追踪**：使用 `kasan.h`, `page_owner.h` 进行调试；通过 `trace/events/compaction.h` 提供 ftrace 事件。
- **系统调用与接口**：通过 sysctl (`/proc/sys/vm/`) 和 sysfs (`/sys/devices/system/node/`) 暴露用户空间控制接口。
- **进程与调度**：使用 `kthread.h`, `freezer.h` 管理后台压缩线程；`psi.h` 用于压力状态监控。

## 5. 使用场景

1. **高阶内存分配失败时**：当 `alloc_pages()` 请求高阶页面（如 order ≥ 3）失败时，内核会尝试同步内存压缩以满足请求。
2. **透明大页（THP）分配**：THP 需要连续的 2MB 物理内存，压缩是满足此类请求的关键机制。
3. **主动后台压缩**：通过 `vm.compaction_proactiveness` sysctl 参数配置，内核定期评估内存碎片并主动压缩，预防分配延迟。
4. **用户空间触发**：管理员可通过写入 `/proc/sys/vm/compact_memory` 或特定 NUMA 节点的 `compact` sysfs 文件，手动触发全量内存压缩。
5. **CMA（Contiguous Memory Allocator）**：在 CMA 区域分配大块连续内存前，使用压缩机制迁移占用页面以腾出空间（需 `CONFIG_CMA`）。