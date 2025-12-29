# sched\loadavg.c

> 自动生成时间: 2025-10-25 16:11:54
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\loadavg.c`

---

# `sched/loadavg.c` 技术文档

## 1. 文件概述

`sched/loadavg.c` 是 Linux 内核中负责计算**全局系统负载平均值**（load average）的核心实现文件。该文件通过分布式、异步的方式高效地维护三个时间窗口（1分钟、5分钟、15分钟）的系统负载平均值，用于反映系统中处于运行态（`nr_running`）和不可中断睡眠态（`nr_uninterruptible`）的任务数量。尽管负载平均值在技术上是一个“粗略估计”，但它被广泛用于系统监控、调度决策和用户感知的系统繁忙程度评估。

该实现特别针对**大规模多核系统**和**无滴答**（tickless，即 `NO_HZ`）内核进行了优化，以最小化计算开销并保证在节能模式下的准确性。

## 2. 核心功能

### 主要全局变量
- `atomic_long_t calc_load_tasks`：用于累积所有 CPU 上活跃任务数的全局原子变量。
- `unsigned long calc_load_update`：记录下一次负载计算更新的时间点（基于 `jiffies`）。
- `unsigned long avenrun[3]`：存储三个时间窗口（1/5/15 分钟）的负载平均值，已导出供外部模块使用（注释建议移除导出）。

### 主要函数
- `get_avenrun(unsigned long *loads, unsigned long offset, int shift)`  
  获取当前负载平均值数组，支持偏移和左移操作，用于适配不同精度需求（如 `/proc/loadavg` 输出）。
- `calc_load_fold_active(struct rq *this_rq, long adjust)`  
  计算当前 CPU 运行队列上活跃任务数（`nr_running + nr_uninterruptible`）相对于上次采样的变化量（delta），用于增量更新全局负载。
- `fixed_power_int(unsigned long x, unsigned int frac_bits, unsigned int n)`  
  高效计算定点数的整数次幂（`x^n`），采用二分幂算法（O(log n)），用于负载衰减因子的指数运算。
- `calc_load_n(unsigned long load, unsigned long exp, unsigned long active, unsigned int n)`  
  计算经过 `n` 个采样周期后的负载值，基于指数平滑公式。
- `calc_load_nohz_start()` / `calc_load_nohz_stop()` / `calc_load_nohz_remote()`  
  在 `NO_HZ` 模式下管理负载采样的特殊处理，确保在 CPU 进入/退出无滴答状态时负载统计不丢失。

### NO_HZ 相关变量（条件编译）
- `static atomic_long_t calc_load_nohz[2]`：双缓冲数组，用于暂存 NO_HZ 期间累积的负载 delta。
- `static int calc_load_idx`：索引标志，用于在两个 NO_HZ 缓冲区之间切换读写。

## 3. 关键实现

### 负载平均值计算原理
系统负载平均值采用**指数加权移动平均**（EWMA）算法：
```
avenrun[n] = avenrun[n] * exp + nr_active * (1 - exp)
```
其中 `exp` 是与时间窗口对应的衰减因子（如 1 分钟窗口对应 `exp ≈ 1884/2048`）。每 `LOAD_FREQ`（5 秒）更新一次。

### 分布式增量更新机制
为避免遍历所有 CPU 带来的高开销（尤其在 NUMA 系统上），采用**增量折叠**策略：
- 每个 CPU 维护本地 `calc_load_active` 值。
- 当本地活跃任务数变化时，计算 delta 并原子累加到全局 `calc_load_tasks`。
- 全局更新时直接使用 `calc_load_tasks` 作为 `nr_active`，无需遍历 CPU。

### NO_HZ 模式下的负载补偿
在无滴答内核中，CPU 可能长时间不产生定时器中断，导致负载采样丢失。解决方案包括：
- **双缓冲 NO_HZ Delta**：使用两个原子变量 `calc_load_nohz[2]`，通过 `calc_load_idx` 切换读写窗口，确保旧窗口的 delta 被正确计入，同时新窗口开始累积。
- **写索引偏移**：`calc_load_write_idx()` 在窗口开始后切换写入缓冲区，而读取始终使用当前 `calc_load_idx`，避免读写冲突。
- **远程更新支持**：`calc_load_nohz_remote()` 允许其他 CPU 代为更新处于 NO_HZ 状态的 CPU 的负载 delta（用于 `NO_HZ_FULL` 场景）。

### 定点数幂运算优化
`fixed_power_int()` 使用**二进制幂展开**（Exponentiation by Squaring）高效计算 `x^n`，适用于定点数（`frac_bits` 指定小数位数），避免浮点运算，保证实时性和精度。

## 4. 依赖关系

- **调度器核心**（`kernel/sched/core.c`）：依赖运行队列（`struct rq`）中的 `nr_running` 和 `nr_uninterruptible` 字段。
- **时间子系统**：依赖 `jiffies` 和 `LOAD_FREQ`（定义在 `sched.h`）进行周期性更新。
- **NO_HZ 子系统**（`CONFIG_NO_HZ_COMMON`）：与内核的动态滴答机制深度集成，需处理 CPU 空闲状态下的负载统计。
- **SMP 原子操作**：使用 `atomic_long_t` 和 `smp_rmb()` 确保多核环境下的内存可见性和数据一致性。
- **导出符号**：`avenrun` 被 `EXPORT_SYMBOL` 导出，供其他内核模块（如 procfs）读取。

## 5. 使用场景

- **`/proc/loadavg` 文件生成**：用户空间通过读取 `/proc/loadavg` 获取系统负载，其数据来源于 `avenrun` 数组。
- **系统监控工具**：`top`、`htop`、`uptime` 等工具依赖此负载值评估系统繁忙程度。
- **调度器决策辅助**：某些调度策略（如负载均衡）可能参考全局负载信息。
- **内核调试与性能分析**：开发者可通过负载变化分析系统行为。
- **NO_HZ 节能模式下的负载准确性保障**：在服务器和移动设备中，确保即使 CPU 频繁进入深度睡眠，负载统计仍保持合理精度。