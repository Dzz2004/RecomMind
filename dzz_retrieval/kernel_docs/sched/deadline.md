# sched\deadline.c

> 自动生成时间: 2025-10-25 16:06:40
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\deadline.c`

---

# `sched/deadline.c` 技术文档

## 1. 文件概述

`sched/deadline.c` 是 Linux 内核调度器中 **SCHED_DEADLINE** 调度类的核心实现文件。该调度类基于 **最早截止时间优先（Earliest Deadline First, EDF）** 算法，并结合 **恒定带宽服务器（Constant Bandwidth Server, CBS）** 机制，为具有严格实时性要求的任务提供可预测的调度保障。

其核心目标是：  
- 对于周期性任务，若其实际运行时间不超过所申请的运行时间（runtime），则保证不会错过任何截止时间（deadline）；  
- 对于非周期性任务、突发任务或试图超出其预留带宽的任务，系统会对其进行节流（throttling），防止其影响其他任务的实时性保障。

## 2. 核心功能

### 主要数据结构
- `struct sched_dl_entity`：表示一个 deadline 调度实体，包含任务的运行时间（runtime）、截止期限（deadline）、周期（period）、带宽（dl_bw）等关键参数。
- `struct dl_rq`：每个 CPU 的 deadline 运行队列，维护该 CPU 上所有 deadline 任务的红黑树、当前带宽使用情况（`this_bw`、`running_bw`）等。
- `struct dl_bw`：deadline 带宽管理结构，用于跟踪系统或调度域中已分配的总带宽（`total_bw`）。

### 主要函数与辅助宏

#### 调度实体与运行队列关联
- `dl_task_of(dl_se)`：从 `sched_dl_entity` 获取对应的 `task_struct`（仅适用于普通任务，不适用于服务器实体）。
- `rq_of_dl_rq(dl_rq)` / `rq_of_dl_se(dl_se)`：获取与 deadline 运行队列或调度实体关联的 `rq`（runqueue）。
- `dl_rq_of_se(dl_se)`：获取调度实体所属的 `dl_rq`。
- `on_dl_rq(dl_se)`：判断调度实体是否已在 deadline 运行队列中（通过红黑树节点是否为空判断）。

#### 优先级继承（PI）支持（`CONFIG_RT_MUTEXES`）
- `pi_of(dl_se)`：获取当前调度实体因优先级继承而提升后的“代理”实体。
- `is_dl_boosted(dl_se)`：判断该 deadline 实体是否因优先级继承被提升。

#### 带宽管理（SMP 与 UP 差异处理）
- `dl_bw_of(cpu)`：获取指定 CPU 所属调度域（或本地）的 `dl_bw` 结构。
- `dl_bw_cpus(cpu)`：返回该 CPU 所在调度域中活跃 CPU 的数量。
- `dl_bw_capacity(cpu)`：计算调度域的总 CPU 容量（考虑异构 CPU 的 `arch_scale_cpu_capacity`）。
- `__dl_add()` / `__dl_sub()`：向带宽池中添加或移除任务带宽，并更新 `extra_bw`（用于负载均衡）。
- `__dl_overflow()`：检查新增带宽是否超出系统/调度域的可用带宽上限。

#### 运行时带宽跟踪
- `__add_running_bw()` / `__sub_running_bw()`：更新 `dl_rq->running_bw`（当前正在运行的 deadline 任务所消耗的带宽）。
- `__add_rq_bw()` / `__sub_rq_bw()`：更新 `dl_rq->this_bw`（该运行队列上所有 deadline 任务的总预留带宽）。
- `add_running_bw()` / `sub_running_bw()` / `add_rq_bw()` / `sub_rq_bw()`：带宽操作的封装，跳过“特殊”调度实体（如服务器）。

#### 其他
- `dl_server(dl_se)`：判断调度实体是否为 CBS 服务器（而非普通任务）。
- `dl_bw_visited(cpu, gen)`：用于带宽遍历去重（SMP 场景）。

### 系统控制接口（`CONFIG_SYSCTL`）
- `sched_deadline_period_max_us`：deadline 任务周期上限（默认 ~4 秒）。
- `sched_deadline_period_min_us`：deadline 任务周期下限（默认 100 微秒），防止定时器 DoS。

## 3. 关键实现

### EDF + CBS 调度模型
- 每个 deadline 任务通过 `runtime`、`deadline`、`period` 三个参数定义其资源需求。
- 调度器按 **绝对截止时间（absolute deadline）** 对任务排序，使用红黑树实现 O(log n) 的调度决策。
- CBS 机制确保任务即使突发执行，也不会长期占用超过其 `runtime/period` 的 CPU 带宽，超限任务会被 throttled。

### 带宽隔离与全局限制
- 在 SMP 系统中，deadline 带宽按 **调度域（root domain）** 进行管理，防止跨 CPU 的带宽滥用。
- 总带宽限制默认为 CPU 总容量的 95%（由 `sysctl_sched_util_clamp_min` 等机制间接控制，具体限制逻辑在带宽分配函数中体现）。
- `dl_bw->total_bw` 跟踪已分配带宽，`__dl_overflow()` 用于在任务加入时检查是否超限。

### 异构 CPU 支持
- 通过 `arch_scale_cpu_capacity()` 获取每个 CPU 的相对性能权重。
- `dl_bw_capacity()` 在异构系统中返回调度域内所有活跃 CPU 的容量总和，用于带宽比例计算（`cap_scale()`）。

### 与 cpufreq 集成
- 每次 `running_bw` 变化时调用 `cpufreq_update_util()`，通知 CPU 频率调节器当前 deadline 负载，确保满足实时性能需求。

### 优先级继承（PI）
- 当 deadline 任务因持有 mutex 而阻塞高优先级任务时，通过 `pi_se` 字段临时提升其调度参数，避免优先级反转。

## 4. 依赖关系

- **核心调度框架**：依赖 `kernel/sched/sched.h` 中定义的通用调度结构（如 `rq`、`task_struct`）和宏（如 `SCHED_CAPACITY_SCALE`）。
- **CPU 拓扑与容量**：依赖 `arch_scale_cpu_capacity()`（由各架构实现）获取 CPU 性能信息。
- **RCU 机制**：在 SMP 路径中大量使用 `rcu_read_lock_sched_held()` 进行锁依赖检查。
- **cpufreq 子系统**：通过 `cpufreq_update_util()` 与 CPU 频率调节器交互。
- **实时互斥锁**：`CONFIG_RT_MUTEXES` 启用时，支持 deadline 任务的优先级继承。
- **Sysctl 接口**：`CONFIG_SYSCTL` 启用时，提供用户空间可调的 deadline 参数。

## 5. 使用场景

- **工业实时控制**：如机器人控制、数控机床等需要严格周期性和低延迟响应的场景。
- **音视频处理**：专业音视频采集、编码、播放等对 jitter 敏感的应用。
- **电信基础设施**：5G 基站、核心网网元中的高优先级信令处理。
- **汽车电子**：ADAS、自动驾驶系统中的关键任务调度。
- **科研与高性能计算**：需要确定性执行时间的实验或仿真任务。

用户通过 `sched_setattr(2)` 系统调用设置任务的 `SCHED_DEADLINE` 策略及对应的 `runtime`、`deadline`、`period` 参数，内核则通过本文件实现的调度逻辑确保其满足实时性约束。