# sched\cpufreq_schedutil.c

> 自动生成时间: 2025-10-25 16:03:51
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\cpufreq_schedutil.c`

---

# `sched/cpufreq_schedutil.c` 技术文档

## 1. 文件概述

`sched/cpufreq_schedutil.c` 实现了 Linux 内核中基于调度器提供的 CPU 利用率数据的 **schedutil CPUFreq 调速器（governor）**。该调速器通过实时获取调度器计算的 CPU 利用率（包括 CFS、RT、DL 任务以及 I/O 等待状态），动态调整 CPU 频率，以在性能与能效之间取得平衡。其核心优势在于直接利用调度器的 `util` 信息，避免传统调速器依赖采样机制带来的延迟和不准确性。

## 2. 核心功能

### 主要数据结构

- **`struct sugov_tunables`**  
  调速器可调参数，包含：
  - `rate_limit_us`：频率更新的最小时间间隔（微秒），防止过于频繁的频率切换。

- **`struct sugov_policy`**  
  每个 `cpufreq_policy` 对应的 schedutil 策略实例，包含：
  - `policy`：关联的 CPUFreq 策略。
  - `update_lock`：保护频率更新的自旋锁。
  - `last_freq_update_time` / `freq_update_delay_ns`：控制频率更新速率。
  - `next_freq` / `cached_raw_freq`：目标频率与原始计算频率缓存。
  - `irq_work` / `worker` / `thread`：用于慢速切换平台（非 fast-switch）的异步工作队列机制。
  - `limits_changed` / `need_freq_update`：标志策略限制（如 min/max freq）是否变更。

- **`struct sugov_cpu`**  
  每个 CPU 的 schedutil 状态，包含：
  - `update_util`：注册到调度器的回调接口（`update_util_data`）。
  - `util` / `bw_min`：当前有效利用率及带宽最小值。
  - `iowait_boost` / `iowait_boost_pending`：I/O 等待唤醒时的频率提升机制。
  - `last_update`：上次更新时间戳。

### 主要函数

- **`sugov_should_update_freq()`**  
  判断是否应执行频率更新，考虑硬件是否支持本 CPU 更新、策略限制变更、以及频率更新间隔限制。

- **`sugov_update_next_freq()`**  
  更新目标频率，处理策略限制变更场景，避免不必要的驱动回调。

- **`get_next_freq()`**  
  核心频率计算函数，根据 CPU 利用率、最大容量和参考频率，计算目标频率，并通过 `cpufreq_driver_resolve_freq()` 映射到驱动支持的频率。

- **`sugov_get_util()`**  
  获取当前 CPU 的综合利用率，整合 CFS/RT/DL 任务利用率、boost 值，并调用 `sugov_effective_cpu_perf()` 计算有效性能目标。

- **`sugov_effective_cpu_perf()`**  
  计算最终的有效性能目标，确保不低于最小性能要求，并限制不超过实际需求。

- **`sugov_iowait_reset()` / `sugov_iowait_boost()`**  
  实现 I/O 等待唤醒时的动态频率提升机制：短时间内连续 I/O 唤醒会逐步提升 boost 值（从 `IOWAIT_BOOST_MIN` 到最大 OPP），超过一个 tick 无 I/O 唤醒则重置。

- **`get_capacity_ref_freq()`**  
  获取用于计算 CPU 容量的参考频率，优先使用架构特定的 `arch_scale_freq_ref()`，其次为最大频率或当前频率。

- **`sugov_deferred_update()`**  
  在不支持 fast-switch 的平台上，通过 `irq_work` 触发异步频率更新。

## 3. 关键实现

### 频率计算算法
- **频率不变性支持**：若系统支持频率不变调度（`arch_scale_freq_invariant()`），则直接使用调度器提供的频率不变利用率 `util`，按比例计算目标频率：  
  `next_freq = C * max_freq * util / max`  
  其中常数 `C = 1.25`，使在 `util/max = 0.8` 时达到 `max_freq`，提供性能余量。
- **非频率不变性**：使用原始利用率 `util_raw` 乘以 `(curr_freq / max_freq)` 近似频率不变利用率，再计算目标频率。

### I/O 等待 Boost 机制
- 当任务因 I/O 完成而唤醒时，标记 `SCHED_CPUFREQ_IOWAIT`。
- 若在 **一个 tick 内** 多次发生 I/O 唤醒，则 `iowait_boost` 值倍增（上限为最大 OPP 对应的利用率）。
- 若超过一个 tick 无 I/O 唤醒，则重置 boost 值为 `IOWAIT_BOOST_MIN`（`SCHED_CAPACITY_SCALE / 8`），避免对偶发 I/O 过度响应，提升能效。

### 快速切换（Fast-Switch）与异步更新
- **Fast-Switch 平台**：支持在调度上下文中直接调用 `cpufreq_driver_fast_switch()` 更新频率，延迟最低。
- **非 Fast-Switch 平台**：通过 `irq_work` 触发内核线程（`kthread_worker`）异步执行频率更新，避免在中断上下文或持有 rq 锁时调用可能阻塞的驱动接口。

### 策略限制变更处理
- 当用户空间修改 policy 的 min/max 频率时，`sugov_limits()` 设置 `limits_changed` 标志。
- 下次更新时，强制重新计算频率，并通过内存屏障（`smp_mb()`）确保读取到最新的策略限制。

## 4. 依赖关系

- **调度器子系统**：
  - 依赖 `update_util_data` 回调机制（通过 `cpufreq_add_update_util_hook()` 注册）。
  - 调用 `cpu_util_cfs_boost()`、`effective_cpu_util()` 等函数获取综合利用率。
  - 使用 `scx_cpuperf_target()`（若启用了 SCHED_CLASS_EXT）。
- **CPUFreq 核心**：
  - 依赖 `cpufreq_policy`、`cpufreq_driver_resolve_freq()`、`cpufreq_driver_fast_switch()` 等接口。
  - 使用 `cpufreq_this_cpu_can_update()` 判断硬件更新能力。
- **架构相关支持**：
  - 依赖 `arch_scale_freq_ref()` 和 `arch_scale_freq_invariant()` 提供频率不变性信息。
- **内核基础设施**：
  - 使用 `irq_work`、`kthread_worker` 实现异步更新。
  - 依赖 `TICK_NSEC` 定义 tick 时间。

## 5. 使用场景

- **默认高性能能效平衡场景**：现代 Linux 发行版通常将 `schedutil` 作为默认 CPUFreq 调速器，适用于大多数桌面、服务器和移动设备。
- **实时性要求较高的系统**：由于其低延迟特性（尤其在 fast-switch 平台上），适合对响应时间敏感的应用。
- **能效敏感设备**：通过 I/O boost 机制和精确的利用率跟踪，在保证交互性能的同时降低空闲功耗。
- **异构多核系统（如 big.LITTLE）**：结合调度器的 CPU capacity 信息，为不同性能核提供差异化频率调整。