# sched\syscalls.c

> 自动生成时间: 2025-10-25 16:19:13
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\syscalls.c`

---

# `sched/syscalls.c` 技术文档

## 1. 文件概述

`sched/syscalls.c` 是 Linux 内核调度子系统的核心源文件之一，主要负责实现与调度相关的系统调用接口和优先级管理逻辑。该文件封装了任务优先级计算、nice 值设置、CPU 空闲状态判断等关键功能，为用户空间提供 `nice()` 等系统调用的内核支持，并为调度器内部模块提供优先级操作原语。

## 2. 核心功能

### 主要函数

- `__normal_prio()`：根据调度策略（SCHED_NORMAL/SCHED_BATCH/SCHED_IDLE、SCHED_FIFO/SCHED_RR、SCHED_DEADLINE）计算任务的“正常”优先级。
- `normal_prio()`：基于任务当前策略、实时优先级和静态 nice 值计算其正常优先级。
- `effective_prio()`：计算任务当前实际生效的调度优先级，考虑 RT 继承或提升。
- `set_user_nice()`：安全地修改指定任务的 nice 值，更新其静态优先级和调度权重，并触发调度器重评估。
- `is_nice_reduction()` / `can_nice()`：检查任务是否具备降低 nice 值（即提高优先级）的权限。
- `sys_nice()`：实现 `nice(2)` 系统调用，允许当前进程调整自身优先级。
- `task_prio()`：返回任务在 `/proc` 中对外暴露的用户可见优先级值。
- `idle_cpu()` / `available_idle_cpu()`：判断指定 CPU 是否处于空闲状态。
- `idle_task()`：获取指定 CPU 的 idle 任务结构体。
- `update_other_load_avgs()`（SMP）：更新除 CFS 外其他调度类（RT、DL、IRQ）的负载平均值。
- `effective_cpu_util()`（SMP）：计算 CPU 的有效利用率，用于频率调节（如 CPUFreq）。

### 关键数据结构
- 无独立定义的数据结构，主要操作 `struct task_struct` 和 `struct rq`（运行队列）。

## 3. 关键实现

### 优先级计算模型
- **优先级映射**：
  - 用户态 nice 值范围 `[-20, 19]` 映射到内核静态优先级 `[100, 139]`（通过 `NICE_TO_PRIO`）。
  - 实时任务（RT/DL）使用 `[0, 99]` 的高优先级范围（`MAX_RT_PRIO = 100`）。
  - `task_prio()` 返回值将内核优先级转换为用户可见格式：普通任务为 `[0,39]`，RT 任务为 `[-2,-100]`，DL 任务为 `-101`。
- **有效优先级**：`effective_prio()` 区分“正常优先级”与“被提升的优先级”。若任务当前优先级为 RT/DL（即 `rt_or_dl_prio(p->prio)` 为真），则保留提升后的值；否则使用 `normal_prio`。

### Nice 值修改安全机制
- `set_user_nice()` 在修改 nice 值前：
  1. 获取任务所在 CPU 的运行队列锁（`task_rq_lock`），防止并发调度。
  2. 对 RT/DL 任务仅更新 `static_prio`（不影响调度行为）。
  3. 对普通任务，先从运行队列中移除（若已入队或正在运行），更新 `static_prio` 和负载权重（`set_load_weight`），重新计算 `prio`，再重新入队。
  4. 调用调度类的 `prio_changed` 回调，通知调度器优先级变更。

### 权限控制
- `can_nice()` 结合资源限制（`RLIMIT_NICE`）和特权（`CAP_SYS_NICE`）判断是否允许降低 nice 值（提高优先级）。
- `nice_to_rlimit()` 将 nice 值 `[19,-20]` 转换为 rlimit 格式 `[1,40]` 以匹配 `RLIMIT_NICE` 的语义。

### CPU 空闲判断
- `idle_cpu()` 检查：
  - 当前运行任务是否为 idle 任务。
  - 运行队列中无其他可运行任务（`nr_running == 0`）。
  - （SMP）无待处理的远程唤醒（`ttwu_pending == 0`）。
- `available_idle_cpu()` 额外检查虚拟化场景下 CPU 是否被抢占（`vcpu_is_preempted`）。

### 负载与利用率计算（SMP）
- `update_other_load_avgs()` 周期性更新 RT、DL、IRQ 和硬件压力的负载平均值。
- `effective_cpu_util()` 聚合 CFS、RT、DL、IRQ 的利用率，并考虑 DL 带宽预留，输出用于 CPU 频率调节的有效利用率。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/sched.h>`：核心调度数据结构和 API。
  - `<linux/cpuset.h>`：CPU 亲和性相关（间接影响调度）。
  - `"sched.h"`（本地）：调度器内部实现细节。
  - `"autogroup.h"`：自动任务分组支持。
- **调度类依赖**：
  - 调用各调度类（CFS、RT、DL）的回调函数（如 `prio_changed`、`enqueue_task` 等）。
- **安全模块**：调用 LSM 钩子 `security_task_setnice()`。
- **架构相关**：
  - `arch_scale_cpu_capacity()` / `arch_scale_hw_pressure()`：架构特定的 CPU 容量和硬件压力缩放。
  - `__ARCH_WANT_SYS_NICE`：控制 `sys_nice` 是否编译进内核。

## 5. 使用场景

- **系统调用处理**：为 `nice(2)` 系统调用提供内核实现，允许用户进程动态调整自身优先级。
- **调度器内部操作**：
  - 在 `fork()`、`sched_setscheduler()` 等操作中计算任务优先级。
  - 调度类在任务入队/出队时更新优先级和负载。
- **资源监控与管理**：
  - `/proc/[pid]/stat` 中的优先级字段通过 `task_prio()` 获取。
  - 负载均衡器和 CPUFreq 驱动使用 `effective_cpu_util()` 获取 CPU 利用率。
- **空闲检测**：
  - 负载均衡、任务迁移、节能策略（如 cpuidle）依赖 `idle_cpu()` 和 `available_idle_cpu()` 判断 CPU 状态。
- **权限控制**：在设置优先级时执行安全检查，防止非特权进程提升调度优先级。