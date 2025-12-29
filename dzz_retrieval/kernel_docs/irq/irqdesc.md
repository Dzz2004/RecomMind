# irq\irqdesc.c

> 自动生成时间: 2025-10-25 13:59:49
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\irqdesc.c`

---

# `irq/irqdesc.c` 技术文档

## 1. 文件概述

`irq/irqdesc.c` 是 Linux 内核通用中断子系统（Generic IRQ）的核心实现文件之一，负责中断描述符（`struct irq_desc`）的分配、初始化、管理和释放。该文件实现了中断描述符的生命周期管理，包括在稀疏 IRQ（`CONFIG_SPARSE_IRQ`）配置下的动态分配机制，以及与 SMP（对称多处理）相关的中断亲和性（affinity）管理。它为上层中断处理（如设备驱动注册中断处理函数）和底层硬件中断控制器（通过 `irq_chip`）之间提供了统一的抽象层。

## 2. 核心功能

### 主要数据结构
- **`struct irq_desc`**：中断描述符，代表一个逻辑中断号（IRQ number），包含中断状态、处理函数、统计信息、锁、亲和性掩码等。
- **`struct irq_data`**：嵌入在 `irq_desc` 中，包含与硬件中断控制器相关的数据（如 `irq_chip`、`hwirq`、`irq_domain` 等）。
- **`struct irq_common_data`**：`irq_desc` 和 `irq_data` 共享的数据，如 MSI 描述符、亲和性掩码等。
- **`sparse_irqs`**：基于 Maple Tree 的稀疏 IRQ 描述符存储结构，用于动态分配 IRQ 号。

### 主要函数
- **`init_desc()`**：初始化一个 `irq_desc` 实例，包括分配 per-CPU 统计结构、SMP 掩码、初始化锁和默认值。
- **`desc_set_defaults()`**：设置 `irq_desc` 的默认初始状态（如禁用、屏蔽、默认处理函数为 `handle_bad_irq`）。
- **`alloc_masks()` / `free_masks()` / `desc_smp_init()`**：SMP 相关的亲和性掩码（affinity、effective_affinity、pending_mask）的分配、释放和初始化。
- **`irq_find_free_area()` / `irq_find_at_or_after()`**：在稀疏 IRQ 模式下查找可用的 IRQ 号范围或下一个可用 IRQ。
- **`irq_insert_desc()` / `delete_irq_desc()`**：将 `irq_desc` 插入或从稀疏 IRQ 的 Maple Tree 中删除。
- **`init_irq_default_affinity()`**：初始化默认的中断亲和性掩码（通常为所有 CPU）。
- **`irq_kobj_release()` 及相关 sysfs 属性函数**：实现 IRQ 描述符的 sysfs 接口（如 `per_cpu_count`、`chip_name`、`hwirq` 等）。

### 全局变量
- **`nr_irqs`**：系统支持的最大 IRQ 数量，可被平台代码覆盖。
- **`irq_default_affinity`**：默认的中断亲和性 CPU 掩码（SMP 模式下）。
- **`irq_desc_lock_class`**：用于 lockdep 的 IRQ 描述符自旋锁的统一锁类。

## 3. 关键实现

### 稀疏 IRQ 管理（`CONFIG_SPARSE_IRQ`）
- 使用 **Maple Tree** 数据结构（`sparse_irqs`）替代传统的静态数组，支持动态分配 IRQ 描述符。
- `irq_find_free_area()` 利用 Maple Tree 的空闲区间查找功能，高效分配连续的 IRQ 号。
- `irq_insert_desc()` 和 `delete_irq_desc()` 通过 RCU 安全地插入/删除描述符，支持运行时 IRQ 的动态增删。
- 每个 `irq_desc` 作为独立的 kobject，通过 sysfs 暴露属性（如中断计数、芯片名称等）。

### SMP 中断亲和性
- **亲和性掩码**：每个 IRQ 可配置其允许运行的 CPU 集合（`affinity`），支持负载均衡和局部性优化。
- **有效亲和性**（`effective_affinity`）：实际生效的亲和性（可能受中断迁移或 pending 状态影响）。
- **Pending 掩码**（`pending_mask`）：用于在中断迁移过程中暂存中断事件。
- 启动参数 `irqaffinity=` 可设置全局默认亲和性，但至少包含引导 CPU 以防配置错误。

### 描述符初始化
- `init_desc()` 完成描述符的完整初始化：
  - 分配 per-CPU 中断统计结构（`kstat_irqs`）。
  - 初始化 SMP 相关掩码（若启用）。
  - 设置自旋锁（带 lockdep 类）和互斥锁（`request_mutex`）。
  - 调用 `desc_set_defaults()` 设置默认状态（禁用、屏蔽、无效处理函数）。
  - 初始化 RCU 回调（用于稀疏 IRQ 的延迟释放）。

### 锁与并发控制
- **`desc->lock`**：raw spinlock，保护描述符关键字段（如状态、处理函数），在中断上下文中使用。
- **`desc->request_mutex`**：mutex，用于串行化中断请求/释放操作（如 `request_irq()`）。
- **Maple Tree 操作**：通过外部互斥锁（`sparse_irq_lock`）和 RCU 保证并发安全。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/irq.h>`、`<linux/interrupt.h>`：IRQ 子系统核心 API 和数据结构。
  - `<linux/irqdomain.h>`：硬件中断号（hwirq）到逻辑 IRQ 号的映射。
  - `<linux/maple_tree.h>`：稀疏 IRQ 的底层存储实现。
  - `<linux/sysfs.h>`：sysfs 属性支持。
  - `"internals.h"`：IRQ 子系统内部函数和宏。
- **配置依赖**：
  - `CONFIG_SMP`：启用多处理器支持（亲和性掩码管理）。
  - `CONFIG_SPARSE_IRQ`：启用动态 IRQ 分配（替代静态数组）。
  - `CONFIG_GENERIC_PENDING_IRQ` / `CONFIG_GENERIC_IRQ_EFFECTIVE_AFF_MASK`：扩展的 SMP 中断管理功能。
- **模块交互**：
  - **中断控制器驱动**：通过 `irq_chip` 操作硬件，依赖 `irq_desc` 提供的抽象。
  - **设备驱动**：通过 `request_irq()` 等接口注册中断处理函数，操作 `irq_desc`。
  - **电源管理**：通过 `wakeup` 属性控制中断的唤醒能力。

## 5. 使用场景

- **系统启动阶段**：
  - 初始化默认中断亲和性（`init_irq_default_affinity()`）。
  - 预分配或动态创建平台所需的 IRQ 描述符（通过 `alloc_descs()` 等）。
- **设备驱动加载/卸载**：
  - 动态分配 IRQ 描述符（稀疏 IRQ 模式下通过 `irq_alloc_desc()`）。
  - 注册/注销中断处理函数（修改 `handle_irq` 和 action 链表）。
- **运行时中断管理**：
  - 修改中断亲和性（`/proc/irq/<n>/smp_affinity`）。
  - 查询中断统计信息（`/proc/interrupts`，通过 per-CPU 计数）。
  - 通过 sysfs 查看 IRQ 属性（芯片名称、硬件 IRQ 号、触发类型等）。
- **中断迁移**（SMP）：
  - 在 CPU 热插拔或负载均衡时，更新 `affinity` 和 `pending_mask`。
- **错误处理**：
  - 未处理的中断由 `handle_bad_irq` 处理，记录到 `irqs_unhandled`。