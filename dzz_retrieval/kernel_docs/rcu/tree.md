# rcu\tree.c

> 自动生成时间: 2025-10-25 15:46:46
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rcu\tree.c`

---

# `rcu/tree.c` 技术文档

## 1. 文件概述

`rcu/tree.c` 是 Linux 内核中 **Read-Copy Update (RCU)** 机制的树形（tree-based）实现核心文件。RCU 是一种高性能的同步原语，用于在读多写少的场景下实现无锁读取与安全更新。该文件实现了基于分层树结构的 RCU 状态管理、宽限期（Grace Period）检测、回调处理、CPU 离线/上线处理以及与调度器、中断、kthread 等子系统的集成。树形结构的设计使得 RCU 能够高效扩展到大规模多核系统（数百甚至上千 CPU）。

## 2. 核心功能

### 主要数据结构

- **`struct rcu_data`**（每 CPU）  
  存储每个 CPU 的 RCU 状态，包括待处理的回调链表、宽限期序列号、QS（Quiescent State）状态等。
  
- **`struct rcu_state`**（全局）  
  全局 RCU 状态机，包含宽限期状态（`gp_state`）、序列号（`gp_seq`）、树形节点层级结构（`level[]`）、互斥锁（如 `barrier_mutex`、`exp_mutex`）等。

- **`struct rcu_node`**（层级节点）  
  构成 RCU 树的内部节点，用于聚合子节点（CPU 或下层 `rcu_node`）的宽限期完成状态，实现分层检测，减少全局同步开销。

- **全局变量**：
  - `rcu_scheduler_active`：指示调度器是否已激活，影响 RCU 初始化和优化策略。
  - `rcu_scheduler_fully_active`：指示 RCU 是否已完全初始化（包括 kthread 启动）。
  - `rcu_num_lvls` / `num_rcu_lvl[]` / `rcu_num_nodes`：描述 RCU 树的层级结构和节点数量。
  - 多个模块参数（如 `use_softirq`, `rcu_fanout_leaf`, `kthread_prio` 等）用于运行时调优和调试。

### 主要函数（声明/定义）

- **宽限期管理**：
  - `rcu_report_qs_rnp()`：向上报告某 `rcu_node` 的 QS 状态。
  - `invoke_rcu_core()`：触发 RCU 核心处理（如宽限期推进或回调执行）。

- **回调处理**：
  - `rcu_report_exp_rdp()`：报告扩展（expedited）宽限期完成。
  - `check_cb_ovld_locked()`：检查回调过载情况。

- **CPU 热插拔支持**：
  - `rcu_boost_kthread_setaffinity()`：调整 RCU boost kthread 的 CPU 亲和性。
  - `sync_sched_exp_online_cleanup()`：清理 CPU 上线时的扩展同步状态。
  - `rcu_cleanup_dead_rnp()` / `rcu_init_new_rnp()`：处理 CPU 离线/上线时的 `rcu_node` 结构。

- **辅助函数**：
  - `rcu_rdp_is_offloaded()`：判断 RCU 回调是否被卸载到专用 kthread（NO_HZ_FULL/NO_CB 场景）。
  - `rcu_rdp_cpu_online()`：检查对应 CPU 是否在线。
  - `rcu_init_invoked()`：判断 RCU 初始化是否已启动。

- **导出接口**：
  - `rcu_get_gp_kthreads_prio()`：供 `rcutorture` 等测试模块获取 RCU kthread 优先级。

## 3. 关键实现

### 树形宽限期检测机制
RCU 使用分层树结构（`rcu_node` 树）来高效检测宽限期完成：
- 叶子层对应 CPU，上层节点聚合子节点状态。
- 每个 `rcu_node` 维护一个位图（`qsmask`），记录哪些子节点尚未报告 QS。
- 当所有子节点都报告 QS 后，该节点向上层报告，最终根节点完成整个宽限期。
- 此设计将 O(N) 的全局同步开销降低为 O(log N)，适用于大规模系统。

### 宽限期状态机
- 全局状态 `rcu_state.gp_state` 控制宽限期生命周期（IDLE → WAITING → DONE 等）。
- 使用 64 位序列号 `gp_seq` 标识宽限期，通过位移（`RCU_SEQ_CTR_SHIFT`）区分状态。
- 初始序列号设为 `(0UL - 300UL) << RCU_SEQ_CTR_SHIFT`，确保启动时处于有效状态。

### 调度器集成与启动阶段优化
- `rcu_scheduler_active` 分三阶段：
  1. `RCU_SCHEDULER_INACTIVE`：单任务阶段，`synchronize_rcu()` 退化为内存屏障。
  2. `RCU_SCHEDULER_INIT`：调度器启动但 RCU 未完全初始化。
  3. `RCU_SCHEDULER_RUNNING`：RCU 完全激活。
- `rcu_scheduler_fully_active` 确保 RCU 回调和 kthread 在调度器支持多任务后才启用。

### 回调处理策略
- 支持两种回调执行模式：
  - **软中断（`RCU_SOFTIRQ`）**：默认模式，通过 `rcu_softirq` 处理。
  - **专用 kthread（`rcuc`/`rcub`）**：在 `PREEMPT_RT` 或配置 `NO_CB` 时使用，避免软中断延迟。
- 通过 `use_softirq` 模块参数控制模式选择。

### 调试与调优支持
- 多个延迟参数（`gp_preinit_delay` 等）用于注入延迟以暴露竞态条件。
- `rcu_unlock_delay` 在 `CONFIG_RCU_STRICT_GRACE_PERIOD` 下强制延迟 `rcu_read_unlock()`。
- `dump_tree` 参数可在启动时打印 RCU 树结构用于验证。
- `rcu_fanout_leaf` 和 `rcu_fanout_exact` 控制树的扇出（fanout）结构。

### 内存与资源管理
- `rcu_min_cached_objs` 控制每 CPU 缓存的最小对象数（以页为单位）。
- `rcu_delay_page_cache_fill_msec` 在内存压力下延迟填充 RCU 缓存，避免与页回收冲突。

## 4. 依赖关系

- **头文件依赖**：
  - 基础内核设施：`<linux/smp.h>`, `<linux/sched.h>`, `<linux/interrupt.h>`, `<linux/percpu.h>` 等。
  - 时间子系统：`<linux/tick.h>`, `<linux/jiffies.h>`。
  - 内存管理：`<linux/mm.h>`, `<linux/slab.h>`, `<linux/vmalloc.h>`。
  - 调试与追踪：`<linux/lockdep.h>`, `<linux/ftrace.h>`, `<linux/kasan.h>`。
  - RCU 内部头文件：`"tree.h"`, `"rcu.h"`。

- **模块依赖**：
  - 与调度器深度集成（`rcu_scheduler_active` 状态依赖 `sched/`）。
  - 依赖中断子系统处理 QS 检测（如 tick 中断）。
  - 与 CPU 热插拔机制协同（`cpuhp` 框架）。
  - 在 `PREEMPT_RT` 下依赖实时调度特性。
  - 与内存回收（shrinker）交互以管理缓存。

## 5. 使用场景

- **内核同步原语**：为 `synchronize_rcu()`, `call_rcu()` 等 API 提供底层实现。
- **大规模多核系统**：通过树形结构支持数百至数千 CPU 的高效宽限期检测。
- **实时系统**：通过 `rcuc` kthread 和优先级控制（`kthread_prio`）满足实时性要求。
- **CPU 热插拔**：动态调整 RCU 树结构以适应 CPU 在线/离线。
- **内存压力场景**：与页回收协同，避免 RCU 缓存加剧内存紧张。
- **内核调试与测试**：
  - `rcutorture` 模块利用此文件接口进行压力测试。
  - 通过延迟参数和 `dump_tree` 辅助调试竞态和结构问题。
- **低延迟场景**：在 `NO_HZ_FULL` 或 `NO_CB` 配置下，将 RCU 回调卸载到专用 CPU，减少主 CPU 干扰。