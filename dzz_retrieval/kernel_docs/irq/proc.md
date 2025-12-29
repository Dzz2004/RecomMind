# irq\proc.c

> 自动生成时间: 2025-10-25 14:06:44
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\proc.c`

---

# `irq/proc.c` 技术文档

## 1. 文件概述

`irq/proc.c` 是 Linux 内核中负责管理 `/proc/irq/` 目录下中断相关 proc 文件的实现模块。该文件提供了用户空间通过 `/proc` 文件系统查询和配置中断属性（如 CPU 亲和性、默认亲和性、中断统计信息等）的接口。其核心目标是在保证并发安全的前提下，暴露中断描述符（`irq_desc`）的关键信息，并允许用户动态调整中断的 CPU 亲和性策略。

## 2. 核心功能

### 主要数据结构
- `root_irq_dir`：指向 `/proc/irq` 根目录的 `proc_dir_entry` 指针。
- `no_irq_affinity`：全局标志，用于禁用所有中断亲和性设置（通常用于调试或特定架构）。

### 主要函数

#### 中断亲和性相关（SMP 环境）
- `show_irq_affinity()`：根据类型（AFFINITY/AFFINITY_LIST/EFFECTIVE/EFFECTIVE_LIST）格式化输出中断的 CPU 亲和性掩码。
- `irq_affinity_proc_show()` / `irq_affinity_list_proc_show()`：分别以十六进制位图或 CPU 列表格式显示当前中断的亲和性。
- `irq_affinity_proc_write()` / `irq_affinity_list_proc_write()`：解析用户输入并设置中断的 CPU 亲和性。
- `irq_affinity_hint_proc_show()`：显示中断的亲和性提示（`affinity_hint`）。
- `default_affinity_show()` / `default_affinity_write()`：读写全局默认中断亲和性掩码（`irq_default_affinity`）。
- `irq_node_proc_show()`：显示中断所属的 NUMA 节点编号。

#### 中断统计信息
- `irq_spurious_proc_show()`：输出中断的异常统计信息，包括总触发次数、未处理次数及上次未处理时间。

#### 工具函数
- `name_unique()`：检查新注册的中断处理程序名称在当前中断线上是否唯一（代码片段截断，但功能明确）。
- `irq_select_affinity_usr()`：在特定配置下（如 `CONFIG_AUTO_IRQ_AFFINITY`）尝试为中断自动选择合适的 CPU 亲和性。

#### 文件操作结构体
- `irq_affinity_proc_ops` / `irq_affinity_list_proc_ops`：定义 `/proc/irq/N/smp_affinity` 和 `/proc/irq/N/smp_affinity_list` 的文件操作。
- `default_affinity_proc_ops`：定义 `/proc/irq/default_smp_affinity` 的文件操作。

## 3. 关键实现

### 并发安全机制
- **中断描述符生命周期保护**：通过 `procfs` 自身的同步机制（`remove_proc_entry()` 阻塞新访问并等待现有操作完成）确保在 `/proc/irq/N/` 文件被访问期间，对应的 `irq_desc` 不会被释放。因此，在文件操作回调中调用 `irq_to_desc()` 是安全的。
- **中断描述符内部数据保护**：访问 `irq_desc` 内部字段（如 `affinity_hint`）时，使用 `desc->lock` 自旋锁进行保护。
- **全局中断列表保护**：访问 `/proc/interrupts` 时需使用 `sparse_irq_lock`（注释提及，但本文件未直接实现该文件）。

### 亲和性设置逻辑
- **有效性检查**：写入亲和性掩码时，强制要求至少包含一个在线 CPU（`cpumask_intersects(new_value, cpu_online_mask)`），防止系统因中断无法投递而挂起。
- **空掩码特殊处理**：若用户写入空掩码，尝试调用 `irq_select_affinity_usr()` 触发自动亲和性分配（仅在 `CONFIG_AUTO_IRQ_AFFINITY` 下有效），否则返回错误。
- **格式支持**：同时支持位图格式（`%pb`，用于 `smp_affinity`）和 CPU 列表格式（`%pbl`，用于 `smp_affinity_list`）的读写。

### 特性条件编译
- **SMP 支持**：大部分亲和性相关代码受 `CONFIG_SMP` 宏保护。
- **有效亲和性掩码**：`EFFECTIVE` 相关接口依赖 `CONFIG_GENERIC_IRQ_EFFECTIVE_AFF_MASK`。
- **自动亲和性**：`irq_select_affinity_usr()` 的行为由 `CONFIG_AUTO_IRQ_AFFINITY` 控制。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/irq.h>` / `<linux/interrupt.h>`：中断核心数据结构和 API。
  - `<linux/proc_fs.h>` / `<linux/seq_file.h>`：proc 文件系统和序列化文件操作。
  - `<linux/kernel_stat.h>`：内核统计信息（如中断计数）。
  - `"internals.h"`：中断子系统内部头文件，包含 `irq_to_desc()` 等内部函数。
- **内核配置依赖**：
  - `CONFIG_SMP`：多处理器支持（亲和性功能的前提）。
  - `CONFIG_GENERIC_PENDING_IRQ`：处理挂起的亲和性变更。
  - `CONFIG_GENERIC_IRQ_EFFECTIVE_AFF_MASK`：支持有效亲和性掩码。
  - `CONFIG_AUTO_IRQ_AFFINITY`：启用自动亲和性选择（历史遗留特性）。
- **其他模块**：
  - 依赖中断描述符管理模块（`irqdesc.c`）提供 `irq_to_desc()` 和 `irq_set_affinity()`。
  - 依赖 CPU 掩码操作（`cpumask_*`）和内存分配（`zalloc_cpumask_var`）。

## 5. 使用场景

- **系统监控**：用户通过读取 `/proc/irq/N/spurious` 诊断中断异常（如频繁未处理中断）。
- **性能调优**：管理员通过修改 `/proc/irq/N/smp_affinity` 或 `smp_affinity_list` 将特定中断绑定到指定 CPU，优化缓存局部性或隔离关键中断。
- **NUMA 优化**：通过 `/proc/irq/N/node` 了解中断与 NUMA 节点的关联，辅助内存和中断亲和性配置。
- **默认策略配置**：通过 `/proc/irq/default_smp_affinity` 设置新注册中断的默认 CPU 亲和性。
- **驱动调试**：验证中断处理程序名称唯一性（`name_unique`），避免命名冲突。