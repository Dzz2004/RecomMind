# cgroup\freezer.c

> 自动生成时间: 2025-10-25 12:46:21
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cgroup\freezer.c`

---

# cgroup/freezer.c 技术文档

## 文件概述

`cgroup/freezer.c` 实现了 cgroup v2 的 freezer 子系统核心逻辑，用于冻结（suspend）或解冻（resume）指定 cgroup 中的所有用户态任务（不包括内核线程）。该机制允许系统管理员或容器运行时临时挂起一组进程，常用于容器快照、检查点/恢复（CRIU）、资源管理等场景。文件通过维护每个 cgroup 的冻结状态标志和计数器，结合任务迁移、状态传播等机制，确保冻结状态在 cgroup 层次结构中的一致性。

## 核心功能

### 主要函数

- **`cgroup_propagate_frozen(struct cgroup *cgrp, bool frozen)`**  
  向上遍历 cgroup 祖先，根据子 cgroup 的冻结状态更新祖先的 `nr_frozen_descendants` 计数，并在满足条件时设置或清除 `CGRP_FROZEN` 标志。

- **`cgroup_update_frozen(struct cgroup *cgrp)`**  
  重新评估指定 cgroup 的冻结状态：若 `CGRP_FREEZE` 已设置且所有任务均已冻结，则标记为 `CGRP_FROZEN`；否则清除该标志，并触发状态传播。

- **`cgroup_enter_frozen(void)`**  
  当前任务进入冻结状态时调用，增加所属 cgroup 的 `nr_frozen_tasks` 计数，并更新 cgroup 冻结状态。

- **`cgroup_leave_frozen(bool always_leave)`**  
  当前任务尝试离开冻结状态时调用。若 `always_leave` 为真或目标 cgroup 未处于冻结请求状态，则减少计数并更新状态；否则设置 `JOBCTL_TRAP_FREEZE` 以防止任务真正退出冻结。

- **`cgroup_freeze_task(struct task_struct *task, bool freeze)`**  
  通过设置或清除任务的 `JOBCTL_TRAP_FREEZE` 标志来冻结或解冻单个任务，并唤醒任务以响应状态变化。

- **`cgroup_do_freeze(struct cgroup *cgrp, bool freeze)`**  
  对指定 cgroup 中所有非内核线程任务执行冻结或解冻操作，并更新 cgroup 的 `CGRP_FREEZE` 标志。

- **`cgroup_freezer_migrate_task(struct task_struct *task, struct cgroup *src, struct cgroup *dst)`**  
  在任务从一个 cgroup 迁移到另一个 cgroup 时，调整冻结计数并确保任务处于目标 cgroup 所需的冻结状态。

- **`cgroup_freeze(struct cgroup *cgrp, bool freeze)`**  
  对指定 cgroup 及其所有后代递归应用冻结或解冻操作，维护 `e_freeze` 嵌套计数以支持祖先 cgroup 的冻结状态覆盖。

### 关键数据结构字段（位于 `struct cgroup`）

- `freezer.nr_frozen_tasks`：当前 cgroup 中已进入冻结状态的任务数量。
- `freezer.nr_frozen_descendants`：当前 cgroup 的后代中处于 `CGRP_FROZEN` 状态的 cgroup 数量。
- `freezer.freeze`：用户请求的冻结状态（布尔值）。
- `freezer.e_freeze`：有效冻结请求的嵌套计数（用于处理祖先冻结覆盖）。
- `flags` 中的位标志：
  - `CGRP_FREEZE`：表示该 cgroup 被请求冻结。
  - `CGRP_FROZEN`：表示该 cgroup 实际已完全冻结。

## 关键实现

### 冻结状态模型
- **`CGRP_FREEZE`**：表示用户或祖先 cgroup 请求冻结该 cgroup。
- **`CGRP_FROZEN`**：表示该 cgroup 中所有任务均已冻结，且满足冻结条件。
- 冻结状态由 `cgroup_update_frozen()` 动态计算：仅当 `CGRP_FREEZE` 为真 **且** `nr_frozen_tasks == 总任务数` 时，才设置 `CGRP_FROZEN`。

### 状态传播机制
- **向下传播**：通过 `cgroup_freeze()` 遍历所有后代，设置 `CGRP_FREEZE` 并调用 `cgroup_do_freeze()` 冻结任务。
- **向上传播**：当叶 cgroup 状态变化时，`cgroup_propagate_frozen()` 更新祖先的 `nr_frozen_descendants`，若祖先所有后代均冻结且自身被请求冻结，则祖先也被标记为 `CGRP_FROZEN`。

### 任务冻结控制
- 使用 `task->frozen` 标记任务是否已进入冻结状态。
- 使用 `task->jobctl & JOBCTL_TRAP_FREEZE` 控制任务是否应被冻结；当设置时，任务在信号处理路径中会重新进入冻结。
- 冻结/解冻通过 `signal_wake_up()` 或 `wake_up_process()` 触发任务状态检查。

### 任务迁移处理
- 任务迁移时，`cgroup_freezer_migrate_task()` 确保冻结计数在源和目标 cgroup 间正确转移，并强制任务进入目标 cgroup 的冻结状态。

### 嵌套冻结支持
- `e_freeze` 计数器跟踪冻结请求的嵌套层级（如祖先冻结会影响后代）。仅当 `e_freeze` 从 0 变为 1（冻结）或从 1 变为 0（解冻）时，才实际修改任务状态，避免重复操作。

### 空 cgroup 处理
- 在 `cgroup_do_freeze()` 末尾，显式调用 `cgroup_update_frozen()` 以处理无任务的叶 cgroup 或所有后代已冻结的情况。

## 依赖关系

- **`<linux/cgroup.h>` / `cgroup-internal.h`**：cgroup 核心框架，提供 cgroup 结构、遍历接口（如 `css_for_each_descendant_pre`）、锁机制（`cgroup_mutex`, `css_set_lock`）等。
- **`<linux/sched.h>` / `<linux/sched/task.h>` / `<linux/sched/signal.h>`**：任务调度和信号子系统，用于任务状态操作（`lock_task_sighand`）、信号唤醒（`signal_wake_up`）和任务冻结标志管理。
- **`trace/events/cgroup.h`**：提供冻结事件的跟踪点（如 `TRACE_CGROUP_PATH`），用于调试和监控。
- **Freezer 子系统**：作为 cgroup v2 的一个控制器，依赖 cgroup 的统一接口进行状态管理和事件通知（`cgroup_file_notify`）。

## 使用场景

1. **容器暂停/恢复**：容器运行时（如 Docker、containerd）通过写入 cgroup 的 `cgroup.freeze` 文件来暂停整个容器的进程，用于迁移、快照或调试。
2. **检查点/恢复（CRIU）**：在创建进程检查点前冻结所有相关进程，确保内存和状态一致性。
3. **系统休眠辅助**：在系统进入 suspend 状态前，冻结用户空间任务以减少干扰。
4. **资源隔离与调试**：临时冻结特定服务或应用组以进行性能分析或故障排查。
5. **cgroup 层次冻结**：冻结父 cgroup 会自动冻结所有子 cgroup，适用于批量管理进程组。