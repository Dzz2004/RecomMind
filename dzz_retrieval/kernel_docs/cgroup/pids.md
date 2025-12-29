# cgroup\pids.c

> 自动生成时间: 2025-10-25 12:50:03
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cgroup\pids.c`

---

# cgroup/pids.c 技术文档

## 1. 文件概述

`cgroup/pids.c` 实现了 Linux 内核中 cgroup 的 **PID 控制器（pids controller）**，用于限制指定 cgroup 及其子层级中可创建的最大进程（任务）数量。该控制器通过监控 `fork()` 系统调用，在进程数量即将超过设定阈值时拒绝创建新进程（返回 `-EAGAIN`），从而防止 PID 资源耗尽。该控制器支持层级继承语义，即子 cgroup 的有效限制为其自身与所有祖先中**最严格**的限制。

## 2. 核心功能

### 主要数据结构

- **`struct pids_cgroup`**  
  表示一个 cgroup 的 PID 控制状态，包含：
  - `counter`：当前 cgroup 中的进程数量（64 位原子计数器）
  - `limit`：允许的最大进程数（64 位原子值，`PIDS_MAX` 表示无限制）
  - `watermark`：历史最高进程数（用于监控）
  - `events` / `events_local`：事件计数器（如 `PIDCG_MAX`、`PIDCG_FORKFAIL`）
  - `events_file` / `events_local_file`：用于通知用户空间事件发生的 cgroup 文件句柄

- **`enum pidcg_event`**  
  定义两类事件：
  - `PIDCG_MAX`：因本 cgroup 或祖先限制被触发而导致 fork 失败
  - `PIDCG_FORKFAIL`：在本 cgroup 中 fork 失败（用于本地事件通知）

### 主要函数

- **资源分配与释放**
  - `pids_css_alloc()`：为新 cgroup 分配 `pids_cgroup` 结构，初始限制设为 `PIDS_MAX`（无限制）
  - `pids_css_free()`：释放 `pids_cgroup` 结构

- **计数操作**
  - `pids_charge()`：**无条件**增加指定 cgroup 及其所有祖先的进程计数（用于回滚）
  - `pids_uncharge()`：减少指定 cgroup 及其所有祖先的进程计数
  - `pids_cancel()`：内部辅助函数，执行实际的原子减操作，并检查负值（视为 bug）
  - `pids_try_charge()`：**有条件**增加计数，若任一祖先层级超过限制则回滚并返回 `-EAGAIN`

- **cgroup 钩子函数**
  - `pids_can_attach()`：在任务迁移到新 cgroup 时，更新源/目标 cgroup 的计数
  - `pids_cancel_attach()`：回滚 `pids_can_attach()` 的操作
  - `pids_can_fork()`：在 `fork()` 前检查是否允许创建新进程（未在提供的代码片段中完整显示）
  - `pids_cancel_fork()`：回滚 fork 失败时的计数（未在提供的代码片段中完整显示）

- **事件通知**
  - `pids_event()`：当 fork 因 PID 限制失败时，记录事件并通知用户空间（通过 `cgroup_file_notify`）

- **辅助函数**
  - `css_pids()`：从 `cgroup_subsys_state` 转换为 `pids_cgroup`
  - `parent_pids()`：获取父 cgroup 的 `pids_cgroup`
  - `pids_update_watermark()`：更新历史最高进程数（非原子，容忍竞态）

## 3. 关键实现

### 层级限制语义
PID 限制遵循 cgroup 的层级继承规则：一个进程的实际限制由其所在 cgroup 路径上**所有祖先中最小的 `limit` 值**决定。`pids_try_charge()` 在从当前 cgroup 向根方向遍历时，一旦发现任一祖先的 `counter + num > limit`，即判定为违反策略。

### 原子计数与回滚机制
- 所有计数操作均使用 `atomic64_t` 保证并发安全。
- `pids_try_charge()` 采用“先增加后检查+回滚”策略：先原子增加所有祖先计数，再逐级检查是否超限。若超限，则从当前节点回滚到起始节点的所有增量。
- `pids_charge()` 用于必须成功的场景（如 attach 回滚），**不检查限制**，允许临时超限。

### 事件通知机制
- 当 fork 因限制失败时，调用 `pids_event()`：
  - 在 fork 发生的 cgroup 中记录 `PIDCG_FORKFAIL` 事件（仅首次触发时打印内核日志）
  - 若启用了本地事件（通过 `cgroup v2` 的 `pids.local_events` 选项），则仅通知本地事件文件
  - 否则，在**触发限制的祖先 cgroup** 中记录 `PIDCG_MAX` 事件，并向上传播通知

### 无限制表示
使用 `PIDS_MAX = PID_MAX_LIMIT + 1` 表示“无限制”，因为实际 PID 数量不可能超过 `PID_MAX_LIMIT`，因此该值可安全用于比较（`new > limit` 永远为假）。

## 4. 依赖关系

- **`<linux/cgroup.h>`**：cgroup 核心框架，提供 `cgroup_subsys_state`、`cgroup_taskset` 等基础结构和钩子函数接口
- **`<linux/atomic.h>`**：提供 64 位原子操作（`atomic64_t`）
- **`<linux/sched/task.h>`**：提供 `task_css()` 等任务与 cgroup 关联的接口
- **`<linux/slab.h>`**：内存分配（`kzalloc`/`kfree`）
- **`pids_cgrp_id`**：全局子系统 ID，用于从 `css_set` 或 `task_struct` 中获取 PID 控制器状态
- **`cgroup_threadgroup_change_begin()`**：确保在 `fork` 过程中 cgroup 关联稳定（`pids_can_fork` 依赖此锁）

## 5. 使用场景

1. **容器资源隔离**  
   在容器运行时（如 Docker、Podman）中限制单个容器或 Pod 可创建的最大进程数，防止 fork bomb 耗尽系统 PID 资源。

2. **多租户系统防护**  
   在共享主机环境中，为不同用户或服务分配独立的 cgroup，并设置 PID 限制，避免某一用户进程泛滥影响其他用户。

3. **系统稳定性保障**  
   通过全局或关键服务 cgroup 设置 PID 上限，确保即使某个子系统异常，也不会导致整个系统因 PID 耗尽而无法创建新进程。

4. **监控与告警**  
   通过读取 `pids.current`、`pids.max` 和 `pids.events` 文件，监控进程使用情况并在接近或达到限制时触发告警。