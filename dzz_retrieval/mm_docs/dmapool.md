# dmapool.c

> 自动生成时间: 2025-12-07 15:56:43
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `dmapool.c`

---

# dmapool.c 技术文档

## 1. 文件概述

`dmapool.c` 实现了 Linux 内核中的 **DMA 池（DMA Pool）分配器**，用于为设备驱动程序提供小块、一致（coherent）且可 DMA 访问的内存。该分配器基于 `dma_alloc_coherent()` 分配整页内存，并将其划分为固定大小的块，以满足频繁分配/释放小块 DMA 内存的需求，避免直接使用页级分配造成的内存浪费。此机制特别适用于需要大量相同大小 DMA 缓冲区的设备驱动（如 USB、网络、存储控制器等）。

## 2. 核心功能

### 主要数据结构

- **`struct dma_pool`**  
  表示一个 DMA 池，包含：
  - `page_list`：已分配物理页的双向链表
  - `lock`：自旋锁，保护池内操作
  - `next_block`：空闲块的单向链表头指针
  - `nr_blocks` / `nr_active` / `nr_pages`：统计信息（总块数、活跃块数、页数）
  - `dev`：关联的设备
  - `size` / `allocation` / `boundary`：块大小、页分配大小、边界对齐限制
  - `name`：池名称（用于调试）
  - `pools`：挂载到设备 `dma_pools` 列表的节点

- **`struct dma_page`**  
  表示从 `dma_alloc_coherent()` 分配的一个物理页，包含虚拟地址 `vaddr` 和 DMA 地址 `dma`。

- **`struct dma_block`**  
  嵌入在每个 DMA 块起始位置的元数据结构，仅包含指向下一个空闲块的指针 `next_block` 和该块的 DMA 地址 `dma`。

### 主要函数

- **`dma_pool_create()`**  
  创建一个新的 DMA 池，指定名称、设备、块大小、对齐要求和边界限制。

- **`pool_block_pop()` / `pool_block_push()`**  
  从空闲链表中分配/归还一个 DMA 块。

- **`pool_check_block()` / `pool_block_err()` / `pool_init_page()`**  
  调试辅助函数（在 `DMAPOOL_DEBUG` 启用时），用于检测内存越界、重复释放等错误，并进行内存毒化（poisoning）。

- **`pools_show()`**  
  sysfs 接口回调，显示设备下所有 DMA 池的统计信息。

## 3. 关键实现

- **内存组织**：  
  每次调用 `dma_alloc_coherent()` 分配至少一页（`PAGE_SIZE`）的连续物理内存（`allocation` 字段）。该页被划分为多个 `size` 字节的块。每个块的起始处嵌入 `struct dma_block` 元数据。

- **空闲管理**：  
  所有空闲块通过 `next_block` 指针组成一个**全局单向链表**（由 `dma_pool.next_block` 指向头节点）。分配时从链表头部弹出，释放时压入头部。**已分配块不被显式跟踪**，仅通过 `nr_active` 计数。

- **边界对齐处理**：  
  若指定了 `boundary`（如 4KB），则确保单个 DMA 块不会跨越该边界。实现上通过限制每页实际可用区域或调整分配策略（代码片段未完整展示具体划分逻辑）。

- **调试支持（DMAPOOL_DEBUG）**：  
  在 SLUB 调试开启时启用：
  - 分配时用 `POOL_POISON_ALLOCATED` 填充用户区域（若未启用 init-on-alloc）
  - 释放时用 `POOL_POISON_FREED` 填充，并检查是否已被释放（防 double-free）
  - 提供 `pool_find_page()` 辅助验证 DMA 地址有效性

- **Sysfs 集成**：  
  首次为设备创建 DMA 池时，自动注册 `pools` sysfs 属性文件，可通过 `/sys/devices/.../pools` 查看池状态（名称、活跃块数、总块数、块大小、页数）。

- **并发控制**：  
  - `pools_lock`：保护设备 `dma_pools` 列表的增删
  - `pools_reg_lock`：防止 `dma_pool_create()` 与 `dma_pool_destroy()` 之间的竞争
  - `dma_pool.lock`：保护池内部的空闲链表和计数器

## 4. 依赖关系

- **核心依赖**：
  - `<linux/dma-mapping.h>`：提供 `dma_alloc_coherent()` / `dma_free_coherent()` 等底层 DMA 映射接口
  - `<linux/device.h>`：设备模型及 sysfs 支持
  - `<linux/slab.h>`：用于分配 `struct dma_pool` 结构体内存

- **调试依赖**：
  - `CONFIG_SLUB_DEBUG_ON`：启用内存毒化和错误检查
  - `<linux/poison.h>`：提供 `POOL_POISON_*` 常量

- **同步原语**：
  - `<linux/mutex.h>` / `<linux/spinlock.h>`：提供互斥锁和自旋锁

## 5. 使用场景

- **设备驱动开发**：  
  当驱动需要频繁分配/释放**固定大小**的小块（通常小于一页）DMA 缓冲区时，使用 DMA 池可显著提升性能并减少内存碎片。典型场景包括：
  - USB 主机控制器的传输描述符（TD）池
  - 网络设备的接收/发送描述符环
  - 存储控制器的命令/状态块

- **替代方案**：  
  相比直接调用 `dma_alloc_coherent()` 分配整页内存，DMA 池避免了小块分配的内存浪费；相比通用 slab 分配器（如 kmalloc），它保证了返回内存的 DMA 一致性（无需手动缓存维护）。

- **限制条件**：  
  - 仅适用于**一致性 DMA 映射**（coherent DMA）
  - 所有块大小在池创建时固定
  - 不适用于大块（接近或超过一页）内存分配