# kmsan\shadow.c

> 自动生成时间: 2025-12-07 16:33:44
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kmsan\shadow.c`

---

# `kmsan/shadow.c` 技术文档

## 1. 文件概述

`kmsan/shadow.c` 是 Linux 内核内存安全检测工具 **KMSAN**（Kernel Memory Sanitizer）的核心实现文件之一，主要负责管理与主内存页一一对应的 **影子内存**（shadow memory）和 **起源信息**（origin metadata）的分配、映射、复制与释放。该文件实现了 KMSAN 对物理页和虚拟地址空间（包括 vmalloc 和模块区域）的元数据访问接口，确保在运行时能够追踪每个字节的初始化状态及其污染来源。

## 2. 核心功能

### 主要函数

| 函数名 | 功能描述 |
|--------|---------|
| `kmsan_get_metadata()` | 获取指定地址对应的 shadow 或 origin 元数据指针，支持物理页、vmalloc 和模块地址 |
| `kmsan_get_shadow_origin_ptr()` | 为给定内存区间返回 shadow 和 origin 指针结构体；若元数据不可用，则返回 dummy 页面 |
| `kmsan_copy_page_meta()` | 将源页的 shadow 和 origin 元数据完整复制到目标页 |
| `kmsan_alloc_page()` | 为新分配的物理页初始化其 shadow 和 origin 元数据（根据是否已清零或处于运行时） |
| `kmsan_free_page()` | 在释放页面前对其主内存进行 poison 操作，并标记元数据为无效 |
| `kmsan_vmap_pages_range_noflush()` | 为 vmalloc 区域批量映射对应的 shadow 和 origin 元数据页 |
| `kmsan_init_alloc_meta_for_range()` | 在内核启动早期为指定物理内存范围预分配并绑定 shadow/origin 元数据 |

### 关键数据结构与宏

- `struct shadow_origin_ptr`：包含 `shadow` 和 `origin` 两个指针，用于同时返回两种元数据。
- `dummy_load_page` / `dummy_store_page`：全局对齐的 PAGE_SIZE 缓冲区，用于在元数据缺失时提供安全的默认行为（load 返回 0，store 被忽略）。
- `shadow_page_for(page)` / `origin_page_for(page)`：通过 `struct page` 的扩展字段直接获取其关联的元数据页。
- `vmalloc_meta()`：将 vmalloc 或模块地址转换为其在 KMSAN 预留元数据区域中的对应地址。

## 3. 关键实现

### 元数据布局
- 每个普通物理页（`struct page`）通过其 `kmsan_shadow` 和 `kmsan_origin` 字段指向独立的 shadow 页和 origin 页。
- Shadow 页中每个字节表示主内存对应字节的“是否初始化”状态（0=已初始化，非0=未初始化）。
- Origin 页存储 `depot_stack_handle_t` 类型的栈轨迹 ID，用于追踪未初始化值的来源。

### 地址空间支持
- **线性映射区**：通过 `virt_to_page()` 获取主内存页，再通过页结构获取元数据页。
- **vmalloc/模块区**：使用 `vmalloc_meta()` 将虚拟地址偏移映射到 KMSAN 预留的元数据虚拟地址空间（`KMSAN_VMALLOC_SHADOW_START` 等）。
- 支持跨页但要求 **元数据连续**（`kmsan_metadata_is_contiguous`），单次访问不超过 PAGE_SIZE。

### 安全兜底机制
- 当元数据不可用（如 slab 对象、DMA 内存等）时，`kmsan_get_shadow_origin_ptr()` 返回 dummy 页面：
  - **Load 操作**：从 `dummy_load_page`（全零）读取，保证返回已初始化值。
  - **Store 操作**：写入 `dummy_store_page`（被丢弃），避免影响其他访问。

### 运行时保护
- 所有涉及元数据操作的函数（如 `kmsan_copy_page_meta`、`kmsan_alloc_page`）在非运行时上下文中执行时，需通过 `kmsan_enter_runtime()` / `kmsan_leave_runtime()` 临时禁用 KMSAN 检查，防止递归触发。

### 启动阶段初始化
- `kmsan_init_alloc_meta_for_range()` 使用 `memblock_alloc()` 在 bootmem 阶段为指定物理内存范围分配连续的 shadow 和 origin 内存，并建立页级映射关系，用于初始化内核静态数据的元数据。

## 4. 依赖关系

- **架构相关**：依赖 `<asm/kmsan.h>` 提供的 `arch_kmsan_get_meta_or_null()` 等平台特定实现。
- **内存管理**：紧密集成 `mm/` 子系统，使用 `struct page`、`virt_to_page()`、`page_address()`、`memblock`、`vmalloc` 等接口。
- **KMSAN 核心**：依赖 `kmsan.h` 和 `internal.h` 中定义的常量（如 `KMSAN_ORIGIN_SIZE`）、状态标志（`kmsan_enabled`）及内部函数（如 `kmsan_save_stack_with_flags()`）。
- **TLB 与缓存管理**：调用 `flush_tlb_kernel_range()` 和 `flush_cache_vmap()` 确保元数据映射生效。

## 5. 使用场景

- **内存分配器集成**：当伙伴系统或 slab 分配器分配/释放页面时，调用 `kmsan_alloc_page()` / `kmsan_free_page()` 初始化或清理元数据。
- **内存拷贝操作**：在 `memcpy`、`copy_user` 等路径中，通过 `kmsan_get_shadow_origin_ptr()` 获取元数据以传播污染状态。
- **vmalloc 映射**：在 `vmap()` 创建虚拟映射时，调用 `kmsan_vmap_pages_range_noflush()` 同步建立元数据映射。
- **内核启动**：在 `start_kernel()` 早期阶段，为 `.data`、`.bss` 等静态区域调用 `kmsan_init_alloc_meta_for_range()` 建立初始元数据。
- **调试与诊断**：当检测到未初始化内存使用时，通过 origin 信息回溯污染源头，辅助开发者定位问题。