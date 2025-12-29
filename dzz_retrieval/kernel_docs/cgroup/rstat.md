# cgroup\rstat.c

> 自动生成时间: 2025-10-25 12:51:37
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cgroup\rstat.c`

---

# cgroup/rstat.c 技术文档

## 1. 文件概述

`cgroup/rstat.c` 实现了 cgroup 资源统计（rstat）的底层机制，用于高效地跟踪和聚合每个 CPU 上的 cgroup 资源使用情况（如 CPU 时间、内存等）。该机制采用延迟刷新（lazy flush）策略，通过 per-CPU 数据结构和精细的锁控制，减少高频更新路径的开销，并支持 BPF 程序集成以扩展统计能力。

## 2. 核心功能

### 主要函数

- `cgroup_rstat_updated(struct cgroup *cgrp, int cpu)`  
  标记指定 cgroup 在某 CPU 上的统计信息已更新，并将其加入祖先链的“待刷新”链表中。

- `cgroup_rstat_updated_list(struct cgroup *root, int cpu)`  
  从指定根 cgroup 开始，遍历并提取该 CPU 上所有待刷新的 cgroup，返回一个按“子在前、父在后”顺序排列的单向链表。

- `cgroup_rstat_push_children()`  
  辅助函数，用于在遍历更新树时按层级“压栈”方式构建刷新链表，确保子 cgroup 先于父 cgroup 被处理。

- `_cgroup_rstat_cpu_lock()` / `_cgroup_rstat_cpu_unlock()`  
  封装 per-CPU 自旋锁操作，支持 fast-path 与 slow-path 的 tracepoint 区分，便于性能诊断。

### 关键数据结构

- `struct cgroup_rstat_cpu`（定义于 `cgroup-internal.h`）  
  每个 cgroup 在每个 CPU 上的统计快照和链表指针，包含：
  - `updated_next`：指向同级链表中的下一个 cgroup，链表以父 cgroup 为终止（根 cgroup 自环）。
  - `updated_children`：指向该 cgroup 的第一个已更新子 cgroup。
  - `rstat_flush_next`：临时用于构建刷新链表的指针。

## 3. 关键实现

### 延迟刷新机制（Lazy Flush）

- **更新阶段**：当某 cgroup 在某 CPU 上的资源使用发生变化时，调用 `cgroup_rstat_updated()`，将其及其所有祖先加入 per-CPU 的“已更新”链表（`updated_children` / `updated_next`）。
- **刷新阶段**：当需要获取准确统计值时（如用户读取 `/sys/fs/cgroup/.../cpu.stat`），调用 `cgroup_rstat_updated_list()` 获取待刷新 cgroup 列表，然后自底向上（子 → 父）聚合统计值并清空链表。

### 链表结构设计

- `updated_children`：每个 cgroup 维护一个指向其**第一个已更新子 cgroup**的指针。
- `updated_next`：在子 cgroup 链表中，指向**下一个兄弟**；链表尾部指向**父 cgroup**（根 cgroup 指向自身），形成自终止结构，避免 NULL 检查。
- 此设计允许 O(1) 插入，但删除需 O(n) 遍历（因单向链表），但整体因延迟刷新而摊销成本低。

### 锁与并发控制

- 使用 per-CPU `raw_spinlock_t`（`cgroup_rstat_cpu_lock`）保护每个 CPU 的更新链表。
- 提供带 tracepoint 的锁封装，区分 fast-path（如 `cgroup_rstat_updated`）和 slow-path（如 flush 操作），便于生产环境性能分析。
- 在 PREEMPT_RT 内核中，正确处理中断禁用（使用 `raw_spin_trylock_irqsave`）。

### BPF 集成支持

- `cgroup_rstat_updated` 标记为 `__bpf_kfunc`，允许 BPF 程序调用以通知内核其自定义统计已更新。
- 预留 hook（代码末尾注释）用于 BPF 程序在 flush 阶段回调，实现完整的 BPF 统计收集与刷新流程。

## 4. 依赖关系

- **内部依赖**：
  - `cgroup-internal.h`：定义 `struct cgroup_rstat_cpu` 及相关 cgroup 内部接口（如 `cgroup_parent()`）。
- **内核子系统**：
  - **cgroup 核心**：依赖 cgroup 层级结构和生命周期管理。
  - **调度器**：通过 `linux/sched/cputime.h` 获取 CPU 时间统计。
  - **BPF 子系统**：通过 `linux/bpf.h`、`linux/btf.h` 支持 BPF kfunc 和类型信息。
  - **tracepoint**：使用 `trace/events/cgroup.h` 中定义的 tracepoint 用于锁竞争诊断。

## 5. 使用场景

- **资源控制器统计聚合**：如 CPU controller 在读取 `cpu.stat` 时，触发 rstat flush 以获取精确的 CPU 时间。
- **BPF 资源监控程序**：BPF 程序可调用 `cgroup_rstat_updated()` 标记自定义指标更新，并在内核 flush 时同步数据。
- **高频率更新优化**：适用于需要 per-CPU 快速更新（如进程切换时的 CPU 时间累加），但低频精确读取的场景，避免每次更新都遍历 cgroup 层级。
- **性能分析**：通过 tracepoint 监控 rstat 锁竞争情况，诊断 cgroup 统计路径的性能瓶颈。