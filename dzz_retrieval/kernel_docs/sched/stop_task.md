# sched\stop_task.c

> 自动生成时间: 2025-10-25 16:17:42
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\stop_task.c`

---

# `sched/stop_task.c` 技术文档

## 1. 文件概述

`sched/stop_task.c` 实现了 Linux 内核调度器中的 **stop 调度类（stop scheduling class）**。该调度类用于管理 per-CPU 的 **stop 任务（stop task）**，这些任务具有系统中最高的调度优先级，能够抢占所有其他任务，且自身不会被任何任务抢占。stop 任务主要用于需要在所有 CPU 上立即停止常规调度活动的场景，例如 CPU 热插拔、内核模块卸载或 `stop_machine()` 机制执行期间。

## 2. 核心功能

### 主要函数

- `select_task_rq_stop()`：在 SMP 系统中，确保 stop 任务始终运行在其初始 CPU 上，禁止迁移。
- `balance_stop()`：在负载均衡时判断当前运行队列上是否有可运行的 stop 任务。
- `wakeup_preempt_stop()`：空实现，因为 stop 任务不会被抢占。
- `set_next_task_stop()`：设置下一个运行的 stop 任务，并记录其执行起始时间。
- `pick_task_stop()`：从运行队列中选择 stop 任务（如果存在且可运行）。
- `enqueue_task_stop()` / `dequeue_task_stop()`：将 stop 任务加入/移出运行队列，并更新运行任务计数。
- `yield_task_stop()`：触发 `BUG()`，因为 stop 任务绝不应主动让出 CPU。
- `put_prev_task_stop()`：在切换出 stop 任务时更新其运行统计（调用通用更新函数）。
- `task_tick_stop()`：空实现，stop 任务不受调度 tick 影响。
- `switched_to_stop()` / `prio_changed_stop()`：均触发 `BUG()`，因为任务不能动态切换到 stop 调度类，也无优先级概念。
- `update_curr_stop()`：空实现，stop 任务不参与常规的运行时间更新逻辑。

### 数据结构

- `DEFINE_SCHED_CLASS(stop)`：定义并初始化名为 `stop` 的调度类实例，实现了 `struct sched_class` 接口的所有必要回调函数。

## 3. 关键实现

- **最高优先级保证**：stop 调度类在调度类层级中位于最顶端（高于 `rt`、`fair`、`idle`），确保其任务总是优先获得 CPU。
- **禁止迁移**：在 `CONFIG_SMP` 下，`select_task_rq_stop()` 强制 stop 任务绑定到其创建时的 CPU，防止跨 CPU 迁移，保证操作的局部性和确定性。
- **无抢占逻辑**：所有与抢占相关的函数（如 `wakeup_preempt_stop`）均为空或触发错误，因为 stop 任务运行期间系统处于“停止”状态，不应被中断。
- **错误防护机制**：任何试图动态切换到 stop 调度类、修改其优先级或主动让出 CPU 的行为都会触发 `BUG()`，防止误用。
- **轻量级统计**：虽然调用 `update_curr_common()` 更新运行时间，但 `update_curr_stop()` 本身为空，表明 stop 任务不参与复杂的调度实体（`sched_entity`）时间计算。
- **与 `stop_machine` 协同**：该文件与 `kernel/stop_machine.c` 紧密配合，为 `stop_machine()` 提供底层调度支持，确保在所有 CPU 上同步执行关键操作。

## 4. 依赖关系

- **调度核心**：依赖 `kernel/sched/core.c` 中定义的调度类框架、运行队列（`rq`）结构和通用辅助函数（如 `add_nr_running`、`update_curr_common`）。
- **SMP 支持**：在 `CONFIG_SMP` 编译选项下，依赖 `kernel/sched/sched.h` 中的 `set_cpus_allowed_common` 函数。
- **Stop Machine 机制**：与 `kernel/stop_machine.c` 深度集成，后者负责创建和管理 per-CPU stop 任务，并触发其执行。
- **时间子系统**：使用 `rq_clock_task()` 获取任务执行时间戳，依赖内核时间管理基础设施。

## 5. 使用场景

- **`stop_machine()` 执行**：当内核需要在所有在线 CPU 上同步执行一段不能被中断的代码时（如修改全局数据结构、CPU 热插拔），会激活所有 CPU 的 stop 任务。
- **CPU 热插拔**：在 CPU 上线或下线过程中，使用 stop 任务确保目标 CPU 处于可控状态，避免调度干扰。
- **内核关键路径保护**：在极少数需要完全禁止调度器干预的内核关键操作中，临时启用 stop 任务以获得独占 CPU 的能力。
- **调试与诊断**：某些内核调试机制可能利用 stop 任务来冻结系统状态进行分析。