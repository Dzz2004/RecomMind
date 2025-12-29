# nommu.c

> 自动生成时间: 2025-12-07 16:57:15
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `nommu.c`

---

# nommu.c 技术文档

## 1. 文件概述

`nommu.c` 是 Linux 内核中为不支持内存管理单元（MMU）的 CPU 架构提供的内存管理替代实现。在无 MMU 的系统（如某些嵌入式处理器）中，无法使用虚拟内存机制，因此该文件提供了一套简化但功能完整的内存管理接口，以兼容标准内核 API。其核心目标是模拟 `mm/` 子系统中与虚拟内存相关的函数行为，同时避免依赖页表、地址转换等 MMU 特性。

## 2. 核心功能

### 主要全局变量
- `high_memory`：指向高内存区域起始地址（在 NOMMU 系统中通常为 NULL 或物理内存末尾）
- `mem_map`：物理页描述符数组的起始地址
- `max_mapnr`：系统中最大页帧号（PFN）
- `highest_memmap_pfn`：`mem_map` 中最高有效 PFN
- `sysctl_nr_trim_pages`：初始内存修剪阈值（用于释放未使用的内存块）
- `heap_stack_gap`：堆与栈之间的最小间隙（NOMMU 下通常为 0）
- `mmap_pages_allocated`：通过 mmap 分配的总页数（原子计数器）
- `nommu_region_tree`：红黑树，用于管理已映射的共享内存区域
- `nommu_region_sem`：读写信号量，保护 `nommu_region_tree` 的并发访问
- `vm_region_jar`：slab 缓存，用于分配 `vm_region` 结构

### 主要函数
- `kobjsize(const void *objp)`：估算给定指针所占内存大小（支持 kmalloc、VMA 区域或普通页）
- `follow_pfn(struct vm_area_struct *vma, unsigned long address, unsigned long *pfn)`：从用户虚拟地址获取物理页帧号（仅支持 IO 或 PFN 映射）
- `vfree(const void *addr)`：释放由 vmalloc 分配的内存（实际调用 kfree）
- `__vmalloc_noprof()` 及相关变体（`vmalloc`, `vzalloc`, `vmalloc_user` 等）：提供 vmalloc 系列函数的 NOMMU 实现（底层使用 kmalloc）
- `vmalloc_to_page()` / `vmalloc_to_pfn()`：将 vmalloc 地址转换为 page 或 PFN（直接使用 `virt_to_page`）
- `vread_iter()`：将内核地址内容拷贝到 iov_iter（用于 `/proc/vmallocinfo` 等）

### 操作结构体
- `generic_file_vm_ops`：空的 `vm_operations_struct`，作为 NOMMU 下文件映射的默认操作集

## 3. 关键实现

### 内存分配模型
- **无虚拟地址空间**：所有“虚拟”地址实为物理地址的线性映射，`vmalloc` 系列函数退化为 `kmalloc` 调用。
- **GFP 标志处理**：自动清除 `__GFP_HIGHMEM`（因 kmalloc 无法返回高端内存逻辑地址），并添加 `__GFP_COMP` 以支持复合页。
- **零填充支持**：`vzalloc` 等函数通过 `__GFP_ZERO` 标志实现。

### 内存区域管理
- **共享区域跟踪**：使用红黑树 `nommu_region_tree` 和 slab 缓存 `vm_region_jar` 管理可共享的映射区域（如文件映射），确保多个进程可共享同一物理内存。
- **VMA 标记**：`vmalloc_user` 分配的内存会标记 `VM_USERMAP`，允许后续通过 `remap_vmalloc_range` 映射到用户空间。

### 地址转换简化
- **PFN 获取**：`follow_pfn` 直接通过地址右移 `PAGE_SHIFT` 计算 PFN（因无虚拟地址转换）。
- **vmalloc 地址转换**：`vmalloc_to_page` 直接调用 `virt_to_page`（因 vmalloc 地址即物理地址的线性映射）。

### 安全与兼容性
- **kobjsize 安全检查**：先验证地址有效性（`virt_addr_valid`），再根据页类型（Slab/Compound/VMA）返回不同大小。
- **用户空间映射**：`vmalloc_user` 在分配后查找对应 VMA 并设置 `VM_USERMAP`，确保安全暴露给用户态。

## 4. 依赖关系

### 头文件依赖
- **核心内存管理**：`<linux/mm.h>`, `<linux/mman.h>`, `"internal.h"`
- **内存分配**：`<linux/slab.h>`, `<linux/vmalloc.h>`
- **页与地址转换**：`<linux/highmem.h>`, `<linux/pagemap.h>`, `<asm/tlb.h>`
- **进程与安全**：`<linux/sched/mm.h>`, `<linux/security.h>`, `<linux/audit.h>`
- **I/O 与文件**：`<linux/file.h>`, `<linux/uio.h>`, `<linux/backing-dev.h>`

### 符号导出
- 导出关键符号供其他模块使用：`high_memory`, `max_mapnr`, `mem_map`, `follow_pfn`, `vfree`, `vmalloc` 系列函数等。

### 架构依赖
- 依赖架构特定头文件（如 `asm/tlb.h`, `asm/mmu_context.h`），但 NOMMU 架构下这些通常为空实现。

## 5. 使用场景

- **无 MMU 嵌入式系统**：运行于 uClinux 等无虚拟内存系统的设备（如早期 ARM7、Blackfin、m68knommu）。
- **内核子系统兼容**：为依赖 `vmalloc`、`vfree`、`follow_pfn` 等接口的驱动或子系统（如 GPU 驱动、DMA 映射）提供 NOMMU 兼容层。
- **用户空间内存映射**：支持 `mmap` 系统调用对文件或设备的映射（通过 `nommu_region_tree` 管理共享区域）。
- **调试与监控**：`vread_iter` 支持 `/proc/vmallocinfo` 等接口读取内核内存布局。
- **安全内存分配**：`vmalloc_user` 提供可安全映射到用户空间的零初始化内存（用于 IPC 或共享缓冲区）。