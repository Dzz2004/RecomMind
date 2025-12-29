# mlock.c

> 自动生成时间: 2025-12-07 16:49:19
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `mlock.c`

---

# mlock.c 技术文档

## 1. 文件概述

`mlock.c` 是 Linux 内核内存管理子系统中负责实现内存锁定（memory locking）功能的核心文件。该文件提供了对页（folio）级别的内存锁定/解锁操作，确保被锁定的内存不会被交换（swap）到磁盘，并将其标记为不可回收（unevictable）。此机制用于支持用户空间的 `mlock()`、`mlockall()` 等系统调用，以及内核中需要保证物理内存驻留的场景。

## 2. 核心功能

### 主要函数

- **`can_do_mlock(void)`**  
  判断当前进程是否具有执行内存锁定操作的权限，依据资源限制（`RLIMIT_MEMLOCK`）或 `CAP_IPC_LOCK` 能力。

- **`mlock_folio(struct folio *folio)`**  
  对已位于 LRU 链表（或临时脱离 LRU）的 folio 执行内存锁定操作。

- **`mlock_new_folio(struct folio *folio)`**  
  对新分配、尚未加入 LRU 的 folio 执行内存锁定。

- **`munlock_folio(struct folio *folio)`**  
  对 folio 执行内存解锁操作。

- **`mlock_drain_local(void)`**  
  处理当前 CPU 上累积的待处理 folio 批量操作。

- **`mlock_drain_remote(int cpu)`**  
  处理指定离线 CPU 上的待处理 folio 批量操作（用于 CPU 热插拔等场景）。

- **`need_mlock_drain(int cpu)`**  
  检查指定 CPU 是否有待处理的 mlock/munlock 批量操作。

### 内部辅助函数

- **`__mlock_folio()` / `__mlock_new_folio()` / `__munlock_folio()`**  
  实际执行 folio 状态变更、LRU 链表调整和统计计数的核心逻辑。

- **`mlock_folio_batch()`**  
  批量处理带有标志位的 folio，统一执行 mlock/munlock 操作。

### 数据结构

- **`struct mlock_fbatch`**  
  每 CPU 的 folio 批处理结构，包含一个 `local_lock_t` 锁和一个 `folio_batch`，用于延迟批量处理 mlock/munlock 请求，减少锁竞争和中断开销。

- **标志位宏定义**  
  - `LRU_FOLIO (0x1)`：表示 folio 已在 LRU 上，需调用 `__mlock_folio`
  - `NEW_FOLIO (0x2)`：表示 folio 为新分配，需调用 `__mlock_new_folio`

## 3. 关键实现

### 内存锁定状态管理
- 使用 `PG_mlocked` 页标志表示 folio 被用户或内核显式锁定。
- 使用 `PG_unevictable` 表示 folio 当前不可被回收，即使未被 mlock（如某些特殊内存区域）。
- 引入 `folio->mlock_count` 计数器，支持对同一 folio 的多次 mlock/munlock（引用计数语义）。

### 批处理与每 CPU 缓存
- 为避免频繁获取 LRU 锁和中断禁用，mlock/munlock 操作被暂存到 per-CPU 的 `mlock_fbatch` 中。
- 当 batch 满、遇到大页（THP）或 LRU 缓存被禁用时，立即触发批量处理。
- 使用指针低两位作为标志位（`LRU_FOLIO`/`NEW_FOLIO`），在单个 batch 中区分三种操作类型（mlock on LRU、mlock new、munlock）。

### LRU 链表操作
- 锁定 folio 时：若 folio 可回收，则从 active/inactive LRU 移除，清除 active 标志，设置 unevictable，并加入 unevictable LRU（逻辑上）。
- 解锁 folio 时：清除 `PG_mlocked`，若 `mlock_count` 归零且 folio 变为可回收，则清除 `PG_unevictable` 并移回普通 LRU。
- 所有 LRU 操作通过 `folio_lruvec_relock_irq()` 安全地在正确 zone 的 lruvec 上执行，并自动处理锁重入。

### 统计与监控
- 更新 `NR_MLOCK` zone 统计项，跟踪系统中被 mlock 的页数。
- 通过 `__count_vm_events()` 记录多种事件：
  - `UNEVICTABLE_PGMLOCKED` / `PGMUNLOCKED`：成功锁定/解锁
  - `UNEVICTABLE_PGCULLED`：因 mlock 被移入 unevictable
  - `UNEVICTABLE_PGRESCUED`：因 munlock 被救回可回收 LRU
  - `UNEVICTABLE_PGSTRANDED`：munlock 后仍 stranded 在 unevictable（需后续回收修复）

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`、`<linux/pagevec.h>`、`<linux/pagewalk.h>` 等提供的 folio、LRU、zone 管理接口。
- **交换子系统**：与 `<linux/swap.h>`、`<linux/swapops.h>` 协同，确保 mlocked 页不被交换。
- **反向映射（rmap）**：通过 `<linux/rmap.h>` 支持在页表遍历时识别 mlocked 区域。
- **内存控制组（memcg）**：集成 `<linux/memcontrol.h>`，支持 cgroup 级别的内存锁定统计。
- **大页支持**：通过 `<linux/hugetlb.h>` 处理透明大页（THP）的 mlock 行为。
- **安全与能力**：使用 `<linux/capability.h>` 和 `rlimit` 进行权限检查。
- **内部头文件**：包含 `"internal.h"` 获取 mm 子系统内部函数。

## 5. 使用场景

- **用户空间系统调用**：`sys_mlock()`、`sys_munlock()`、`sys_mlockall()` 等通过此模块实现对进程地址空间的内存锁定。
- **内核内存分配**：某些内核子系统（如 RDMA、DPDK 驱动）在分配关键内存时调用 `mlock_new_folio()` 确保物理页驻留。
- **页面故障处理**：在缺页异常路径中，若访问的 VMA 被标记为 `VM_LOCKED`，则新分配的页会通过 `mlock_new_folio()` 锁定。
- **内存回收（vmscan）**：回收器跳过 `PG_unevictable` 页，依赖此模块维护的 unevictable 状态。
- **CPU 热插拔**：当 CPU 离线时，通过 `mlock_drain_remote()` 清理其 per-CPU mlock batch，防止内存泄漏。
- **性能优化**：通过 per-CPU 批处理减少全局锁竞争，提升高并发 mlock/munlock 场景下的性能。