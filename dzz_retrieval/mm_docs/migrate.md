# migrate.c

> 自动生成时间: 2025-12-07 16:46:52
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `migrate.c`

---

# migrate.c 技术文档

## 1. 文件概述

`migrate.c` 是 Linux 内核内存管理子系统中实现**页面迁移（Page Migration）**功能的核心文件。该机制最初为支持内存热插拔（Memory Hotplug）而设计，现广泛应用于内存紧缩（Compaction）、NUMA 负载均衡、透明大页（THP）整理、内存碎片整理以及用户空间发起的迁移请求等场景。其核心目标是在不中断应用程序的前提下，将物理页从一个位置安全地迁移到另一个位置，并更新所有对该页的引用。

## 2. 核心功能

### 主要函数
- `isolate_movable_page()`：尝试隔离一个可移动页面，供迁移使用。
- `putback_movable_pages()`：将之前隔离但未成功迁移的页面放回其原始 LRU 列表或由驱动程序管理。
- `isolate_folio_to_list()`：将指定 folio 隔离并加入到给定列表中，支持普通页、可移动页和巨页。
- `remove_migration_pte()`：在迁移完成后，将页表项（PTE/PMD）中的迁移交换项恢复为指向新物理页的有效页表项。

### 关键数据结构与接口
- `movable_operations`：定义了可移动页面（如 balloon、ZSMALLOC 等）的驱动回调接口，包括 `isolate_page()` 和 `putback_page()`。
- `isolate_mode_t`：隔离模式标志，用于控制隔离行为（如 `ISOLATE_UNEVICTABLE`）。
- 迁移交换项（Migration Swap Entry）：一种特殊的 swap entry，用于在页表中标记正在迁移的页面，保留访问权限、脏位、软脏位等元信息。

## 3. 关键实现

### 页面隔离机制
- **可移动页识别**：通过 `__folio_test_movable()` 检查 folio 是否属于可移动类型（如 balloon、ZSMALLOC），这类页面不由标准 LRU 管理。
- **并发安全**：使用 `folio_trylock()` 获取 folio 锁，防止在释放或迁移过程中被重复隔离。通过内存屏障（`smp_rmb()`）确保与 SLAB 分配器的同步。
- **隔离标记**：成功隔离后设置 `PG_isolated` 标志，防止其他路径误操作。

### 迁移 PTE 处理
- **元信息保留**：在 `remove_migration_pte()` 中，从旧的迁移 PTE 中提取并重建新 PTE 的属性：
  - 软脏位（soft-dirty）
  - 访问/脏位（young/dirty）
  - 写权限（writable）
  - 用户态缺页调试写保护（UFFD-WP）
- **设备私有内存支持**：对 `device_private` 页面（如 GPU 内存），生成特殊的设备私有交换项而非普通 PTE。
- **巨页支持**：通过 `CONFIG_ARCH_ENABLE_THP_MIGRATION` 支持 PMD 级别的 THP 迁移，调用 `remove_migration_pmd()`。

### 回滚与清理
- `putback_movable_pages()` 遍历隔离列表，根据页面类型执行不同回滚逻辑：
  - 巨页：调用 `folio_putback_active_hugetlb()`
  - 可移动页：调用驱动注册的 `putback_page()` 回调
  - 普通 LRU 页：减少 `NR_ISOLATED_ANON/FILE` 统计并放回 LRU

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`, `<linux/pagemap.h>`, `<linux/rmap.h>`, `<linux/swap.h>` 等进行页表操作、反向映射、LRU 管理。
- **特殊内存类型**：
  - HugeTLB：通过 `hugetlb.h` 和 `hugetlb_cgroup.h` 支持巨页迁移。
  - KSM：与内核同页合并模块交互。
  - Balloon：通过 `balloon_compaction.h` 支持 virtio-balloon 内存回收。
  - Device Private：支持异构内存架构（如 GPU）。
- **系统设施**：依赖 CPUSET、内存策略（mempolicy）、OOM killer、compaction、userfaultfd 等子系统协同工作。
- **架构支持**：包含 `asm/tlbflush.h` 用于 TLB 刷新，`CONFIG_ARCH_ENABLE_THP_MIGRATION` 提供架构级 THP 迁移支持。

## 5. 使用场景

- **内存紧缩（Compaction）**：在分配高阶内存失败时，通过迁移页面整理出连续物理内存。
- **NUMA Balancing**：将进程页面迁移到其运行 CPU 所属的本地 NUMA 节点，提升性能。
- **内存热移除（Memory Hotplug）**：在移除物理内存前，将其上的活跃页面迁移到其他节点。
- **用户空间迁移**：通过 `migrate_pages()` 系统调用，允许特权进程主动迁移指定进程的页面。
- **透明大页（THP）整理**：合并小页为 THP 或拆分 THP 时涉及页面迁移。
- **内存 Tiering**：在异构内存系统（如 PMEM + DRAM）中，根据访问热度迁移页面。