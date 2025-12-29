# sched\sched-pelt.h

> 自动生成时间: 2025-10-25 16:15:27
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\sched-pelt.h`

---

# `sched/sched-pelt.h` 技术文档

## 1. 文件概述

`sched/sched-pelt.h` 是 Linux 内核调度器中用于实现 **PELT（Per-Entity Load Tracking，每实体负载跟踪）** 机制的头文件。该文件定义了 PELT 算法所需的关键常量和预计算的衰减系数表，用于高效计算任务和运行队列的负载贡献。PELT 是 CFS（完全公平调度器）中用于准确跟踪 CPU 负载和利用率的核心机制，支持负载均衡、能效调度（如 EAS）等高级调度功能。

## 2. 核心功能

本文件不包含函数定义，主要提供以下数据结构和宏定义：

- **`runnable_avg_yN_inv[]`**：一个预计算的 32 位无符号整型数组，存储 PELT 算法中用于指数衰减计算的倒数系数。
- **`LOAD_AVG_PERIOD`**：定义 PELT 负载计算的基本周期长度（单位为调度周期数），值为 32。
- **`LOAD_AVG_MAX`**：表示 PELT 负载值的理论最大值（约为 47742），用于归一化和防止溢出。

## 3. 关键实现

### PELT 衰减模型
PELT 将时间划分为 1ms 的调度周期（`SCHED_CAPACITY_SCALE` 相关），并假设负载在每个周期内呈指数衰减。负载贡献按如下方式累积：

$$
L(t) = L_0 \cdot y + L_1 \cdot y^2 + L_2 \cdot y^3 + \cdots
$$

其中 $ y = e^{-\Delta t / T} $，$ T $ 为时间常数（通常为 32ms），$ \Delta t $ 为周期长度（1ms）。因此 $ y \approx 0.96875 $。

### 预计算系数表
`runnable_avg_yN_inv[]` 数组存储的是 $ 1 / y^n $ 的 32 位定点数近似值（Q31 格式），用于在运行时通过乘法代替除法，加速衰减计算。例如：
- `runnable_avg_yN_inv[0] = 0xffffffff` 对应 $ 1 / y^0 = 1 $
- 后续项依次对应 $ 1 / y^1, 1 / y^2, \dots, 1 / y^{31} $

该表由脚本 `Documentation/scheduler/sched-pelt` 自动生成，确保精度与性能平衡。

### 负载归一化
- `LOAD_AVG_PERIOD = 32` 表示每 32 个调度周期（约 32ms）构成一个完整的衰减窗口。
- `LOAD_AVG_MAX = 47742` 是当实体持续 100% 可运行时，PELT 累积负载的稳态最大值，计算公式为：

$$
\text{LOAD\_AVG\_MAX} = \sum_{i=0}^{\infty} y^i \cdot \text{period\_contrib} \approx \frac{1024 - 1024 \cdot y^{32}}{1 - y}
$$

该值用于将原始负载值映射到 [0, 1024] 或 [0, SCHED_CAPACITY_SCALE] 的标准化范围。

## 4. 依赖关系

- **调度核心模块**：被 `kernel/sched/pelt.c` 和 `kernel/sched/fair.c` 包含，用于实现 `___update_load_avg()` 等负载更新函数。
- **调度类**：CFS 调度类（`struct sched_class` 的 `fair_sched_class`）依赖此文件进行任务和运行队列的负载跟踪。
- **能效调度（EAS）**：EAS 使用 PELT 提供的利用率信号进行 CPU 频率选择和任务放置。
- **负载均衡器**：`load_balance()` 等函数利用 PELT 负载值评估 CPU 间负载差异。

## 5. 使用场景

- **任务负载跟踪**：每个 `struct sched_entity` 使用 PELT 计算其对 CPU 的负载贡献。
- **运行队列负载聚合**：`struct cfs_rq` 聚合其下所有任务的 PELT 负载，用于负载均衡决策。
- **CPU 利用率估计**：为 CPUFreq 的 schedutil 调频策略提供实时利用率输入。
- **能效感知调度**：在异构多核系统（如 big.LITTLE）中，基于 PELT 利用率进行任务迁移以优化能效。
- **热插拔与 CPU 疲劳管理**：系统根据 PELT 负载动态启停 CPU 核心。