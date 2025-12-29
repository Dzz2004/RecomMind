# irq\affinity.c

> 自动生成时间: 2025-10-25 13:46:53
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\affinity.c`

---

# `irq/affinity.c` 技术文档

## 1. 文件概述

`irq/affinity.c` 是 Linux 内核中用于管理中断亲和性（IRQ affinity）的核心实现文件，主要负责为多队列设备（如多队列网卡、NVMe SSD 等）动态生成合理的 CPU 亲和性掩码（cpumask），以实现中断在多个 CPU 核心上的均衡分布。该文件提供了两个关键接口：  
- `irq_create_affinity_masks()`：根据设备需求和系统 CPU 拓扑，生成每中断向量对应的 CPU 亲和性掩码。  
- `irq_calc_affinity_vectors()`：计算在给定约束下可有效用于亲和性分配的最优中断向量数量。  

该机制支持将中断向量划分为多个“集合”（sets），每个集合可独立分配 CPU 资源，适用于需要分层或分组中断处理的复杂设备。

## 2. 核心功能

### 主要函数

- **`irq_create_affinity_masks(unsigned int nvecs, struct irq_affinity *affd)`**  
  为指定数量的中断向量生成亲和性掩码数组。支持预定义（pre_vectors）、可管理（managed）和后置（post_vectors）三类中断向量，并通过 `group_cpus_evenly()` 实现 CPU 均匀分配。

- **`irq_calc_affinity_vectors(unsigned int minvec, unsigned int maxvec, const struct irq_affinity *affd)`**  
  在 `[minvec, maxvec]` 范围内计算可用于亲和性分配的最优中断向量总数，考虑设备保留向量和系统 CPU 数量限制。

### 关键数据结构

- **`struct irq_affinity`**（定义于 `<linux/interrupt.h>`）  
  描述中断亲和性分配需求：
  - `pre_vectors` / `post_vectors`：保留的前后固定向量数（通常用于管理或特殊用途）。
  - `calc_sets`：回调函数，用于自定义如何将可分配向量划分为多个集合（sets）。
  - `nr_sets` / `set_size[]`：由 `calc_sets` 填充，表示集合数量及每个集合的向量数。

- **`struct irq_affinity_desc`**（定义于 `<linux/interrupt.h>`）  
  单个中断向量的亲和性描述：
  - `mask`：该向量绑定的 CPU 掩码。
  - `is_managed`：标志位，表示该向量是否由内核自动管理亲和性。

### 辅助函数

- **`default_calc_sets(struct irq_affinity *affd, unsigned int affvecs)`**  
  默认的集合划分策略：将所有可分配向量归入单个集合。

## 3. 关键实现

### 亲和性掩码生成流程（`irq_create_affinity_masks`）

1. **计算可分配向量数**：  
   `affvecs = nvecs - pre_vectors - post_vectors`，若结果 ≤0 则无需分配。

2. **设置集合划分策略**：  
   若用户未提供 `calc_sets` 回调，则使用 `default_calc_sets`（单集合）。

3. **生成每集合的 CPU 掩码**：  
   对每个集合调用 `group_cpus_evenly(this_vecs)`，该函数根据系统 CPU 拓扑（如 NUMA、超线程）将 `this_vecs` 个中断均匀分配到物理 CPU 上，返回一个 `cpumask` 数组。

4. **填充掩码数组**：  
   - 前 `pre_vectors` 个向量：使用全局默认亲和性 `irq_default_affinity`。
   - 中间 `affvecs` 个向量：按集合依次填充 `group_cpus_evenly` 的结果。
   - 后 `post_vectors` 个向量：同样使用默认亲和性。
   - 标记 `pre_vectors` 到 `nvecs - post_vectors` 之间的向量为 `is_managed = 1`。

### 向量数量计算（`irq_calc_affinity_vectors`）

- 若设备保留向量数（`resv = pre + post`）超过 `minvec`，返回 0（无法满足最小需求）。
- 若提供 `calc_sets` 回调，则最大可分配向量数为 `maxvec - resv`。
- 否则，以系统可能 CPU 数（`cpu_possible_mask`）为上限。
- 最终结果：`resv + min(可分配向量上限, maxvec - resv)`。

### 错误处理

- 集合数超过 `IRQ_AFFINITY_MAX_SETS`（通常为 4）时触发 `WARN_ON_ONCE` 并返回 `NULL`。
- 内存分配失败或 `group_cpus_evenly` 失败时释放已分配资源并返回 `NULL`。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/interrupt.h>`：定义 `irq_affinity`、`irq_affinity_desc` 等核心结构。
  - `<linux/group_cpus.h>`：提供 `group_cpus_evenly()` 函数，实现基于拓扑的 CPU 分组。
  - `<linux/cpu.h>`：访问 CPU 掩码（如 `cpu_possible_mask`）和锁机制（`cpus_read_lock/unlock`）。
  - `<linux/slab.h>`：内存分配（`kcalloc`/`kfree`）。
  - `<linux/kernel.h>`：基础内核 API（如 `WARN_ON_ONCE`、`min` 宏）。

- **内核子系统**：
  - **中断子系统**：与 `irqdesc`、`irqdomain` 等模块协同工作。
  - **CPU 拓扑管理**：依赖 `group_cpus_evenly` 的底层实现（位于 `kernel/cpu.c`），该函数利用调度域（sched domain）信息进行 CPU 分组。

## 5. 使用场景

- **多队列设备驱动初始化**：  
  网卡（如 `ixgbe`、`mlx5`）、NVMe SSD 等驱动在申请 MSI-X 中断时，调用 `irq_create_affinity_masks` 生成亲和性掩码，再通过 `pci_alloc_irq_vectors_affinity()` 申请中断，实现中断在 CPU 间的负载均衡。

- **动态中断向量调整**：  
  设备在运行时调整队列数量时，通过 `irq_calc_affinity_vectors` 计算可用向量数，确保不超过硬件和系统限制。

- **NUMA 感知中断分配**：  
  `group_cpus_evenly` 自动考虑 NUMA 节点拓扑，使同一队列的中断优先分配到同一 NUMA 节点的 CPU，减少跨节点访问延迟。

- **保留中断向量处理**：  
  设备可保留部分向量用于管理任务（如 `pre_vectors` 用于控制队列，`post_vectors` 用于错误处理），其余向量交由内核自动分配亲和性。