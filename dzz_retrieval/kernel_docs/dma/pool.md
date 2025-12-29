# dma\pool.c

> 自动生成时间: 2025-10-25 13:15:49
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `dma\pool.c`

---

# `dma/pool.c` 技术文档

## 1. 文件概述

`dma/pool.c` 实现了 Linux 内核中的 **DMA 原子内存池（atomic DMA pools）** 机制，用于在无法睡眠的上下文（如中断处理、原子上下文）中分配一致性（coherent）DMA 内存。该机制通过预分配多个按内存区域（ZONE_DMA、ZONE_DMA32、普通内核内存）划分的通用内存池（`gen_pool`），并在池空间不足时通过工作队列异步扩展，从而支持在 GFP_ATOMIC 等限制性分配标志下安全地分配 DMA 内存。

该文件主要用于支持 `dma-direct` 子系统中的原子 DMA 分配路径，确保即使在内存压力大或无法睡眠的场景下，设备驱动仍能获得满足地址限制（如 32 位或 24 位寻址）的一致性 DMA 缓冲区。

## 2. 核心功能

### 全局变量
- `atomic_pool_dma` / `pool_size_dma`：用于 `GFP_DMA` 区域的原子 DMA 池及其已分配大小。
- `atomic_pool_dma32` / `pool_size_dma32`：用于 `GFP_DMA32` 区域的原子 DMA 池及其已分配大小。
- `atomic_pool_kernel` / `pool_size_kernel`：用于普通内核区域（无特殊 DMA 限制）的原子 DMA 池及其已分配大小。
- `atomic_pool_size`：每个池的初始目标大小，可通过内核命令行参数 `coherent_pool=` 设置。
- `atomic_pool_work`：用于后台动态扩展内存池的工作项。

### 主要函数
- `early_coherent_pool()`：解析内核命令行参数 `coherent_pool`，设置 `atomic_pool_size`。
- `dma_atomic_pool_init()`：初始化所有原子 DMA 池（postcore 阶段调用）。
- `__dma_atomic_pool_init()`：创建并填充指定 GFP 标志的原子池。
- `atomic_pool_expand()`：向指定池中添加一块连续物理内存。
- `atomic_pool_resize()` / `atomic_pool_work_fn()`：检查池剩余空间，若不足则触发扩展。
- `dma_alloc_from_pool()`：从合适的原子池中分配指定大小的 DMA 内存。
- `dma_free_from_pool()`：将内存归还到对应的原子池。
- `dma_guess_pool()`：根据 GFP 标志和尝试顺序选择合适的内存池。
- `cma_in_zone()`：判断 CMA 区域是否位于指定 DMA 区域内，以决定是否优先从 CMA 分配。
- `dma_atomic_pool_debugfs_init()`：在 debugfs 中导出各池的当前大小。

## 3. 关键实现

### 内存池初始化策略
- 若未通过 `coherent_pool=` 指定大小，则默认按 **每 1GB 物理内存分配 128KB** 原子池，最小 128KB，最大不超过 `MAX_ORDER_NR_PAGES` 对应的内存。
- 每个池使用 `gen_pool` 管理，分配算法为 `gen_pool_first_fit_order_align`，保证分配地址按页对齐。
- 初始化时调用 `atomic_pool_expand()` 预分配内存。

### 内存分配来源
- 优先尝试从 **CMA（Contiguous Memory Allocator）** 区域分配（若 CMA 区域位于目标 DMA zone 内）。
- 若 CMA 不可用或不在目标 zone，则回退到 `alloc_pages()`。
- 分配的内存块大小不超过 `MAX_PAGE_ORDER`，通过降序尝试（从大到小）提高分配成功率。

### 内存属性处理
- 调用 `arch_dma_prep_coherent()` 通知架构层准备一致性内存。
- 在支持内存加密（如 AMD SEV、Intel TDX）的系统上，显式调用 `set_memory_decrypted()` 确保 DMA 内存为 **未加密状态**，因为设备无法访问加密内存。
- 若启用了 `CONFIG_DMA_DIRECT_REMAP`，则通过 `dma_common_contiguous_remap()` 建立非缓存或设备专用的页表映射。

### 动态扩展机制
- 每次从池中分配内存后，检查剩余空间是否小于 `atomic_pool_size`。
- 若不足，则调度 `atomic_pool_work` 工作项，在进程上下文中异步扩展对应池。
- 扩展时尝试分配与当前池总大小相当的新内存块，避免频繁小量扩展。

### 多池选择逻辑
- `dma_guess_pool()` 实现池选择策略：
  1. 首选与 GFP 标志匹配的池（DMA32 > DMA > 普通内核）。
  2. 若首次分配失败，按 `kernel → dma32 → dma` 顺序尝试其他池（fallback 机制）。
- 释放时遍历所有池，通过 `gen_pool_has_addr()` 确定内存归属。

## 4. 依赖关系

- **内存管理子系统**：
  - 依赖 `genalloc`（`gen_pool`）实现内存池管理。
  - 使用 `alloc_pages()`、`__free_pages()` 进行底层页分配。
  - 依赖 CMA 接口（`dma_alloc_from_contiguous()`）获取大块连续内存。
- **DMA 子系统**：
  - 与 `dma-direct.c` 紧密集成，为其提供 `___dma_direct_alloc_pages()` 中的原子分配路径。
  - 使用 `dma-map-ops.h` 和 `dma-direct.h` 中的辅助函数。
- **架构相关支持**：
  - 调用 `arch_dma_prep_coherent()`（架构可选实现）。
  - 使用 `set_memory_decrypted()`/`set_memory_encrypted()`（x86/ARM64 等支持内存加密的架构）。
  - 依赖 `DMA_BIT_MASK()` 和 `zone_dma_bits` 判断 DMA 地址范围。
- **其他**：
  - 使用 `debugfs` 导出调试信息。
  - 依赖 `workqueue` 实现异步扩展。
  - 使用 `slab.h` 中的内存分配器（间接）。

## 5. 使用场景

- **原子上下文 DMA 分配**：当设备驱动在中断处理程序、自旋锁保护区域或使用 `GFP_ATOMIC` 标志调用 `dma_alloc_coherent()` 时，若常规页分配器无法满足（如内存碎片），内核会回退到从原子池分配。
- **满足地址限制的 DMA 缓冲区**：对于需要 24 位（ISA 设备）或 32 位（旧 PCIe 设备）寻址能力的设备，驱动使用 `DMA_BIT_MASK(24)` 或 `DMA_BIT_MASK(32)` 限制 DMA 地址范围，原子池确保分配的内存物理地址符合要求。
- **一致性内存需求**：适用于需要 CPU 与设备之间缓存一致性的场景（如网络数据包缓冲区、音频流缓冲区），原子池分配的内存经过 `arch_dma_prep_coherent()` 处理，保证一致性。
- **内存加密环境**：在启用内存加密的系统中，确保分配给设备的 DMA 内存处于解密状态，使设备能正常访问。