# irq\matrix.c

> 自动生成时间: 2025-10-25 14:03:08
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\matrix.c`

---

# `irq/matrix.c` 技术文档

## 1. 文件概述

`irq/matrix.c` 实现了一个通用的中断位图（IRQ matrix）管理机制，用于在多 CPU 系统中高效地分配和管理中断向量（或中断位）。该机制支持两类中断分配：

- **普通分配（allocated）**：由设备驱动等动态申请的中断。
- **托管分配（managed）**：由内核子系统（如 MSI/MSI-X）预先保留、按需激活的中断。

该文件通过 per-CPU 的位图结构，结合全局状态跟踪，实现了跨 CPU 的中断资源分配、预留、释放和在线/离线管理，特别适用于中断向量数量有限（如 x86 的 256 个向量）的架构。

## 2. 核心功能

### 主要数据结构

- **`struct cpumap`**：每个 CPU 的本地中断位图状态
  - `available`：当前 CPU 可用的中断数量
  - `allocated`：已分配的普通中断数量
  - `managed` / `managed_allocated`：预留和已激活的托管中断数量
  - `alloc_map[]`：记录已分配的普通中断位
  - `managed_map[]`：记录预留的托管中断位
  - `initialized` / `online`：CPU 初始化和在线状态

- **`struct irq_matrix`**：全局中断矩阵控制结构
  - `matrix_bits`：总位图大小（≤ `IRQ_MATRIX_BITS`）
  - `alloc_start` / `alloc_end`：可分配范围
  - `global_available`：全局可用中断总数
  - `system_map[]`：系统保留位（如 APIC 自身使用的向量）
  - `maps`：指向 per-CPU `cpumap` 的指针
  - `scratch_map[]`：临时位图，用于分配时的合并计算

### 主要函数

| 函数 | 功能 |
|------|------|
| `irq_alloc_matrix()` | 分配并初始化一个 `irq_matrix` 结构 |
| `irq_matrix_online()` / `irq_matrix_offline()` | 将本地 CPU 的中断矩阵置为在线/离线状态 |
| `irq_matrix_assign_system()` | 在矩阵中保留系统级中断位（如 APIC 向量） |
| `irq_matrix_reserve_managed()` | 在指定 CPU 掩码上为托管中断预留位 |
| `irq_matrix_remove_managed()` | 移除托管中断的预留位 |
| `irq_matrix_alloc_managed()` | 从预留的托管中断中分配一个实际使用的中断 |
| `matrix_alloc_area()` | 内部辅助函数：在合并位图中查找连续空闲区域 |
| `matrix_find_best_cpu()` / `matrix_find_best_cpu_managed()` | 选择最优 CPU（基于可用数或托管分配数最少） |

## 3. 关键实现

### 位图合并分配策略
- 在分配中断时，`matrix_alloc_area()` 会临时合并三个位图：
  1. 当前 CPU 的 `managed_map`（托管预留）
  2. 全局 `system_map`（系统保留）
  3. 当前 CPU 的 `alloc_map`（已分配）
- 使用 `bitmap_find_next_zero_area()` 在合并后的位图中查找连续空闲区域，确保不会重复分配。

### 托管中断（Managed IRQ）机制
- **两阶段分配**：
  1. **预留（reserve）**：调用 `irq_matrix_reserve_managed()` 在多个 CPU 上各预留一个位（不一定对齐）。
  2. **激活（alloc）**：调用 `irq_matrix_alloc_managed()` 从预留位中选择一个未使用的位进行实际分配。
- **动态 CPU 选择**：`matrix_find_best_cpu_managed()` 优先选择 `managed_allocated` 最少的 CPU，实现负载均衡。

### 系统中断保留
- `irq_matrix_assign_system()` 用于保留如 x86 的 `IRQ0_VECTOR`（时钟中断）等关键系统向量。
- 通过 `BUG_ON()` 强制保证：系统中断只能在单 CPU 初始化阶段分配，防止运行时冲突。

### 在线/离线管理
- CPU 上线时，将其 `available` 计数加入 `global_available`。
- CPU 离线时，从全局计数中减去，但保留其位图数据（支持重新上线）。

### 跟踪与调试
- 集成 `trace/events/irq_matrix.h`，提供分配、预留、系统保留等关键操作的 tracepoint，便于调试中断分配问题。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/bitmap.h>`：位图操作（`bitmap_set`, `bitmap_find_next_zero_area` 等）
  - `<linux/percpu.h>`：Per-CPU 变量支持
  - `<linux/cpu.h>`：CPU 在线/离线状态
  - `<linux/irq.h>`：中断子系统基础定义
  - `<trace/events/irq_matrix.h>`：自定义 tracepoint

- **内核子系统**：
  - **中断子系统**：作为底层分配器，被 `irqdomain`、MSI/MSI-X 驱动等使用。
  - **x86 APIC 驱动**：典型使用者，用于管理 256 个中断向量的分配（如 `kernel/irq/vector.c`）。

## 5. 使用场景

- **x86 中断向量管理**：在 `CONFIG_X86_IO_APIC` 或 `CONFIG_X86_LOCAL_APIC` 下，用于分配 IRQ 向量（0-255），区分系统向量、普通设备中断和 MSI 中断。
- **MSI/MSI-X 中断分配**：PCIe 设备的 MSI 中断通过托管机制预留和分配，确保每个设备在多个 CPU 上有可用向量。
- **CPU 热插拔**：支持 CPU 动态上线/下线时的中断资源重新平衡。
- **中断负载均衡**：通过 `matrix_find_best_cpu*` 函数，在多 CPU 间均匀分配中断，避免单 CPU 向量耗尽。