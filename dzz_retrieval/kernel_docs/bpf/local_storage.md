# bpf\local_storage.c

> 自动生成时间: 2025-10-25 12:15:04
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\local_storage.c`

---

# `bpf/local_storage.c` 技术文档

## 1. 文件概述

`bpf/local_storage.c` 是 Linux 内核中 BPF（Berkeley Packet Filter）子系统的一部分，专门用于实现 **cgroup 本地存储（cgroup local storage）** 功能。该文件在 `CONFIG_CGROUP_BPF` 配置启用时编译，提供了一种机制，允许 BPF 程序为每个 cgroup 实例关联私有的、可持久化的存储空间（即“本地存储”）。这种存储可用于在 BPF 程序中跨调用保存状态，例如统计信息、配置参数等。

该文件实现了两种 BPF map 类型：
- `BPF_MAP_TYPE_CGROUP_STORAGE`
- `BPF_MAP_TYPE_PERCPU_CGROUP_STORAGE`

分别用于单值存储和 per-CPU 存储，均基于 cgroup 的 inode ID（及可选的 attach type）作为键进行索引。

## 2. 核心功能

### 主要数据结构

- **`struct bpf_cgroup_storage_map`**  
  表示 cgroup 存储类型的 BPF map。包含：
  - `struct bpf_map map`：继承自通用 BPF map 结构
  - `spinlock_t lock`：保护红黑树和链表的自旋锁
  - `struct rb_root root`：以键为索引的红黑树，用于快速查找
  - `struct list_head list`：用于遍历所有存储项的链表

- **`struct bpf_cgroup_storage_key`**  
  键结构体，包含：
  - `__u64 cgroup_inode_id`：cgroup 的 inode ID（唯一标识）
  - `__u32 attach_type`：BPF 程序附加类型（如 `BPF_CGROUP_INET_INGRESS`）

- **`struct bpf_cgroup_storage`**  
  存储条目，包含：
  - `struct rb_node node`：红黑树节点
  - `struct list_head list_map`：链表节点
  - `union { struct bpf_storage_buffer *buf; void __percpu *percpu_buf; }`：指向实际数据的指针（单值或 per-CPU）

### 主要函数

- **`cgroup_storage_lookup()`**  
  在红黑树中根据 key 查找对应的 `bpf_cgroup_storage` 条目，支持加锁/不加锁模式。

- **`cgroup_storage_insert()`**  
  将新的存储条目插入红黑树，若键已存在则返回 `-EEXIST`。

- **`cgroup_storage_lookup_elem()`**  
  BPF map 的 `lookup` 操作回调，返回存储数据的起始地址。

- **`cgroup_storage_update_elem()`**  
  BPF map 的 `update` 操作回调，支持原子更新（带 `BPF_F_LOCK`）或替换整个缓冲区。

- **`bpf_percpu_cgroup_storage_copy()`**  
  用于 `PERCPU_CGROUP_STORAGE` 类型的 lookup，聚合所有 CPU 的数据。

- **`bpf_percpu_cgroup_storage_update()`**  
  用于 `PERCPU_CGROUP_STORAGE` 类型的 update，将用户提供的数据分发到各 CPU。

- **`cgroup_storage_get_next_key()`**  
  实现 BPF map 的 `get_next_key` 操作，用于遍历所有存储条目。

- **`cgroup_storage_map_alloc()`**  
  分配并初始化 cgroup storage 类型的 BPF map。

- **`cgroup_storage_map_free()`**  
  释放 map 及其所有存储条目（代码未完整显示，但功能明确）。

## 3. 关键实现

### 键值设计与比较逻辑

- 支持两种键格式：
  1. 仅 `__u64 cgroup_inode_id`（用于非隔离 attach type）
  2. `struct bpf_cgroup_storage_key`（包含 inode ID + attach type，用于隔离场景）
- `attach_type_isolated()` 判断是否使用完整键结构。
- `bpf_cgroup_storage_key_cmp()` 实现红黑树的比较逻辑，先比较 inode ID，再比较 attach type（如适用）。

### 并发控制

- 使用 `spinlock_t lock` 保护红黑树和链表的修改操作（如插入、遍历）。
- 查找操作可选择是否加锁（`locked` 参数），以支持 RCU 读路径（如 per-CPU update 中使用 `rcu_read_lock()`）。
- 单值存储更新时使用 `xchg()` + `kfree_rcu()` 实现无锁读取和安全释放。

### 内存管理

- 单值存储使用 `bpf_map_kmalloc_node()` 分配 `bpf_storage_buffer`，包含数据和可能的 BTF 记录。
- per-CPU 存储使用 `__percpu` 指针，通过 `per_cpu_ptr()` 访问各 CPU 数据。
- 所有分配考虑 NUMA 节点（通过 `numa_node` 字段）。

### 安全与限制

- `value_size` 限制：
  - 普通类型：最大 `BPF_LOCAL_STORAGE_MAX_VALUE_SIZE`
  - per-CPU 类型：额外受限于 `PCPU_MIN_UNIT_SIZE`
- 键大小必须为 `sizeof(__u64)` 或 `sizeof(bpf_cgroup_storage_key)`
- `max_entries` 必须为 0（动态扩展）
- `map_flags` 仅允许 `BPF_F_NUMA_NODE` 和访问权限标志

### per-CPU 数据对齐

- per-CPU 数据按 8 字节对齐（`round_up(value_size, 8)`），确保跨 CPU 访问安全，并防止内核数据泄露（因 per-CPU 区域初始化为零）。

## 4. 依赖关系

- **BPF 子系统**：依赖 `bpf.h`、`bpf_map.h`、`filter.h` 等核心 BPF 头文件。
- **cgroup 子系统**：依赖 `cgroup-internal.h` 获取 cgroup 内部结构（如 inode ID）。
- **内存管理**：使用 `slab.h`、`mm.h` 进行内存分配。
- **RCU 机制**：用于安全释放旧缓冲区（`kfree_rcu`）。
- **BTF（BPF Type Format）**：支持带锁字段的类型验证（`btf_record_has_field`）。
- **红黑树**：使用 `rbtree.h` 实现高效查找。
- **Per-CPU 基础设施**：使用 `percpu.h` 相关宏（隐式包含）。

## 5. 使用场景

- **BPF 程序状态持久化**：  
  BPF 程序（如 cgroup hook 程序）可为每个 cgroup 维护独立的计数器、配置或状态机。

- **网络策略与限速**：  
  在 `BPF_CGROUP_INET_*` 程序中，为每个 cgroup 存储流量统计或令牌桶状态。

- **资源监控**：  
  用户空间通过 BPF map 接口读取各 cgroup 的累计指标（如 I/O 次数、进程数）。

- **安全策略**：  
  存储 cgroup 特定的安全上下文或访问控制列表。

- **调试与追踪**：  
  在 BPF tracepoint 或 kprobe 程序中，按 cgroup 聚合事件数据。

> **注意**：该机制仅在 cgroup BPF 支持启用（`CONFIG_CGROUP_BPF=y`）时可用，且必须通过 BPF 系统调用创建对应类型的 map，并由 BPF 程序或用户空间程序操作。