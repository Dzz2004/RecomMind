# dmapool_test.c

> 自动生成时间: 2025-12-07 15:57:16
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `dmapool_test.c`

---

# dmapool_test.c 技术文档

## 1. 文件概述

`dmapool_test.c` 是一个 Linux 内核模块，用于对内核的 DMA 池（DMA Pool）机制进行功能与性能测试。该模块通过创建不同参数配置的 DMA 池，反复执行分配与释放操作，并记录执行时间，以验证 `dma_pool_*` 接口的正确性、稳定性及基本性能表现。

## 2. 核心功能

### 数据结构

- **`struct dma_pool_pair`**  
  用于配对存储 DMA 映射的虚拟地址（`v`）和对应的总线地址（`dma`），便于后续释放。

- **`struct dmapool_parms`**  
  定义 DMA 池的创建参数，包括：
  - `size`：每个块的大小（字节）
  - `align`：内存对齐要求
  - `boundary`：跨边界限制（0 表示无限制）

- **全局变量**
  - `pool_parms[]`：预定义的多组测试参数，覆盖常见尺寸和对齐场景。
  - `pool`：当前测试使用的 `dma_pool` 实例。
  - `test_dev`：用于 DMA 操作的虚拟设备。
  - `dma_mask`：设备支持的 DMA 地址位宽掩码。

### 主要函数

- **`nr_blocks(int size)`**  
  根据块大小计算每次测试分配的块数量，范围限制在 1024 到 8192 之间，基于 `PAGE_SIZE` 动态调整。

- **`dmapool_test_alloc(struct dma_pool_pair *p, int blocks)`**  
  执行单次分配/释放循环：分配指定数量的 DMA 块，若失败则回滚已分配资源并返回错误。

- **`dmapool_test_block(const struct dmapool_parms *parms)`**  
  针对一组参数执行完整测试流程：
  1. 创建对应参数的 DMA 池；
  2. 分配足够内存存储地址对；
  3. 循环 `NR_TESTS`（100 次）执行分配/释放；
  4. 记录并打印总耗时（微秒）；
  5. 清理资源。

- **`dmapool_checks(void)`**  
  模块初始化入口函数：
  - 注册虚拟设备 `dmapool-test`；
  - 设置 64 位 DMA 地址掩码；
  - 遍历所有预设参数组合执行测试；
  - 出错时清理设备。

- **`dmapool_test_release(struct device *dev)`**  
  虚拟设备的 release 回调（空实现，仅满足设备模型要求）。

- **`dmapool_exit(void)`**  
  模块退出函数（空实现，因资源已在 `dmapool_checks` 中清理）。

## 3. 关键实现

- **虚拟设备注册**  
  由于 `dma_pool_create()` 需要有效的 `struct device *`，模块动态创建一个名为 `dmapool-test` 的虚拟设备，并为其设置 64 位 DMA 掩码，确保可在大多数平台上运行。

- **动态块数计算**  
  `nr_blocks()` 使用 `clamp_t` 将分配块数限制在合理区间（1024–8192），避免因小块导致内存爆炸或大块导致分配不足。

- **性能测量**  
  使用 `ktime_get()` 和 `ktime_us_delta()` 精确测量 100 次完整分配/释放循环的总耗时，并通过 `printk` 输出结果，便于性能分析。

- **错误处理与资源回收**  
  所有分配路径均包含错误回滚逻辑（如 `dmapool_test_alloc` 中的 `pool_fail` 标签），确保内存和 DMA 资源不泄漏。

- **调度友好性**  
  在测试循环中调用 `need_resched()` 和 `cond_resched()`，避免长时间占用 CPU 导致系统卡顿。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/dmapool.h>`：提供 `dma_pool_*` 接口。
  - `<linux/dma-mapping.h>` 和 `<linux/dma-map-ops.h>`：提供 DMA 映射和设备 DMA 配置支持。
  - `<linux/device.h>`：用于注册虚拟设备。
  - `<linux/ktime.h>`：高精度时间测量。
  - `<linux/module.h>`：模块加载/卸载框架。

- **内核子系统依赖**：
  - **DMA 子系统**：核心依赖，提供一致性 DMA 内存池管理。
  - **设备模型**：用于创建和管理虚拟设备。
  - **内存管理子系统**：底层依赖 `kmalloc`/`kfree` 及页分配器。

## 5. 使用场景

- **内核开发与调试**：作为 DMA 池功能的回归测试工具，验证新平台或修改后的 `dma_pool` 实现是否正常工作。
- **性能基准测试**：评估不同块大小、对齐和边界条件下 DMA 池的分配/释放效率。
- **驱动开发参考**：展示如何正确使用 `dma_pool_create/alloc/free/destroy` 接口，以及如何为无硬件设备的测试场景构造虚拟设备。
- **CI/CD 集成测试**：可集成到内核持续集成流程中，自动检测 DMA 相关变更引入的回归问题。