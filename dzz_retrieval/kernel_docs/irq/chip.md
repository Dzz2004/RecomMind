# irq\chip.c

> 自动生成时间: 2025-10-25 13:48:28
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\chip.c`

---

# `irq/chip.c` 技术文档

## 1. 文件概述

`irq/chip.c` 是 Linux 内核通用中断子系统（Generic IRQ）的核心实现文件之一，主要负责基于 `irq_chip` 抽象的中断控制器底层操作。该文件提供了中断芯片（IRQ chip）的注册、配置、启停、数据管理等基础接口，是架构无关的中断处理基础设施，为各种硬件中断控制器（如 GIC、APIC、MSI 等）提供统一的管理框架。

## 2. 核心功能

### 主要函数

| 函数名 | 功能说明 |
|--------|--------|
| `irq_set_chip()` | 为指定 IRQ 号绑定 `irq_chip` 操作结构体 |
| `irq_set_irq_type()` | 设置中断触发类型（电平/边沿触发等） |
| `irq_set_handler_data()` | 设置中断处理程序私有数据（`handler_data`） |
| `irq_set_chip_data()` | 设置中断芯片私有数据（`chip_data`） |
| `irq_set_msi_desc()` / `irq_set_msi_desc_off()` | 为 MSI/MSI-X 中断设置描述符 |
| `irq_get_irq_data()` | 获取指定 IRQ 的 `irq_data` 结构指针 |
| `irq_startup()` | 启动一个中断（调用 chip 的 `irq_startup` 或 `irq_enable`） |
| `irq_shutdown()` | 关闭一个中断（调用 chip 的 `irq_shutdown` 或 `irq_disable`） |
| `irq_activate()` | 激活中断（通常用于 IRQ domain 资源分配） |
| `irq_activate_and_startup()` | 组合激活并启动中断 |
| `irq_shutdown_and_deactivate()` | 组合关闭并去激活中断 |

### 关键数据结构

- **`chained_action`**：专用于级联中断（chained IRQ）的默认 `irqaction`，其处理函数 `bad_chained_irq` 会在错误调用时发出警告。
- **`struct irq_chip`**：中断控制器操作抽象，包含 `irq_startup`、`irq_shutdown`、`irq_enable`、`irq_disable` 等回调函数。
- **`struct irq_desc`**：中断描述符，包含中断状态、操作函数、私有数据等。
- **`struct irq_data`**：中断数据结构，嵌入在 `irq_desc` 中，包含 `chip`、`chip_data`、状态标志（如 `IRQD_IRQ_DISABLED`）等。

## 3. 关键实现

### 中断状态管理
- 使用 `irqd_set()` / `irqd_clear()` 操作 `irq_data` 中的状态位（如 `IRQD_IRQ_DISABLED`、`IRQD_IRQ_MASKED`、`IRQD_IRQ_STARTED`）。
- `irq_startup()` 和 `irq_shutdown()` 通过检查 `irqd_is_started()` 决定是否执行完整启停流程。

### 级联中断保护
- `chained_action` 的 `bad_chained_irq` 处理函数用于防止级联中断被误当作普通中断处理，确保级联中断仅由父中断控制器驱动调用。

### 管理型中断（Managed IRQ）支持
- 在 `CONFIG_SMP` 下，`__irq_startup_managed()` 检查中断是否为“管理型”（由内核自动管理 CPU 亲和性）。
- 若亲和性掩码中无在线 CPU，则进入 `IRQ_STARTUP_ABORT` 状态并设置 `IRQD_MANAGED_SHUTDOWN`，等待 CPU 热插拔事件重新启动。

### 启动流程
- `irq_startup()` 根据 `irq_chip` 是否提供 `irq_startup` 回调选择不同路径：
  - 有 `irq_startup`：调用该函数，并清除 `DISABLED` 和 `MASKED` 状态。
  - 无 `irq_startup`：调用通用 `irq_enable()`。
- 支持亲和性设置时机控制：通过 `IRQCHIP_AFFINITY_PRE_STARTUP` 标志决定在启动前还是启动后设置 CPU 亲和性。

### MSI 描述符管理
- `irq_set_msi_desc_off()` 支持为 MSI 中断组（base + offset）设置描述符，并在 offset 为 0 时更新 `msi_desc->irq` 字段。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/irq.h>`：定义 `irq_chip`、`irq_desc` 等核心结构。
  - `<linux/msi.h>`：MSI 相关定义。
  - `<linux/irqdomain.h>`：IRQ domain 支持。
  - `"internals.h"`：中断子系统内部接口。
- **模块依赖**：
  - 依赖通用中断子系统（Generic IRQ）的其他组件，如 `irqdesc.c`（描述符管理）、`irqdomain.c`（IRQ domain 映射）。
  - 与 CPU 热插拔子系统交互（管理型中断场景）。
  - 被各类中断控制器驱动（如 GIC、IOAPIC、MSI 驱动）调用以注册和配置中断。

## 5. 使用场景

- **中断控制器驱动初始化**：在平台或设备驱动中调用 `irq_set_chip()`、`irq_set_chip_data()` 等函数注册中断控制器操作。
- **中断类型配置**：设备驱动通过 `irq_set_irq_type()` 设置中断触发方式（如 `IRQ_TYPE_EDGE_RISING`）。
- **MSI/MSI-X 中断设置**：PCIe 驱动使用 `irq_set_msi_desc()` 关联 MSI 描述符与 IRQ 号。
- **中断启停控制**：内核在 `request_irq()` / `free_irq()` 或 `enable_irq()` / `disable_irq()` 路径中调用 `irq_startup()` / `irq_shutdown()`。
- **CPU 热插拔处理**：管理型中断在 CPU 上线/下线时自动启停，依赖本文件的 `__irq_startup_managed()` 逻辑。
- **级联中断实现**：父中断控制器使用 `chained_action` 作为占位符，防止子中断被错误处理。