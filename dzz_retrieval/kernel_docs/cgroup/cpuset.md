# cgroup\cpuset.c

> 自动生成时间: 2025-10-25 12:43:36
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cgroup\cpuset.c`

---

# `cpuset.c` 技术文档

## 1. 文件概述

`cpuset.c` 是 Linux 内核中实现 **CPU 和内存节点资源约束控制组（cgroup）子系统** 的核心文件。它允许系统管理员将一组任务（进程/线程）限制在特定的 CPU 核心和内存节点（NUMA 节点）上运行，从而实现资源隔离、性能优化和拓扑感知调度。该文件同时支持 **传统（legacy）cgroup 层级** 和 **统一（default/unified）cgroup 层级**，并在统一层级中引入了 **分区（partition）** 和 **独占 CPU（exclusive CPUs）** 等高级特性，以支持实时任务、低延迟应用和系统关键服务的资源保障。

## 2. 核心功能

### 主要数据结构

*   **`struct cpuset`**: 核心数据结构，代表一个 cpuset 控制组实例。包含：
    *   `css`: 嵌入的 cgroup 子系统状态。
    *   `cpus_allowed` / `mems_allowed`: 用户配置的 CPU 和内存节点掩码。
    *   `effective_cpus` / `effective_mems`: 实际生效的 CPU 和内存节点掩码（受父级和热插拔影响）。
    *   `exclusive_cpus` / `effective_xcpus`: （统一层级）用户请求的独占 CPU 和实际分配的独占 CPU。
    *   `partition_root_state`: 分区根状态（普通成员、分区根、隔离分区根、无效等）。
    *   `nr_deadline_tasks` 等: 跟踪 `SCHED_DEADLINE` 任务，用于带宽管理。
    *   `prs_err`: 分区配置错误代码。
    *   各种标志位（`flags`）、计数器（`nr_subparts`, `child_ecpus_count`）和辅助结构（`fmeter`, `uf_node`）。
*   **`enum prs_errcode`**: 定义分区配置无效时的错误代码（如 `PERR_INVCPUS`, `PERR_NOTPART` 等）。
*   **`struct fmeter`**: “频率计”，用于平滑 `memory_pressure` 指标。
*   **`struct cpuset_remove_tasks_struct`**: 用于异步处理传统层级中任务迁移的工作结构。

### 全局变量

*   **`cpusets_pre_enable_key` / `cpusets_enabled_key`**: 静态分支预测键，用于优化 cpuset 功能未启用时的代码路径。
*   **`cpusets_insane_config_key`**: 静态分支预测键，用于快速判断是否存在异常的 cpuset 配置。
*   **`subpartitions_cpus` / `isolated_cpus`**: 全局 CPU 掩码，跟踪已分配给子分区和隔离分区的独占 CPU。
*   **`boot_hk_cpus` / `have_boot_isolcpus`**: 记录启动时由 `isolcpus` 内核参数指定的 housekeeping CPU。
*   **`remote_children`**: 链表头，用于管理远程分区根子节点。

## 3. 关键实现

*   **层级模型差异处理**:
    *   **传统层级**: 用户配置的 `cpus_allowed`/`mems_allowed` 直接作为有效掩码，并且必须是父级掩码的子集。
    *   **统一层级**: 引入了 `effective_cpus`/`effective_mems` 概念。有效掩码是用户配置掩码与父级有效掩码的交集。如果交集为空，则继承父级掩码。这提供了更大的配置灵活性。
*   **分区（Partition）机制**:
    *   允许将一个 cpuset 标记为分区根（通过 `cpuset.cpus.partition` 文件）。
    *   **本地分区**: 父级本身也是分区根。`cpuset.cpus.exclusive` 可选。
    *   **远程分区**: 父级不是分区根。**必须**通过祖先链上的 `cpuset.cpus.exclusive` 属性将独占 CPU 传递下来。
    *   分区根的有效 CPU (`effective_cpus`) 主要来源于其 `effective_xcpus`（独占 CPU），而非 `cpus_allowed`。
    *   严格的验证逻辑确保分区配置的有效性（如 CPU 不重叠、父级状态正确等），错误通过 `prs_err` 报告。
*   **独占 CPU (`exclusive_cpus`) 管理**:
    *   用户通过 `cpuset.cpus.exclusive` 指定希望独占的 CPU 集合。
    *   内核负责在分区创建和 CPU 热插拔时，从祖先的独占 CPU 池中分配 `effective_xcpus` 给子分区，并确保全局唯一性。
    *   全局变量 `subpartitions_cpus` 和 `isolated_cpus` 用于跟踪已分配的独占 CPU。
*   **与调度器集成**:
    *   更新 `cpus_allowed` 会触发任务的 CPU 亲和性 (`cpus_mask`) 更新。
    *   跟踪 `SCHED_DEADLINE` 任务数量 (`nr_deadline_tasks`)，以便在需要时重建调度域的带宽信息。
    *   `relax_domain_level` 用于自定义调度域的松弛级别。
*   **内存策略集成**:
    *   更新 `mems_allowed` 会触发任务内存策略 (`mempolicy`) 的更新，确保内存分配遵守新的节点约束。
    *   `old_mems_allowed` 用于在迁移内存策略时进行比较。
*   **CPU/内存热插拔处理**: 在 CPU 或内存节点上线/下线时，会递归更新受影响的 cpuset 的有效掩码，并可能触发任务迁移。
*   **Housekeeping 集成**: 检查分区配置是否与启动时通过 `isolcpus` 指定的 housekeeping CPU 设置冲突 (`PERR_HKEEPING`)。

## 4. 依赖关系

*   **`cgroup`**: 核心依赖，`cpuset` 是 cgroup v1 和 v2 的一个子系统。使用 `cgroup_subsys_state (css)` 进行集成。
*   **`sched`**: 深度依赖。cpuset 通过修改任务的 `cpus_mask` 影响调度器的 CPU 选择。与 `SCHED_DEADLINE` 带宽管理和调度域 (`sched_domain`) 构建紧密相关。
*   **`mm` / `mempolicy`**: 依赖内存管理子系统。cpuset 通过设置任务的内存策略 (`set_mempolicy`) 来约束内存分配的 NUMA 节点。
*   **`cpu` / `memory`**: 依赖 CPU 和内存热插拔通知机制，以动态调整 cpuset 的有效资源掩码。
*   **`cpumask` / `nodemask`**: 基础数据结构，用于表示 CPU 和内存节点的集合。
*   **`rcupdate` / `spinlock`**: 用于实现并发安全的数据访问。
*   **`workqueue`**: 用于异步处理任务迁移等可能耗时的操作（主要在传统层级）。

## 5. 使用场景

*   **资源隔离**: 将关键应用（如数据库、实时控制系统）限制在特定 CPU 和内存节点上，避免被其他任务干扰。
*   **NUMA 优化**: 将任务和其内存分配绑定到同一 NUMA 节点，减少远程内存访问延迟，提升性能。
*   **实时系统**: 结合 `SCHED_DEADLINE` 调度策略和 cpuset 分区/独占 CPU 功能，为硬实时任务提供确定性的 CPU 资源保障。
*   **虚拟化**: Hypervisor 或容器运行时（如 Docker, Kubernetes）使用 cpuset 为虚拟机或容器分配专属的 CPU 和内存资源。
*   **系统管理**: 通过 `/sys/fs/cgroup/cpuset/` (v1) 或 `/sys/fs/cgroup/` (v2) 下的接口，管理员可以动态调整进程组的资源约束。
*   **内核自保护**: 将内核线程或中断处理程序限制在特定 CPU 上，保证系统关键路径的响应性。