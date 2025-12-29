# swapfile.c

> 自动生成时间: 2025-12-07 17:28:37
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `swapfile.c`

---

# swapfile.c 技术文档

## 1. 文件概述

`swapfile.c` 是 Linux 内核内存管理子系统中负责交换（swap）功能的核心实现文件之一。该文件主要实现了对交换文件（swap file）和交换分区（swap partition）的管理，包括交换空间的分配、释放、回收、状态跟踪以及与页缓存（page cache）和反向映射（rmap）系统的集成。它为虚拟内存子系统提供底层支持，使得在物理内存不足时可以将不活跃的内存页换出到磁盘上的交换区域，并在需要时换入。

## 2. 核心功能

### 主要全局数据结构
- `swap_info[MAX_SWAPFILES]`：存储所有已激活交换设备/文件的元数据（`struct swap_info_struct`）。
- `swap_active_head`：按优先级排序的活跃交换设备链表（受 `swap_lock` 保护）。
- `swap_avail_heads`：按优先级排序的**可用**（未满）交换设备链表（受 `swap_avail_lock` 保护），用于高效分配交换槽。
- `nr_swap_pages` / `total_swap_pages`：全局交换页计数器，分别表示当前可用和总交换页数。
- `swapon_mutex`：用于序列化 `swapon`/`swapoff` 系统调用的互斥锁。

### 关键函数
- `__try_to_reclaim_swap()`：尝试回收指定交换槽对应的内存页，支持多种回收策略（强制回收、无映射回收、内存压力回收等）。
- `swap_count_continued()` / `free_swap_count_continuations()`：处理交换引用计数溢出的延续机制。
- `swap_entry_range_free()` / `swap_range_alloc()`：批量释放或分配交换槽。
- `folio_swapcache_freeable()`：判断一个 folio 是否可以从交换缓存中安全移除。
- `lock_cluster_or_swap_info()` / `unlock_cluster_or_swap_info()`：用于在交换位图操作时获取适当的锁（集群锁或整个交换设备锁）。
- `discard_swap()`：通知底层块设备丢弃旧的交换内容，用于 SSD 等设备的 TRIM/DISCARD 优化。

### 辅助函数与宏
- `swap_type_to_swap_info()`：根据交换类型索引获取对应的 `swap_info_struct`。
- `swap_count()`：从交换位图项中提取实际的引用计数值。
- `TTRS_*` 宏：定义交换回收的不同触发条件标志。

## 3. 关键实现

### 交换槽分配与回收
- 使用位图（`swap_map`）跟踪每个交换槽的使用状态和引用计数。
- 引用计数超过 254 时，使用 `COUNT_CONTINUED` 标志和额外的数据结构记录溢出部分。
- 通过 `swap_avail_heads` 链表优化分配路径，仅遍历未满的交换设备，避免检查已满设备。

### 交换缓存（Swap Cache）集成
- 换出的页会保留在交换缓存（基于 `address_space` 的 radix tree）中，避免重复 I/O。
- `__try_to_reclaim_swap()` 在满足条件时（如无页表映射、内存压力大）可主动删除缓存项并释放交换槽。
- 支持直接回收模式（`TTRS_DIRECT`），绕过交换槽缓存，立即释放底层交换槽。

### 并发控制
- 全局 `swap_lock` 保护交换设备列表和全局计数器。
- 每个交换设备有独立的自旋锁（`si->lock`）保护其位图和状态。
- 引入 `swap_avail_lock` 解决交换设备“满/不满”状态切换时的锁序问题。
- 使用 RCU 机制安全读取 `swap_info[]` 数组。

### 大页（Huge Page）支持
- 函数如 `folio_nr_pages()` 和 `swap_entry_range_free()` 支持跨多个连续交换槽的大页操作。
- 交换槽分配和释放以 folio 为单位处理，确保大页的原子性。

### 设备优化
- `discard_swap()` 在激活交换设备时调用，向 SSD 发送 DISCARD 命令，提升性能和寿命。
- 支持 zswap（压缩交换缓存），在直接释放交换槽时调用 `zswap_invalidate()`。

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`, `<linux/vmalloc.h>`, `<linux/pagemap.h>` 等提供的页分配、地址空间管理功能。
- **虚拟内存子系统**：与 `vmscan.c`（页面回收）、`rmap.c`（反向映射）、`memory.c` 紧密协作。
- **文件系统层**：通过 `shmem_fs.h` 和 `namei.h` 支持基于文件的交换（而非仅分区）。
- **块设备层**：通过 `blkdev.h` 与底层存储交互，支持 DISCARD 操作。
- **资源控制**：集成 `memcontrol.h`（cgroup 内存控制器）和 `blk-cgroup.h`（块设备 cgroup）。
- **安全模块**：通过 `security.h` 钩子进行权限检查。
- **其他子系统**：依赖 `ksm`（内存合并）、`oom`（内存耗尽处理）、`suspend`（休眠）等。

## 5. 使用场景

- **内存压力下的页面回收**：当系统内存不足时，`kswapd` 或直接回收路径调用 `__try_to_reclaim_swap()` 释放交换槽。
- **交换空间激活/停用**：`sys_swapon()` / `sys_swapoff()` 系统调用通过此文件初始化或清理交换设备。
- **交换槽分配**：`folio_alloc_swap()` 在需要换出页面时从此文件获取空闲交换槽。
- **交换缓存管理**：当页面被换入或显式释放时，更新交换缓存和位图状态。
- **系统休眠（Suspend-to-Disk）**：休眠过程大量使用交换机制保存内存镜像。
- **性能监控与调优**：`/proc/swaps` 和 `/proc/vmstat` 通过此文件暴露交换统计信息。
- **容器内存隔离**：配合 memcg 实现 per-cgroup 的交换限制和统计。