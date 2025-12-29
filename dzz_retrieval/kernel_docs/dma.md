# dma.c

> 自动生成时间: 2025-10-25 13:09:28
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `dma.c`

---

# `dma.c` 技术文档

## 1. 文件概述

`dma.c` 是 Linux 内核中用于管理系统 DMA（Direct Memory Access，直接内存访问）通道分配的核心文件。它提供了一套简单的资源管理机制，允许多个设备驱动程序以互斥方式请求和释放有限的系统 DMA 通道资源。该实现灵感来源于 `irq.c`，主要用于传统的 ISA 架构下的 DMA 控制器（如 Intel 8237），在现代系统中主要用于兼容旧硬件或特定嵌入式平台。文件还支持通过 `/proc/dma` 接口向用户空间暴露当前 DMA 通道的使用情况。

## 2. 核心功能

### 主要数据结构

- **`struct dma_chan`**  
  表示一个 DMA 通道的状态：
  - `int lock`：标志位，非零表示通道已被占用。
  - `const char *device_id`：占用该通道的设备标识字符串，用于 `/proc/dma` 显示。

- **`dma_chan_busy[MAX_DMA_CHANNELS]`**  
  全局静态数组，记录每个 DMA 通道的占用状态。其中通道 4 被预设为 `"cascade"`（用于级联主从 DMA 控制器），并标记为已占用。

- **`dma_spin_lock`**  
  全局自旋锁（`DEFINE_SPINLOCK`），用于保护 DMA 通道分配/释放操作的原子性（尽管当前实现未显式使用该锁，但供外部模块使用）。

### 主要函数

- **`request_dma(unsigned int dmanr, const char *device_id)`**  
  请求指定编号的 DMA 通道。若通道有效且空闲，则标记为占用并记录设备 ID；否则返回 `-EINVAL`（通道号越界）或 `-EBUSY`（已被占用）。

- **`free_dma(unsigned int dmanr)`**  
  释放指定编号的 DMA 通道。若通道已被占用，则将其标记为空闲；若尝试释放未占用或无效通道，会打印警告信息。

- **`proc_dma_show(struct seq_file *m, void *v)`**  
  用于生成 `/proc/dma` 文件内容，遍历 `dma_chan_busy` 数组，输出所有被占用通道的编号及其设备 ID。

- **`proc_dma_init(void)`**  
  初始化函数，在内核启动时注册 `/proc/dma` 文件。

## 3. 关键实现

- **原子性保障**：  
  使用 `xchg()` 原子操作实现对 `dma_chan_busy[].lock` 的读-改-写，确保多 CPU 环境下 DMA 通道分配/释放的线程安全，避免竞态条件。

- **资源分配策略**：  
  采用简单的位标志数组管理通道状态。通道 4 固定保留用于 DMA 控制器级联（cascade），不可被普通设备申请。

- **条件编译支持**：  
  通过 `#ifdef MAX_DMA_CHANNELS` 判断平台是否支持传统 DMA。若未定义（如纯现代平台），则 `request_dma()` 直接返回 `-EINVAL`，`free_dma()` 为空操作。

- **/proc 接口**：  
  仅在 `CONFIG_PROC_FS` 启用时编译 `/proc/dma` 支持。使用 `proc_create_single()` 创建只读文件，通过 `seq_printf()` 安全输出通道使用信息。

- **资源释放顺序建议**：  
  注释中强调：若同时使用 DMA 和 IRQ，应先申请 IRQ 再申请 DMA，释放时则先释放 DMA 再释放 IRQ，以避免不必要的分配失败（尤其在引入更复杂同步机制后）。

## 4. 依赖关系

- **头文件依赖**：
  - `<asm/dma.h>`：定义平台相关的 `MAX_DMA_CHANNELS` 等宏。
  - `<linux/spinlock.h>`：提供自旋锁和原子操作支持。
  - `<linux/proc_fs.h>`、`<linux/seq_file.h>`：用于 `/proc/dma` 实现。
  - 其他通用内核头文件（如 `kernel.h`、`errno.h` 等）。

- **导出符号**：  
  通过 `EXPORT_SYMBOL` 导出以下符号供其他内核模块使用：
  - `request_dma`
  - `free_dma`
  - `dma_spin_lock`（虽未在本文件中使用，但供外部同步）

- **架构依赖**：  
  仅在定义了 `MAX_DMA_CHANNELS` 的架构（如 x86、部分 ARM 平台）上启用实际功能；否则提供空实现。

## 5. 使用场景

- **传统 ISA 设备驱动**：  
  如声卡（Sound Blaster）、软盘控制器、早期网卡等依赖 ISA DMA 通道的设备，在初始化时调用 `request_dma()` 获取通道，退出时调用 `free_dma()` 释放。

- **内核调试与监控**：  
  用户可通过 `cat /proc/dma` 查看当前系统中 DMA 通道的占用情况，辅助硬件调试或资源冲突排查。

- **嵌入式或兼容性平台**：  
  在仍使用传统 DMA 控制器的嵌入式系统中，作为底层 DMA 资源管理的基础组件。

- **资源协调**：  
  在多设备共享有限 DMA 通道的系统中，确保设备驱动按规范申请/释放资源，避免冲突。