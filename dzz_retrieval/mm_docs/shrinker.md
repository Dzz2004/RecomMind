# shrinker.c

> 自动生成时间: 2025-12-07 17:19:57
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `shrinker.c`

---

# shrinker.c 技术文档

## 1. 文件概述

`shrinker.c` 是 Linux 内核内存管理子系统中负责管理 **shrinker**（收缩器）机制的核心实现文件。Shrinker 是一种回调机制，允许内核子系统（如 dentry、inode、buffer cache 等）在系统内存压力下释放可回收的缓存对象。该文件主要实现了：

- 全局 shrinker 列表的注册与管理
- 基于 cgroup v2 的 memcg（memory control group）感知的 shrinker 支持
- 每个 memcg 对每个 shrinker 的延迟扫描计数（`nr_deferred`）和活跃状态位图（`shrinker_bit`）的动态分配与维护
- 在 memcg 层级结构变化（如 cgroup 删除）时，将子 cgroup 的 deferred 计数迁移至父 cgroup（reparent）

该文件特别关注 **memcg-aware shrinker** 的可扩展性设计，通过分块（unit-based）数据结构支持动态增长的 shrinker ID 空间。

## 2. 核心功能

### 主要全局变量
- `shrinker_list`：全局链表，用于链接所有已注册的 `struct shrinker` 实例。
- `shrinker_mutex`：保护 shrinker 注册/注销及 memcg shrinker info 扩展操作的互斥锁。
- `shrinker_idr`（仅 CONFIG_MEMCG）：IDR 结构，为每个 memcg-aware shrinker 分配唯一 ID。
- `shrinker_nr_max`（仅 CONFIG_MEMCG）：当前系统中 shrinker ID 的最大值（向上对齐到 `SHRINKER_UNIT_BITS`）。

### 主要数据结构（仅 CONFIG_MEMCG）
- `struct shrinker_info`：每个 memcg 每个 NUMA 节点维护的 shrinker 元数据容器。
- `struct shrinker_info_unit`：`shrinker_info` 中的分块单元，包含：
  - `map[SHRINKER_UNIT_BITS]`：位图，标记对应 shrinker 是否在此 memcg 中有可回收对象。
  - `nr_deferred[SHRINKER_UNIT_BITS]`：原子长整型数组，记录每个 shrinker 在此 memcg 中的延迟扫描计数。

### 主要函数

#### 全局 shrinker 管理
- `register_shrinker()` / `unregister_shrinker()`（定义在其他文件，但使用本文件的 list 和 mutex）

#### Memcg Shrinker Info 生命周期管理（仅 CONFIG_MEMCG）
- `alloc_shrinker_info(struct mem_cgroup *memcg)`：为指定 memcg 分配所有 NUMA 节点的 `shrinker_info`。
- `free_shrinker_info(struct mem_cgroup *memcg)`：释放指定 memcg 的所有 `shrinker_info`。
- `expand_shrinker_info(int new_id)`：当新 shrinker ID 超出当前 `shrinker_nr_max` 时，扩展所有 memcg 的 `shrinker_info` 容量。

#### Shrinker 状态操作（仅 CONFIG_MEMCG）
- `set_shrinker_bit(struct mem_cgroup *memcg, int nid, int shrinker_id)`：设置指定 memcg/nid/shrinker 的活跃位。
- `xchg_nr_deferred_memcg()` / `add_nr_deferred_memcg()`：原子地交换或增加指定 shrinker 在 memcg 中的 deferred 计数。

#### Memcg 层级维护
- `reparent_shrinker_deferred(struct mem_cgroup *memcg)`：将被销毁 memcg 的 deferred 计数累加到其父 memcg。

#### 辅助函数（条件编译）
- `shrinker_memcg_alloc()` / `shrinker_memcg_remove()`：为 shrinker 分配/移除 memcg ID。
- `xchg_nr_deferred()` / `add_nr_deferred()`：根据是否启用 memcg，调用全局或 memcg 特定的 deferred 操作。

## 3. 关键实现

### 动态可扩展的 Shrinker ID 管理
- 使用 `idr` 为每个 memcg-aware shrinker 分配唯一 ID。
- `shrinker_nr_max` 记录当前最大 ID（向上对齐到 `SHRINKER_UNIT_BITS`，通常为 `PAGE_SIZE * 8`）。
- 当新 shrinker ID ≥ `shrinker_nr_max` 时，调用 `expand_shrinker_info()` 遍历所有 memcg，为其 `shrinker_info` 分配更多 `shrinker_info_unit` 块。

### 分块存储设计（Unit-based Storage）
- `shrinker_info` 不直接存储大数组，而是通过指针数组 `unit[]` 指向多个 `shrinker_info_unit`。
- 每个 `unit` 管理 `SHRINKER_UNIT_BITS` 个 shrinker 的状态（位图 + deferred 计数）。
- 扩展时只需分配新增的 unit 块，已有数据通过 `memcpy` 复用，避免全量重分配。

### RCU 与锁协同
- `shrinker_info` 的读取使用 RCU（`rcu_dereference`），保证扫描路径无锁。
- 修改（分配、扩展、释放）受 `shrinker_mutex` 保护，并使用 `rcu_assign_pointer` / `kvfree_rcu` 实现安全替换。

### Deferred 计数迁移（Reparenting）
- 当 memcg 被销毁时，其所有 shrinker 的 deferred 计数需合并到父 memcg。
- 通过 `reparent_shrinker_deferred()` 在 `shrinker_mutex` 保护下遍历所有 shrinker 单元，原子累加计数。

### 内存节点（NUMA）感知
- 每个 memcg 为每个 NUMA 节点维护独立的 `shrinker_info`，支持 `SHRINKER_NUMA_AWARE` shrinker 按节点回收。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/memcontrol.h>`：memcg 核心接口
  - `<linux/shrinker.h>`：shrinker 结构定义
  - `<linux/rculist.h>`：RCU 保护的链表操作
  - `"internal.h"`：mm 子系统内部头文件
- **内核配置依赖**：
  - `CONFIG_MEMCG`：启用 memcg-aware shrinker 支持
  - `CONFIG_SHRINKER_DEBUG`（间接）：可能影响 tracepoint 行为
- **协作模块**：
  - VFS（dentry/inode cache）、Buffer Cache、Tmpfs 等通过注册 shrinker 使用此机制
  - Memory Cgroup（memcg）子系统提供层级结构和 per-node 数据
  - VM writeback 和 kswapd 调用 shrinker 回调进行内存回收

## 5. 使用场景

1. **内存压力下的缓存回收**：
   - 当系统内存不足时，kswapd 或 direct reclaim 路径调用 `shrink_slab()`，遍历 `shrinker_list` 并执行各 shrinker 的 `.scan_objects` 回调。

2. **Memcg 内存限制回收**：
   - 当某个 memcg 超过内存限制时，reclaim 过程会针对该 memcg 调用 shrinker，利用 `shrinker_bit` 快速判断哪些 shrinker 在此 memcg 中有对象，避免无效扫描。

3. **Shrinker 注册/注销**：
   - 子系统初始化时调用 `register_shrinker()`，将 shrinker 加入全局列表；模块卸载时调用 `unregister_shrinker()` 移除。

4. **Cgroup 层级变更**：
   - 当 memcg 被删除时，其资源（包括 shrinker deferred 计数）通过 `reparent_shrinker_deferred()` 迁移到父 cgroup，确保回收逻辑连续性。

5. **动态 Shrinker 扩展**：
   - 系统运行时加载新模块（如新文件系统）注册 shrinker，若 ID 超出现有范围，自动触发 `expand_shrinker_info()` 扩容所有 memcg 的元数据。