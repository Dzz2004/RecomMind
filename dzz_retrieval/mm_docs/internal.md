# internal.h

> 自动生成时间: 2025-12-07 16:09:45
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `internal.h`

---

# `internal.h` 技术文档

## 1. 文件概述

`internal.h` 是 Linux 内核内存管理子系统（`mm/`）的内部头文件，定义了仅供内存管理模块内部使用的宏、辅助函数、数据结构和常量。该文件不对外暴露接口，主要用于协调页分配、映射、回收、大页（hugetlb/folio）处理、VMA 操作等核心内存管理逻辑，并提供调试与一致性保障机制。

## 2. 核心功能

### 宏定义
- **GFP 掩码相关**：
  - `GFP_RECLAIM_MASK`：仅影响水位检查和回收行为的 GFP 标志集合。
  - `GFP_BOOT_MASK`：早期启动阶段允许使用的 GFP 标志。
  - `GFP_CONSTRAINT_MASK`：控制 cpuset 和节点放置约束的标志。
  - `GFP_SLAB_BUG_MASK`：用于检测错误地将 slab 不支持的标志（如 `__GFP_HIGHMEM`）传递给 slab 分配器。
- **调试与警告**：
  - `WARN_ON_ONCE_GFP(cond, gfp)`：带 `__GFP_NOWARN` 控制的单次警告宏。
- **映射状态标志**：
  - `SHOW_MEM_FILTER_NODES`：用于 `__show_mem()` 和 `show_free_areas()` 的节点过滤标志。
- **folio 映射计数**：
  - `ENTIRELY_MAPPED` 与 `FOLIO_PAGES_MAPPED`：用于区分 folio 是否被整体映射或部分页面被映射。

### 内联函数
- `folio_nr_pages_mapped()`：获取 folio 中被单独映射的页面数量（排除整体映射计数）。
- `folio_swap()`：根据 folio 和一个 swap entry 计算其所属 folio 的起始 swap entry。
- `folio_raw_mapping()`：安全提取 folio 的原始 mapping 指针（清除标志位）。
- `mmap_file()`：安全调用文件的 `mmap` 钩子，失败时安装 dummy VMA 操作以防止后续误用。
- `vma_close()`：安全关闭 VMA，调用 close 钩子后替换为 dummy 操作集。
- `folio_pte_batch()`（仅在 `CONFIG_MMU` 下）：检测连续 PTE 是否构成一个“PTE 批处理”（即连续映射同一 folio 的多个页面）。
- `__pte_batch_clear_ignored()`：根据标志清除 PTE 中可忽略的位（如 dirty、soft-dirty），用于 PTE 批处理比较。

### 函数声明
- `page_writeback_init()`：初始化页回写子系统。

### 类型定义
- `fpb_t`：`folio_pte_batch()` 使用的标志类型（强类型位掩码）。
- `FPB_IGNORE_DIRTY` / `FPB_IGNORE_SOFT_DIRTY`：控制 PTE 批处理比较时忽略哪些状态位。

## 3. 关键实现

### Folio 映射计数设计
- 使用 `atomic_t _nr_pages_mapped` 字段的低 23 位（`FOLIO_PAGES_MAPPED = 0x7FFFFF`）记录被单独映射的页面数。
- 最高位（`ENTIRELY_MAPPED = 0x800000`）保留用于标记整个 folio 被一次性映射（如通过 PMD/PUD 映射大页），避免与逐页映射计数冲突。
- 即使 hugetlb 当前未使用该字段，此设计也为未来扩展预留空间。

### 安全 VMA 钩子调用机制
- `mmap_file()` 和 `vma_close()` 在操作失败或完成关闭后，立即将 `vma->vm_ops` 替换为 `&vma_dummy_vm_ops`（空操作集）。
- 此设计防止 VMA 处于不一致状态时被意外调用其他钩子，提升内核健壮性。

### PTE 批处理检测（`folio_pte_batch`）
- 目标：高效识别连续 PTE 是否映射同一 folio 的连续物理页。
- 实现要点：
  - 使用 `pte_batch_hint()` 获取硬件或架构建议的批处理步长（如 THP 场景下为 512）。
  - 通过 `__pte_batch_clear_ignored()` 标准化 PTE（清除可忽略位），再用 `pte_same()` 比较。
  - 动态推进 `expected_pte` 的 PFN，确保连续性。
  - 支持通过指针参数返回非首项 PTE 的 writable/young/dirty 状态。
  - 严格限制扫描范围不超过单个页表（由 `max_nr` 保证）。

### GFP 标志分组策略
- 将 GFP 标志按用途分类（回收行为、启动约束、放置约束、slab 兼容性），便于在不同内存分配路径中精确控制行为，避免标志误用。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/fs.h>`：文件和 VMA 相关操作。
  - `<linux/mm.h>`、`<linux/pagemap.h>`、`<linux/rmap.h>`、`<linux/swap.h>`、`<linux/swapops.h>`：核心内存管理、页缓存、反向映射、交换子系统。
  - `<linux/khugepaged.h>`：透明大页后台合并支持。
  - `<linux/tracepoint-defs.h>`：跟踪点定义。
- **内核配置依赖**：
  - `CONFIG_MMU`：决定是否编译 `folio_pte_batch` 等 MMU 相关功能。
- **模块依赖**：
  - 被 `mm/` 子目录下的多个源文件包含（如 `memory.c`, `mmap.c`, `swap.c`, `huge_memory.c` 等），作为内部实现细节共享。

## 5. 使用场景

- **内存分配路径**：在 `alloc_pages()` 等底层分配函数中，使用 `GFP_RECLAIM_MASK` 等掩码控制回收行为。
- **VMA 生命周期管理**：在 `do_mmap()` 和 `remove_vma()` 中调用 `mmap_file()` 和 `vma_close()` 安全处理文件映射。
- **大页（Folio/HugeTLB/THP）处理**：
  - 使用 `folio_nr_pages_mapped()` 跟踪部分映射状态。
  - `folio_pte_batch()` 用于优化大页的 PTE 遍历（如缺页处理、页迁移、内存规整）。
- **页回收与回写**：`page_writeback_init()` 在系统初始化时设置回写参数。
- **调试与诊断**：`WARN_ON_ONCE_GFP` 用于条件性报告内存分配异常；`SHOW_MEM_FILTER_NODES` 控制内存状态输出。
- **交换子系统**：`folio_swap()` 辅助在 folio 粒度上管理 swap entry。