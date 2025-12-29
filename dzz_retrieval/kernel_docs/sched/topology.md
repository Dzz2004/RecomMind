# sched\topology.c

> 自动生成时间: 2025-10-25 16:20:01
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\topology.c`

---

# `sched/topology.c` 技术文档

## 1. 文件概述

`sched/topology.c` 是 Linux 内核调度器子系统中负责 **调度域（Scheduling Domain）拓扑结构的构建、验证与调试** 的核心实现文件。该文件定义了调度域层级结构的管理逻辑，包括调度域的退化（degenerate）判断、父子域一致性检查、以及在启用 `CONFIG_SCHED_DEBUG` 时的详细调试输出。此外，在支持能耗感知调度（EAS, Energy Aware Scheduling）的系统中，该文件还提供了与 EAS 相关的拓扑重建和系统控制接口。

## 2. 核心功能

### 主要全局变量
- `sched_domains_mutex`：保护调度域结构修改的互斥锁。
- `sched_domains_tmpmask` / `sched_domains_tmpmask2`：临时 CPU 掩码，用于调试和拓扑操作。
- `sched_energy_present`（条件编译）：静态键，指示系统是否启用了能耗感知调度。
- `sysctl_sched_energy_aware`：控制 EAS 是否启用的 sysctl 参数。

### 主要函数
- `sd_degenerate(struct sched_domain *sd)`：判断给定调度域是否为“退化”域（即无需调度逻辑的简单域）。
- `sd_parent_degenerate(struct sched_domain *sd, struct sched_domain *parent)`：判断父调度域相对于子域是否退化，用于优化拓扑结构。
- `sched_domain_debug(struct sched_domain *sd, int cpu)`（仅 `CONFIG_SCHED_DEBUG`）：递归打印调度域及其组的详细拓扑信息，并进行一致性校验。
- `sched_is_eas_possible(const struct cpumask *cpu_mask)`（EAS 条件编译）：检查当前系统是否满足启用能耗感知调度的所有前提条件。
- `rebuild_sched_domains_energy(void)`：在 EAS 配置变更时触发调度域重建。
- `sched_energy_aware_handler(...)`：`/proc/sys/kernel/sched_energy_aware` 的 sysctl 处理函数。

### 调试支持结构
- `sd_flag_debug[]`：将调度域标志（`SD_*`）映射到其名称和元属性（如 `SDF_SHARED_CHILD`），用于调试时的语义化输出和一致性检查。

## 3. 关键实现

### 调度域退化判断
- **单 CPU 域**：若调度域仅包含一个 CPU，则视为退化。
- **标志依赖**：通过 `SD_DEGENERATE_GROUPS_MASK` 宏（由 `sd_flags.h` 生成）识别那些**需要多个调度组**才能生效的标志（如 `SD_BALANCE_NEWIDLE`）。若域中只有一个组但设置了此类标志，则仍视为退化。
- **无组标志**：如 `SD_WAKE_AFFINE` 不依赖调度组，即使单 CPU 域也不退化。

### 调度域调试验证
- **层级遍历**：从 CPU 的底层域开始，逐级向上遍历至根域。
- **一致性检查**：
  - 域的 `span` 必须包含当前 CPU。
  - 域的首个组必须包含当前 CPU。
  - 共享标志（`SDF_SHARED_CHILD`/`SDF_SHARED_PARENT`）必须在父子域间一致。
  - 组的 `span` 不能重复（除非 `SD_OVERLAP` 标志置位）。
  - 所有组的 `span` 并集必须等于域的 `span`。
  - 子域的 `span` 必须等于父域首个组的 `span`。

### 能耗感知调度（EAS）支持
- **启用条件检查**：
  1. 存在非对称 CPU 算力（通过 `sd_asym_cpucapacity` 检测）。
  2. 未启用 SMT（超线程）。
  3. 架构支持频率不变负载跟踪（`arch_scale_freq_invariant()`）。
  4. 所有 CPU 使用 `schedutil` 调频策略。
- **动态重建**：当 `sched_energy_aware` sysctl 值变更且条件满足时，调用 `rebuild_sched_domains_energy()` 重建调度域以启用/禁用 EAS。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/bsearch.h>`：用于二分查找（虽未在片段中直接使用，但可能被其他部分引用）。
  - `<linux/sched/sd_flags.h>`：定义调度域标志及其元属性。
  - `<linux/cpumask.h>`：CPU 掩码操作。
  - `<linux/sched.h>`：调度器核心数据结构（`sched_domain`, `sched_group`）。
  - `<linux/cpufreq.h>`：调频策略相关（EAS 部分）。
  - `<linux/energy_model.h>`：能耗模型（EAS 部分）。
- **内核配置依赖**：
  - `CONFIG_SCHED_DEBUG`：启用调试输出和验证。
  - `CONFIG_ENERGY_MODEL` + `CONFIG_CPU_FREQ_GOV_SCHEDUTIL`：启用 EAS 支持。
  - `CONFIG_PROC_SYSCTL`：提供 EAS 的 sysctl 接口。
- **外部接口**：
  - `rebuild_sched_domains()`：由该文件调用，实际定义在 `kernel/sched/core.c` 中，用于触发全局调度域重建。

## 5. 使用场景

- **系统启动/拓扑变更**：在 CPU 热插拔、NUMA 拓扑变化或调度参数调整时，内核调用 `rebuild_sched_domains()`，该文件中的退化判断逻辑用于**优化调度域层级**，移除不必要的中间层。
- **调度器调试**：当内核启动参数包含 `sched_verbose` 时，调度域构建过程会输出详细拓扑信息并执行严格的一致性检查，帮助开发者诊断调度器配置错误。
- **能耗优化**：在 ARM big.LITTLE 等异构系统中，管理员可通过 `/proc/sys/kernel/sched_energy_aware` 动态启用 EAS，该文件负责验证系统兼容性并触发调度域重建以激活能耗感知调度逻辑。
- **性能调优**：通过分析 `sched_domain_debug` 输出，系统管理员可理解当前调度域结构，进而调整 `sched_domain` 相关内核参数（如 `SD_*` 标志）以优化负载均衡行为。