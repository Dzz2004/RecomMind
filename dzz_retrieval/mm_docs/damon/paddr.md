# damon\paddr.c

> 自动生成时间: 2025-12-07 15:49:43
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `damon\paddr.c`

---

# `damon/paddr.c` 技术文档

## 1. 文件概述

`damon/paddr.c` 是 Linux 内核中 DAMON（Data Access MONitor）子系统的一部分，专门用于监控**物理地址空间**中的内存访问行为。该文件实现了针对物理页的访问检测、老化标记、访问状态检查以及基于策略的操作（如 pageout、LRU 调整等），为 DAMON 提供了面向物理内存的操作原语（primitives）。它注册了一组 `damon_operations`，使 DAMON 能够在不依赖虚拟地址映射的情况下直接对物理页进行监控和管理。

## 2. 核心功能

### 主要函数

| 函数名 | 功能说明 |
|--------|--------|
| `damon_pa_mkold()` | 将指定物理地址对应的 folio 标记为“未被访问”（老化），通过遍历其所有虚拟映射并清除 PTE/PMD 的 young 位，同时设置 folio idle 标志。 |
| `damon_pa_young()` | 检查指定物理地址对应的 folio 是否近期被访问过，通过检查 PTE/PMD 的 young 位、folio idle 状态及 MMU notifier 的 young 状态。 |
| `__damon_pa_prepare_access_check()` / `damon_pa_prepare_access_checks()` | 为每个监控区域随机选择一个采样地址，并调用 `damon_pa_mkold()` 进行预老化，为下一轮访问检测做准备。 |
| `__damon_pa_check_access()` / `damon_pa_check_accesses()` | 检查各区域采样地址是否被访问，若被访问则递增 `nr_accesses`；支持缓存上一次检查结果以提升性能。 |
| `damos_pa_filter_out()` / `__damos_pa_filter_out()` | 根据 DAMOS（DAMON Operation Scheme）过滤器（如匿名页、memcg ID）判断是否应跳过对某 folio 的操作。 |
| `damon_pa_pageout()` | 对区域内所有符合条件的 folio 执行 pageout（回收到 swap 或释放），通过隔离 LRU 并调用 `reclaim_pages()`。 |
| `damon_pa_mark_accessed()` / `damon_pa_deactivate_pages()` | 分别将 folio 标记为“已访问”（提升 LRU 优先级）或“非活跃”（降低 LRU 优先级）。 |
| `damon_pa_apply_scheme()` | 根据 DAMOS 策略动作（如 `PAGEOUT`、`LRU_PRIO`、`LRU_DEPRIO`）执行对应操作。 |
| `damon_pa_scheme_score()` | 为不同 DAMOS 动作返回评分（hot/cold），用于策略排序。 |
| `damon_pa_initcall()` | 模块初始化函数，注册 `DAMON_OPS_PADDR` 操作集。 |

### 关键数据结构

- **`struct damon_operations`**：定义了 DAMON 物理地址监控所需的一组回调函数，ID 为 `DAMON_OPS_PADDR`。
- **`struct rmap_walk_control`**：用于遍历 folio 的反向映射（rmap），以访问其所有虚拟地址映射。

## 3. 关键实现

### 访问检测机制
- **预老化（Prepare）**：在每次采样周期开始前，随机选取区域内的一个物理地址，通过 `damon_pa_mkold()` 清除其所有虚拟映射的 young 位，并设置 folio idle 标志。
- **访问检查（Check）**：在周期结束时，通过 `damon_pa_young()` 检查该地址是否被访问。检查逻辑包括：
  - PTE/PMD 的 `young` 位是否置位；
  - folio 的 `idle` 标志是否未设置；
  - 通过 `mmu_notifier_test_young()` 查询硬件或架构特定的访问状态。
- **结果缓存优化**：`__damon_pa_check_access()` 缓存上一次检查的物理地址、folio 大小和访问结果，若当前采样地址落在同一 folio 内，则复用结果，避免重复遍历 rmap。

### 反向映射遍历
- 使用 `page_vma_mapped_walk()` 遍历 folio 的所有 VMA 映射，分别处理 PTE 和 PMD（透明大页）层级。
- 对于非匿名页或 KSM 页，需加 folio 锁以保证 rmap 遍历时的一致性。

### DAMOS 策略执行
- **Pageout**：隔离 folio 到临时链表，调用 `reclaim_pages()` 回收。
- **LRU 调整**：通过 `folio_mark_accessed()`（提升到 active LRU）或 `folio_deactivate()`（降级到 inactive LRU）调整页面优先级。
- **过滤机制**：支持按匿名页类型或 memcg ID 过滤目标页面，确保策略仅作用于指定内存。

### 透明大页（THP）支持
- 在 `__damon_pa_young()` 中，通过 `#ifdef CONFIG_TRANSPARENT_HUGEPAGE` 条件编译支持 PMD 层级的 young 位检查，若未启用 THP 则触发 `WARN_ON_ONCE(1)`。

## 4. 依赖关系

- **内核头文件依赖**：
  - `<linux/page_idle.h>`：提供 `folio_set_idle()`、`folio_test_idle()` 等接口。
  - `<linux/rmap.h>`：提供反向映射遍历功能（`rmap_walk`、`page_vma_mapped_walk`）。
  - `<linux/mmu_notifier.h>`：用于跨架构的 young 状态查询。
  - `<linux/swap.h>`：提供 `reclaim_pages()` 用于页面回收。
  - `<linux/pagemap.h>`：提供 folio 相关操作。
- **DAMON 内部依赖**：
  - `../internal.h`：包含 DAMON 核心数据结构和辅助函数（如 `damon_get_folio()`、`damon_rand()`）。
  - `"ops-common.h"`：提供通用操作辅助函数（如 `damon_ptep_mkold()`、`damon_pmdp_mkold()`）。
- **配置依赖**：透明大页（`CONFIG_TRANSPARENT_HUGEPAGE`）为可选依赖，影响 PMD 层级访问检查。

## 5. 使用场景

- **物理内存监控**：当系统需要监控物理内存的访问热度（而非进程虚拟地址空间）时使用，例如 NUMA 节点内存分析、设备内存（如 CXL）监控。
- **内存回收优化**：结合 DAMOS 策略，自动识别冷物理页并执行 pageout 或 LRU 降级，提升内存利用率。
- **内核内存管理研究**：为内存子系统提供低开销的物理页访问行为数据，用于开发新的内存管理算法。
- **容器/虚拟化环境**：通过 memcg 过滤器，对特定 cgroup 的物理内存使用情况进行监控和调控。

该模块通过 `subsys_initcall` 在内核启动早期注册，可通过 DAMON 用户接口（如 debugfs 或 tracefs）激活 `paddr` 操作模式。