# zbud.c

> 自动生成时间: 2025-12-07 17:36:35
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `zbud.c`

---

# zbud.c 技术文档

## 1. 文件概述

`zbud.c` 实现了一个专用于存储压缩页面（compressed pages）的特殊用途内存分配器——**zbud**。尽管名称中包含“buddy”，但它并非传统的伙伴系统分配器，而是通过将两个压缩页面（称为“zpages”）配对存放在同一个物理内存页（称为“zbud page”）中来实现高效管理。

该设计在牺牲一定存储密度的前提下，提供了简单且可预测的内存回收特性，特别适用于需要频繁进行内存回收（reclaim）的场景（如 zswap、zcache 等压缩交换子系统）。zbud 保证其空间利用率不会低于 1:1（即不会比直接使用未压缩页面占用更多物理页），从而确保“不会造成损害”。

此外，zbud 的 API 与传统分配器不同：`zbud_alloc()` 返回一个不透明句柄（handle），用户必须通过 `zbud_map()` 映射该句柄才能获得可访问的数据指针，并在操作完成后调用 `zbud_unmap()` 解除映射。

## 2. 核心功能

### 主要数据结构

- **`struct zbud_pool`**  
  表示一个 zbud 内存池，包含：
  - `lock`：自旋锁，保护池内所有字段及其中 zbud 页面的元数据。
  - `unbuddied[NCHUNKS]`：数组，每个元素是一个链表头，用于管理仅包含一个 buddy（单配对）的 zbud 页面；索引表示页面中空闲块的数量。
  - `buddied`：链表头，管理已包含两个 buddy（满配对）的 zbud 页面（复用 `unbuddied[0]`）。
  - `pages_nr`：池中 zbud 页面的总数。

- **`struct zbud_header`**  
  位于每个 zbud 页面的第一个 chunk 中，作为页面元数据，包含：
  - `buddy`：用于将页面链接到 `unbuddied` 或 `buddied` 链表。
  - `first_chunks`：第一个 buddy 占用的 chunk 数（为 0 表示空闲）。
  - `last_chunks`：最后一个 buddy 占用的 chunk 数（为 0 表示空闲）。

### 主要函数

- **`zbud_create_pool(gfp_t gfp)`**  
  创建并初始化一个新的 zbud 内存池。

- **`zbud_destroy_pool(struct zbud_pool *pool)`**  
  销毁指定的 zbud 内存池（要求池已清空）。

- **`zbud_alloc(struct zbud_pool *pool, size_t size, gfp_t gfp, unsigned long *handle)`**  
  在池中分配指定大小的内存区域，返回不透明句柄。

- **`zbud_free(struct zbud_pool *pool, unsigned long handle)`**  
  释放由句柄标识的分配区域。

- **`zbud_map(struct zbud_pool *pool, unsigned long handle)`**  
  将句柄映射为可访问的虚拟地址指针。

- **`zbud_unmap(struct zbud_pool *pool, unsigned long handle)`**  
  解除句柄的映射。

- **辅助函数**：
  - `size_to_chunks()`：将字节大小转换为 chunk 数量。
  - `init_zbud_page()` / `free_zbud_page()`：初始化/释放 zbud 页面。
  - `encode_handle()` / `handle_to_zbud_header()`：句柄编码与解码。
  - `num_free_chunks()`：计算 zbud 页面中的空闲 chunk 数。

## 3. 关键实现

### 内存布局与配对机制

- 每个 **zbud 页面**（物理页）被划分为固定大小的 **chunks**（默认 `PAGE_SIZE / 64`，由 `NCHUNKS_ORDER=6` 决定）。
- 第一个 chunk 被 `zbud_header` 占用，剩余 `NCHUNKS = 63` 个 chunks 可用于存储数据。
- **First buddy** 从页面起始位置（跳过 header）向右分配（左对齐）。
- **Last buddy** 从页面末尾向左分配（右对齐）。
- 当任一 buddy 被释放时，其空间会与中间的 slack space 合并，形成页面内最大的连续空闲区域，便于后续分配。

### 空闲管理策略

- 使用 **`unbuddied[NCHUNKS]` 数组** 管理单配对页面：
  - 索引 `i` 对应空闲 chunk 数为 `i` 的页面。
  - 分配时优先遍历满足需求的最小空闲列表（best-fit 策略）。
- **`buddied` 链表** 管理已满（双配对）的页面，无法再分配。

### 句柄机制

- 句柄本质是数据在页面内的虚拟地址，但通过 `encode_handle()` 封装：
  - First buddy 句柄 = `zhdr 地址 + ZHDR_SIZE_ALIGNED`
  - Last buddy 句柄 = `页面起始地址 + PAGE_SIZE - (last_chunks << CHUNK_SHIFT)`
- 通过 `handle & PAGE_MASK` 可快速还原出 `zbud_header` 指针。

### 密度保证

- 由于每个 zbud 页面至少可容纳一个压缩页，因此 **zpages : zbud pages ≥ 1**，确保不会因压缩反而增加内存消耗。

## 4. 依赖关系

- **内核头文件**：
  - `<linux/atomic.h>`、`<linux/spinlock.h>`：提供原子操作和自旋锁支持。
  - `<linux/list.h>`：链表操作。
  - `<linux/mm.h>`、`<linux/slab.h>`：内存页和 slab 分配器接口。
  - `<linux/zpool.h>`：zbud 作为 zpool API 的一种后端实现，需符合其接口规范。
- **架构依赖**：使用 `PAGE_SHIFT`、`PAGE_MASK` 等与页大小相关的宏，依赖体系结构定义。
- **内存属性限制**：分配时禁止使用 `__GFP_HIGHMEM`，因高内存页无法直接映射访问。

## 5. 使用场景

- **zswap**：Linux 内核的交换页压缩缓存机制，使用 zbud（或 z3fold/zsmalloc）作为后端分配器存储压缩后的交换页。
- **zcache**（历史项目）：早期基于 transcendent memory 的压缩缓存，zbud 最初为其设计。
- **其他需要确定性回收行为的压缩内存池**：适用于对内存回收延迟敏感、且能接受较低存储密度的场景。
- **作为 zpool 的注册后端**：通过 `zpool_register_driver()` 注册，供上层子系统按需选择。