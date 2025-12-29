# sched\cpufreq.c

> 自动生成时间: 2025-10-25 16:02:58
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\cpufreq.c`

---

# `sched/cpufreq.c` 技术文档

## 1. 文件概述

`sched/cpufreq.c` 是 Linux 内核调度器子系统中与 CPU 频率调节（cpufreq）紧密集成的核心文件。该文件提供了调度器与 cpufreq 子系统之间的桥梁，允许调度器在运行时动态通知频率调节器当前 CPU 的负载或利用率变化，从而驱动 CPU 频率的动态调整（DVFS, Dynamic Voltage and Frequency Scaling）。其核心机制是通过 per-CPU 的回调函数指针，实现低延迟、无锁的利用率更新通知。

## 2. 核心功能

### 数据结构
- `cpufreq_update_util_data`：一个 per-CPU 的 RCU 指针，指向 `struct update_util_data` 实例。该结构体封装了用于更新 CPU 利用率的回调函数及上下文数据。

### 主要函数
- `cpufreq_add_update_util_hook(int cpu, struct update_util_data *data, void (*func)(...))`  
  为指定 CPU 注册一个利用率更新回调钩子。
- `cpufreq_remove_update_util_hook(int cpu)`  
  移除指定 CPU 的利用率更新回调钩子。
- `cpufreq_this_cpu_can_update(struct cpufreq_policy *policy)`  
  判断当前 CPU 是否有权限更新给定的 cpufreq 策略。

## 3. 关键实现

- **RCU 安全的回调机制**：  
  所有对 `cpufreq_update_util_data` 的读写操作均通过 RCU（Read-Copy-Update）机制保护。写操作使用 `rcu_assign_pointer()` 发布新指针，读操作（如在 `cpufreq_update_util()` 中）位于 RCU-sched 读端临界区内，确保无锁且安全地访问回调函数。

- **回调函数约束**：  
  注册的回调函数 `func` 必须是非阻塞的（不能睡眠），因为它会在调度器关键路径中被调用（例如在 `update_load_avg()` 或 `enqueue/dequeue_task()` 路径中）。函数接收 `update_util_data` 指针、时间戳和标志位，允许驱动程序访问其私有数据结构。

- **钩子注册/注销的安全性**：  
  `cpufreq_add_update_util_hook()` 要求目标 CPU 的钩子必须为 `NULL`，否则触发 `WARN_ON`，防止重复注册。`cpufreq_remove_update_util_hook()` 仅将指针置空，调用者需自行通过 `synchronize_rcu()` 或 RCU 回调确保旧数据结构在无读者后再释放，避免 use-after-free。

- **策略更新权限判断**：  
  `cpufreq_this_cpu_can_update()` 通过两个条件判断当前 CPU 是否可更新策略：
  1. 当前 CPU 属于该策略管理的 CPU 集合（`policy->cpus`）；
  2. 或策略支持从任意 CPU 更新（`dvfs_possible_from_any_cpu` 为真）且当前 CPU 仍注册了有效的更新钩子（即未离线）。

## 4. 依赖关系

- **调度器核心**：依赖 `kernel/sched/` 中的负载跟踪和利用率计算逻辑（如 `update_load_avg()`），这些逻辑会调用 `cpufreq_update_util()` 触发频率更新。
- **cpufreq 子系统**：与 `drivers/cpufreq/` 中的具体调频驱动（如 `schedutil`）紧密协作。`schedutil` 驱动会调用 `cpufreq_add_update_util_hook()` 注册其回调函数。
- **RCU 子系统**：依赖 `kernel/rcu/` 提供的 RCU-sched 机制，确保多核环境下回调指针的安全读写。
- **CPU 热插拔**：在 CPU 离线时需调用 `cpufreq_remove_update_util_hook()`，防止离线 CPU 继续参与频率决策。

## 5. 使用场景

- **调度器驱动的频率调节（如 schedutil）**：  
  当启用 `schedutil` 调频策略时，该策略会为每个 CPU 注册一个回调函数。调度器在任务入队、出队或周期性负载更新时，通过 `cpufreq_update_util()` 调用此回调，将当前 CPU 的利用率信息传递给 cpufreq 驱动，驱动据此计算并设置最优频率。

- **异构多核系统（如 big.LITTLE）**：  
  在共享频率域（如多个小核共享一个调频策略）的场景中，即使当前 CPU 不属于策略的主控 CPU，只要 `dvfs_possible_from_any_cpu` 被设置，任何 CPU 都可触发该策略的频率更新，提升响应速度。

- **CPU 热插拔处理**：  
  在 CPU 离线流程中，系统会调用 `cpufreq_remove_update_util_hook()` 清除钩子，确保离线 CPU 不再影响频率决策；上线时重新注册钩子。