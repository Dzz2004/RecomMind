# dma\map_benchmark.c

> 自动生成时间: 2025-10-25 13:13:45
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `dma\map_benchmark.c`

---

# `dma/map_benchmark.c` 技术文档

## 1. 文件概述

`dma/map_benchmark.c` 是 Linux 内核中用于对 DMA（Direct Memory Access）映射和解映射操作进行性能基准测试的模块。该模块通过用户空间 ioctl 接口接收测试参数，创建多个内核线程并发执行 `dma_map_single()` 和 `dma_unmap_single()` 操作，统计其平均延迟和标准差，用于评估不同硬件平台或驱动实现下 DMA 映射的性能开销。

## 2. 核心功能

### 主要数据结构

- **`struct map_benchmark_data`**  
  封装测试上下文，包含：
  - `bparam`：用户传入的测试参数（线程数、测试时长、DMA 方向、粒度等）
  - `dev`：关联的设备结构体，用于 DMA 操作
  - `debugfs`：用于调试的 debugfs 条目
  - `dir`：转换后的 DMA 数据方向（`DMA_BIDIRECTIONAL` 等）
  - 多个 `atomic64_t` 字段用于线程安全地累积映射/解映射耗时及其平方值，以及循环次数

### 主要函数

- **`map_benchmark_thread(void *data)`**  
  内核线程主函数，循环执行以下操作：
  - 分配指定大小的内存缓冲区（按页对齐）
  - 若非 `DMA_FROM_DEVICE`，预填充缓冲区以模拟缓存污染
  - 调用 `dma_map_single()` 并记录耗时
  - 模拟 DMA 传输延迟（`ndelay`）
  - 调用 `dma_unmap_single()` 并记录耗时
  - 累加耗时（以 100 纳秒为单位）及其平方值，用于后续统计
  - 定期调用 `cond_resched()` 避免阻塞调度

- **`do_map_benchmark(struct map_benchmark_data *map)`**  
  启动并管理多个测试线程：
  - 根据参数创建指定数量的内核线程（可绑定到指定 NUMA 节点）
  - 重置统计计数器
  - 启动所有线程并休眠指定秒数
  - 停止所有线程并收集结果
  - 计算平均延迟和标准差（基于方差公式）

- **`map_benchmark_ioctl(struct file *file, unsigned int cmd, unsigned long arg)`**  
  用户空间 ioctl 接口处理函数：
  - 验证输入参数合法性（线程数、时长、NUMA 节点、粒度等）
  - 转换 DMA 方向枚举值
  - 临时设置设备的 `dma_mask`（测试完成后恢复原值）
  - 调用 `do_map_benchmark()` 执行测试
  - 将结果拷贝回用户空间

- **`__map_benchmark_probe(struct device *dev)`**  
  设备探测函数（代码片段未完整），负责初始化 `map_benchmark_data` 结构并关联设备。

## 3. 关键实现

- **高精度时间测量**  
  使用 `ktime_get()` 获取纳秒级时间戳，计算 `dma_map_single()` 和 `dma_unmap_single()` 的实际耗时。

- **统计方法**  
  为避免浮点运算，所有时间以 **100 纳秒** 为单位存储。通过累加时间和时间平方值，在测试结束后计算：
  - 平均值：`sum / loops`
  - 方差：`E[X²] - (E[X])²`
  - 标准差：使用 `int_sqrt64()` 计算整数平方根

- **缓存行为模拟**  
  对于 `DMA_BIDIRECTIONAL` 或 `DMA_TO_DEVICE`，在映射前填充缓冲区（`memset(buf, 0x66, size)`），以触发缓存写回，更真实地反映非一致性设备的开销。

- **DMA 掩码隔离**  
  测试期间临时修改设备的 `dma_mask`，测试结束后恢复原始值，避免影响设备正常驱动行为。

- **调度友好性**  
  在密集循环中调用 `cond_resched()`，防止在非抢占内核中因线程数 ≥ CPU 数而导致系统挂死。

- **NUMA 感知**  
  支持将测试线程绑定到指定 NUMA 节点，用于评估 NUMA 架构下的 DMA 性能差异。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/dma-mapping.h>`：提供 `dma_map_single`/`dma_unmap_single` 等核心 DMA API
  - `<linux/debugfs.h>`：用于创建调试接口（虽未在片段中完整体现）
  - `<linux/kthread.h>`：内核线程管理
  - `<linux/math64.h>`：64 位除法和平方根计算
  - `<linux/map_benchmark.h>`：定义用户接口结构体 `map_benchmark` 和 ioctl 命令（如 `DMA_MAP_BENCHMARK`）
  - 其他基础内核头文件（`slab.h`, `device.h`, `timekeeping.h` 等）

- **内核子系统**：
  - **DMA 子系统**：依赖底层架构（如 ARM64、x86）或总线（PCI、平台设备）提供的 DMA 映射实现
  - **调度子系统**：依赖 `kthread` 和 `cond_resched()` 机制
  - **内存管理**：使用 `alloc_pages_exact()` 分配连续物理内存

## 5. 使用场景

- **驱动开发与调优**：评估不同 DMA 映射策略（如一致性 vs 非一致性）的性能开销。
- **平台性能分析**：比较不同 SoC 或服务器平台的 IOMMU 或 DMA 引擎效率。
- **内核子系统验证**：测试 DMA 子系统在高并发场景下的稳定性与延迟表现。
- **NUMA 性能研究**：分析跨 NUMA 节点 DMA 操作的额外延迟。
- **回归测试**：在内核版本迭代中监控 DMA 映射性能是否退化。

该模块通常通过用户空间工具（如专用 benchmark 程序）打开 debugfs 或字符设备节点，传入测试参数后触发 ioctl 执行基准测试，并读取返回的统计结果。