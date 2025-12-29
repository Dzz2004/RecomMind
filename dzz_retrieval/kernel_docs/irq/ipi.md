# irq\ipi.c

> 自动生成时间: 2025-10-25 13:58:10
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\ipi.c`

---

# `irq/ipi.c` 技术文档

## 1. 文件概述

`irq/ipi.c` 是 Linux 内核通用中断子系统（genirq）中用于管理处理器间中断（Inter-Processor Interrupt, IPI）的核心实现文件。该文件提供了一套统一的 API，用于在多核系统中动态分配、释放和发送 IPI。它抽象了底层硬件差异，支持两种 IPI 实现模式：
- **单硬件中断模式（single IPI）**：所有 CPU 共享同一个硬件中断号；
- **每 CPU 硬件中断模式（per-CPU IPI）**：每个 CPU 拥有独立的硬件中断号。

该文件为架构无关的 IPI 管理提供了基础支持，使上层驱动或核心代码能够以统一方式使用 IPI 功能。

## 2. 核心功能

### 主要函数

| 函数名 | 功能描述 |
|--------|--------|
| `irq_reserve_ipi()` | 为指定 CPU 掩码分配一个或多个 Linux 虚拟 IRQ（virq），用于后续发送 IPI |
| `irq_destroy_ipi()` | 释放之前通过 `irq_reserve_ipi()` 分配的 IPI 资源 |
| `ipi_get_hwirq()` | 获取指定 CPU 对应的硬件中断号（hwirq），用于协处理器通信等场景 |
| `__ipi_send_single()` | 向单个目标 CPU 发送 IPI（仅供架构或核心代码使用） |
| `__ipi_send_mask()` | 向多个目标 CPU（通过 cpumask 指定）发送 IPI（仅供架构或核心代码使用） |

### 辅助函数

- `ipi_send_verify()`：验证 IPI 发送参数的合法性（仅在 DEBUG 模式下启用完整检查）

### 关键数据结构字段（扩展）

- `struct irq_common_data::ipi_offset`：记录 IPI 分配时的起始 CPU 编号，用于 per-CPU 模式下计算偏移
- `IRQ_NO_BALANCING`：设置该标志防止中断负载均衡器迁移 IPI

## 3. 关键实现

### IPI 分配策略

- **单中断模式（`irq_domain_is_ipi_single`）**：
  - 无论目标 CPU 掩码包含多少 CPU，仅分配 **1 个 virq**
  - 底层 `irq_chip` 负责处理多 CPU 目标路由
  - 允许目标掩码存在“空洞”（非连续 CPU）

- **每 CPU 中断模式（`irq_domain_is_ipi_per_cpu`）**：
  - 为每个目标 CPU 分配独立的 virq（数量 = `cpumask_weight(dest)`）
  - **要求目标 CPU 掩码必须连续**（无空洞），否则返回 `-EINVAL`
  - 使用 `ipi_offset = cpumask_first(dest)` 作为基准偏移量

### 中断亲和性设置

在 `irq_reserve_ipi()` 中，为每个分配的 virq 设置：
```c
cpumask_copy(data->common->affinity, dest);
data->common->ipi_offset = offset;
irq_set_status_flags(virq + i, IRQ_NO_BALANCING);
```
确保中断仅在指定 CPU 上处理，且不会被内核的中断均衡机制迁移。

### IPI 发送机制

- 优先使用 `chip->ipi_send_mask()`（批量发送）
- 若不支持，则回退到循环调用 `chip->ipi_send_single()`
- 在 per-CPU 模式下，需根据目标 CPU 动态计算对应的 `irq_data`：
  ```c
  data = irq_get_irq_data(irq + cpu - data->common->ipi_offset);
  ```

### 错误处理与资源回收

- 分配失败时通过 `goto free_descs` 回收已分配的中断描述符
- 严格校验输入参数（如 CPU 掩码是否在 `cpu_possible_mask` 范围内）

## 4. 依赖关系

### 头文件依赖
- `<linux/irqdomain.h>`：提供 `irq_domain` 操作接口和 IPI 域类型判断宏（如 `irq_domain_is_ipi_*`）
- `<linux/irq.h>`：提供中断核心 API（如 `irq_alloc_descs`, `irq_get_irq_data` 等）

### 内核子系统依赖
- **通用中断子系统（genirq）**：依赖其虚拟 IRQ 管理、中断域（irqdomain）和中断芯片（irqchip）抽象
- **CPU 掩码操作**：依赖 `cpumask_*` 系列函数进行 CPU 集合操作
- **NUMA 支持**：使用 `NUMA_NO_NODE` 表示无特定 NUMA 节点偏好

### 导出符号
- `ipi_get_hwirq` 通过 `EXPORT_SYMBOL_GPL` 导出，供其他 GPL 模块使用

## 5. 使用场景

### 典型使用流程
1. **分配 IPI**：驱动或核心代码调用 `irq_reserve_ipi(domain, dest_mask)` 获取 virq
2. **注册处理函数**：使用 `request_irq()` 或 `irq_set_handler()` 设置 IPI 处理回调
3. **发送 IPI**：
   - 架构代码调用 `__ipi_send_single()` / `__ipi_send_mask()`
   - 或通过标准中断触发机制（如 `raise_softirq()` 底层可能使用 IPI）
4. **释放资源**：调用 `irq_destroy_ipi()` 释放 virq

### 具体应用场景
- **SMP 核心功能**：如调度器负载均衡、TLB 刷新、CPU 热插拔通知
- **自定义 IPI 驱动**：如某些 SoC 的私有消息传递机制
- **协处理器通信**：通过 `ipi_get_hwirq()` 获取 hwirq 供协处理器使用
- **实时内核扩展**：实现低延迟核间通信

> **注意**：`__ipi_send_*` 系列函数明确标注“**不可用于驱动代码**”，仅限可信的架构或核心代码调用，以避免安全性和稳定性问题。