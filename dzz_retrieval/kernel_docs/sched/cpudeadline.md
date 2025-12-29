# sched\cpudeadline.c

> 自动生成时间: 2025-10-25 16:02:17
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\cpudeadline.c`

---

# `sched/cpudeadline.c` 技术文档

## 1. 文件概述

`sched/cpudeadline.c` 是 Linux 内核调度器中用于 **全局 CPU 截止时间（Deadline）管理** 的核心实现文件。该文件维护一个 **最大堆（max-heap）数据结构**，用于高效追踪系统中所有运行 SCHED_DEADLINE 任务的 CPU 上 **最早截止时间（earliest deadline）** 的任务信息。通过此结构，调度器可快速找到最适合迁移或唤醒 deadline 任务的目标 CPU，从而满足实时调度的截止时间约束。

## 2. 核心功能

### 主要数据结构
- **`struct cpudl`**：CPU 截止时间管理上下文，包含：
  - `elements[]`：堆数组，每个元素为 `struct cpudl_item`，记录 CPU ID 和其上最早 deadline
  - `size`：堆中有效元素数量
  - `free_cpus`：位图，标记当前无 deadline 任务的 CPU
  - `lock`：保护堆操作的自旋锁
- **`struct cpudl_item`**：堆中单个元素，包含：
  - `cpu`：CPU ID
  - `dl`：该 CPU 上最早 deadline 时间戳
  - `idx`：该 CPU 在堆中的索引（用于快速定位）

### 主要函数
| 函数 | 功能描述 |
|------|----------|
| `cpudl_init()` / `cpudl_cleanup()` | 初始化/销毁 `cpudl` 结构 |
| `cpudl_set()` | 更新指定 CPU 的最早 deadline，并维护堆性质 |
| `cpudl_clear()` | 从堆中移除指定 CPU（如 CPU 下线或无 deadline 任务） |
| `cpudl_find()` | 查找满足任务截止时间约束的最佳 CPU |
| `cpudl_set_freecpu()` / `cpudl_clear_freecpu()` | 设置/清除 CPU 的“空闲”状态（无 deadline 任务） |
| `cpudl_heapify_up()` / `cpudl_heapify_down()` | 堆调整函数，维护最大堆性质 |

## 3. 关键实现

### 堆结构设计
- 使用 **数组实现的最大堆**，堆顶（`elements[0]`）始终保存 **系统中最早的 deadline**。
- 每个 CPU 在堆中有唯一索引（`idx`），支持 **O(log n)** 时间复杂度的插入、删除和更新操作。
- 堆比较基于 `dl_time_before(a, b)` 宏（定义在 `sched/deadline.h`），判断 `a` 是否早于 `b`。

### 核心操作逻辑
- **`cpudl_set()`**：
  - 若 CPU 首次加入堆（`idx == IDX_INVALID`），将其插入堆尾并上滤（`heapify_up`）。
  - 否则直接更新 deadline 值，并根据新旧值关系选择上滤或下滤（`heapify`）。
- **`cpudl_clear()`**：
  - 用堆尾元素覆盖待删除元素，缩小堆大小，再调整堆结构。
  - 将 CPU 标记为“空闲”（加入 `free_cpus` 位图）。
- **`cpudl_find()`**：
  - **优先使用 `free_cpus`**：若存在空闲 CPU 且满足任务亲和性，则从中选择。
    - 在异构系统（`sched_asym_cpucap_active()`）中，进一步筛选满足任务计算能力需求（`dl_task_fits_capacity()`）的 CPU。
    - 若无满足条件的空闲 CPU，则选择能力最强的 CPU。
  - **回退到堆顶 CPU**：若无空闲 CPU，则检查堆顶 CPU 的 deadline 是否晚于任务 deadline，若是则选择该 CPU。

### 并发控制
- 所有堆操作均通过 `raw_spin_lock_irqsave()` 保护，确保多 CPU 环境下的数据一致性。
- 调用者需持有对应 CPU 的运行队列锁（`cpu_rq(cpu)->lock`），避免与调度器主逻辑冲突。

## 4. 依赖关系

- **头文件依赖**：
  - `linux/sched.h`：`task_struct`, `cpumask`
  - `linux/sched/deadline.h`：`sched_dl_entity`, `dl_time_before()`, `dl_task_fits_capacity()`
  - `linux/cpumask.h`：CPU 位图操作
  - `linux/kernel.h`：`kcalloc()`, `WARN_ON()`
- **功能依赖**：
  - **SCHED_DEADLINE 调度类**：提供 deadline 任务的核心调度逻辑。
  - **CPU 拓扑与能力模型**：`arch_scale_cpu_capacity()` 用于异构系统 CPU 能力评估。
  - **调度域（sched_domain）**：`free_cpus` 的管理与调度域 CPU 列表关联。

## 5. 使用场景

- **Deadline 任务负载均衡**：
  - 当新 deadline 任务被创建或唤醒时，`find_later_rq()` 调用 `cpudl_find()` 选择迁移目标 CPU。
- **CPU 热插拔**：
  - CPU 下线时调用 `cpudl_clear()` 移除其 deadline 信息。
  - CPU 上线时通过 `cpudl_set_freecpu()` 标记为空闲。
- **任务迁移**：
  - 调度器在跨 CPU 迁移 deadline 任务前，通过 `cpudl_find()` 验证目标 CPU 的 deadline 约束。
- **异构系统优化**：
  - 在 ARM big.LITTLE 等架构中，结合 CPU 计算能力筛选满足任务需求的 CPU，避免小核过载。