# zsmalloc.c

> 自动生成时间: 2025-12-07 17:38:04
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `zsmalloc.c`

---

# zsmalloc.c 技术文档

## 1. 文件概述

`zsmalloc.c` 实现了 **zsmalloc** —— 一种专为压缩内存（如 zram、zswap）设计的物理页面级内存分配器。其核心目标是在不依赖虚拟内存连续性的前提下，高效地分配和管理小于页面大小的对象，同时最小化内部碎片。该分配器通过将多个物理页面组合成逻辑单元（zspage），并在其中紧凑地排列固定大小的对象，从而支持高效的对象分配、释放和迁移（用于内存压缩场景）。

## 2. 核心功能

### 主要数据结构

- **`struct zs_pool`**: 内存池对象，代表一个独立的 zsmalloc 实例。包含：
  - 多个 `size_class` 数组（按对象大小分类）
  - 统计信息（`pages_allocated`, `stats`）
  - 缓存（`handle_cachep`, `zspage_cachep`）
  - 自旋锁（`lock`）和压缩相关字段（`shrinker`, `free_work`）

- **`struct size_class`**: 尺寸类别，管理相同大小对象的分配。包含：
  - 按“满度”（fullness）分组的 zspage 链表（`fullness_list`）
  - 对象大小（`size`）、每 zspage 对象数（`objs_per_zspage`）
  - 每 zspage 页面数（`pages_per_zspage`）
  - 统计信息（`stats`）

- **`struct zspage`**: 逻辑内存页，由 1 到 `ZS_MAX_PAGES_PER_ZSPAGE` 个物理页组成。包含：
  - 元数据位域（`huge`, `fullness`, `class`, `isolated`, `magic`）
  - 使用计数（`inuse`）、首个空闲对象索引（`freeobj`）
  - 首页指针（`first_page`）、所属池（`pool`）
  - 读写锁（`lock`，用于迁移）

- **`struct link_free`**: 嵌入在空闲对象中的单向链表节点，用于追踪空闲对象。

- **`struct mapping_area`**: 每 CPU 映射区域，用于安全访问跨页对象（通过 `kmap_atomic` 和临时缓冲区）。

### 关键函数（部分声明/定义）

- **初始化与销毁**: `zs_create_pool()`, `zs_destroy_pool()`
- **分配与释放**: `zs_malloc()`, `zs_free()`
- **对象映射**: `zs_map_object()`, `zs_unmap_object()`
- **压缩支持**: `migrate_*_lock()` 系列函数、`kick_deferred_free()`
- **统计与调试**: `zs_size_classes_init()`, `zs_register_migration()`（未在片段中完整显示）

## 3. 关键实现

### 对象句柄编码
- 使用 `unsigned long` 类型的 **handle** 编码对象位置：`<PFN><obj_idx><tag>`。
- **PFN**: 物理页帧号（占用 `_PFN_BITS` 位）。
- **obj_idx**: 对象在 zspage 内的索引（占用 `OBJ_INDEX_BITS` 位）。
- **tag**: 最低位 (`OBJ_ALLOCATED_TAG`) 标记对象是否已分配。
- 此设计允许在不解引用的情况下快速判断对象状态，并定位其物理页。

### Zspage 管理
- **多页组合**: 小对象类别的 zspage 可跨越多个物理页（最多 `ZS_MAX_PAGES_PER_ZSPAGE`），以提高空间利用率。
- **满度分组**: 每个 `size_class` 维护 `NR_FULLNESS_GROUPS` (12) 个链表，按使用率（0%, ≤10%, ..., 100%）组织 zspage，便于快速查找合适页面并减少碎片。
- **Huge Page 优化**: 当对象大小接近或等于页面时，使用单页 zspage (`huge=1`)，简化管理。

### 跨页对象处理
- 对象可能跨越两个物理页边界。
- 通过 `struct mapping_area` 提供每 CPU 的原子映射区域 (`vm_addr`) 和临时缓冲区 (`vm_buf`)。
- `zs_map_object()` 根据对象是否跨页，选择直接映射或通过缓冲区复制，确保访问安全。

### 并发与迁移
- **锁层次**: 定义了 `page_lock` → `pool->lock` → `zspage->lock` 的锁顺序。
- **迁移锁**: `zspage->lock` 是读写锁，读锁用于常规访问，写锁用于压缩迁移（`CONFIG_COMPACTION`）。
- **延迟释放**: 在压缩场景下，释放操作可能被延迟执行（`deferred_free`），以避免在迁移关键路径上持有锁。

### 内存布局复用
- 巧妙复用 `struct page` 的字段：
  - `page->private`: 指向所属 `zspage`。
  - `page->index`: 链接同一 zspage 的所有物理页；对 huge zspage 存储 handle。
  - `page->page_type`: 存储子页中首个对象的偏移。
- 使用页面标志位：
  - `PG_private`: 标记 zspage 的首页。
  - `PG_owner_priv_1`: 标记 huge zspage 的页。

## 4. 依赖关系

- **内核基础组件**:
  - `<linux/slab.h>`: 用于分配 `zs_pool`、`zspage` 和 handle 的元数据。
  - `<linux/highmem.h>`, `<asm/tlbflush.h>`: 支持高内存页的原子映射 (`kmap_atomic`)。
  - `<linux/spinlock.h>`, `<linux/rwlock.h>`: 提供并发控制原语。
  - `<linux/shrinker.h>`: 实现内存回收接口，供 VM 在内存压力下压缩 zsmalloc 池。
- **压缩子系统**:
  - **zram**: 主要用户，将压缩后的内存块存储在 zsmalloc 中。
  - **zswap**: 作为交换缓存的后端，使用 zsmalloc 存储压缩页。
  - **zpool API**: 通过 `zpool` 抽象层集成到压缩框架中。
- **内存管理**:
  - `<linux/migrate.h>`: 支持页面迁移，是内存压缩 (`CONFIG_COMPACTION`) 的关键。
  - `<linux/pagemap.h>`: 操作页面标志和属性。

## 5. 使用场景

- **zram 块设备**: 作为 RAM-based 压缩块设备的后端存储，显著提高可用内存容量。
- **zswap 交换缓存**: 在将内存页写入交换设备前，先压缩并暂存于 zsmalloc，减少 I/O。
- **通用小对象分配**: 适用于需要大量小于页面大小、且生命周期较短的对象分配场景，尤其在内存受限环境中。
- **内存压缩框架**: 作为 `zpool` 的一种实现，为内核提供可压缩的内存池服务。