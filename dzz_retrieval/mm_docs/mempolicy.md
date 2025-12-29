# mempolicy.c

> 自动生成时间: 2025-12-07 16:44:01
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `mempolicy.c`

---

# mempolicy.c 技术文档

## 1. 文件概述

`mempolicy.c` 实现了 Linux 内核中的 NUMA（Non-Uniform Memory Access）内存策略机制，允许用户通过系统调用为进程或虚拟内存区域（VMA）指定内存分配偏好。该机制支持多种内存分配策略，包括本地优先、绑定节点、轮询交错和基于权重的交错分配等，以优化多节点 NUMA 系统上的内存访问性能。

## 2. 核心功能

### 主要数据结构
- `struct mempolicy`：表示内存策略的核心结构，包含策略模式（如 MPOL_INTERLEAVE、MPOL_BIND、MPOL_PREFERRED 等）、节点掩码（nodemask）和引用计数。
- `struct weighted_interleave_state`：用于实现加权交错分配策略，包含每个节点的权重表（iw_table）和自动模式标志。
- `default_policy`：全局默认内存策略，初始为 MPOL_LOCAL（本地节点优先）。
- `preferred_node_policy[MAX_NUMNODES]`：为每个节点预定义的首选策略数组。

### 主要函数与接口
- `get_il_weight(int node)`：获取指定节点在加权交错策略中的权重。
- `reduce_interleave_weights(unsigned int *bw, u8 *new_iw)`：将带宽值转换为归一化的交错权重。
- `mempolicy_set_node_perf(unsigned int node, struct access_coordinate *coords)`：根据节点性能坐标（读/写带宽）动态更新加权交错策略。
- 多个辅助函数用于策略创建、复制、合并、验证及与 VMA 和进程上下文的集成。

### 全局变量
- `policy_cache` / `sn_cache`：用于高效分配 mempolicy 和相关子结构的 slab 缓存。
- `policy_zone`：标识受策略控制的最高内存区域类型（zone_type），低区域（如 GFP_DMA）不应用策略。
- `wi_state`：RCU 保护的加权交错状态指针。
- `node_bw_table`：存储各节点带宽信息，用于动态权重计算。
- `weightiness`：权重归一化常量（值为 32），平衡权重精度与分配公平性。

## 3. 关键实现

### 策略优先级与作用域
- **VMA 策略优先于进程策略**：页错误处理时，若 VMA 有策略则使用 VMA 策略，否则回退到当前进程的策略。
- **中断上下文忽略策略**：所有中断相关的内存分配始终尝试在本地 CPU 节点分配。
- **策略不跨 swap 保留**：进程策略在页面换出/换入时不被保留。

### 加权交错分配（Weighted Interleave）
- 基于各 NUMA 节点的读/写带宽动态计算分配权重。
- 使用 `weightiness=32` 对带宽进行缩放，并通过 GCD（最大公约数）约简权重以减少分配周期长度。
- 权重状态通过 RCU 机制安全更新，读路径无锁，写路径由 `wi_state_lock` 互斥锁保护。

### 策略类型详解
- **interleave**：按偏移量（VMA）或进程计数器（进程）在节点集上轮询分配。
- **weighted interleave**：按节点权重比例分配（如权重 [2,1] 表示节点0:节点1 = 2:1）。
- **bind**：严格限制在指定节点集分配，无回退（当前实现按节点顺序分配，非最优）。
- **preferred / preferred many**：优先在指定单个/多个节点分配，失败后回退到默认策略。
- **default / local**：优先本地节点分配，VMA 中则继承进程策略。

### 内存区域限制
- 仅对 **最高 zone 层级**（如 NORMAL 或 MOVABLE）应用策略，GFP_DMA、HIGHMEM 等低层级分配忽略策略。

### 特殊共享内存处理
- **shmem/tmpfs**：策略在所有映射进程间共享，即使无活跃映射也持久保存。

## 4. 依赖关系

- **内存管理子系统**：依赖 `<linux/mm.h>`、`<linux/vm_area_struct.h>`、`<linux/page-flags.h>` 等进行页分配、VMA 操作和页表遍历。
- **NUMA 感知调度**：与 `<linux/sched/numa_balancing.h>` 协同，支持自动 NUMA 迁移。
- **CPUSET 子系统**：通过 `<linux/cpuset.h>` 集成节点可用性约束。
- **Slab 分配器**：使用 kmem_cache 管理 mempolicy 对象生命周期。
- **RCU 机制**：用于加权交错状态的无锁读取。
- **系统调用接口**：通过 `sys_mbind()`、`sys_set_mempolicy()` 等提供用户空间配置入口。
- **安全模块**：调用 LSM hooks（`security_task_movememory()`）进行权限检查。

## 5. 使用场景

- **高性能计算（HPC）应用**：通过 `mbind()` 将关键数据结构绑定到特定 NUMA 节点，减少远程内存访问延迟。
- **数据库系统**：使用交错策略均衡多节点内存带宽，提升吞吐量。
- **虚拟化环境**：VMM 可为不同虚拟机设置独立内存策略，隔离资源并优化性能。
- **自动 NUMA 优化**：内核 NUMA balancing 机制结合默认策略，自动迁移热点页面至访问 CPU 所在节点。
- **实时系统**：通过 `MPOL_BIND` 严格限制内存位置，确保确定性访问延迟。
- **大页（HugeTLB）分配**：策略同样适用于透明大页和显式 HugeTLB 页面分配。