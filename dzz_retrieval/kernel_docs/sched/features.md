# sched\features.h

> 自动生成时间: 2025-10-25 16:09:45
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\features.h`

---

# `sched/features.h` 技术文档

## 1. 文件概述

`sched/features.h` 是 Linux 内核调度器（CFS 和 EEVDF 调度类）中用于定义和管理**调度特性（Scheduling Features）** 的头文件。该文件通过宏 `SCHED_FEAT(name, enabled)` 声明一系列可配置的调度行为开关，用于控制调度器在运行时的各种策略，如任务放置、抢占、迁移、缓存局部性优化、延迟处理、利用率估计等。这些特性通常在编译时默认启用或禁用，但部分可通过 `/sys/kernel/debug/sched_features` 在运行时动态调整。

## 2. 核心功能

本文件不包含函数或数据结构定义，而是通过一系列 `SCHED_FEAT(feature_name, default_value)` 宏声明调度器的**可配置特性标志**。每个特性对应一个布尔开关，控制调度器某一方面的行为逻辑。主要特性包括：

- **任务放置策略**：`PLACE_LAG`、`PLACE_DEADLINE_INITIAL`、`PLACE_REL_DEADLINE`
- **抢占控制**：`RUN_TO_PARITY`、`PREEMPT_SHORT`、`WAKEUP_PREEMPTION`
- **缓存局部性优化**：`NEXT_BUDDY`、`CACHE_HOT_BUDDY`
- **延迟出队机制**：`DELAY_DEQUEUE`、`DELAY_ZERO`
- **高精度定时器支持**：`HRTICK`、`HRTICK_DL`
- **CPU 容量与负载管理**：`NONTASK_CAPACITY`、`ATTACH_AGE_LOAD`
- **唤醒优化**：`TTWU_QUEUE`、`SIS_UTIL`
- **实时任务调度优化**：`RT_PUSH_IPI`、`RT_RUNTIME_SHARE`
- **利用率估计**：`UTIL_EST`、`UTIL_EST_FASTUP`
- **调试与告警**：`WARN_DOUBLE_CLOCK`、`LATENCY_WARN`

## 3. 关键实现

- **`SCHED_FEAT` 宏机制**：  
  该宏在 `kernel/sched/features.h` 中定义（通常通过 `#define SCHED_FEAT(x, enabled) SCHED_FEAT_##x`），最终在 `kernel/sched/core.c` 中展开为位图（`sysctl_sched_features`）中的位标志。调度器代码通过 `sched_feat(FEAT_NAME)` 宏查询某特性是否启用。

- **EEVDF 相关特性**：
  - `PLACE_LAG`：启用后，任务在睡眠/唤醒周期中保留其虚拟运行时间（avg_vruntime）的“滞后”（lag），确保公平性。这是 EEVDF（Earliest Eligible Virtual Deadline First）调度器的核心策略之一。
  - `PLACE_DEADLINE_INITIAL`：新任务初始虚拟截止时间设为当前时间加半个时间片，避免新任务因虚拟截止时间过早而过度抢占。
  - `PLACE_REL_DEADLINE`：任务迁移时保持其相对于当前虚拟时间的截止时间偏移，维持调度公平性。

- **抢占抑制与唤醒抢占**：
  - `RUN_TO_PARITY`：禁止唤醒抢占，直到当前任务达到“零滞后点”（即其虚拟运行时间追平队列平均值）或耗尽时间片。
  - `PREEMPT_SHORT`：允许具有更短时间片的唤醒任务抢占当前任务，即使 `RESPECT_SLICE` 被设置。
  - `WAKEUP_PREEMPTION`：启用唤醒时的抢占检查，是 CFS/EEVDF 实现低延迟响应的关键。

- **缓存局部性优化**：
  - `NEXT_BUDDY`（默认关闭）：优先调度最近被唤醒但未成功抢占的任务，因其可能复用刚访问的数据。
  - `CACHE_HOT_BUDDY`：将 buddy 任务视为缓存热任务，降低其被迁移的概率。

- **延迟出队（`DELAY_DEQUEUE`）**：  
  非就绪任务（如睡眠中）不会立即从运行队列移除，使其保留在调度竞争中以“消耗”负滞后（negative lag），当选中时自然具有正滞后，提升调度平滑性。`DELAY_ZERO` 则在出队或唤醒时将滞后裁剪为 0。

- **TTWU_QUEUE 优化**：  
  在非 `PREEMPT_RT` 配置下，默认启用远程唤醒排队机制，通过调度 IPI 异步处理跨 CPU 唤醒，减少运行队列锁竞争。

- **利用率估计（Utilization Estimation）**：  
  `UTIL_EST` 启用基于 PELT（Per-Entity Load Tracking）信号的 CPU 利用率估计，`UTIL_EST_FASTUP` 允许利用率快速上升以响应突发负载，用于 EAS（Energy Aware Scheduling）等场景。

- **RT 调度优化**：  
  `RT_PUSH_IPI` 在支持 `HAVE_RT_PUSH_IPI` 的平台上启用，通过 IPI 推送高优先级 RT 任务，避免多 CPU 同时争抢单个运行队列锁导致的“惊群”问题。

## 4. 依赖关系

- **依赖头文件**：通常由 `kernel/sched/sched.h` 或 `kernel/sched/core.c` 包含。
- **依赖配置选项**：
  - `CONFIG_PREEMPT_RT`：影响 `TTWU_QUEUE` 默认值。
  - `HAVE_RT_PUSH_IPI`：决定 `RT_PUSH_IPI` 特性是否定义。
- **依赖调度核心模块**：特性标志在 `kernel/sched/core.c`、`kernel/sched/fair.c`（CFS/EEVDF）、`kernel/sched/rt.c`（实时调度）中被实际使用。
- **依赖调试接口**：部分特性（如 `WARN_DOUBLE_CLOCK`、`LATENCY_WARN`）依赖内核调试基础设施。

## 5. 使用场景

- **调度策略调优**：系统管理员或开发者可通过 `/sys/kernel/debug/sched_features` 动态开启/关闭特性，以优化特定工作负载（如低延迟、高吞吐、能效）下的调度行为。
- **EEVDF 调度器支持**：`PLACE_LAG`、`PLACE_DEADLINE_INITIAL` 等特性是 Linux 6.6+ 引入的 EEVDF 调度器实现公平性和响应性的关键。
- **实时系统优化**：`RT_PUSH_IPI`、`RT_RUNTIME_SHARE` 等用于改善实时任务的调度延迟和 CPU 资源分配。
- **能效调度（EAS）**：`UTIL_EST` 和 `UTIL_EST_FASTUP` 为 EAS 提供准确的 CPU 利用率预测，用于任务放置决策。
- **性能调试**：`LATENCY_WARN`、`WARN_DOUBLE_CLOCK` 等特性用于检测调度器内部异常或性能瓶颈。
- **多核扩展性优化**：`TTWU_QUEUE`、`SIS_UTIL` 减少跨 CPU 唤醒和 LLC 域扫描开销，提升大规模系统可扩展性。