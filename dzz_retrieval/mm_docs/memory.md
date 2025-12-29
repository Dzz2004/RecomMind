# memory.c

> 自动生成时间: 2025-12-07 16:42:16
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `memory.c`

---

# memory.c 技术文档

## 1. 文件概述

`memory.c` 是 Linux 内核内存管理子系统（MM）的核心实现文件之一，位于 `mm/` 目录下。该文件主要负责虚拟内存到物理内存的映射管理、缺页异常（page fault）处理、页表结构的分配与释放、以及与用户空间内存操作相关的底层机制。它实现了按需加载（demand-loading）、共享页面、交换（swapping）等关键虚拟内存功能，并为多级页表架构（如 x86-64 的四级页表）提供通用支持。

## 2. 核心功能

### 主要全局变量
- `high_memory`：指向直接映射区域（ZONE_NORMAL）的上界，用于区分低端内存和高端内存。
- `randomize_va_space`：控制地址空间布局随机化（ASLR）策略的级别（0=关闭，1=部分启用，2=完全启用）。
- `zero_pfn`：指向全零物理页的页帧号（PFN），用于高效实现只读零页映射。
- `max_mapnr` 和 `mem_map`（非 NUMA 配置下）：分别表示最大页帧号和全局页描述符数组。
- `highest_memmap_pfn`：记录系统中最高的已注册页帧号。

### 关键函数
- `free_pgd_range()`：释放指定虚拟地址范围内的用户级页表结构（从 PGD 到 PTE）。
- `free_p4d_range()`, `free_pud_range()`, `free_pmd_range()`, `free_pte_range()`：递归释放各级页表项及其对应的页表页。
- `do_fault()`：处理基于文件映射的缺页异常。
- `do_anonymous_page()`：处理匿名映射（如堆、栈）的缺页异常。
- `vmf_orig_pte_uffd_wp()`：判断原始 PTE 是否为 userfaultfd 写保护标记。
- `init_zero_pfn()`：早期初始化 `zero_pfn`。
- `mm_trace_rss_stat()`：触发 RSS（Resident Set Size）统计的跟踪事件。

### 内联辅助函数
- `arch_wants_old_prefaulted_pte()`：允许架构层决定预取页表项是否应标记为“old”以优化访问位更新开销。

## 3. 关键实现

### 页表释放机制
- 采用自顶向下（PGD → P4D → PUD → PMD → PTE）的递归方式释放页表。
- 每级释放函数（如 `free_pmd_range`）遍历地址范围内的页表项：
  - 跳过空或无效项（`pmd_none_or_clear_bad`）。
  - 递归释放下一级页表。
  - 在满足对齐和边界条件（`floor`/`ceiling`）时，释放当前级页表页并更新 MMU gather 结构中的计数器（如 `mm_dec_nr_ptes`）。
- 使用 `mmu_gather` 机制批量延迟 TLB 刷新和页表页释放，提升性能。

### 缺页处理框架
- 提供 `do_fault` 和 `do_anonymous_page` 作为缺页处理的核心入口，分别处理文件映射和匿名映射。
- 支持 `userfaultfd` 写保护机制，通过 `vmf_orig_pte_uffd_wp` 检测特殊 PTE 标记。

### 地址空间随机化（ASLR）
- 通过 `randomize_va_space` 控制栈、mmap 区域、brk 等的随机化行为。
- 支持内核启动参数 `norandmaps` 完全禁用 ASLR。
- 兼容旧版 libc5 二进制（`CONFIG_COMPAT_BRK`），此时 brk 区域不参与随机化。

### 零页优化
- `zero_pfn` 指向一个全局只读的全零物理页，用于高效实现对未初始化数据段（如 `.bss`）或显式映射 `/dev/zero` 的只读访问，避免每次分配新页。

### 架构适配
- 通过 `arch_wants_old_prefaulted_pte` 允许特定架构优化页表项的“young/old”状态设置。
- 依赖 `asm/mmu_context.h`、`asm/pgalloc.h`、`asm/tlb.h` 等架构相关头文件实现底层操作。

## 4. 依赖关系

### 内核头文件依赖
- **内存管理核心**：`<linux/mm.h>`, `<linux/mman.h>`, `<linux/swap.h>`, `<linux/pagemap.h>`, `<linux/memcontrol.h>`
- **进程与调度**：`<linux/sched/mm.h>`, `<linux/sched/task.h>`, `<linux/delayacct.h>`
- **NUMA 与迁移**：`<linux/numa.h>`, `<linux/migrate.h>`, `<linux/sched/numa_balancing.h>`
- **特殊内存类型**：`<linux/hugetlb.h>`, `<linux/highmem.h>`, `<linux/dax.h>`, `<linux/zswap.h>`
- **调试与跟踪**：`<trace/events/kmem.h>`, `<linux/debugfs.h>`, `<linux/oom.h>`
- **架构相关**：`<asm/io.h>`, `<asm/mmu_context.h>`, `<asm/pgalloc.h>`, `<asm/tlbflush.h>`

### 内部模块依赖
- `internal.h`：包含 MM 子系统内部通用定义。
- `swap.h`：交换子系统接口。
- `pgalloc-track.h`：页表分配跟踪（用于调试）。

## 5. 使用场景

- **进程创建与退出**：在 `fork()` 和进程终止时，通过 `free_pgd_range` 释放整个地址空间的页表。
- **内存映射操作**：`mmap()`、`munmap()`、`mremap()` 等系统调用触发页表的建立或释放。
- **缺页异常处理**：当 CPU 访问未映射或换出的虚拟地址时，由体系结构相关的缺页处理程序调用 `do_fault` 或 `do_anonymous_page`。
- **内存回收**：在内存压力下，kswapd 或直接回收路径可能触发页表清理。
- **用户态内存监控**：`userfaultfd` 机制利用 `vmf_orig_pte_uffd_wp` 实现用户空间对缺页事件的精细控制。
- **内核初始化**：早期调用 `init_zero_pfn` 设置零页，`paging_init()`（架构相关）初始化 `high_memory` 和 `ZERO_PAGE`。