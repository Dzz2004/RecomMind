# bpf\bloom_filter.c

> 自动生成时间: 2025-10-25 11:56:28
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\bloom_filter.c`

---

# `bpf/bloom_filter.c` 技术文档

## 1. 文件概述

该文件实现了 Linux 内核中 eBPF（extended Berkeley Packet Filter）子系统所支持的 **布隆过滤器（Bloom Filter）映射类型**。布隆过滤器是一种空间高效的概率型数据结构，用于快速判断某个元素是否**可能存在于集合中**（允许假阳性，但不允许假阴性）。该映射类型专为只写入、只查询、不可删除的场景设计，适用于高性能、低内存开销的成员存在性检测。

## 2. 核心功能

### 数据结构

- **`struct bpf_bloom_filter`**  
  布隆过滤器的具体实现结构体，包含：
  - `struct bpf_map map`：继承自通用 eBPF 映射结构。
  - `u32 bitset_mask`：位图掩码，用于快速取模（因位图大小为 2 的幂）。
  - `u32 hash_seed`：哈希种子，用于初始化哈希函数（可选随机化）。
  - `u32 nr_hash_funcs`：使用的哈希函数数量（1–15，由 `map_extra` 指定）。
  - `unsigned long bitset[]`：柔性数组，存储位图数据。

### 主要函数

| 函数名 | 功能说明 |
|--------|--------|
| `hash()` | 根据输入值、哈希种子和索引计算哈希值，并通过 `bitset_mask` 取模得到位图索引。支持 4 字节对齐和非对齐数据。 |
| `bloom_map_peek_elem()` | 查询元素是否存在：对每个哈希函数计算位图位置，若任一位为 0 则返回 `-ENOENT`（不存在）；否则返回 0（可能存在）。 |
| `bloom_map_push_elem()` | 插入元素：对每个哈希函数计算位图位置并置位。仅支持 `BPF_ANY` 标志。 |
| `bloom_map_alloc()` | 分配并初始化布隆过滤器映射。根据 `max_entries` 和 `map_extra`（哈希函数数）计算最优位图大小，并向上取整为 2 的幂。 |
| `bloom_map_free()` | 释放布隆过滤器占用的内存。 |
| `bloom_map_alloc_check()` | 在创建映射前校验参数合法性（如 `value_size` 不超过 `KMALLOC_MAX_SIZE`）。 |
| `bloom_map_check_btf()` | BTF（BPF Type Format）校验：要求 key 类型为 `void`（无 key）。 |
| `bloom_map_mem_usage()` | 返回该映射实际占用的内存大小（含位图）。 |

### 不支持的操作（返回 `-EOPNOTSUPP` 或 `-EINVAL`）

- `bloom_map_pop_elem()`：不支持弹出元素。
- `bloom_map_delete_elem()`：不支持删除元素。
- `bloom_map_get_next_key()`：不支持遍历。
- `bloom_map_lookup_elem()` / `bloom_map_update_elem()`：eBPF 程序应使用 `map_peek_elem` 和 `map_push_elem` 替代。

### 映射操作表

- `bloom_filter_map_ops`：定义了该映射类型支持的所有操作回调函数，注册到 eBPF 子系统。

## 3. 关键实现

### 布隆过滤器参数计算

- **哈希函数数量**：由用户通过 `attr->map_extra & 0xF` 指定（1–15），若为 0 则默认使用 5 个。
- **位图大小计算**：
  - 理论最优位数：`n * k / ln(2)`，其中 `n = max_entries`，`k = nr_hash_funcs`。
  - 代码使用 `7/5 ≈ 1/ln(2)` 近似计算：`nr_bits = (max_entries * k * 7) / 5`。
  - 为提升哈希效率，将 `nr_bits` **向上取整为 2 的幂**，从而可用 `& (size - 1)` 替代取模运算。
  - 若计算溢出（> 2^31），则使用最大位图（`U32_MAX` 位，约 512 MB）。

### 哈希函数

- 使用内核提供的 `jhash()` 和 `jhash2()`（Jenkins 哈希）。
- 每个哈希函数通过 `hash_seed + index` 区分，确保独立性。
- 支持任意长度的 `value`（由 `value_size` 指定），自动选择对齐/非对齐版本。

### 内存分配

- 使用 `bpf_map_area_alloc()` 分配连续内存，包含结构体头和位图。
- 位图大小按 `unsigned long` 对齐，确保位操作效率。

### 安全与校验

- 严格校验创建参数：`key_size` 必须为 0，`value_size` 和 `max_entries` 必须 > 0。
- 仅允许特定 `map_flags`（`BPF_F_NUMA_NODE`、`BPF_F_ZERO_SEED`、`BPF_F_ACCESS_MASK`）。
- BTF 校验强制 key 类型为 `void`，符合“无 key”设计。

## 4. 依赖关系

- **内核头文件**：
  - `<linux/bitmap.h>`：提供 `test_bit()`、`set_bit()` 等位操作。
  - `<linux/bpf.h>`：eBPF 核心定义（`bpf_map`、操作码等）。
  - `<linux/btf.h>`：BTF 类型系统支持。
  - `<linux/jhash.h>`：Jenkins 哈希函数实现。
  - `<linux/random.h>`：`get_random_u32()` 用于生成哈希种子。
- **eBPF 子系统**：通过 `bpf_map_ops` 机制集成到 eBPF 映射框架中。
- **内存管理**：依赖 `bpf_map_area_alloc/free` 进行 NUMA 感知内存分配。

## 5. 使用场景

- **网络数据包过滤**：快速判断 IP 地址、端口等是否在可疑集合中。
- **安全监控**：检测进程、文件路径是否属于已知恶意样本（允许少量误报）。
- **性能分析**：记录已观测到的事件 ID，避免重复处理。
- **资源去重**：在无法存储完整集合的场景下，高效判断元素是否已存在。

> **注意**：由于布隆过滤器**不支持删除操作**，且存在**假阳性**，适用于“写一次、查多次”且可容忍少量误报的场景。eBPF 程序需通过 `bpf_map_peek_elem()` 查询，通过 `bpf_map_push_elem()` 插入。