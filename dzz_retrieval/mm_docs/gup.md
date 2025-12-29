# gup.c

> 自动生成时间: 2025-12-07 16:02:31
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `gup.c`

---

# gup.c 技术文档

## 1. 文件概述

`gup.c` 是 Linux 内核中 **get_user_pages (GUP)** 子系统的核心实现文件之一，主要负责用户页的**获取、固定（pinning）和释放**操作。该文件提供了对页面进行引用计数管理的底层机制，特别支持通过 `FOLL_PIN` 标志将用户页“钉住”（pinned），以防止其被换出或迁移，这对 DMA、RDMA、DAX 等需要长期稳定物理内存访问的子系统至关重要。此外，文件还实现了与 folio（新一代页面抽象）兼容的 pin/unpin 接口，并包含调试和一致性校验逻辑。

## 2. 核心功能

### 主要数据结构
- `struct follow_page_context`：用于在页遍历过程中传递上下文信息，包含设备页映射（`pgmap`）和页掩码（`page_mask`）。

### 主要函数
- `sanity_check_pinned_pages()`：在调试模式下验证已 pinned 的匿名页是否仍保持独占映射状态，防止共享匿名页被错误 pin。
- `try_get_folio()`：尝试安全地获取一个 folio 的引用，处理 folio 在引用增加过程中可能被拆分的竞态条件。
- `gup_put_folio()`：根据标志（`FOLL_PIN` 或普通引用）释放 folio 的引用，更新 pin 计数和节点统计。
- `try_grab_folio()`：根据 `FOLL_GET` 或 `FOLL_PIN` 标志，以不同方式增加 folio 的引用计数；是 GUP 慢路径中的关键函数。
- `unpin_user_page()`：释放通过 `pin_user_pages*()` 获取的单个 pinned 用户页。
- `unpin_folio()`：释放通过 `memfd_pin_folios()` 等接口获取的单个 pinned folio。
- `folio_add_pin()`：为已 pinned 的 folio 增加额外的 pin 引用。
- `gup_folio_range_next()` / `gup_folio_next()`：辅助函数，用于在连续页范围或页数组中按 folio 粒度进行迭代。
- `unpin_user_pages_dirty_lock()`（部分实现）：批量释放 pinned 用户页，并可选地标记为 dirty。

## 3. 关键实现

### Pinning 机制
- **`FOLL_PIN` vs `FOLL_GET`**：  
  - `FOLL_GET` 使用标准页引用计数（`_refcount`）。  
  - `FOLL_PIN` 采用特殊计数策略：  
    - 对于普通页（非大页），引用计数增加 `GUP_PIN_COUNTING_BIAS`（通常为 256），以区分普通引用和 pin 引用。  
    - 对于大页（THP/hugetlb），除增加 `_refcount` 外，还使用独立的 `_pincount` 原子变量记录 pin 次数。  
  - 零页（zero page）不参与 pin 计数，因其内容恒定且广泛共享。

### 安全性与一致性
- **`try_get_folio()` 的重试机制**：在增加引用前获取 folio 指针，增加后再次验证页是否仍属于该 folio，防止 folio 拆分导致引用错乱。
- **匿名页独占性检查**：`sanity_check_pinned_pages()` 确保被 pin 的匿名页（包括 THP）在 pin 期间保持 `PageAnonExclusive` 状态，避免因 COW 导致的数据不一致。
- **PCI P2P DMA 限制**：`try_grab_folio()` 拒绝 pin 非 P2P 标记的 PCI P2P DMA 页，返回 `-EREMOTEIO`。

### 统计与跟踪
- 使用 `node_stat_mod_folio()` 更新 per-node 的 `NR_FOLL_PIN_ACQUIRED` 和 `NR_FOLL_PIN_RELEASED` 计数器，便于监控 pinned 页的使用情况。

### Folio 抽象适配
- 所有核心函数均基于 `struct folio` 实现，兼容复合页（compound pages）和透明大页（THP），通过 `folio_test_large()` 区分处理逻辑。

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`、`<linux/pagemap.h>`、`<linux/rmap.h>`、`<linux/swap.h>` 等，与页表遍历、反向映射、交换子系统紧密集成。
- **大页支持**：通过 `<linux/hugetlb.h>` 和 THP 相关接口处理大页 pinning。
- **设备内存**：依赖 `<linux/memremap.h>` 和 `dev_pagemap` 处理持久内存（PMEM）和设备内存映射。
- **特殊内存类型**：支持 `memfd`（`<linux/memfd.h>`）、`secretmem`（`<linux/secretmem.h>`）等特殊内存区域的 pinning。
- **体系结构相关**：包含 `<asm/mmu_context.h>` 和 `<asm/tlbflush.h>`，用于 TLB 刷新和地址空间管理。
- **内部头文件**：包含 `"internal.h"`，访问 MM 子系统内部函数和定义。

## 5. 使用场景

- **DMA/RDMA 操作**：驱动或 RDMA 子系统调用 `pin_user_pages*()` 固定用户缓冲区，确保 DMA 期间物理页不被换出，完成后通过 `unpin_user_page(s)` 释放。
- **DAX（Direct Access）文件系统**：在持久内存上直接访问文件数据时，需 pin 相关页以保证地址稳定性。
- **内核用户态交互**：如 KVM、VFIO 等虚拟化技术，需 pin 用户态内存供硬件直接访问。
- **内存锁定服务**：`mlock()` 系统调用的底层实现可能间接使用 GUP 机制。
- **调试与监控**：通过 `NR_FOLL_PIN_*` 统计项监控 pinned 页数量，辅助性能分析和内存泄漏检测。