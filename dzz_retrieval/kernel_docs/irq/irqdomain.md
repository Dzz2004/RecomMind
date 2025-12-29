# irq\irqdomain.c

> 自动生成时间: 2025-10-25 14:00:54
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\irqdomain.c`

---

# `irq/irqdomain.c` 技术文档

## 1. 文件概述

`irq/irqdomain.c` 是 Linux 内核中断子系统的核心实现文件之一，负责管理 **中断域（IRQ Domain）** 的创建、注册、销毁及与硬件中断号（hwirq）到 Linux 虚拟中断号（virq）之间的映射机制。该文件为设备树（Device Tree）、ACPI 以及平台特定的中断控制器提供统一的抽象接口，使得不同架构和中断控制器能够以一致的方式集成到内核中断处理框架中。

## 2. 核心功能

### 主要数据结构

- **`struct irq_domain`**  
  表示一个中断域，包含：
  - `fwnode`：固件节点句柄（用于标识中断控制器）
  - `name`：域名称（用于调试和识别）
  - `ops`：操作回调函数集（如 `map`、`unmap`、`translate` 等）
  - `revmap_tree`：基数树（radix tree），用于 hwirq 到 virq 的反向映射
  - `revmap_size`：线性映射表大小（若使用线性映射）
  - `hwirq_max`：支持的最大硬件中断号
  - `flags`：域标志（如 `IRQ_DOMAIN_FLAG_NO_MAP`）
  - `root`：指向根域（用于层次化中断域）
  - `mutex`：保护域内部状态的互斥锁

- **`struct irqchip_fwid`**  
  封装非 OF/ACPI 的中断控制器固件节点（fwnode），用于命名和物理地址标识。

- **`irqchip_fwnode_ops`**  
  `fwnode_handle` 的操作接口，提供 `get_name` 方法。

### 主要函数

| 函数 | 功能 |
|------|------|
| `__irq_domain_alloc_fwnode()` | 为中断域分配一个 `fwnode_handle`，支持命名、命名+ID 或物理地址标识 |
| `irq_domain_free_fwnode()` | 释放由 `__irq_domain_alloc_fwnode()` 分配的 fwnode |
| `__irq_domain_create()` | 创建并初始化 `irq_domain` 结构体 |
| `__irq_domain_add()` | 创建并注册中断域到全局列表 |
| `irq_domain_remove()` | 从系统中移除并清理中断域 |
| `debugfs_add/remove_domain_dir()` | （调试）在 debugfs 中为域创建/移除目录 |

### 全局变量

- `irq_domain_list`：所有已注册中断域的链表
- `irq_domain_mutex`：保护 `irq_domain_list` 的互斥锁
- `irq_default_domain`：默认中断域（用于未指定域的中断分配）

## 3. 关键实现

### 中断域创建流程

1. **fwnode 处理**：
   - 支持 OF（设备树）、ACPI、软件节点及自定义 `irqchip_fwid` 类型。
   - 对于自定义命名类型（`IRQCHIP_FWNODE_NAMED` / `NAMED_ID`），动态分配名称字符串。
   - 对于路径含 `/` 的 fwnode（如 OF 节点路径），将其替换为 `:` 以兼容 debugfs。

2. **内存分配**：
   - 使用 `struct_size(domain, revmap, size)` 为线性映射表预留空间。
   - 根据 fwnode 所属 NUMA 节点进行内存分配（`of_node_to_nid`）。

3. **映射模式支持**：
   - **线性映射**：当 `size > 0` 时，使用数组直接索引。
   - **基数树映射**：默认使用 `radix_tree` 存储 hwirq → virq 映射。
   - **无映射（direct）**：当 `direct_max` 非零时，设置 `IRQ_DOMAIN_FLAG_NO_MAP`，virq = hwirq + 偏移。

4. **层次化中断域支持**：
   - 通过 `irq_domain_check_hierarchy()` 检查是否为层次化结构。
   - 所有子域共享根域的锁（`domain->root->mutex`）。

5. **注册与发布**：
   - 创建后调用 `__irq_domain_publish()`：
     - 加入全局 `irq_domain_list`
     - 在 debugfs 中创建调试目录（若启用 `CONFIG_GENERIC_IRQ_DEBUGFS`）

### 安全与校验

- 创建时校验参数合法性（如 `size` 与 `direct_max` 互斥）。
- 移除时检查 `revmap_tree` 是否为空，防止资源泄漏。
- 使用 `WARN_ON` 提示异常使用（如默认域被移除）。

## 4. 依赖关系

### 头文件依赖

- **中断核心**：`<linux/irq.h>`, `<linux/irqdesc.h>`, `<linux/interrupt.h>`
- **固件接口**：`<linux/of.h>`, `<linux/acpi.h>`, `<linux/fwnode.h>`（隐含）
- **内存管理**：`<linux/slab.h>`, `<linux/smp.h>`, `<linux/topology.h>`
- **调试支持**：`<linux/debugfs.h>`, `<linux/seq_file.h>`
- **同步机制**：`<linux/mutex.h>`

### 模块交互

- **设备树子系统**：通过 `of_irq_parse_raw()` 等函数解析中断属性，并调用 `irq_create_of_mapping()`（间接使用本文件接口）。
- **ACPI 子系统**：通过 `_CRS` 解析中断，并映射到对应域。
- **通用中断分配器**：`irq_alloc_descs()` 与域映射结合，完成 virq 分配。
- **debugfs**：提供 `/sys/kernel/debug/irq/domains/` 下的域信息展示。

## 5. 使用场景

1. **平台中断控制器驱动初始化**  
   如 GIC、MPIC、XICS 等驱动在 `probe()` 中调用 `irq_domain_add_*()` 创建域。

2. **设备树中断解析**  
   当设备节点包含 `interrupts` 属性时，OF 层调用 `irq_create_of_mapping()`，内部通过 `irq_find_matching_fwspec()` 查找对应域并映射。

3. **ACPI 中断处理**  
   ACPI 解析 `_CRS` 中的中断资源，通过 `acpi_register_gsi()` 最终映射到对应 IRQ 域。

4. **虚拟化与级联中断控制器**  
   支持层次化域（如虚拟中断控制器嵌套在物理控制器之上），通过 `irq_domain_create_hierarchy()` 实现。

5. **调试与诊断**  
   开启 `CONFIG_GENERIC_IRQ_DEBUGFS` 后，可通过 debugfs 查看各域的映射关系、状态及统计信息。