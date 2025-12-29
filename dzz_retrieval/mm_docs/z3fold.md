# z3fold.c

> 自动生成时间: 2025-12-07 17:35:52
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `z3fold.c`

---

# z3fold.c 技术文档

## 1. 文件概述

`z3fold.c` 实现了一个专用于存储压缩页面的特殊用途内存分配器——**z3fold**。该分配器继承自 `zbud` 的设计理念，但进行了优化：每个物理页最多可容纳**三个**压缩对象（而 zbud 仅支持两个），从而提升了压缩密度，同时保留了“每页存储整数个对象”的确定性特性。这种设计在需要高效内存回收（reclaim）的场景下，相比无固定对象数量限制的高密度方案更具优势。z3fold 不直接对外暴露 API，而是通过 **zpool** 接口被上层（如 zswap、zram）调用。

## 2. 核心功能

### 主要数据结构
- **`struct z3fold_header`**: 存储在每个 z3fold 页面起始位置的元数据结构（HEADLESS 页除外）。包含：
  - 页面引用计数 (`refcount`) 和自旋锁 (`page_lock`)
  - 指向所属池 (`pool`) 和 CPU 亲和性 (`cpu`)
  - 三个 buddy 区域（first, middle, last）的大小及起始位置
  - 状态标志（如映射计数 `mapped_count`、外部句柄标记 `foreign_handles`）
  - 用于后台优化的工作队列项 (`work`)
- **`struct z3fold_buddy_slots`**: 管理页面内对象句柄的槽位结构，包含读写锁 (`lock`) 和指向所属池的反向链接。
- **`struct z3fold_pool`**: 代表一个 z3fold 内存池，包含：
  - 每 CPU 的 `unbuddied` 列表数组（按空闲区域大小分类）
  - 待释放的 `stale` 页面列表
  - 专用 slab 缓存 (`c_handle`) 用于分配 `buddy_slots`
  - 后台工作队列 (`compact_wq`, `release_wq`) 用于页面整理和安全释放

### 关键枚举与宏
- **`enum buddy`**: 定义页面内对象的三种类型：`FIRST`（页首）、`MIDDLE`（中间）、`LAST`（页尾），以及特殊的 `HEADLESS`（无头部元数据页）。
- **`NCHUNKS_ORDER`**: 核心配置参数（默认为 6），决定内部分配粒度为 `PAGE_SIZE / 64`。
- **页面标志 (`enum z3fold_page_flags`)**: 如 `PAGE_HEADLESS`、`NEEDS_COMPACTING`、`PAGE_STALE` 等，用于管理页面状态。
- **句柄标志 (`enum z3fold_handle_flags`)**: 控制句柄行为（如 `HANDLES_NOFREE`）。

### 核心辅助函数
- **`size_to_chunks()`**: 将字节大小转换为 chunk 单位。
- **`alloc_slots()` / `slots_to_pool()`**: 管理 `buddy_slots` 的分配与池关联。
- **`handle_to_slots()` / `get_z3fold_header()`**: 从用户句柄解析出底层元数据结构，并处理并发访问与迁移。
- **`z3fold_page_lock/unlock/trylock()`**: 提供页面级细粒度锁操作。

## 3. 关键实现

### 内存布局与分配策略
- **Chunk 粒度**: 页面被划分为 `TOTAL_CHUNKS = PAGE_SIZE / CHUNK_SIZE` 个固定大小的 chunk（默认 64 字节）。前 `ZHDR_CHUNKS` 个 chunk 被 `z3fold_header` 占用，剩余 `NCHUNKS`（约 62-63）个用于存储数据。
- **三 Buddy 设计**: 
  - **First Buddy**: 从 `header` 之后开始分配。
  - **Last Buddy**: 从页面末尾向前分配。
  - **Middle Buddy**: 在 First 和 Last 之间动态分配，最大化利用碎片空间。
- **HEADLESS 页**: 当对象大小接近整个页面时，跳过 header 直接使用整页，减少元数据开销。

### 并发与迁移安全
- **双层锁机制**: 
  - `z3fold_header.page_lock` 保护单个页面的元数据修改。
  - `z3fold_buddy_slots.lock` (rwlock) 保护句柄到地址的映射，支持高并发读取。
- **迁移处理**: 在 `get_z3fold_header()` 中检查 `PAGE_MIGRATED` 标志，若页面正在迁移则重试获取锁，确保访问安全。

### 后台优化
- **页面整理 (`compact_page_work`)**: 通过工作队列异步移动 Middle Buddy 对象，尝试合并空闲区域以容纳更大对象。
- **安全释放**: 使用独立工作队列 (`release_wq`) 延迟释放被标记为 `PAGE_STALE` 的页面，避免在中断上下文或持有锁时执行高开销操作。

### 句柄编码
- 用户句柄 (`handle`) 是一个 `unsigned long`，其低 2 位 (`HANDLE_FLAG_MASK`) 用于存储标志（如 `PAGE_HEADLESS`），其余位编码 `buddy_slots` 地址或直接指向页面。这允许在不解引用的情况下快速判断页面类型。

## 4. 依赖关系

- **核心依赖**: 
  - `<linux/zpool.h>`: 作为 zpool 驱动注册，提供 `zpool_ops` 接口。
  - `<linux/slab.h>`: 使用 kmem_cache 分配 `z3fold_buddy_slots`。
  - `<linux/workqueue.h>`: 依赖内核工作队列机制执行后台任务。
- **内存管理子系统**: 
  - 依赖 `alloc_pages()`/`__free_pages()` 进行底层页分配。
  - 使用 `page->private` 存储页面标志位。
  - 与内存压缩 (`compaction.h`) 和迁移 (`migrate.h`) 机制交互。
- **同步原语**: 大量使用 `spinlock_t` 和 `rwlock_t` 保证 SMP 安全。

## 5. 使用场景

z3fold 主要作为 **zpool** 的后端分配器，服务于需要高效压缩内存的子系统：
- **zswap**: 作为交换页的压缩缓存，z3fold 的高密度存储可显著减少实际交换 I/O。
- **zram**: 作为基于 RAM 的块设备，z3fold 提升其有效存储容量。
- **其他内存压缩框架**: 任何需要将变长小对象（尤其是压缩数据）高效打包进物理页的场景。

其**确定性回收特性**（每页对象数固定、布局简单）使其在内存压力大时能快速找到可回收页面，优于更复杂的分配器（如 zsmalloc），特别适合嵌入式或实时系统。