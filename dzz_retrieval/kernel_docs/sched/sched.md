# sched\sched.h

> 自动生成时间: 2025-10-25 16:16:13
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\sched.h`

---

# `sched/sched.h` 技术文档

## 1. 文件概述

`sched/sched.h` 是 Linux 内核调度器（Scheduler）的核心内部头文件，定义了调度子系统内部使用的类型、宏、辅助函数和全局变量。该文件不对外暴露给其他子系统直接使用，而是作为调度器各组件（如 CFS、RT、Deadline 调度类）之间的内部接口和共享基础设施。它整合了任务状态管理、负载计算、策略判断、CPU 能力建模、cgroup 权重转换等关键调度逻辑，并为调试、性能追踪和平台适配提供支持。

## 2. 核心功能

### 主要数据结构
- `struct asym_cap_data`：用于描述非对称 CPU 架构中不同 CPU 集合的计算能力（capacity），支持异构多核系统（如 big.LITTLE）的调度优化。
- `struct rq`（前向声明）：运行队列（runqueue）结构体，每个 CPU 对应一个，是调度器管理可运行任务的核心数据结构。
- `struct cpuidle_state`（前向声明）：CPU 空闲状态信息，用于与调度器协同进行能效管理。

### 关键全局变量
- `scheduler_running`：标志调度器是否已启动。
- `calc_load_update` / `calc_load_tasks`：用于全局负载（load average）计算的时间戳和任务计数。
- `sysctl_sched_rt_period` / `sysctl_sched_rt_runtime`：实时任务带宽控制参数。
- `sched_rr_timeslice`：SCHED_RR 策略的时间片长度。
- `asym_cap_list`：非对称 CPU 能力数据的全局链表。

### 核心辅助函数与宏
- **任务策略判断函数**：
  - `idle_policy()` / `task_has_idle_policy()`
  - `normal_policy()` / `fair_policy()`
  - `rt_policy()` / `task_has_rt_policy()`
  - `dl_policy()` / `task_has_dl_policy()`
  - `valid_policy()`
- **负载与权重转换**：
  - `scale_load()` / `scale_load_down()`：在内部高精度负载值与用户可见权重间转换。
  - `sched_weight_from_cgroup()` / `sched_weight_to_cgroup()`：cgroup 权重与调度器内部权重的映射。
- **时间与精度处理**：
  - `NS_TO_JIFFIES()`：纳秒转 jiffies。
  - `update_avg()`：指数移动平均（EMA）更新。
  - `shr_bound()`：安全右移，避免未定义行为。
- **特殊调度标志**：
  - `SCHED_FLAG_SUGOV`：用于 schedutil 频率调节器的特殊标志，使相关 kworker 临时获得高于 SCHED_DEADLINE 的优先级。
  - `dl_entity_is_special()`：判断 Deadline 实体是否为 SUGOV 特殊任务。

### 重要宏定义
- `TASK_ON_RQ_QUEUED` / `TASK_ON_RQ_MIGRATING`：`task_struct::on_rq` 字段的状态值。
- `NICE_0_LOAD`：nice 值为 0 的任务对应的内部负载基准值。
- `DL_SCALE`：SCHED_DEADLINE 内部计算的精度因子。
- `RUNTIME_INF`：表示无限运行时间的常量。
- `SCHED_WARN_ON()`：调度器专用的条件警告宏（仅在 `CONFIG_SCHED_DEBUG` 时生效）。

## 3. 关键实现

### 高精度负载计算（64 位优化）
在 64 位架构上，通过 `NICE_0_LOAD_SHIFT = 2 * SCHED_FIXEDPOINT_SHIFT` 提升内部负载计算的精度，改善低权重任务组（如 nice +19）和深层 cgroup 层级的负载均衡效果。`scale_load()` 和 `scale_load_down()` 实现了用户权重与内部高精度负载值之间的无损转换。

### 非对称 CPU 能力建模
`asym_cap_data` 结构体结合 `cpu_capacity_span()` 宏，将具有相同计算能力的 CPU 归为一组，并通过全局链表 `asym_cap_list` 管理。这为调度器在异构系统中进行负载均衡和任务迁移提供关键拓扑信息。

### cgroup 权重标准化
通过 `sched_weight_from_cgroup()` 和 `sched_weight_to_cgroup()`，将 cgroup 接口的权重范围（1–10000，默认 100）映射到调度器内部使用的权重值（基于 1024 基准），确保用户配置与调度行为的一致性。

### SCHED_DEADLINE 与频率调节协同
引入 `SCHED_FLAG_SUGOV` 标志，允许 `schedutil` 频率调节器的工作线程在需要时临时突破 SCHED_DEADLINE 的优先级限制，以解决某些平台无法原子切换 CPU 频率的问题。这是一种临时性 workaround，依赖于 `dl_entity_is_special()` 进行识别。

### 安全位运算
`shr_bound()` 宏确保右移操作不会因移位数过大而触发未定义行为（UB），通过 `min_t()` 将移位数限制在 `BITS_PER_TYPE(val) - 1` 以内。

## 4. 依赖关系

### 内核头文件依赖
- **调度子系统内部**：包含多个调度相关子模块头文件（如 `affinity.h`, `deadline.h`, `topology.h`, `cpupri.h` 等）。
- **核心内核设施**：依赖 `atomic.h`, `rcupdate.h`, `cpumask_api.h`, `ktime_api.h`, `trace/events/sched.h` 等。
- **平台与虚拟化**：条件包含 `asm/paravirt.h`（半虚拟化支持）和 `asm/barrier.h`（内存屏障）。
- **工作队列**：包含 `../workqueue_internal.h`，用于与工作队列子系统交互。

### 配置选项依赖
- `CONFIG_64BIT`：启用高精度负载计算。
- `CONFIG_SCHED_DEBUG`：启用 `SCHED_WARN_ON()` 调试检查。
- `CONFIG_CPU_FREQ_GOV_SCHEDUTIL`：启用 `SCHED_FLAG_SUGOV` 相关逻辑。
- `CONFIG_SCHED_CLASS_EXT`：扩展调度类支持（影响 `normal_policy()` 判断）。
- `CONFIG_PARAVIRT`：半虚拟化支持。

## 5. 使用场景

- **调度器初始化与运行**：`scheduler_running` 和负载计算变量在调度器启动和周期性负载更新中使用。
- **任务调度策略处理**：所有调度类（CFS、RT、Deadline、Idle）在入队、出队、选择下一个任务时，通过策略判断函数确定任务类型。
- **负载均衡与迁移**：`asym_cap_data` 和 CPU 拓扑信息用于跨 CPU 的任务迁移决策，尤其在异构系统中。
- **cgroup 资源控制**：在设置或读取 cgroup 的 CPU 权重时，通过权重转换函数确保调度器内部表示与用户接口一致。
- **实时带宽管理**：`sysctl_sched_rt_*` 参数用于限制 SCHED_FIFO/SCHED_RR 任务的 CPU 使用率。
- **能效调度协同**：`SCHED_FLAG_SUGOV` 机制使频率调节器能及时响应 Deadline 任务的性能需求。
- **内核调试与追踪**：`SCHED_WARN_ON()` 用于捕获调度器内部异常状态；tracepoint 定义支持调度事件追踪。