# sched\cputime.c

> 自动生成时间: 2025-10-25 16:05:48
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\cputime.c`

---

# `sched/cputime.c` 技术文档

## 1. 文件概述

`sched/cputime.c` 是 Linux 内核调度子系统中负责 **CPU 时间统计与会计（accounting）** 的核心实现文件。其主要功能包括：

- 对用户态、内核态、中断（硬中断/软中断）、虚拟机（guest）、steal、idle、iowait 等各类 CPU 时间进行精确统计；
- 支持将 CPU 时间按进程、线程组（thread group）和 cgroup 层级进行聚合；
- 在启用 `CONFIG_IRQ_TIME_ACCOUNTING` 时，提供基于高精度调度时钟（`sched_clock`）的中断时间细粒度追踪；
- 为 `/proc/stat`、`/proc/[pid]/stat`、cgroup v1/v2 的 CPU 统计接口提供底层数据支持。

该文件是内核 CPU 使用率监控、资源控制和性能分析的基础组件。

---

## 2. 核心功能

### 主要数据结构

- `struct irqtime`（仅当 `CONFIG_IRQ_TIME_ACCOUNTING` 启用）  
  每 CPU 变量，用于记录当前 CPU 上硬中断和软中断的累计时间及同步状态。
- `cpu_irqtime`  
  `DEFINE_PER_CPU(struct irqtime, cpu_irqtime)`，每个 CPU 的中断时间统计结构。

### 主要函数

| 函数 | 功能说明 |
|------|--------|
| `account_user_time()` | 统计进程在用户态消耗的 CPU 时间 |
| `account_guest_time()` | 统计进程作为虚拟机 guest 消耗的 CPU 时间 |
| `account_system_time()` | 统计进程在内核态（含中断上下文）消耗的 CPU 时间 |
| `account_system_index_time()` | 按指定类型（IRQ/SOFTIRQ/SYSTEM）统计系统态时间 |
| `account_steal_time()` | 统计因虚拟化导致的“被偷走”的 CPU 时间 |
| `account_idle_time()` | 统计 CPU 空闲时间（区分 iowait 与普通 idle） |
| `irqtime_account_irq()` | 在中断进入/退出时更新中断时间统计 |
| `thread_group_cputime()` | 聚合线程组内所有任务的累计 CPU 时间（未完整显示） |
| `account_other_time()` | 综合统计 steal、IRQ、softirq 等“非任务执行”时间 |
| `read_sum_exec_runtime()` | 安全读取任务的累计执行时间（32 位平台加锁） |

### 控制接口

- `enable_sched_clock_irqtime()` / `disable_sched_clock_irqtime()`  
  动态启停基于 `sched_clock` 的中断时间会计功能。

---

## 3. 关键实现

### 中断时间会计（`CONFIG_IRQ_TIME_ACCOUNTING`）

- 使用每 CPU 的 `cpu_irqtime` 结构，通过 `u64_stats` 同步机制保证读写一致性；
- 在 `{soft,}irq_enter/exit` 路径中调用 `irqtime_account_irq()`，利用 `sched_clock_cpu()` 计算中断持续时间；
- **无锁设计**：写操作仅在本 CPU 中断关闭时进行，读操作（如 `update_rq_clock()`）可能读到稍旧值，但避免了中断路径加锁开销；
- 特殊处理 `ksoftirqd`：其软中断时间仍计入该内核线程自身，避免调度器误判。

### 时间分类与统计

- **用户时间**：根据 `task_nice(p) > 0` 区分 `CPUTIME_USER` 与 `CPUTIME_NICE`；
- **Guest 时间**：同时计入用户时间与 `CPUTIME_GUEST`/`GUEST_NICE`；
- **系统时间**：根据中断上下文动态判断为 `IRQ`、`SOFTIRQ` 或 `SYSTEM`；
- **Idle 时间**：通过 `rq->nr_iowait` 判断是否为 I/O 等待状态；
- **Steal 时间**：通过 `paravirt_steal_clock()` 获取虚拟化层报告的被抢占时间。

### cgroup 集成

- 所有时间统计均通过 `task_group_account_field()` 同时更新：
  - 全局 `kernel_cpustat`（用于 `/proc/stat`）；
  - 当前任务所属 cgroup 的 CPU 统计（通过 `cgroup_account_cputime_field()`）。

### 32 位平台兼容性

- 在 32 位系统上，`sum_exec_runtime` 的读取需加 `rq` 锁以避免 64 位值撕裂（tearing）；
- 64 位平台可直接原子读取。

---

## 4. 依赖关系

- **架构依赖**：
  - `CONFIG_VIRT_CPU_ACCOUNTING_NATIVE`：包含 `<asm/cputime.h>`，用于架构特定的 CPU 时间处理；
- **配置选项**：
  - `CONFIG_IRQ_TIME_ACCOUNTING`：启用高精度中断时间追踪；
  - `CONFIG_PARAVIRT`：支持虚拟化 steal time 统计；
  - `CONFIG_SCHED_CORE`：支持 core scheduling 的 forceidle 时间统计；
  - `CONFIG_CGROUPS`：通过 `cgroup_account_cputime_field()` 集成 cgroup CPU 统计；
- **内核模块**：
  - 调度器核心（`kernel/sched/core.c`）：调用时间会计函数；
  - 进程管理（`kernel/fork.c`, `kernel/exit.c`）：使用 `thread_group_cputime()`；
  - 虚拟化子系统（`arch/*/kernel/paravirt.c`）：提供 `paravirt_steal_clock()`；
  - procfs（`fs/proc/stat.c`）：读取 `kcpustat_this_cpu` 生成 `/proc/stat`。

---

## 5. 使用场景

1. **系统监控工具**  
   `top`、`htop`、`vmstat`、`iostat` 等通过 `/proc/stat` 获取全局 CPU 使用分布（user/nice/system/irq/steal 等）。

2. **进程资源统计**  
   `/proc/[pid]/stat` 中的 `utime`/`stime` 字段由 `account_user_time()` 和 `account_system_time()` 更新。

3. **cgroup 资源控制**  
   cgroup v1 的 `cpuacct` 子系统和 cgroup v2 的 `cpu.stat` 依赖 `task_group_account_field()` 聚合计费数据。

4. **虚拟化性能分析**  
   在 KVM/Xen 等虚拟机中，`steal time` 反映宿主机对 vCPU 的调度延迟，用于诊断性能瓶颈。

5. **调度器决策**  
   CFS 调度器使用 `sum_exec_runtime` 进行公平调度；`ksoftirqd` 的特殊处理确保软中断负载被正确感知。

6. **功耗与能效分析**  
   精确的 idle/iowait/irq 时间统计为 CPU 频率调节（如 `intel_pstate`）和电源管理提供依据。