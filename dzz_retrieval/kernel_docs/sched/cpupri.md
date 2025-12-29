# sched\cpupri.c

> 自动生成时间: 2025-10-25 16:04:45
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\cpupri.c`

---

# `sched/cpupri.c` 技术文档

## 1. 文件概述

`sched/cpupri.c` 实现了 **CPU 优先级管理（CPU Priority Management）** 机制，用于实时任务（RT tasks）的全局负载均衡和迁移决策。该机制通过维护一个二维位图结构，快速追踪每个 CPU 当前运行任务的最高优先级，从而在 O(1) 时间复杂度内为新唤醒或迁移的实时任务找到合适的 CPU 目标。该机制特别优化了无 CPU 亲和性限制的任务调度路径，同时支持带亲和性约束的场景。

## 2. 核心功能

### 主要函数

| 函数 | 功能描述 |
|------|--------|
| `convert_prio(int prio)` | 将任务的调度优先级（`p->prio`）转换为内部 `cpupri` 优先级值（范围：-1 到 100） |
| `__cpupri_find(struct cpupri *cp, struct task_struct *p, struct cpumask *lowest_mask, int idx)` | 在指定优先级层级 `idx` 中查找满足任务 `p` 的 CPU（考虑亲和性） |
| `cpupri_find(struct cpupri *cp, struct task_struct *p, struct cpumask *lowest_mask)` | 查找系统中优先级 **低于或等于** 任务 `p` 的 CPU（即任务可运行的 CPU） |
| `cpupri_find_fitness(...)` | 增强版查找函数，支持通过 `fitness_fn` 自定义 CPU 适配条件（如容量感知） |
| `cpupri_set(struct cpupri *cp, int cpu, int newpri)` | 更新指定 CPU 的当前最高优先级状态 |
| `cpupri_init(struct cpupri *cp)` | 初始化 `cpupri` 数据结构（声明但未在片段中实现） |

### 关键数据结构（隐含）

- `struct cpupri`：全局 CPU 优先级管理上下文
  - `cpu_to_pri[]`：每个 CPU 当前的 `cpupri` 优先级
  - `pri_to_cpu[]`：每个优先级对应的 `struct cpupri_vec`
- `struct cpupri_vec`：
  - `mask`：该优先级下所有 CPU 的位图
  - `count`：该优先级下活跃 CPU 的数量（原子计数）

### 优先级映射关系

| 任务 `p->prio` | `cpupri` 值 | 含义 |
|---------------|------------|------|
| -1 | -1 (`CPUPRI_INVALID`) | 无效状态（CPU 不可调度） |
| 0–98 | 99–1 | 实时优先级（数值越大，任务优先级越高，`cpupri` 值越小） |
| 99 (`MAX_RT_PRIO-1`) | 0 (`CPUPRI_NORMAL`) | 普通（非实时）任务 |
| 100 (`MAX_RT_PRIO`) | 100 (`CPUPRI_HIGHER`) | 高于所有 RT 任务的特殊优先级 |

> **注意**：`cpupri` 值越小，表示 CPU 当前负载的优先级 **越高**。

## 3. 关键实现

### 优先级转换逻辑
- `convert_prio()` 实现了任务调度优先级到 `cpupri` 内部表示的映射，确保实时任务（`p->prio` ∈ [0, 98]）被正确映射到 `cpupri` ∈ [1, 99]，且高优先级任务对应更小的 `cpupri` 值。

### 快速查找算法
- 使用 **二维位图**：第一维为优先级（0–100），第二维为 CPU 位图。
- `cpupri_find_fitness()` 从最低优先级（`idx = 0`）开始遍历，找到第一个存在可用 CPU 的优先级层级。
- 对于每个层级，通过 `cpumask_any_and()` 快速判断任务亲和性掩码与该优先级 CPU 掩码是否有交集。
- 若提供 `fitness_fn`（如容量检查），会过滤掉不满足条件的 CPU；若过滤后无 CPU 可用，则继续搜索更高优先级层级。

### 容错与回退策略
- 如果启用了 `fitness_fn` 但未找到满足条件的 CPU，函数会 **忽略 fitness 条件重新搜索**，确保高优先级任务总能找到运行 CPU（优先保证实时性，而非最优资源匹配）。

### 并发安全更新
- `cpupri_set()` 使用 **内存屏障（`smp_mb__before/after_atomic()`）** 确保 CPU 位图和计数器的更新顺序：
  1. **添加 CPU**：先设置位图 → 内存屏障 → 增加计数器
  2. **移除 CPU**：先减少计数器 → 内存屏障 → 清除位图
- 此顺序防止 `cpupri_find` 在并发读取时看到不一致状态（如计数器为 0 但位图仍置位）。

### 亲和性处理
- 所有查找操作均与任务的 `p->cpus_mask`（CPU 亲和性）和 `cpu_active_mask`（活跃 CPU）进行交集运算，确保只返回合法 CPU。

## 4. 依赖关系

- **调度器核心**：依赖 `task_struct`、`p->prio`、`p->cpus_mask` 等调度器基本结构。
- **实时调度类（`rt.c`）**：`cpupri` 主要服务于 `SCHED_FIFO`/`SCHED_RR` 任务的负载均衡。
- **CPU 掩码操作**：使用 `cpumask_*` 系列函数（如 `cpumask_and`, `cpumask_clear_cpu`）。
- **内存屏障原语**：依赖 `smp_rmb()`、`smp_mb__before_atomic()` 等 SMP 同步机制。
- **原子操作**：使用 `atomic_read/inc/dec` 管理优先级层级的 CPU 计数。

## 5. 使用场景

- **实时任务唤醒/迁移**：当高优先级 RT 任务被唤醒或需要迁移时，调用 `cpupri_find()` 快速定位可运行的最低优先级 CPU（减少抢占开销）。
- **全局负载均衡**：RT 调度器的 `push_rt_task()` 和 `pull_rt_task()` 机制利用 `cpupri` 决定任务推送/拉取的目标 CPU。
- **容量感知调度（Capacity Awareness）**：通过 `cpupri_find_fitness()` 的 `fitness_fn` 参数，集成 CPU 性能/能效信息（如 ARM big.LITTLE 架构），在满足优先级前提下选择合适 CPU。
- **CPU 热插拔**：CPU 上下线时通过 `cpupri_set()` 更新其优先级状态（设为 `CPUPRI_INVALID` 或恢复）。