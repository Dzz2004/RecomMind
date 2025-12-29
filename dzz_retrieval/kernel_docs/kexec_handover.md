# kexec_handover.c

> 自动生成时间: 2025-10-25 14:26:16
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kexec_handover.c`

---

# kexec_handover.c 技术文档

## 文件概述

`kexec_handover.c` 实现了 **Kexec Handover (KHO)** 机制中的内存保留元数据处理功能。该机制允许在通过 `kexec` 加载新内核时，将当前内核中某些关键内存区域（如已分配的页）的状态信息传递给后继内核，从而实现内存状态的延续。本文件主要负责：

- 跟踪需跨内核保留的物理内存页（按分配阶 order 分类）
- 使用两级 `xarray` 高效管理稀疏位图
- 将内存保留信息序列化为链表结构，嵌入到设备树（FDT）中供后继内核解析
- 提供接口供后继内核恢复 `struct folio` 对象

## 核心功能

### 主要数据结构

| 结构体 | 说明 |
|--------|------|
| `kho_mem_phys_bits` | 包含 4096 位（512 字节）的位图，用于标记某一段物理地址范围内哪些页需保留 |
| `kho_mem_phys` | 按物理地址分块管理 `kho_mem_phys_bits`，使用 `xarray` 实现稀疏存储 |
| `kho_mem_track` | 按分配阶（order）组织多个 `kho_mem_phys`，顶层使用 `xarray` 索引 |
| `khoser_mem_chunk` | 序列化后的内存保留信息块，每页大小，包含多个位图指针及起始物理地址 |
| `kho_serialization` | KHO 序列化上下文，包含 FDT、调试目录及内存跟踪结构 |

### 主要函数

| 函数 | 功能 |
|------|------|
| `kho_is_enabled()` | 查询 KHO 功能是否启用（通过 `kho=` 内核参数控制） |
| `__kho_preserve_order()` | 将指定 PFN 和 order 的内存标记为需保留 |
| `__kho_unpreserve()` | 取消对指定物理页范围的保留标记 |
| `kho_restore_folio()` | 根据物理地址恢复 `struct folio`，供后继内核使用 |
| `kho_mem_serialize()` | 将 `xarray` 中的保留内存信息序列化为页链表 |
| `xa_load_or_alloc()` | 辅助函数：若 `xarray` 中无元素则分配并插入 |

## 关键实现

### 两级稀疏位图管理

为高效跟踪大内存系统中稀疏分布的保留页，KHO 采用两级 `xarray` 结构：

1. **第一级（按 order 索引）**：`kho_mem_track::orders`，键为分配阶（0 ~ MAX_ORDER）
2. **第二级（按高地址索引）**：每个 order 对应一个 `kho_mem_phys::phys_bits`，键为 `pfn_high / 4096`（即每 4096 个高位 PFN 一组）

每个位图块（`kho_mem_phys_bits`）管理 `4096 << (order + PAGE_SHIFT)` 字节的物理地址空间。例如：
- order=0（4KB 页）：每块覆盖 16MB
- order=9（2MB 页）：每块覆盖 8GB

### 序列化为页链表

在 `kexec` 前，调用 `kho_mem_serialize()` 将 `xarray` 转换为连续的页链表（`khoser_mem_chunk`），每页结构如下：

```c
struct khoser_mem_chunk {
    struct khoser_mem_chunk_hdr hdr;  // 包含 next 指针、order、元素数量
    struct khoser_mem_bitmap_ptr bitmaps[KHOSER_BITMAP_SIZE]; // 最多 508 个条目（4KB 页）
};
```

每个 `khoser_mem_bitmap_ptr` 记录：
- `phys_start`：该位图对应的起始物理地址
- `bitmap`：指向 `kho_mem_phys_bits` 的指针（使用 `KHOSER_STORE_PTR` 宏处理指针序列化）

### 内存恢复机制

后继内核通过 `kho_restore_folio(phys)` 恢复页：
1. 通过 `pfn_to_online_page()` 获取 `struct page`
2. 若为高阶页（`page->private != 0`），调用 `prep_compound_page()` 初始化复合页
3. 若为普通页，调用 `kho_restore_page()` 清除 `PG_reserved` 并调整页计数器

## 依赖关系

### 内核头文件依赖
- `<linux/kexec.h>`：kexec 核心接口
- `<linux/xarray.h>`（隐式通过 `xarray.h`）：稀疏数组管理
- `<linux/page-isolation.h>`：页隔离与释放
- `<linux/libfdt.h>`：设备树操作
- `"../mm/internal.h"`：访问内存管理内部 API（如 `prep_compound_page`）
- `"kexec_internal.h"`：kexec 内部实现

### 架构依赖
- `asm/early_ioremap.h`：早期 I/O 映射（用于访问保留内存）
- `PAGE_SHIFT` / `MAX_PAGE_ORDER`：架构相关页大小定义

### 导出符号
- `kho_is_enabled()`：供其他模块查询 KHO 状态
- `kho_restore_folio()`：供后继内核恢复页结构

## 使用场景

1. **Kexec 内核热替换**  
   当系统通过 `kexec -e` 切换到新内核时，当前内核将关键内存（如 CMA 区域、已分配的 DMA 缓冲区）标记为保留，并通过 FDT 传递元数据。

2. **内存状态延续**  
   后继内核启动早期（在内存初始化完成前）解析 FDT 中的 `preserved-memory-map` 属性，调用 `kho_restore_folio()` 恢复页描述符，避免重复分配或覆盖关键数据。

3. **调试与验证**  
   通过 debugfs 挂载点（`sub_fdt_dir`）可检查序列化后的 FDT 子树，验证保留内存信息的正确性。

4. **大内存系统优化**  
   在 TB 级内存系统中，两级位图设计确保内存开销可控（例如 16GB 内存仅需 512KB 位图跟踪 order=0 页）。