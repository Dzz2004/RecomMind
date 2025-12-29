# sched\pelt.c

> 自动生成时间: 2025-10-25 16:13:26
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\pelt.c`

---

# `sched/pelt.c` 技术文档

## 1. 文件概述

`sched/pelt.c` 实现了 **Per-Entity Load Tracking（PELT）** 机制，这是 Linux 内核 CFS（Completely Fair Scheduler）调度器中用于精确跟踪每个调度实体（如任务或任务组）负载、可运行性和 CPU 利用率的核心算法。  
PELT 将时间划分为约 1ms（1024ns）的周期段，使用指数衰减的几何级数对历史负载进行加权求和，使得近期负载权重更高，远期负载影响逐渐衰减。该机制为负载均衡、能效调度（如 EAS）和 CPU 频率调节等子系统提供关键的负载指标。

## 2. 核心功能

### 主要函数

- `decay_load(u64 val, u64 n)`  
  计算负载值 `val` 经过 `n` 个时间单位后的衰减值，利用预计算的衰减系数表和位移优化实现高效指数衰减。

- `__accumulate_pelt_segments(u64 periods, u32 d1, u32 d3)`  
  计算跨越多个完整周期时，负载贡献的三部分之和：上一周期剩余部分（d1）、中间完整周期总和（d2）、当前周期已过部分（d3）。

- `accumulate_sum(u64 delta, struct sched_avg *sa, unsigned long load, unsigned long runnable, int running)`  
  核心累加函数，根据时间增量 `delta` 更新 `load_sum`、`runnable_sum` 和 `util_sum`，处理跨周期衰减与新贡献累加。

- `___update_load_sum(u64 now, struct sched_avg *sa, unsigned long load, unsigned long runnable, int running)`  
  入口函数，计算自上次更新以来的时间差，调用 `accumulate_sum` 更新负载总和，并处理时间回退等异常情况。

- `___update_load_avg(struct sched_avg *sa, unsigned long load)`  
  根据当前 `*_sum` 值和动态除数（divider）计算并更新 `load_avg`、`runnable_avg` 和 `util_avg`。

### 关键数据结构

- `struct sched_avg`  
  存储 PELT 相关状态，包括：
  - `load_sum` / `runnable_sum` / `util_sum`：衰减加权后的负载总和
  - `load_avg` / `runnable_avg` / `util_avg`：归一化后的平均负载值
  - `last_update_time`：上次更新时间戳
  - `period_contrib`：当前周期内已累积的时间（<1024ns）

## 3. 关键实现

### 时间分段与衰减模型
- 时间以 **1024ns（≈1μs）** 为基本单位，每 **1024 单位（≈1ms）** 构成一个 PELT 周期。
- 衰减因子 `y` 满足 `y^32 ≈ 0.5`，即约 32ms 前的负载贡献衰减至当前的一半。
- 负载历史表示为几何级数：`u₀ + u₁·y + u₂·y² + ...`，其中 `uᵢ` 是第 `i` 个周期内的可运行比例。

### 高效衰减计算
- `decay_load()` 利用 `y^32 = 1/2` 的特性，将 `y^n` 拆分为 `1/2^(n/32) * y^(n%32)`。
- 通过右移操作快速计算 `1/2^k` 部分，再查表 `runnable_avg_yN_inv[]` 获取 `y^(n%32)` 的倒数，结合 `mul_u64_u32_shr` 完成乘法。

### 负载累加三段式
当时间增量跨越多个周期时，负载贡献分为：
1. **d1**：上一周期未完成部分（`1024 - period_contrib`）
2. **d2**：中间完整周期的理论最大贡献（`LOAD_AVG_MAX - decay_load(LOAD_AVG_MAX, periods) - 1024`）
3. **d3**：当前周期已过部分（`delta % 1024`）

### 动态归一化
- 使用 `get_pelt_divider()` 获取当前周期位置对应的归一化除数，避免因周期未结束导致的平均值震荡。
- 除数公式：`LOAD_AVG_MAX - 1024 + period_contrib`，确保最大负载值在 `[1002, 1024)` 区间稳定。

### 状态一致性保障
- 若 `load == 0`，强制 `runnable = running = 0`，避免已出队实体产生无效贡献。
- 时间回退（如 TSC 切换）时直接重置 `last_update_time`，防止负时间差导致异常。

## 4. 依赖关系

- **头文件依赖**：  
  依赖 `kernel/sched/sched.h` 中定义的 `struct sched_avg`、`SCHED_CAPACITY_SHIFT`、`LOAD_AVG_*` 常量及 `get_pelt_divider()` 等辅助函数。
- **预计算表**：  
  使用外部定义的 `runnable_avg_yN_inv[32]` 衰减系数表（通常在 `fair.c` 或 `pelt.h` 中初始化）。
- **调度器集成**：  
  被 `fair.c` 中的 CFS 调度实体（`sched_entity`）和 CFS 运行队列（`cfs_rq`）调用，用于更新任务/任务组的负载状态。
- **能效调度**：  
  为 Energy Aware Scheduling (EAS) 提供 `util_avg` 作为 CPU 需求预测依据。

## 5. 使用场景

- **任务负载跟踪**：  
  每个 `task_struct` 的 `sched_entity` 通过 PELT 实时更新其 `load_avg` 和 `util_avg`，反映任务对 CPU 的历史需求。
- **任务组调度**：  
  CFS 任务组（`task_group`）的 `cfs_rq` 使用 PELT 聚合子任务的负载，实现层级化负载均衡。
- **负载均衡决策**：  
  `load_balance()` 等函数依据 `runnable_avg` 判断 CPU 间负载差异，触发任务迁移。
- **CPU 频率调节**：  
  CPUFreq 的 `schedutil` 调速器使用 `util_avg` 动态调整 CPU 频率，平衡性能与功耗。
- **空闲负载处理**：  
  在 `idle_balance()` 等场景中，即使任务已出队，仍需通过 PELT 正确衰减其历史负载贡献。