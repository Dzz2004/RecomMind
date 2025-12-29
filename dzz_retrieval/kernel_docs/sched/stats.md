# sched\stats.c

> 自动生成时间: 2025-10-25 16:17:07
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\stats.c`

---

# `sched/stats.c` 技术文档

## 1. 文件概述

`sched/stats.c` 是 Linux 内核调度器统计信息模块的核心实现文件，负责收集和导出与任务调度相关的性能统计指标。该文件实现了 `/proc/schedstat` 接口，向用户空间提供调度器运行队列（runqueue）、任务等待/睡眠/阻塞时间、负载均衡事件等详细统计数据，主要用于性能分析、调度调优和系统监控。

## 2. 核心功能

### 主要函数

- **`__update_stats_wait_start()`**  
  记录任务进入等待状态的起始时间戳。

- **`__update_stats_wait_end()`**  
  计算任务等待时间，更新最大等待时间、等待次数和总等待时间，并处理任务迁移场景。

- **`__update_stats_enqueue_sleeper()`**  
  处理任务从睡眠或阻塞状态被重新入队时的统计更新，包括睡眠时间、阻塞时间、I/O 等待时间等。

- **`show_schedstat()`**  
  格式化输出 `/proc/schedstat` 的内容，包括版本号、时间戳、每个 CPU 的运行队列统计以及调度域（SMP）的负载均衡统计。

- **`schedstat_start()` / `schedstat_next()` / `schedstat_stop()`**  
  实现 `seq_file` 迭代器，用于遍历所有在线 CPU 并生成 `/proc/schedstat` 的多行输出。

- **`proc_schedstat_init()`**  
  初始化函数，通过 `subsys_initcall` 在内核启动时注册 `/proc/schedstat` 文件。

### 关键宏与常量

- **`SCHEDSTAT_VERSION`**  
  当前调度统计 API 的版本号（值为 15），用于兼容性检查。

- **`__schedstat_set/inc/add` 系列宏**  
  安全地更新调度统计字段（通常在 `CONFIG_SCHEDSTATS` 启用时有效）。

## 3. 关键实现

### 等待时间统计机制
- 任务进入不可运行状态时调用 `__update_stats_wait_start()`，记录当前运行队列时钟时间。
- 当任务重新变为可运行时调用 `__update_stats_wait_end()`，计算等待时长 `delta`。
- 若任务正在 CPU 间迁移（`task_on_rq_migrating`），则保留 `delta` 作为新的 `wait_start`，以便在目标 CPU 上继续累加等待时间，确保跨 CPU 迁移时等待时间统计的连续性。

### 睡眠与阻塞时间区分
- `sleep_start`：任务主动睡眠（如调用 `schedule()`）时设置。
- `block_start`：任务因等待资源（如 I/O）而阻塞时设置。
- 两者在任务被唤醒并重新入队时分别计算持续时间，并累加到 `sum_sleep_runtime`；阻塞时间额外计入 `sum_block_runtime` 和 I/O 等待统计（若 `in_iowait` 为真）。

### `/proc/schedstat` 输出格式
- **首行**：`version <N>` 和 `timestamp <jiffies>`，用于工具识别格式版本和采样时间。
- **每 CPU 行**：以 `cpu<N>` 开头，包含 yield 次数、调度次数、空闲调度次数、wake-up 次数等运行队列级指标。
- **调度域行（SMP）**：以 `domain<N>` 开头，列出各 CPU 空闲类型下的负载均衡尝试、成功、失败等详细计数。

### 迭代器设计
- 使用特殊指针值区分头部（`(void *)1`）和 CPU 数据（`(void *)(cpu + 2)`）。
- 通过 `cpumask_next()` 和 `cpumask_first()` 遍历 `cpu_online_mask`，支持 CPU 热插拔场景。

## 4. 依赖关系

- **调度器核心**：依赖 `kernel/sched/` 下的运行队列（`struct rq`）、任务结构（`struct task_struct`）和时钟函数（`rq_clock()`）。
- **配置选项**：功能受 `CONFIG_SCHEDSTATS` 控制（虽未在本文件显式检查，但相关字段和宏由该配置启用）。
- **SMP 支持**：调度域统计仅在 `CONFIG_SMP` 启用时编译。
- **跟踪子系统**：调用 `trace_sched_stat_*` 系列 tracepoint，依赖 `kernel/trace/`。
- **延迟账户**：调用 `account_scheduler_latency()`，与延迟跟踪机制集成。
- **proc 文件系统**：使用 `proc_create_seq()` 注册 `/proc` 接口。

## 5. 使用场景

- **性能分析工具**：如 `perf`、`sar`、`vmstat` 等读取 `/proc/schedstat` 获取调度延迟、负载均衡效率等指标。
- **内核调试**：开发者通过分析等待/睡眠时间分布定位调度瓶颈或任务饥饿问题。
- **调度器调优**：系统管理员根据域级负载均衡统计调整 `sched_domain` 参数。
- **I/O 性能诊断**：通过 `iowait_sum` 和 `iowait_count` 识别 I/O 密集型任务对调度的影响。
- **实时性评估**：结合 `wait_max` 和 `run_delay` 评估任务响应延迟。