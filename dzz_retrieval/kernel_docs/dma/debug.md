# dma\debug.c

> 自动生成时间: 2025-10-25 13:11:41
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `dma\debug.c`

---

# `dma/debug.c` 技术文档

## 1. 文件概述

`dma/debug.c` 是 Linux 内核中用于调试 DMA（Direct Memory Access）API 使用错误的核心模块。该文件实现了对 `dma_map_*`、`dma_unmap_*`、`dma_alloc_coherent` 等 DMA 操作的运行时跟踪与验证机制，旨在检测常见的 DMA 编程错误，例如：

- 重复映射或重复释放
- 未配对的映射/解除映射操作
- 越界访问
- 未检查 `dma_mapping_error()` 返回值

当检测到违规行为时，该模块会输出详细的错误信息（包括设备信息、DMA 地址、操作类型、调用栈等），帮助开发者定位问题。该功能通过 `CONFIG_DMA_API_DEBUG` 配置选项启用，主要用于开发和调试阶段。

## 2. 核心功能

### 主要数据结构

- **`struct dma_debug_entry`**  
  表示一个 DMA 映射记录，包含设备指针、DMA 地址、大小、方向、类型（single/sg/coherent/resource）、页帧号、偏移量、错误检查状态及调用栈信息。

- **`struct hash_bucket`**  
  哈希桶结构，包含一个链表头和自旋锁，用于并发安全地管理哈希表中的 DMA 条目。

- **全局变量**
  - `dma_entry_hash[HASH_SIZE]`：哈希表，用于快速查找 DMA 映射条目。
  - `free_entries`：预分配的空闲 `dma_debug_entry` 链表。
  - `global_disable`：全局禁用标志，一旦发生严重错误即关闭调试功能。
  - `error_count`：累计错误计数。
  - `show_num_errors` / `show_all_errors`：控制错误输出数量。
  - `current_driver_name` / `current_driver`：支持按驱动名称过滤错误输出。

### 主要函数与宏

- **`hash_fn()`**：基于 DMA 地址的哈希函数（使用 bits 20–27）。
- **`get_hash_bucket()` / `put_hash_bucket()`**：获取/释放哈希桶的自旋锁，支持中断上下文安全。
- **`exact_match()` / `containing_match()`**：用于在哈希链表中匹配条目（精确匹配或包含匹配）。
- **`driver_filter()`**：根据当前设置的驱动名过滤错误报告。
- **`err_printk()`**：错误打印宏，自动递增错误计数、应用过滤规则、打印警告及调用栈。
- **`dump_entry_trace()`**：在支持 `CONFIG_STACKTRACE` 时打印 DMA 映射时的调用栈。

### 枚举类型

- **DMA 类型枚举**：
  - `dma_debug_single`
  - `dma_debug_sg`
  - `dma_debug_coherent`
  - `dma_debug_resource`

- **映射错误检查状态**：
  - `MAP_ERR_CHECK_NOT_APPLICABLE`
  - `MAP_ERR_NOT_CHECKED`
  - `MAP_ERR_CHECKED`

## 3. 关键实现

### 哈希表设计

- 使用大小为 16384（`HASH_SIZE`）的静态哈希表。
- 哈希函数 `hash_fn()` 通过右移 13 位（`HASH_FN_SHIFT`）并掩码 `0x3FFF` 提取地址中间位，以减少冲突。
- 每个桶（`hash_bucket`）配备独立自旋锁，支持高并发访问。

### 内存管理

- 启动时预分配 `PREALLOC_DMA_DEBUG_ENTRIES`（65536）个 `dma_debug_entry`。
- 若池耗尽，动态按页分配（每页可容纳 `DMA_DEBUG_DYNAMIC_ENTRIES` 个条目）。
- 使用 `free_entries` 链表和 `free_entries_lock` 管理空闲条目。

### 错误抑制与过滤

- 通过 `show_num_errors` 限制初始错误输出数量（默认 1），避免日志爆炸。
- 支持通过 debugfs 动态设置 `show_all_errors` 以显示所有错误。
- `driver_filter()` 允许用户指定只监控特定驱动的 DMA 操作，提升调试效率。

### 调用栈追踪

- 在 `CONFIG_STACKTRACE` 启用时，每个 `dma_debug_entry` 记录最多 5 层调用栈（`DMA_DEBUG_STACKTRACE_ENTRIES`）。
- 出错时通过 `dump_entry_trace()` 打印映射发生的位置，极大提升问题定位能力。

### 线程安全

- 哈希桶使用 `spin_lock_irqsave`/`spin_unlock_irqrestore` 保证中断上下文安全。
- 全局状态变量（如 `error_count`）虽存在竞态，但设计上容忍轻微不一致（如少计错误），以避免性能开销。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/dma-map-ops.h>`：DMA 映射操作接口。
  - `<linux/stacktrace.h>`：调用栈记录支持。
  - `<linux/debugfs.h>`：用于暴露调试参数（如错误数量、驱动过滤器）。
  - `<linux/scatterlist.h>`：SG 列表相关定义。
  - `<asm/sections.h>`：内核段信息（可能用于地址合法性检查）。

- **配置依赖**：
  - 由 `CONFIG_DMA_API_DEBUG` 控制编译。
  - `CONFIG_STACKTRACE` 决定是否启用调用栈记录。

- **与其他模块交互**：
  - 与 `dma-mapping.c` 紧密集成，在 `dma_map_*` / `dma_unmap_*` 等函数中调用本模块的钩子函数（如 `dma_debug_add()`、`dma_debug_remove()` 等，虽未在本片段中展示）。
  - 通过 `device` 和 `device_driver` 结构与设备模型交互，实现驱动级过滤。

## 5. 使用场景

- **内核开发与调试**：在开发新驱动或修改 DMA 代码时启用，检测潜在的 DMA 使用错误。
- **系统稳定性分析**：在出现内存损坏、设备异常时，开启 DMA 调试以排查是否由 DMA 操作不当引起。
- **CI/测试环境**：在自动化测试中启用 `CONFIG_DMA_API_DEBUG`，作为静态检查的补充，捕获运行时错误。
- **生产环境（谨慎）**：通常不在生产内核中启用，因其带来显著内存与性能开销；但在特定高可靠性场景下可临时开启用于问题复现。

该模块是 Linux 内核 DMA 子系统的重要调试基础设施，显著提升了 DMA 相关 bug 的可发现性和可诊断性。