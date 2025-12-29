# irq\autoprobe.c

> 自动生成时间: 2025-10-25 13:47:42
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\autoprobe.c`

---

# `irq/autoprobe.c` 技术文档

## 1. 文件概述

`irq/autoprobe.c` 实现了 Linux 内核中的中断自动探测（IRQ autodetection）机制。该机制用于在设备驱动程序无法预先知道其所使用的中断号时，动态探测硬件实际触发的中断线。文件提供了一组 API，允许驱动程序在安全、受控的环境下扫描并识别有效的中断请求（IRQ）线路。

## 2. 核心功能

### 主要函数

- **`probe_irq_on(void)`**  
  启动中断自动探测过程。激活所有可探测的未分配中断线，等待潜在中断触发，并返回一个位掩码，表示可能有效的低编号（<32）中断线。

- **`probe_irq_mask(unsigned long val)`**  
  扫描所有中断线，返回在指定掩码 `val` 范围内被触发的有效中断位图，并清理探测状态。

- **`probe_irq_off(unsigned long val)`**  
  结束中断探测，检查哪些中断线在探测期间被触发。若唯一中断被触发，返回其中断号；若多个中断被触发，返回负值表示冲突；若无中断触发，返回 0。

### 关键数据结构与状态标志

- **`IRQS_AUTODETECT`**：标记该中断正处于自动探测状态。
- **`IRQS_WAITING`**：表示该中断尚未被触发；若在探测期间被触发，此标志会被清除。
- **`probing_active`**：全局互斥锁（`mutex`），确保同一时间只有一个探测过程在进行。

## 3. 关键实现

### 探测流程

1. **准备阶段（`probe_irq_on`）**：
   - 调用 `async_synchronize_full()` 确保异步任务完成，避免干扰。
   - 获取 `probing_active` 互斥锁，防止并发探测。
   - 遍历所有中断描述符（`irq_desc`），对未分配（`!desc->action`）且允许探测（`irq_settings_can_probe`）的中断：
     - 若芯片支持，调用 `irq_set_type(..., IRQ_TYPE_PROBE)` 通知硬件进入探测模式。
     - 调用 `irq_activate_and_startup()` 激活并启用中断（不重发）。
   - 等待 20ms，让“陈旧”中断（longstanding irq）有机会触发并自屏蔽。

2. **正式探测阶段**：
   - 再次遍历中断描述符，为可探测中断设置 `IRQS_AUTODETECT | IRQS_WAITING`。
   - 重新激活中断（处理可能因陈旧中断而被屏蔽的情况）。
   - 等待 100ms，让真实硬件中断触发。

3. **结果收集与清理**：
   - 在 `probe_irq_off` 或 `probe_irq_mask` 中：
     - 检查哪些中断仍带有 `IRQS_AUTODETECT` 且 **未** 设置 `IRQS_WAITING`（即已被触发）。
     - 清除 `IRQS_AUTODETECT` 标志，并调用 `irq_shutdown_and_deactivate()` 关闭中断。
     - 根据触发中断的数量返回结果：唯一中断返回正号，多个返回负号，无触发返回 0。

### 并发控制

- 使用 `probing_active` 互斥锁保证探测过程的原子性。
- 所有对 `irq_desc` 的访问均在 `raw_spin_lock_irq()` 保护下进行，确保中断上下文安全。

### 硬件交互

- 支持通过 `irq_chip->irq_set_type()` 向中断控制器发送 `IRQ_TYPE_PROBE` 类型，使某些硬件（如 ISA 控制器）进入探测兼容模式。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/irq.h>`：IRQ 核心定义。
  - `<linux/interrupt.h>`：中断处理相关 API。
  - `<linux/delay.h>`：提供 `msleep()`。
  - `<linux/async.h>`：用于同步异步任务。
  - `"internals.h"`：包含 IRQ 子系统内部函数（如 `irq_activate_and_startup`、`irq_shutdown_and_deactivate`）。

- **内核子系统依赖**：
  - **IRQ 子系统核心**：依赖 `irq_desc` 管理、中断激活/关闭逻辑。
  - **中断控制器驱动**：依赖 `irq_chip` 回调（特别是 `irq_set_type`）。

## 5. 使用场景

- **传统 ISA/PnP 设备驱动**：在即插即用（PnP）或资源未知的旧硬件驱动中，用于动态确定设备使用的 IRQ 号。
- **调试与诊断工具**：内核调试时用于验证硬件中断线路是否正常工作。
- **模块化驱动初始化**：在 `module_init` 阶段，当设备资源未通过 ACPI/FDT 等机制明确指定时，作为后备探测手段。

> **注意**：现代设备通常通过设备树（Device Tree）、ACPI 或 PCI 配置空间明确指定中断号，因此该机制主要用于遗留硬件支持。文档中也指出，在模块中使用时存在并发风险，应避免重叠调用。