# oom_kill.c

> 自动生成时间: 2025-12-07 16:58:11
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `oom_kill.c`

---

# oom_kill.c 技术文档

## 1. 文件概述

`oom_kill.c` 是 Linux 内核内存管理子系统中的关键组件，负责在系统严重内存不足（Out-Of-Memory, OOM）时选择并终止一个或多个进程，以释放内存资源、防止系统崩溃。该文件实现了 OOM Killer 的核心逻辑，包括候选进程的选择策略、内存压力评估、以及与内存控制组（memcg）、NUMA 策略、cpuset 等子系统的集成。OOM Killer 通常由 `__alloc_pages()` 在无法满足内存分配请求时触发。

## 2. 核心功能

### 主要函数
- **`out_of_memory()`**：OOM Killer 的主入口函数（虽未在片段中完整显示，但为本文件核心）
- **`oom_badness()`**：计算进程“坏度”（badness）分数的核心启发式函数，用于决定哪个进程最应被杀死
- **`find_lock_task_mm()`**：在进程及其线程组中查找具有有效内存描述符（`mm_struct`）的可杀任务，并加锁
- **`oom_unkillable_task()`**：判断某任务是否不可被 OOM Killer 杀死（如 init 进程、内核线程）
- **`constrained_alloc()`**：确定当前内存分配所受的约束类型（如 memcg、cpuset、mempolicy）
- **`oom_cpuset_eligible()`**（仅 CONFIG_NUMA）：在 NUMA 系统中检查任务是否符合 cpuset 或 mempolicy 的 OOM 杀死条件
- **`should_dump_unreclaim_slab()`**：判断是否因不可回收 slab 内存过多而触发 OOM，用于辅助诊断

### 关键数据结构
- **`struct oom_control`**：封装 OOM 事件上下文，包括分配标志（`gfp_mask`）、节点掩码（`nodemask`）、内存控制组（`memcg`）、分配阶数（`order`）等
- **`enum oom_constraint`**：表示内存分配受限的类型（`CONSTRAINT_NONE`、`CONSTRAINT_CPUSET`、`CONSTRAINT_MEMORY_POLICY`、`CONSTRAINT_MEMCG`）

### 全局变量
- **`sysctl_panic_on_oom`**：控制 OOM 时是否直接 panic
- **`sysctl_oom_kill_allocating_task`**：若置位，则优先杀死触发 OOM 的进程
- **`sysctl_oom_dump_tasks`**：控制 OOM 时是否打印所有任务的内存使用信息
- **`oom_lock`**：互斥锁，序列化 OOM Killer 调用，防止并发过度杀进程
- **`oom_adj_mutex`**：互斥锁，保护 `oom_score_adj` 和 `oom_score_adj_min` 的更新

## 3. 关键实现

### OOM 坏度评分算法 (`oom_badness`)
- **基础分值**：基于进程的 RSS（Resident Set Size）、交换页数量（`MM_SWAPENTS`）和页表占用内存（`mm_pgtables_bytes`），单位为页数。
- **调整因子**：通过 `oom_score_adj`（范围 [-1000, 1000]）进行线性调整。调整量 = `oom_score_adj * totalpages / 1000`，其中 `totalpages` 为当前 OOM 上下文允许的最大内存页数（全局或 memcg 限制）。
- **排除规则**：
  - 全局 init 进程（PID 1）和内核线程（`PF_KTHREAD`）不可杀。
  - 显式设置 `oom_score_adj = OOM_SCORE_ADJ_MIN (-1000)` 的进程不可杀。
  - 已被标记跳过（`MMF_OOM_SKIP`）或处于 `vfork` 中间状态的进程不可杀。
- **返回值**：`LONG_MIN` 表示不可杀；否则返回综合评分，值越大越优先被杀。

### 内存分配约束识别 (`constrained_alloc`)
- **Memcg OOM**：若 `oc->memcg` 非空，则 `totalpages` 设为 memcg 的内存上限，约束类型为 `CONSTRAINT_MEMCG`。
- **全局 OOM**：默认 `totalpages = totalram_pages + total_swap_pages`。
- **NUMA 约束**：
  - 若分配请求指定 `__GFP_THISNODE`，视为无特殊约束（避免杀死当前进程）。
  - 若存在非全集的 `nodemask`（来自 mempolicy），则 `totalpages` 仅统计该 nodemask 覆盖节点的内存，约束类型为 `CONSTRAINT_MEMORY_POLICY`。
  - Cpuset 约束由页面分配器处理，此处不直接计算。

### 多线程与内存描述符处理 (`find_lock_task_mm`)
- 遍历目标进程的整个线程组（`for_each_thread`），寻找任一仍持有有效 `mm_struct` 的线程。
- 对找到的线程加 `task_lock` 并返回，确保在检查其内存状态时不会被释放。
- 适用于主线程已退出但子线程仍在运行的场景。

### NUMA 可杀性检查 (`oom_cpuset_eligible`)
- 在 NUMA 系统中，仅当候选任务与触发 OOM 的当前任务在内存策略（mempolicy）或 cpuset 允许的节点集上有交集时，才视为可杀。
- 若 OOM 由 mempolicy 触发（`oc->nodemask` 非空），则仅检查 mempolicy 交集。
- 否则，检查 cpuset 的 `mems_allowed` 交集。

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`、`<linux/gfp.h>`、`<linux/swap.h>` 获取内存状态、分配标志和交换信息。
- **进程调度与管理**：依赖 `<linux/sched.h>` 及相关头文件访问任务结构、线程组、cpuset 和内存策略。
- **内存控制组 (cgroup v2)**：通过 `<linux/memcontrol.h>` 集成 memcg，支持容器级 OOM。
- **安全模块**：通过 `<linux/security.h>` 调用 LSM 钩子（如 `security_oom_kill()`）。
- **调试与追踪**：使用 ftrace (`<linux/ftrace.h>`) 和自定义 tracepoint (`trace/events/oom.h`) 记录 OOM 事件。
- **体系结构相关**：包含 `<asm/tlb.h>` 处理 TLB 刷新。
- **内部 MM 实现**：包含 `"internal.h"` 和 `"slab.h"` 访问内核私有内存管理接口。

## 5. 使用场景

- **全局内存耗尽**：当系统整体可用内存（含 swap）低于临界阈值，且无法通过页面回收释放足够内存时，由页面分配器调用 `out_of_memory()`。
- **Memcg 内存超限**：当某个 memory cgroup 的内存使用超过其配额时，触发该 cgroup 内的 OOM Killer。
- **SysRq 触发**：通过 Magic SysRq 键（`Alt+SysRq+f`）手动触发 OOM Killer，此时 `oc->order = -1`。
- **诊断辅助**：当不可回收 slab 内存（如内核对象缓存）异常增长导致 OOM 时，`should_dump_unreclaim_slab()` 可触发 slab 信息转储以辅助调试。
- **策略约束下的 OOM**：在 NUMA 系统中，受 cpuset 或 mempolicy 限制的进程在局部节点内存耗尽时触发针对性 OOM。