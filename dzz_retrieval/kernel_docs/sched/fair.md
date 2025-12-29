# sched\fair.c

> 自动生成时间: 2025-10-25 16:09:04
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\fair.c`

---

# `sched/fair.c` 技术文档

## 1. 文件概述

`sched/fair.c` 是 Linux 内核中 **完全公平调度器**（Completely Fair Scheduler, CFS）的核心实现文件，负责实现 `SCHED_NORMAL` 和 `SCHED_BATCH` 调度策略。CFS 旨在通过红黑树（RB-tree）维护可运行任务的虚拟运行时间（vruntime），以实现 CPU 时间的公平分配。该文件实现了任务调度、负载跟踪、时间片计算、组调度（group scheduling）、NUMA 负载均衡、带宽控制等关键机制，是 Linux 通用调度子系统的核心组成部分。

## 2. 核心功能

### 主要数据结构
- `struct sched_entity`：调度实体，代表一个可调度单元（任务或任务组）
- `struct cfs_rq`：CFS 运行队列，管理一组调度实体
- `struct load_weight`：负载权重结构，用于计算任务对系统负载的贡献

### 关键函数与宏
- `__calc_delta()` / `calc_delta_fair()`：计算基于权重的调度时间增量
- `update_load_add()` / `update_load_sub()` / `update_load_set()`：更新负载权重
- `__update_inv_weight()`：预计算权重的倒数以优化除法运算
- `get_update_sysctl_factor()`：根据在线 CPU 数量动态调整调度参数
- `update_sysctl()` / `sched_init_granularity()`：初始化和更新调度粒度参数
- `for_each_sched_entity()`：遍历调度实体层级结构（用于组调度）

### 可调参数（sysctl）
- `sysctl_sched_base_slice`：基础时间片（默认 700,000 纳秒）
- `sysctl_sched_tunable_scaling`：调度参数缩放策略（NONE/LOG/LINEAR）
- `sysctl_sched_migration_cost`：任务迁移成本阈值（500 微秒）
- `sysctl_sched_cfs_bandwidth_slice_us`（CFS 带宽控制切片，默认 5 毫秒）
- `sysctl_numa_balancing_promote_rate_limit_MBps`（NUMA 页迁移速率限制）

## 3. 关键实现

### 虚拟时间与公平性
CFS 使用 **虚拟运行时间**（vruntime）衡量任务已使用的 CPU 时间，并通过 `calc_delta_fair()` 将实际执行时间按任务权重归一化。权重由任务的 nice 值决定（`NICE_0_LOAD = 1024` 为基准）。调度器总是选择 vruntime 最小的任务运行，确保高优先级（高权重）任务获得更多 CPU 时间。

### 高效除法优化
为避免频繁除法运算，CFS 预计算 `inv_weight = WMULT_CONST / weight`（`WMULT_CONST = ~0U`），将除法转换为乘法和右移操作（`mul_u64_u32_shr`）。`__calc_delta()` 通过动态调整移位位数（`shift`）保证计算精度，适用于 32/64 位架构。

### 动态粒度调整
基础时间片 `sched_base_slice` 根据在线 CPU 数量动态缩放：
- `SCHED_TUNABLESCALING_NONE`：固定值
- `SCHED_TUNABLESCALING_LINEAR`：线性缩放（×ncpus）
- `SCHED_TUNABLESCALING_LOG`（默认）：对数缩放（×(1 + ilog2(ncpus))）  
此设计确保在多核系统中保持合理的调度延迟和交互性。

### 组调度支持
通过 `for_each_sched_entity()` 宏遍历任务所属的调度实体层级（任务 → 任务组 → 父任务组），实现 CPU 带宽在任务组间的公平分配。每个 `cfs_rq` 独立维护其子实体的红黑树。

### SMP 相关优化
- **非对称 CPU 优先级**：`arch_asym_cpu_priority()` 允许架构定义 CPU 能力差异（如大小核）
- **容量比较宏**：`fits_capacity()`（20% 容差）和 `capacity_greater()`（5% 容差）用于负载均衡决策

## 4. 依赖关系

### 内核头文件依赖
- 调度核心：`"sched.h"`、`"stats.h"`、`"autogroup.h"`
- 系统服务：`<linux/sched/clock.h>`、`<linux/sched/nohz.h>`、`<linux/psi.h>`
- 内存管理：`<linux/mem_policy.h>`、`<linux/energy_model.h>`
- SMP 支持：`<linux/topology.h>`、`<linux/cpumask_api.h>`
- 数据结构：`<linux/rbtree_augmented.h>`

### 条件编译特性
- `CONFIG_SMP`：多处理器调度优化
- `CONFIG_CFS_BANDWIDTH`：CPU 带宽限制（cgroup v1/v2）
- `CONFIG_NUMA_BALANCING`：NUMA 自动迁移
- `CONFIG_FAIR_GROUP_SCHED`：CFS 组调度（cgroup 支持）

## 5. 使用场景

- **通用任务调度**：所有使用 `SCHED_NORMAL` 或 `SCHED_BATCH` 策略的用户态进程
- **cgroup CPU 资源控制**：通过 `cpu.cfs_quota_us` 和 `cpu.cfs_period_us` 限制任务组带宽
- **NUMA 优化**：自动迁移内存页以减少远程访问（`numa_balancing`）
- **节能调度**：结合 `energy_model` 在满足性能前提下选择低功耗 CPU
- **实时性保障**：通过 `cond_resched()` 在长循环中主动让出 CPU，避免内核抢占延迟过高
- **系统调优**：管理员通过 `/proc/sys/kernel/` 下的 sysctl 参数动态调整调度行为