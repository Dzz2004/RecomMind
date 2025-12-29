# list_lru.c

> 自动生成时间: 2025-12-07 16:35:23
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `list_lru.c`

---

# list_lru.c 技术文档

## 1. 文件概述

`list_lru.c` 实现了 Linux 内核中通用的 **List-based LRU（Least Recently Used）基础设施**，用于管理可回收对象的双向链表。该机制支持按 NUMA 节点（node）和内存控制组（memcg）进行细粒度组织，便于内存压力下的高效回收。主要服务于 slab 分配器等子系统，作为 shrinker 框架的一部分，在内存紧张时协助释放非活跃对象。

## 2. 核心功能

### 主要数据结构
- `struct list_lru`：顶层 LRU 管理结构，包含 per-node 的 `list_lru_node`
- `struct list_lru_node`：每个 NUMA 节点对应的 LRU 节点，含自旋锁和总项数
- `struct list_lru_one`：实际存储对象链表和计数的单元（per-memcg per-node）
- `struct list_lru_memcg`：当启用 `CONFIG_MEMCG` 时，为每个 memcg 存储 per-node 的 `list_lru_one`

### 主要导出函数
- `list_lru_add()` / `list_lru_add_obj()`：向 LRU 添加对象
- `list_lru_del()` / `list_lru_del_obj()`：从 LRU 删除对象
- `list_lru_isolate()` / `list_lru_isolate_move()`：在回收过程中隔离对象
- `list_lru_count_one()` / `list_lru_count_node()`：查询 LRU 中对象数量
- `list_lru_walk_one()` / `list_lru_walk_node()`：遍历并处理 LRU 中的对象（用于 shrinker 回调）

### 内部辅助函数
- `list_lru_from_memcg_idx()`：根据 memcg ID 获取对应的 `list_lru_one`
- `__list_lru_walk_one()`：带锁的 LRU 遍历核心逻辑
- `list_lru_register()` / `list_lru_unregister()`：注册/注销 memcg-aware 的 LRU（用于全局追踪）

## 3. 关键实现

### 内存控制组（memcg）支持
- 通过 `CONFIG_MEMCG` 条件编译控制 memcg 相关逻辑
- 使用 XArray (`lru->xa`) 动态存储每个 memcg 对应的 `list_lru_memcg` 结构
- 每个 memcg 在每个 NUMA 节点上拥有独立的 `list_lru_one`，实现资源隔离
- 全局 `memcg_list_lrus` 链表和 `list_lrus_mutex` 用于跟踪所有 memcg-aware 的 LRU 实例

### 并发控制
- 每个 NUMA 节点 (`list_lru_node`) 拥有独立的自旋锁 (`nlru->lock`)
- 所有对 LRU 链表的操作（增、删、遍历）均在对应节点锁保护下进行
- 提供 `_irq` 版本的遍历函数（`list_lru_walk_one_irq`）用于中断上下文

### 回收遍历机制
- `list_lru_walk_*` 函数接受回调函数 `isolate`，由调用者定义回收策略
- 回调返回值控制遍历行为：
  - `LRU_REMOVED`：成功移除
  - `LRU_REMOVED_RETRY`：移除后需重新开始遍历（锁曾被释放）
  - `LRU_RETRY`：未移除但需重新开始遍历
  - `LRU_ROTATE`：将对象移到链表尾部（标记为最近使用）
  - `LRU_SKIP`：跳过当前对象
  - `LRU_STOP`：立即停止遍历
- 通过 `nr_to_walk` 限制单次遍历的最大对象数，防止长时间持锁

### Shrinker 集成
- 当向空的 `list_lru_one` 添加首个对象时，调用 `set_shrinker_bit()` 标记该 memcg/node 需要被 shrinker 处理
- `lru_shrinker_id()` 返回关联的 shrinker ID，用于通知内存回收子系统

### 对象归属识别
- `list_lru_add_obj()` / `list_lru_del_obj()` 通过 `mem_cgroup_from_slab_obj()` 自动获取对象所属的 memcg
- 使用 `page_to_nid(virt_to_page(item))` 确定对象所在的 NUMA 节点

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/list_lru.h>`：定义核心数据结构和 API
  - `<linux/memcontrol.h>`：memcg 相关接口（如 `memcg_kmem_id`）
  - `"slab.h"` 和 `"internal.h"`：slab 分配器内部接口（如 `mem_cgroup_from_slab_obj`）
- **配置依赖**：
  - `CONFIG_MEMCG`：决定是否编译 memcg 相关代码
  - `CONFIG_NUMA`：影响 per-node 数据结构的大小（通过 `nr_node_ids`）
- **子系统依赖**：
  - Slab 分配器：作为主要使用者，管理可回收 slab 对象
  - Memory Control Group (memcg)：提供内存隔离和记账
  - Shrinker 框架：通过 shrinker 回调触发 LRU 遍历回收

## 5. 使用场景

- **Slab 对象回收**：当系统内存压力大时，shrinker 通过 `list_lru_walk_*` 遍历 inactive slab 对象链表，释放可回收对象
- **Per-memcg 内存限制**：在 cgroup 内存超限时，仅遍历该 memcg 对应的 LRU 部分，实现精确回收
- **NUMA 感知管理**：按 NUMA 节点分离 LRU 链表，减少远程内存访问，提升性能
- **通用 LRU 容器**：任何需要按 LRU 策略管理可回收对象的内核子系统均可使用此基础设施（如 dentry、inode 缓存等）