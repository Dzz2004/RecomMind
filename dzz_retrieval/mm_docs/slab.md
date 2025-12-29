# slab.h

> 自动生成时间: 2025-12-07 17:22:03
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `slab.h`

---

# `slab.h` 技术文档

## 1. 文件概述

`slab.h` 是 Linux 内核内存管理子系统中 SLAB/SLUB 分配器的核心内部头文件，定义了 slab 分配器所使用的底层数据结构（如 `struct slab` 和 `struct kmem_cache`）、关键宏和辅助函数。该文件主要用于在页（`struct page`）与 slab 表示之间进行安全转换，并提供对 slab 元数据的原子访问机制，以支持高性能、可扩展的对象缓存分配。

此头文件专供内核内存管理内部使用，不对外暴露给模块开发者，是实现 SLUB（默认）或 SLAB 分配器的关键基础设施。

## 2. 核心功能

### 主要数据结构

- **`freelist_aba_t`**  
  联合体，将空闲对象指针（`freelist`）与计数器（`counter`）打包为一个原子单元，用于避免 ABA 问题（Compare-and-Swap 中因值重复导致的逻辑错误）。

- **`struct slab`**  
  slab 的内部表示，复用 `struct page` 的内存布局。包含：
  - 所属的 `kmem_cache`
  - 空闲对象链表（`freelist`）
  - 对象使用计数（`inuse`）、总对象数（`objects`）
  - 冻结状态（`frozen`，用于调试）
  - RCU 回收头（`rcu_head`）
  - 引用计数（`__page_refcount`）
  - 可选的 per-object 扩展数据（`obj_exts`）

- **`struct kmem_cache_order_objects`**  
  封装 slab 阶数（order）与对象数量的复合值，支持原子读写。

- **`struct kmem_cache`**  
  slab 缓存描述符，包含：
  - 每 CPU 缓存（`cpu_slab`）
  - 对象大小（`size`, `object_size`）
  - 构造函数（`ctor`）
  - 对齐要求（`align`）
  - 分配标志（`allocflags`）
  - NUMA 相关参数（如 `remote_node_defrag_ratio`）
  - 安全特性（如 `random` 用于 freelist 加固）

### 主要宏与辅助函数

- **类型安全转换宏**：
  - `folio_slab()` / `slab_folio()`：在 `folio` 与 `slab` 之间安全转换
  - `page_slab()` / `slab_page()`：兼容旧代码，在 `page` 与 `slab` 之间转换

- **slab 属性访问函数**：
  - `slab_address()`：获取 slab 起始虚拟地址
  - `slab_nid()` / `slab_pgdat()`：获取所属 NUMA 节点和内存域
  - `slab_order()` / `slab_size()`：获取分配阶数和总字节数

- **pfmemalloc 标志操作**：
  - `slab_test_pfmemalloc()` / `slab_set_pfmemalloc()` 等：标记 slab 是否来自紧急内存预留区（用于网络交换等场景）

- **每 CPU partial slab 支持（`CONFIG_SLUB_CPU_PARTIAL`）**：
  - `slub_percpu_partial()` 等宏：管理每 CPU 的 partial slab 链表

## 3. 关键实现

### 内存布局复用与静态断言

- `struct slab` 并非独立分配，而是直接复用 `struct page` 的内存空间。通过 `static_assert` 确保关键字段偏移一致（如 `flags` ↔ `__page_flags`），保证类型转换安全。
- 整个 `struct slab` 大小不超过 `struct page`，确保无越界访问。

### ABA 问题防护

- 在支持 `cmpxchg128`（64 位）或 `cmpxchg64`（32 位）的架构上，启用 `freelist_aba_t` 结构，将 `freelist` 指针与递增计数器打包为单个原子单元。
- 使用 `try_cmpxchg_freelist` 进行原子更新，防止因指针值循环重用导致的 ABA 错误。
- 若系统不支持对齐的 `struct page`（`!CONFIG_HAVE_ALIGNED_STRUCT_PAGE`），则禁用此优化。

### 类型安全转换

- 使用 C11 `_Generic` 实现类型安全的 `folio`/`slab`/`page` 转换，避免强制类型转换带来的风险，并为未来重构（如完全迁移到 folio）预留接口。

### pfmemalloc 标志复用

- 利用 `folio` 的 `PG_active` 位存储 `pfmemalloc` 标志，指示该 slab 是否从紧急内存池分配，用于网络子系统在内存压力下仍能分配 skb 等关键结构。

## 4. 依赖关系

- **核心依赖**：
  - `<linux/page.h>` / `<linux/folio.h>`：通过 `folio_*` 系列函数操作底层内存
  - `<linux/reciprocal_div.h>`：用于快速除法（计算对象索引）
  - `<linux/rcupdate.h>`：通过 `rcu_head` 支持 RCU 安全的 slab 回收

- **可选依赖（由 Kconfig 控制）**：
  - `CONFIG_SLUB_CPU_PARTIAL`：每 CPU partial slab 优化
  - `CONFIG_SLAB_OBJ_EXT`：per-object 扩展元数据
  - `CONFIG_SLAB_FREELIST_HARDENED`：freelist 指针随机化加固
  - `CONFIG_NUMA`：NUMA 感知分配与碎片整理
  - `CONFIG_KASAN` / `CONFIG_KFENCE`：内存错误检测集成

- **与内存控制器集成**：
  - 通过 `memcg_data` 字段（复用 `obj_exts`）支持 memcg 内存统计

## 5. 使用场景

- **SLUB 分配器内部**：作为 `slub.c` 的核心数据结构定义，用于管理 slab 生命周期、对象分配/释放。
- **内存回收路径**：在 direct reclaim 或 kswapd 中，通过 `slab_folio` 获取 folio 信息以决策回收策略。
- **调试与监控**：sysfs (`kobj`)、KASAN/KFENCE 集成依赖此结构获取 slab 元数据。
- **网络子系统**：通过 `pfmemalloc` 标志识别紧急内存分配，确保高优先级数据包处理不被阻塞。
- **NUMA 优化**：在远程节点分配时使用 `remote_node_defrag_ratio` 参数控制跨节点分配行为。
- **安全加固**：`SLAB_FREELIST_HARDENED` 利用 `random` 字段混淆 freelist 指针，防止堆利用攻击。