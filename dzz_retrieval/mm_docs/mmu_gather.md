# mmu_gather.c

> 自动生成时间: 2025-12-07 16:52:52
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `mmu_gather.c`

---

# mmu_gather.c 技术文档

## 1. 文件概述

`mmu_gather.c` 是 Linux 内核内存管理子系统中的关键组件，负责在页表项（PTE）或更高层级页表被撤销映射（unmap）后，高效地批量释放对应的物理页面和页表结构。该文件实现了 **MMU gather** 机制，用于延迟并批量处理 TLB（Translation Lookaside Buffer）刷新、反向映射（rmap）清理以及页面回收操作，以减少频繁的 TLB 刷新开销和锁竞争，提升性能。

当内核需要释放大量虚拟内存区域（如进程退出、mmap 区域销毁）时，不会立即释放每个页面，而是先将待释放的页面收集到 `mmu_gather` 结构中，待累积到一定数量或显式调用 flush 操作时，再统一执行 TLB 刷新、rmap 解除和页面释放。

## 2. 核心功能

### 主要函数

- `tlb_next_batch(struct mmu_gather *tlb)`  
  分配新的批处理批次（batch），用于扩展可收集的页面数量上限。

- `tlb_flush_rmaps(struct mmu_gather *tlb, struct vm_area_struct *vma)`  
  （仅在 SMP 下）处理延迟的反向映射（delayed rmap）移除操作，在 TLB 刷新后调用。

- `__tlb_batch_free_encoded_pages(struct mmu_gather_batch *batch)`  
  批量释放编码后的页面（包括普通页面和 swap 缓存），支持防软锁定（soft lockup）的调度点。

- `tlb_batch_pages_flush(struct mmu_gather *tlb)`  
  遍历所有批次，释放其中收集的所有页面。

- `tlb_batch_list_free(struct mmu_gather *tlb)`  
  释放动态分配的批次内存（非本地批次）。

- `__tlb_remove_folio_pages_size(...)` / `__tlb_remove_folio_pages(...)` / `__tlb_remove_page_size(...)`  
  将页面（单页或多页 folio）加入当前 gather 批次，支持延迟 rmap 和不同页面大小。

- `tlb_remove_table_sync_one(void)`  
  （RCU 表释放模式下）触发 IPI 同步，确保软件页表遍历安全。

- `tlb_remove_table_rcu(struct rcu_head *head)`  
  RCU 回调函数，用于异步释放页表结构。

- `tlb_remove_table_free(struct mmu_table_batch *batch)`  
  将页表批次提交给 RCU 机制进行延迟释放。

### 关键数据结构

- `struct mmu_gather`  
  核心上下文结构，包含本地批次（`local`）、当前活跃批次（`active`）、批次计数、延迟 rmap 标志等。

- `struct mmu_gather_batch`  
  页面批次结构，包含指向编码页面指针数组、当前数量（`nr`）、最大容量（`max`）及下一个批次指针。

- `struct mmu_table_batch`  
  页表结构批次，用于批量收集待释放的页表（如 PMD、PUD 等）。

- `encoded_page` 相关机制  
  使用指针低位编码额外信息（如是否延迟 rmap、是否后跟 nr_pages 字段），节省内存并提高缓存效率。

## 3. 关键实现

### 批处理与动态扩展
- 默认使用栈上或局部存储的 `local` 批次（避免内存分配）。
- 当 `local` 批次满时，通过 `__get_free_page()` 动态分配新批次（最多 `MAX_GATHER_BATCH_COUNT` 个）。
- `tlb_next_batch()` 在存在延迟 rmap 时限制扩展，确保语义正确性。

### 延迟反向映射（Delayed Rmap）
- 当页面仍被其他 VMA 引用但当前 VMA 正在 unmap 时，不立即调用 `folio_remove_rmap_ptes()`，而是标记 `ENCODED_PAGE_BIT_DELAY_RMAP`。
- 在 `tlb_flush_rmaps()` 中统一处理，确保在 TLB 刷新**之后**才解除 rmap，防止 CPU 访问已释放页面。

### 安全释放与防软锁定
- 页面释放循环中每处理最多 `MAX_NR_FOLIOS_PER_FREE`（512）个 folio 调用 `cond_resched()`，避免在非抢占内核中长时间占用 CPU。
- 若启用 `page_poisoning` 或 `init_on_free`，则按实际内存大小（而非 folio 数量）限制单次释放量，因初始化开销与内存大小成正比。

### 页表结构的安全释放（RCU 模式）
- 在支持软件页表遍历（如 `gup_fast`）的架构上，页表释放需与遍历操作同步。
- 使用 `call_rcu()` 延迟释放页表，配合 `smp_call_function()` 触发 IPI 确保所有 CPU 完成 TLB 刷新后再释放内存。
- 若 RCU 批次分配失败，则回退到即时释放（代码未完整展示，但注释提及）。

### 编码页面指针
- 利用页面指针对齐特性（通常低 2~3 位为 0），将标志位（如 `DELAY_RMAP`、`NR_PAGES_NEXT`）存储在指针低位。
- 支持多页 folio：若 `nr_pages > 1`，则连续两个条目分别存储页面指针（带标志）和页数。

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm_types.h>`、`<linux/mm_inline.h>`、`<linux/rmap.h>` 等，与 folio、page、VMA 管理紧密集成。
- **TLB 管理**：通过 `<asm/tlb.h>` 与架构相关 TLB 刷新接口交互。
- **RCU 机制**：在 `CONFIG_MMU_GATHER_RCU_TABLE_FREE` 下依赖 `<linux/rcupdate.h>` 实现页表安全释放。
- **SMP 支持**：`tlb_flush_rmaps` 和页表同步仅在 `CONFIG_SMP` 下编译。
- **高阶内存与交换**：使用 `<linux/highmem.h>`、`<linux/swap.h>` 处理高端内存和 swap 缓存释放。
- **内存分配器**：通过 `__get_free_page(GFP_NOWAIT)` 动态分配批次内存。

## 5. 使用场景

- **进程退出（exit_mmap）**：释放整个地址空间时，大量页面通过 mmu_gather 批量回收。
- **munmap 系统调用**：解除大块内存映射时，避免逐页 TLB 刷新。
- **内存回收（reclaim）**：在直接回收或 kswapd 中撤销映射时使用。
- **透明大页（THP）拆分**：拆分大页时需撤销多个 PTE 映射并释放 sub-page。
- **页表收缩（shrink_page_list）**：在页面回收路径中解除映射。
- **KSM（Kernel Samepage Merging）**：合并或取消合并页面时更新 rmap。
- **页表层级释放**：当上层页表（如 PGD/P4D/PUD/PMD）不再被引用时，通过 `tlb_remove_table` 机制安全释放。