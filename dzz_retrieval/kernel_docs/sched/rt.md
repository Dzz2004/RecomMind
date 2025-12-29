# sched\rt.c

> 自动生成时间: 2025-10-25 16:14:51
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\rt.c`

---

# `sched/rt.c` 技术文档

## 1. 文件概述

`sched/rt.c` 是 Linux 内核调度子系统中实现实时（Real-Time, RT）调度类的核心文件，主要支持 `SCHED_FIFO` 和 `SCHED_RR` 两种 POSIX 实时调度策略。该文件负责管理实时任务的运行队列、优先级调度、时间片分配、带宽限制（RT throttling）以及在多核系统（SMP）下的负载均衡机制。此外，它还提供了对实时任务组调度（RT Group Scheduling）的支持，允许通过 cgroups 对实时任务的 CPU 使用进行资源控制。

## 2. 核心功能

### 全局变量
- `sched_rr_timeslice`：定义 `SCHED_RR` 策略的默认时间片长度（单位：调度 tick）。
- `max_rt_runtime`：实时任务在单个周期内可使用的最大运行时间上限（通常为 4 小时以上）。
- `sysctl_sched_rt_period`：实时带宽控制的周期，默认为 1,000,000 微秒（1 秒）。
- `sysctl_sched_rt_runtime`：每个周期内允许实时任务运行的时间，默认为 950,000 微秒（0.95 秒）。

### sysctl 接口（`CONFIG_SYSCTL` 启用时）
- `/proc/sys/kernel/sched_rt_period_us`：设置 RT 带宽控制周期。
- `/proc/sys/kernel/sched_rt_runtime_us`：设置 RT 带宽控制运行时间（可设为 -1 表示无限制）。
- `/proc/sys/kernel/sched_rr_timeslice_ms`：设置 `SCHED_RR` 时间片（毫秒）。

### 主要函数
- `init_rt_rq(struct rt_rq *rt_rq)`：初始化实时运行队列（`rt_rq`），包括优先级位图、链表、SMP 相关字段及带宽控制状态。
- `init_rt_bandwidth(struct rt_bandwidth *rt_b, u64 period, u64 runtime)`：初始化 RT 带宽控制结构，配置高精度定时器。
- `sched_rt_period_timer(struct hrtimer *timer)`：高精度定时器回调函数，用于周期性重置 RT 运行时间配额。
- `start_rt_bandwidth(struct rt_bandwidth *rt_b)`：启动 RT 带宽控制定时器。
- `alloc_rt_sched_group / free_rt_sched_group / unregister_rt_sched_group`：管理实时任务组（task group）的资源分配与释放。
- `init_tg_rt_entry`：初始化任务组在指定 CPU 上的 RT 调度实体和运行队列。
- `rt_task_of / rq_of_rt_rq / rt_rq_of_se / rq_of_rt_se`：辅助函数，用于在调度实体、任务、运行队列和 CPU 队列之间相互转换。

### SMP 支持函数（`CONFIG_SMP` 启用时）
- `need_pull_rt_task`：判断是否需要从其他 CPU 拉取高优先级 RT 任务。
- `rt_overloaded` / `rt_set_overload`：用于跟踪系统中是否存在过载的 RT 运行队列，支持 RT 任务迁移。

## 3. 关键实现

### 实时运行队列（`rt_rq`）管理
- 使用 `rt_prio_array` 结构维护 0 到 `MAX_RT_PRIO-1`（通常为 99）共 100 个优先级的双向链表。
- 通过位图（`bitmap`）快速查找最高优先级的可运行任务，`__set_bit(MAX_RT_PRIO, bitmap)` 作为位图搜索的终止标记。
- `rt_queued` 标志表示是否有 RT 任务入队；`highest_prio.curr/next` 跟踪当前和下一个最高优先级（SMP 专用）。

### RT 带宽控制（Throttling）
- 通过 `rt_bandwidth` 结构限制 RT 任务在每个 `rt_period` 内最多使用 `rt_runtime` 的 CPU 时间。
- 使用高精度定时器（`hrtimer`）实现周期性重置：每经过 `rt_period`，将 `rt_time` 清零并解除 throttling。
- 若 `rt_runtime == RUNTIME_INF`（即 -1），则禁用带宽限制。
- 定时器回调 `sched_rt_period_timer` 支持处理定时器 overrun（跳过多个周期），确保带宽控制的准确性。

### RT 任务组调度（`CONFIG_RT_GROUP_SCHED`）
- 每个 `task_group` 拥有 per-CPU 的 `rt_rq` 和 `sched_rt_entity`。
- 根叶节点（普通任务）的 `rt_se` 直接链接到 CPU 的全局 `rt_rq`；非叶节点（cgroup）的 `rt_se` 链接到父组的 `rt_rq`，形成调度树。
- `rt_entity_is_task()` 用于区分调度实体是任务还是任务组。

### SMP 负载均衡
- 当某 CPU 上运行的 RT 任务优先级降低（如被抢占或阻塞），若其当前最高优先级高于刚被替换的任务，则触发 `need_pull_rt_task`，尝试从其他 CPU 拉取更高优先级的 RT 任务。
- `overloaded` 标志和 `pushable_tasks` 链表用于支持 RT 任务的主动推送（push）和拉取（pull）机制，确保高优先级任务尽快运行。

## 4. 依赖关系

- **调度核心**：依赖 `kernel/sched/core.c` 提供的通用调度框架、运行队列（`rq`）结构和调度类注册机制。
- **高精度定时器**：使用 `kernel/time/hrtimer.c` 实现 RT 带宽控制的周期性重置。
- **SMP 调度**：与 `kernel/sched/topology.c` 和 `kernel/sched/fair.c` 协同实现跨 CPU 的 RT 任务迁移。
- **cgroups**：当启用 `CONFIG_RT_GROUP_SCHED` 时，与 `kernel/cgroup/` 子系统集成，支持基于 cgroup v1/v2 的 RT 带宽分配。
- **sysctl**：通过 `kernel/sysctl.c` 暴露运行时可调参数。

## 5. 使用场景

- **实时应用调度**：为音视频处理、工业控制、机器人等需要确定性延迟的应用提供 `SCHED_FIFO`/`SCHED_RR` 调度支持。
- **系统资源保护**：通过 `sched_rt_runtime_us` 限制 RT 任务的 CPU 占用率（默认 95%），防止其独占 CPU 导致系统僵死。
- **多租户 RT 资源隔离**：在容器或虚拟化环境中，利用 RT 任务组调度为不同租户分配独立的 RT 带宽配额。
- **SMP 实时性能优化**：在多核系统中，通过 RT 任务迁移机制减少高优先级任务的调度延迟，提升实时响应能力。