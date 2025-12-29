# bpf\hashtab.c

> 自动生成时间: 2025-10-25 12:10:56
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\hashtab.c`

---

# bpf/hashtab.c 技术文档

## 1. 文件概述

`bpf/hashtab.c` 是 Linux 内核中 BPF（Berkeley Packet Filter）子系统的核心实现文件之一，负责提供基于哈希表（hash table）的 BPF map 类型支持。该文件实现了多种 BPF map 类型，包括普通哈希表（`BPF_MAP_TYPE_HASH`）、LRU 哈希表（`BPF_MAP_TYPE_LRU_HASH`）、每 CPU 哈希表（`BPF_MAP_TYPE_PERCPU_HASH`）及其 LRU 变体。它支持预分配（pre-allocated）和动态分配（non-preallocated）两种内存管理模式，并集成了 BPF 内存分配器（`bpf_mem_alloc`）、LRU 驱逐机制、每 CPU 自由列表（percpu freelist）等高级特性，以满足高性能、低延迟的 BPF 程序需求。

## 2. 核心功能

### 主要数据结构

- **`struct bucket`**  
  哈希桶结构，包含一个 `hlist_nulls_head` 链表头和一个 `raw_spinlock_t` 原始自旋锁，用于保护桶内元素的并发访问。

- **`struct bpf_htab`**  
  BPF 哈希表的主控制结构，继承自 `struct bpf_map`，包含：
  - 桶数组指针 `buckets`
  - 元素存储区 `elems`
  - 内存分配器 `ma`（主）和 `pcpu_ma`（每 CPU）
  - LRU 或 percpu_freelist 联合体
  - 元素计数器（`pcount` 或 `count`）
  - 哈希种子 `hashrnd`
  - 锁依赖类键 `lockdep_key`
  - 每 CPU 锁状态数组 `map_locked`（用于防止递归）

- **`struct htab_elem`**  
  哈希表元素结构，包含：
  - 哈希链表节点 `hash_node`
  - LRU 节点或自由列表节点
  - 指向每 CPU 指针的指针（用于 per-CPU map）
  - 哈希值 `hash`
  - 可变长键 `key[]`（后接值或 per-CPU 指针）

### 关键辅助函数

- `htab_is_prealloc()`：判断是否为预分配模式
- `htab_is_lru()` / `htab_is_percpu()`：判断 map 类型是否为 LRU 或 per-CPU
- `htab_init_buckets()`：初始化所有哈希桶
- `htab_lock_bucket()` / `htab_unlock_bucket()`：带递归保护的桶锁操作
- `htab_elem_set_ptr()` / `htab_elem_get_ptr()`：操作 per-CPU 指针
- `get_htab_elem()`：从预分配区域获取第 i 个元素
- `htab_has_extra_elems()`：判断是否包含额外元素（用于 per-CPU 扩展）
- `htab_free_prealloced_timers_and_wq()`：释放预分配元素中的 BPF 定时器和工作队列资源

### 批量操作宏

- `BATCH_OPS(_name)`：定义批量操作函数指针，如 `map_lookup_batch`、`map_update_batch` 等。

## 3. 关键实现

### 并发控制与死锁预防

- 使用 **原始自旋锁（`raw_spinlock_t`）** 保护每个哈希桶，确保在任意上下文（如 kprobe、perf、tracepoint）中安全使用。
- 引入 **每 CPU 递归计数器 `map_locked[]`**，防止 BPF 程序在持有桶锁时再次进入（例如通过 `sys_bpf()` 或嵌套 BPF 调用），避免死锁。
- 在 `PREEMPT_RT` 实时内核上，由于普通自旋锁可能睡眠，必须使用 `raw_spinlock` 以保证原子性；结合 `bpf_mem_alloc` 后，即使非预分配模式也可安全使用原始锁。

### 内存管理

- **预分配模式（`BPF_F_NO_PREALLOC` 未设置）**：启动时一次性分配所有元素，使用 `pcpu_freelist` 管理空闲元素。
- **非预分配模式**：按需通过 `bpf_mem_alloc` 动态分配元素，支持 NUMA 感知和内存回收。
- **Per-CPU 支持**：对于 `PERCPU_HASH` 类型，每个键对应一个 per-CPU 值数组，通过 `htab_elem_get_ptr()` 访问。

### LRU 驱逐机制

- 当 map 类型为 `LRU_HASH` 或 `LRU_PERCPU_HASH` 时，使用 `bpf_lru` 子系统管理元素生命周期，自动驱逐最近最少使用的条目以维持 `max_entries` 限制。

### 扩展字段支持

- 支持 BTF（BPF Type Format）描述的复杂值类型，如 `BPF_TIMER` 和 `BPF_WORKQUEUE`，在销毁 map 时自动释放相关资源（见 `htab_free_prealloced_timers_and_wq`）。

### 哈希与对齐

- 使用 `jhash` 算法计算键的哈希值，并通过 `hashrnd` 引入随机种子防止哈希碰撞攻击。
- 键和值之间按 8 字节对齐（`__aligned(8)`），确保 per-CPU 指针正确对齐。

## 4. 依赖关系

- **内核头文件**：
  - `<linux/bpf.h>`、`<linux/btf.h>`：BPF 和 BTF 核心接口
  - `<linux/jhash.h>`：哈希函数
  - `<linux/rculist_nulls.h>`：RCU 安全的空指针链表
  - `<linux/percpu_freelist.h>`、`<linux/bpf_lru_list.h>`：内存管理子系统
  - `<linux/bpf_mem_alloc.h>`：BPF 专用内存分配器

- **内部模块**：
  - `map_in_map.h`：支持 map-in-map 功能
  - `bpf_lru_list.c`：LRU 驱逐实现
  - `percpu_freelist.c`：每 CPU 自由列表管理

- **BPF 子系统**：
  - 与 `bpf_map` 通用框架集成，通过 `bpf_map_ops` 注册操作函数
  - 依赖 `bpf_prog_active` 机制防止 BPF 递归

## 5. 使用场景

- **网络数据包过滤与监控**：eBPF 程序使用 `BPF_MAP_TYPE_HASH` 存储连接状态、统计信息等。
- **性能分析**：通过 `PERCPU_HASH` 收集每 CPU 的性能计数器，避免锁竞争。
- **资源限制与缓存**：`LRU_HASH` 用于实现有界缓存（如 DNS 缓存、会话表），自动淘汰旧条目。
- **内核跟踪**：kprobe、tracepoint 等 attach 的 BPF 程序频繁读写哈希表，要求低延迟和高并发。
- **用户空间交互**：通过 `bpf(2)` 系统调用进行 map 的创建、更新、查询和删除，支持批量操作提升效率。
- **高级 BPF 功能**：支持包含定时器（`bpf_timer`）或工作队列（`bpf_workqueue`）的复杂 map 值类型，用于异步任务调度。