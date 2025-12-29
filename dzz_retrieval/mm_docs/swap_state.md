# swap_state.c

> 自动生成时间: 2025-12-07 17:27:47
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `swap_state.c`

---

# `swap_state.c` 技术文档

## 1. 文件概述

`swap_state.c` 是 Linux 内核内存管理子系统中负责**交换缓存（swap cache）**管理的核心文件。它实现了将匿名页（anonymous pages）换出到交换设备后，在内存中维护一个缓存层（即 swap cache），用于加速后续可能发生的 swap-in 操作，并保证数据一致性。该文件定义了交换缓存的地址空间操作、页面增删接口、预读机制以及统计信息展示等功能。

## 2. 核心功能

### 主要数据结构
- **`swapper_spaces[MAX_SWAPFILES]`**：每个交换区（swapfile/swap partition）对应一个 `address_space`，用于组织其上的交换页。
- **`swap_aops`**：交换缓存专用的 `address_space_operations`，包含 `writepage`、`dirty_folio` 和迁移支持。
- **`swap_readahead_info`（通过 `vma` 原子变量存储）**：用于实现交换预读（swap read-ahead）的窗口和命中计数。
- **预读宏定义**：
  - `SWAP_RA_VAL()`：将地址、窗口大小、命中次数编码为一个 `long` 值。
  - `SWAP_RA_ADDR()` / `SWAP_RA_WIN()` / `SWAP_RA_HITS()`：解码预读信息。

### 主要函数
- **`add_to_swap_cache()`**：将已分配交换项的 folio 添加到交换缓存中。
- **`__delete_from_swap_cache()` / `delete_from_swap_cache()`**：从交换缓存中移除 folio，并释放对应的交换项。
- **`add_to_swap()`**：为 folio 分配交换空间并加入交换缓存，是页面回收路径的关键步骤。
- **`get_shadow_from_swap_cache()`**：查询交换缓存中是否存在指定交换项的“影子”（shadow entry），用于 workingset 检测。
- **`clear_shadow_from_swap_cache()`**：批量清除指定交换区范围内的 shadow entries。
- **`show_swap_cache_info()`**：打印交换缓存的全局统计信息（页数、空闲/总交换空间）。

## 3. 关键实现

### 交换缓存模型
- 使用 `address_space` + `XArray`（`i_pages`）作为底层数据结构，每个交换项（`swp_entry_t`）的偏移量（`swp_offset`）作为 XArray 的索引。
- Folio 被加入交换缓存时，设置 `PG_swapcache` 标志，并将 `folio->swap` 指向对应的交换项。
- 与普通文件页缓存不同，交换缓存不关联 inode，而是通过虚拟的 `swapper_spaces` 管理。

### 预读机制（Swap Read-Ahead）
- 基于 VMA 的 `swap_readahead_info` 原子变量实现自适应预读。
- 初始预读窗口较小（4 页），根据连续命中的次数动态调整窗口大小。
- 预读信息（地址、窗口、命中数）被压缩存储在一个 `long` 中，通过位域操作高效访问。

### 内存与交换一致性
- 在 `add_to_swap()` 中，**强制标记 folio 为 dirty**，以解决 `MADV_FREE` 页面因 PTE dirty 位清除而导致的数据丢失风险。
- 删除交换缓存项时，需持有 folio 锁并确保不在 writeback 状态，防止并发冲突。
- 使用 `__GFP_NOMEMALLOC` 标志避免在内存紧张时耗尽紧急内存保留区。

### Workingset 支持
- 通过 `xa_is_value()` 存储和识别 **shadow entries**（非 folio 的特殊值），用于 workingset 回收算法判断页面是否近期被访问过。
- `workingset_update_node` 回调用于在 XArray 节点变化时更新 LRU 年龄信息。

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`、`<linux/gfp.h>`、`<linux/pagevec.h>` 等基础内存管理接口。
- **交换子系统**：紧密集成 `<linux/swap.h>`、`<linux/swapops.h>`，使用 `swp_entry_t`、`swap_address_space()` 等交换抽象。
- **页缓存基础设施**：复用 `address_space`、`XArray`、`folio` 等通用页缓存机制（来自 `filemap.c` 和 `xarray.c`）。
- **LRU 与回收**：与 `vmscan`（`shrink_page_list`）交互，通过 `NR_SWAPCACHE` 统计项参与内存回收决策。
- **迁移支持**：若启用 `CONFIG_MIGRATION`，支持 folio 在 NUMA 节点间的迁移。
- **内部头文件**：依赖 `internal.h` 和 `swap.h` 中的内核私有交换实现细节。

## 5. 使用场景

- **页面回收（Page Reclaim）**：当系统内存不足时，`shrink_page_list()` 调用 `add_to_swap()` 将匿名页换出到交换设备，并加入交换缓存。
- **缺页异常处理（Page Fault）**：当访问已换出的匿名页时，`do_swap_page()` 从交换设备读取数据前，先检查交换缓存是否已有该页，若有则直接复用。
- **交换预读优化**：在顺序访问已换出页面时，根据历史访问模式自动扩大预读窗口，减少 I/O 次数。
- **内存压缩与迁移**：在内存规整（compaction）或 NUMA 迁移过程中，通过 `migrate_folio` 操作移动交换缓存中的 folio。
- **系统监控与调试**：通过 `/proc/meminfo` 或内核日志（`show_swap_cache_info()`）查看交换缓存使用情况。