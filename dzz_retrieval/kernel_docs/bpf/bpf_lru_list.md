# bpf\bpf_lru_list.c

> 自动生成时间: 2025-10-25 12:00:28
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\bpf_lru_list.c`

---

# `bpf/bpf_lru_list.c` 技术文档

## 1. 文件概述

`bpf_lru_list.c` 实现了 BPF（Berkeley Packet Filter）子系统中用于管理 LRU（Least Recently Used，最近最少使用）缓存的通用机制。该机制主要用于 BPF map（如 `lru_hash` 类型）中高效地回收不活跃或未被引用的条目，以控制内存使用并提升缓存命中率。文件提供了基于双链表的活跃/非活跃 LRU 链表管理、本地（per-CPU）缓存支持、引用位（ref bit）跟踪以及自动老化和回收策略。

## 2. 核心功能

### 主要数据结构
- `struct bpf_lru_node`：LRU 节点，嵌入在 BPF map 条目中，包含链表指针、类型和引用标志。
- `struct bpf_lru_list`：全局 LRU 链表结构，维护活跃（ACTIVE）和非活跃（INACTIVE）链表，以及各类节点计数。
- `struct bpf_lru_locallist`：每个 CPU 的本地 LRU 链表，用于减少锁竞争，包含 FREE 和 PENDING 本地链表。
- `struct bpf_lru`：LRU 控制结构，包含回调函数（如 `del_from_htab`）、扫描数量（`nr_scans`）等配置。

### 主要函数
- `__bpf_lru_list_rotate_active()`：轮转活跃链表，将带引用位的节点保留在活跃链表头部，无引用位的移至非活跃链表。
- `__bpf_lru_list_rotate_inactive()`：轮转非活跃链表，将带引用位的节点提升回活跃链表。
- `__bpf_lru_list_shrink_inactive()`：从非活跃链表尾部回收无引用位且可删除的节点到指定 free 链表。
- `__bpf_lru_list_shrink()`：尝试正常回收失败后，强制从非活跃或活跃链表中删除节点（忽略引用位）。
- `__bpf_lru_node_move()` / `__bpf_lru_node_move_in()` / `__bpf_lru_node_move_to_free()`：节点在不同链表间移动的内部辅助函数。
- `get_next_cpu()`：用于遍历所有可能 CPU 的辅助函数。

### 关键常量
- `LOCAL_FREE_TARGET` / `PERCPU_FREE_TARGET`：本地和 per-CPU 回收目标数量（分别为 128 和 4）。
- `LOCAL_NR_SCANS` / `PERCPU_NR_SCANS`：本地和 per-CPU 扫描上限，等于各自目标值。
- `BPF_LOCAL_LIST_T_OFFSET`：本地链表类型的偏移量，用于区分全局 LRU 类型和本地类型。

## 3. 关键实现

### LRU 双链表模型
采用经典的 **Active/Inactive 双链表模型**：
- **活跃链表（ACTIVE）**：存放近期被访问或引用的节点。
- **非活跃链表（INACTIVE）**：存放较久未被访问的节点，是回收的主要候选区域。
- 节点首次插入时通常进入活跃链表；经过一次老化周期后，若无引用则移至非活跃链表。

### 引用位（ref bit）机制
- 每个 `bpf_lru_node` 包含一个 `ref` 字段（原子读写），表示该节点是否在最近被访问。
- 在轮转过程中：
  - 若节点 `ref == 1`，则清零并保留在活跃链表（或从非活跃提升至活跃）。
  - 若 `ref == 0`，则可能被移至非活跃链表或直接回收。
- 该机制避免了频繁移动热数据，提高了缓存效率。

### 老化与回收策略
- **轮转（Rotate）**：
  - 定期调用 `__bpf_lru_list_rotate()`。
  - 当非活跃链表长度小于活跃链表时，触发活跃链表轮转。
  - 非活跃链表总是轮转，从 `next_inactive_rotation` 指针开始，避免每次都从头扫描。
- **回收（Shrink）**：
  - 优先从非活跃链表尾部回收无引用且可删除（通过 `del_from_htab` 回调确认）的节点。
  - 若回收不足，强制从非活跃链表（优先）或活跃链表中删除节点，**忽略引用位**，确保内存压力下能释放资源。

### 本地（Local）与 Per-CPU 优化
- 支持 **本地链表类型**（`BPF_LRU_LOCAL_LIST_T_FREE` / `PENDING`），用于暂存待处理或刚释放的节点。
- 通过 `IS_LOCAL_LIST_TYPE()` 宏区分本地与全局类型，防止非法移动。
- 减少全局锁竞争，提升多核性能。

### 安全移动与指针维护
- 在移动节点时，若该节点恰好是 `next_inactive_rotation` 指针指向的对象，则自动将其前移，避免悬空指针。
- 使用 `list_move()` 安全地在链表间转移节点。
- 所有计数操作（`bpf_lru_list_count_inc/dec`）均带边界检查。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/cpumask.h>`：用于 CPU 遍历（`get_next_cpu`）。
  - `<linux/spinlock.h>` 和 `<linux/percpu.h>`：支持 per-CPU 数据结构和同步。
- **内部依赖**：
  - 依赖 `bpf_lru_list.h` 中定义的数据结构和枚举（如 `enum bpf_lru_list_type`）。
- **外部回调**：
  - 通过 `lru->del_from_htab(lru->del_arg, node)` 回调通知上层（如 BPF map 实现）删除哈希表中的条目，实现 LRU 与具体数据结构的解耦。

## 5. 使用场景

- **BPF LRU Hash Map**：该文件是 `BPF_MAP_TYPE_LRU_HASH` 和 `BPF_MAP_TYPE_LRU_PERCPU_HASH` 等 map 类型的核心内存管理组件。
- **内存压力下的自动回收**：当 map 达到容量上限或系统内存紧张时，触发 shrink 操作释放条目。
- **高并发环境优化**：通过本地链表和引用位机制，在多核系统上高效管理缓存，减少锁争用。
- **内核网络与跟踪子系统**：被用于 eBPF 程序中需要高效键值存储且自动淘汰旧数据的场景，如连接跟踪、统计聚合等。