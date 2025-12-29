# memcontrol-v1.c

> 自动生成时间: 2025-12-07 16:38:55
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `memcontrol-v1.c`

---

# memcontrol-v1.c 技术文档

## 1. 文件概述

`memcontrol-v1.c` 是 Linux 内核内存控制组（Memory Cgroup）v1 接口的核心实现文件之一，主要负责基于软限制（soft limit）的内存回收机制、OOM 事件通知以及与 cgroup v1 兼容的资源统计和管理功能。该文件维护了一个独立于 cgroup 层级结构的红黑树（RB-Tree），用于高效地追踪和选择超出软限制最多的内存控制组进行内存回收。

## 2. 核心功能

### 主要数据结构

- **`struct mem_cgroup_tree_per_node`**  
  每个 NUMA 节点对应的红黑树结构，用于存储超出软限制的 `mem_cgroup_per_node` 实例。
  - `rb_root`: 红黑树根节点
  - `rb_rightmost`: 指向使用量超出软限制最多的节点（树中最右侧节点）
  - `lock`: 保护该树的自旋锁

- **`struct mem_cgroup_tree`**  
  全局软限制树结构，包含每个 NUMA 节点对应的 `mem_cgroup_tree_per_node`。

- **`struct mem_cgroup_eventfd_list`**  
  用于 OOM 事件通知的 eventfd 列表项。

- **`struct mem_cgroup_event`**  
  表示用户空间注册的内存事件（如 OOM、阈值触发等），支持通过 eventfd 通知用户空间。

- **枚举常量 `RES_*`**  
  定义了 cgroup v1 接口中可读写的资源属性类型（如使用量、限制、最大使用量、失败计数、软限制等）。

### 主要函数

- **`__mem_cgroup_insert_exceeded()` / `__mem_cgroup_remove_exceeded()`**  
  在指定节点的软限制红黑树中插入或移除一个 `mem_cgroup_per_node` 节点。

- **`memcg1_update_tree()`**  
  根据当前内存使用量与软限制的差值，更新指定 memcg 及其所有祖先在软限制树中的位置。

- **`memcg1_remove_from_trees()`**  
  在 memcg 销毁时，将其从所有 NUMA 节点的软限制树中移除。

- **`mem_cgroup_largest_soft_limit_node()`**  
  从指定节点的软限制树中找出超出软限制最多的 memcg 节点，用于优先回收。

- **`mem_cgroup_soft_reclaim()`**  
  对指定 memcg 层级结构执行软限制驱动的内存回收。

- **`memcg1_soft_limit_reclaim()`**（未完整显示）  
  全局软限制回收入口函数，由内存短缺路径调用，尝试从超出软限制的 memcg 中回收内存。

## 3. 关键实现

### 软限制红黑树机制

- 所有超出软限制（`memory.usage > soft_limit`）的 `mem_cgroup_per_node` 实例被组织到 per-NUMA-node 的红黑树中。
- 树按 `usage_in_excess = usage - soft_limit` 升序排列，最右侧节点即为超出最多的 memcg。
- 当 memcg 的内存使用量变化或软限制被修改时，调用 `memcg1_update_tree()` 更新其在树中的位置（先删除再重新插入）。
- 回收时优先选择 `rb_rightmost` 节点，确保优先回收“最违规”的 memcg。

### 层级遍历与祖先更新

- 在启用 cgroup 层级模式时，子 memcg 的内存使用会影响父 memcg 的统计。
- 因此，当子 memcg 的使用量变化时，需向上遍历所有祖先，更新它们在软限制树中的状态。

### 防止无限循环的回收控制

- `MEM_CGROUP_MAX_RECLAIM_LOOPS`（100）和 `MEM_CGROUP_MAX_SOFT_LIMIT_RECLAIM_LOOPS`（2）用于限制回收循环次数。
- 若一轮遍历未回收足够内存（`total < excess >> 2`），最多再尝试一次。

### 与 LRU_GEN 的集成

- 若启用了多代 LRU（`lru_gen_enabled()`），则绕过红黑树机制，直接调用 `lru_gen_soft_reclaim()` 进行软限制回收。

### 事件通知机制

- 支持通过 `eventfd` 向用户空间发送 OOM 或其他内存事件通知。
- 使用 `poll_table` 和 `wait_queue` 实现 eventfd 的自动注销（当 fd 关闭时）。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/memcontrol.h>`：内存控制组核心接口
  - `<linux/swap.h>`, `"swap.h"`：交换子系统支持
  - `<linux/eventfd.h>`, `<linux/poll.h>`：事件通知机制
  - `"internal.h"`：内核内存管理内部接口

- **功能依赖**：
  - 依赖 `page_counter` 子系统进行内存使用量统计
  - 依赖 `mem_cgroup_iter()` 实现层级遍历
  - 依赖 `mem_cgroup_shrink_node()` 执行实际页面回收
  - 可选依赖 `lru_gen` 多代 LRU 回收器

- **配置依赖**：
  - `CONFIG_MEMCG`：必须启用内存 cgroup
  - `CONFIG_LOCKDEP`：仅在调试时定义锁依赖映射

## 5. 使用场景

- **内存压力下的软限制回收**：当系统内存紧张时，`kswapd` 或直接回收路径会调用 `memcg1_soft_limit_reclaim()`，优先从超出软限制的 memcg 中回收内存，以维持服务质量（QoS）。
- **cgroup v1 接口兼容**：为 `/sys/fs/cgroup/memory/` 下的 `memory.soft_limit_in_bytes` 等文件提供后端支持。
- **OOM 事件通知**：当 memcg 触发 OOM 时，通过预先注册的 eventfd 向用户空间守护进程（如容器运行时）发送通知。
- **动态资源调整**：当用户通过写入 `memory.soft_limit_in_bytes` 修改软限制时，触发 `memcg1_update_tree()` 更新红黑树结构。
- **memcg 销毁清理**：在 cgroup 被删除时，确保其从所有软限制树中正确移除，防止悬挂指针。