# page_table_check.c

> 自动生成时间: 2025-12-07 17:06:25
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `page_table_check.c`

---

# page_table_check.c 技术文档

## 1. 文件概述

`page_table_check.c` 是 Linux 内核中用于检测和验证页表映射一致性的调试模块。该模块通过跟踪每个物理页面被匿名（anonymous）或文件（file-backed）方式映射的次数，确保页表操作（如设置或清除 PTE/PMD/PUD 条目）不会破坏内存管理的基本不变量。当检测到不一致（如计数器为负、混合映射类型等）时，会触发 `BUG_ON()` 导致内核崩溃，从而帮助开发者及早发现页表管理中的逻辑错误。

该功能默认可通过 `CONFIG_PAGE_TABLE_CHECK_ENFORCED` 配置选项启用，并支持通过内核启动参数 `page_table_check=0/1` 动态控制。

## 2. 核心功能

### 数据结构

- **`struct page_table_check`**  
  每个物理页面关联的检查状态结构体，包含两个原子计数器：
  - `anon_map_count`：记录该页面被匿名映射的次数。
  - `file_map_count`：记录该页面被文件映射的次数。

- **`page_table_check_ops`**  
  `struct page_ext_operations` 类型的全局变量，用于将 `page_table_check` 结构集成到内核的 `page_ext` 扩展机制中，定义了大小、初始化条件、初始化函数等。

- **`page_table_check_disabled`**  
  静态分支键（`static_key`），用于在运行时高效地启用/禁用检查逻辑。默认为 `true`（即禁用），若启用则调用 `static_branch_disable()` 关闭该键以激活检查。

### 主要函数

- **`__page_table_check_zero()`**  
  在页面分配或释放时调用，验证指定 order 范围内的所有页面的映射计数器均为零。

- **`__page_table_check_pte_clear()` / `__page_table_check_pmd_clear()` / `__page_table_check_pud_clear()`**  
  在清除用户页表项（PTE/PMD/PUD）时调用，减少对应物理页面的映射计数，并验证类型一致性。

- **`__page_table_check_ptes_set()` / `__page_table_check_pmd_set()` / `__page_table_check_pud_set()`**  
  在设置新的用户页表项时调用，先清除旧项（如有），再增加新项对应页面的映射计数，并进行类型和写权限检查。

- **`__page_table_check_pte_clear_range()`**  
  在释放整个 PMD 对应的 PTE 表时，遍历并清除所有 PTE 条目对应的页面计数。

- **`page_table_check_pte_flags()` / `page_table_check_pmd_flags()`**  
  检查页表项中的特殊标志位（如 `uffd_wp`）与写权限的一致性，防止非法组合。

## 3. 关键实现

### 映射类型互斥性检查
- 每个物理页面只能属于**匿名页面**（如堆、栈、匿名 mmap）或**文件页面**（如文件 mmap、page cache），不能同时被两种方式映射。
- 在 `page_table_check_set/clear` 中，通过 `PageAnon(page)` 判断页面类型，并确保另一类型的计数器始终为 0（`BUG_ON(atomic_read(...))`）。

### 计数器边界检查
- **清除操作**：调用 `atomic_dec_return()` 后检查结果是否 `< 0`，防止过度解除映射。
- **设置操作**：
  - 对于**文件页面**：仅检查计数器非负（实际应始终 ≥0）。
  - 对于**匿名页面**：若为**可写映射**（`rw == true`），则限制 `anon_map_count` 最多为 1（即不允许同一匿名页面被多个进程以可写方式共享，除非是 COW 前的只读共享）。

### 用户地址空间过滤
- 所有检查函数均跳过 `init_mm`（内核地址空间），仅处理用户空间页表操作。
- 使用 `pte_user_accessible_page()` 等宏判断页表项是否指向用户可访问的普通内存页面（排除特殊条目如 swap、hwpoison 等）。

### Swap 条目写权限检查
- 在设置包含 `uffd_wp`（用户故障委托写保护）标志的 swap PTE/PMD 时，通过 `swap_cached_writable()` 检查底层 swap 条目是否缓存了“可写”信息，若存在则报 `WARN_ON_ONCE`，因为 `uffd_wp` 要求页面不可写。

### Page Extension 集成
- 利用内核的 `page_ext` 机制为每个 `struct page` 附加 `page_table_check` 数据，避免修改核心 `struct page`。
- 通过 `page_ext_get/put` 和 `page_ext_next` 安全地访问连续页面的扩展数据。

## 4. 依赖关系

- **`<linux/page_ext.h>`**：通过 `page_ext_operations` 机制集成到页面扩展框架。
- **`<linux/mm.h>`**：使用核心内存管理 API，如 `pfn_to_page()`、`PageAnon()`、`PageSlab()` 等。
- **`<linux/swap.h>` / `<linux/swapops.h>`**：处理 swap 页表项及其标志位（如 `is_swap_pte()`、`pte_to_swp_entry()`）。
- **`<linux/kstrtox.h>`**：解析内核启动参数。
- **页表操作宏**：依赖架构相关的页表操作宏（如 `pte_pfn()`、`pmd_write()` 等），这些由各架构的 `pgtable.h` 提供。
- **`CONFIG_PAGE_TABLE_CHECK_ENFORCED`**：编译时配置选项，决定默认是否启用检查。

## 5. 使用场景

- **内核开发与调试**：在开发新内存管理功能（如新页表操作、COW 优化、大页处理）时，启用此模块可捕获页表操作中的逻辑错误。
- **回归测试**：作为内核测试套件的一部分，确保页表修改不会破坏映射一致性。
- **安全加固**（潜在）：虽然主要用于调试，但其强制的映射类型互斥性也可防止某些内存破坏漏洞的利用。
- **启动参数控制**：系统管理员可在启动时通过 `page_table_check=1` 临时启用检查以诊断问题，或通过 `=0` 在已知兼容性问题的系统上禁用。