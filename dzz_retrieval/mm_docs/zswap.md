# zswap.c

> 自动生成时间: 2025-12-07 17:38:47
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `zswap.c`

---

# zswap.c 技术文档

## 1. 文件概述

`zswap.c` 实现了 Linux 内核中的 **zswap** 功能，这是一个基于 RAM 的交换页压缩缓存机制。当系统需要将内存页换出（swap out）时，zswap 会尝试先将这些页压缩并存储在内存池中，而不是立即写入慢速的交换设备（如磁盘或 SSD）。此举可显著减少 I/O 操作，在压缩/解压速度优于磁盘读取速度时还能提升整体性能。该模块通过内核参数支持动态配置压缩算法、内存池类型、容量限制等策略。

## 2. 核心功能

### 主要数据结构
- `struct zswap_entry`：表示一个被压缩存储的交换页元数据，包含 swap 条目、压缩后长度、所属内存池、zpool 句柄（或同值填充页的值）、内存控制组（objcg）及 LRU 链表节点。
- `struct zswap_pool`：管理一组压缩内存池（最多 `ZSWAP_NR_ZPOOLS=32` 个），每个池关联一个异步压缩上下文（`crypto_acomp_ctx`），支持引用计数和延迟释放。
- `zswap_trees[MAX_SWAPFILES]`：每个交换文件对应一个 XArray，用于以 swap entry 为键快速查找对应的 `zswap_entry`。
- `zswap_list_lru`：全局 LRU 列表，用于在内存压力下回收最久未使用的压缩页。

### 关键全局变量与统计
- `zswap_pool_total_size`：当前所有压缩池占用的总字节数。
- `zswap_stored_pages` / `zswap_same_filled_pages`：分别记录已存储的压缩页总数和同值填充页数量。
- 多种拒绝计数器（如 `zswap_reject_compress_fail`、`zswap_reject_alloc_fail` 等）用于诊断失败原因。
- `zswap_pool_reached_full`：标志位，指示是否达到内存池上限。

### 可调参数（通过 `/sys/module/zswap/parameters/` 暴露）
- `enabled`：启用/禁用 zswap。
- `compressor`：指定压缩算法（如 `lzo`, `lz4`, `zstd`）。
- `zpool`：指定底层内存分配器（如 `zbud`, `z3fold`）。
- `max_pool_percent`：压缩池最大占用系统内存百分比（默认 20%）。
- `accept_threshold_percent`：达到上限后仍接受新页的阈值（默认 90%）。
- `same_filled_pages_enabled` / `non_same_filled_pages_enabled`：控制是否处理同值填充页和普通页。
- `shrinker_enabled`：是否启用基于内存压力的 shrinker 回收机制。

### 辅助函数与接口
- `is_zswap_enabled()` / `zswap_never_enabled()`：查询 zswap 状态。
- 异步压缩上下文管理（`crypto_acomp_ctx`）支持睡眠/非睡眠上下文。
- 工作队列 `shrink_wq` 用于后台回收任务。

## 3. 关键实现

### 压缩与存储流程
1. **拦截交换写入**：在 swap-out 路径中，zswap 作为前端缓存拦截待写入交换设备的页。
2. **同值填充检测**：若页内容全为同一字节值（如全零），则不进行压缩，仅记录该值，节省空间。
3. **异步压缩**：使用 crypto API 的 `acomp`（异步压缩）框架对页进行压缩。
4. **内存池分配**：将压缩数据存入由 `zpool` 管理的内存池（如 zbud/z3fold），获得句柄。
5. **元数据注册**：创建 `zswap_entry` 并插入对应 swap 文件的 XArray 树中，同时加入全局 LRU。

### 内存回收机制
- **容量限制**：当 `zswap_pool_total_size` 超过 `max_pool_percent` 限制时，设置 `zswap_pool_reached_full` 标志。
- **写回触发**：后续存储请求可能触发 LRU 最旧页的写回（写入真实 swap 设备）以腾出空间。
- **Shrinker 支持**：注册内核 shrinker 回调，在全局内存压力下主动回收 zswap 中的页。

### 并发与同步
- **锁层次**：`zswap_tree.lock`（XArray 锁） → `zswap_pool.lru_lock`（LRU 锁）。
- **RCU 保护**：`zswap_pools` 列表使用 RCU 进行安全遍历。
- **Per-CPU 压缩上下文**：每个 CPU 拥有独立的 `crypto_acomp_ctx`，避免锁竞争。

### 特殊优化
- **同值填充页**：跳过压缩，仅存储单个字节值，极大节省空间。
- **多 zpool 实例**：每个 `zswap_pool` 包含 32 个 zpool 实例，提升并发扩展性。
- **统计近似**：多数统计计数器无锁，牺牲精确性换取性能。

## 4. 依赖关系

- **内存管理子系统**：依赖 `swap.h`、`internal.h`、`mm_types.h`、`page-flags.h` 等，与 swap 机制深度集成。
- **压缩框架**：使用 `crypto/acompress.h` 提供的异步压缩 API。
- **内存池管理**：依赖 `zpool.h` 抽象（如 zbud、z3fold 实现）。
- **内存控制组**：通过 `obj_cgroup` 支持 cgroup v2 内存记账。
- **LRU 管理**：使用 `list_lru.h` 提供的全局 LRU 基础设施。
- **工作队列**：依赖 `workqueue.h` 执行后台回收任务。
- **内核参数系统**：通过 `module_param_cb` 实现运行时配置。

## 5. 使用场景

- **内存受限系统**：在 RAM 较小但 CPU 较强的设备（如嵌入式系统、低端笔记本）上，用 CPU 换 I/O，避免频繁访问慢速交换设备。
- **SSD 寿命延长**：减少对 SSD 的写入次数，延长其使用寿命。
- **高性能计算**：在 swap-heavy 工作负载中，若内存解压速度 > 磁盘读取速度，可提升响应性能。
- **容器环境**：配合 cgroup 内存限制，为容器提供更高效的交换缓存。
- **调试与监控**：通过暴露的统计信息（`/sys/kernel/debug/zswap` 或 `/proc/vmstat`）分析 swap 行为和压缩效率。