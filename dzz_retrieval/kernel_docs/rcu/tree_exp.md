# rcu\tree_exp.h

> 自动生成时间: 2025-10-25 15:47:23
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rcu\tree_exp.h`

---

# `rcu/tree_exp.h` 技术文档

## 1. 文件概述

`rcu/tree_exp.h` 是 Linux 内核 RCU（Read-Copy-Update）子系统中用于实现**加速型宽限期**（expedited grace periods）的核心头文件。该文件定义了与加速宽限期相关的静态辅助函数，用于快速完成 RCU 宽限期，适用于对延迟敏感的同步场景（如模块卸载、关键路径同步等）。相比常规宽限期，加速宽限期通过主动唤醒 CPU、强制调度等方式显著缩短等待时间，但代价是更高的 CPU 开销。

## 2. 核心功能

### 主要函数

- **宽限期序列管理**
  - `rcu_exp_gp_seq_start()`：记录加速宽限期开始，更新序列号。
  - `rcu_exp_gp_seq_end()`：记录加速宽限期结束，更新序列号并插入内存屏障。
  - `rcu_exp_gp_seq_snap()`：获取当前加速宽限期序列号快照。
  - `rcu_exp_gp_seq_done()`：检查给定快照对应的宽限期是否已完成。
  - `rcu_exp_gp_seq_endval()`：返回当前宽限期结束时的序列号值（仅调试使用）。

- **RCU 节点树状态重置**
  - `sync_exp_reset_tree_hotplug()`：根据 CPU 热插拔状态更新 `rcu_node` 树中的 `expmaskinit` 掩码。
  - `sync_exp_reset_tree()`：为新加速宽限期重置所有 `rcu_node` 的 `expmask`。

- **宽限期完成检测**
  - `sync_rcu_exp_done()`：检查指定 `rcu_node` 的加速宽限期是否完成（需持锁）。
  - `sync_rcu_exp_done_unlocked()`：同上，但自动处理锁操作。

- **宽限期状态上报**
  - `__rcu_report_exp_rnp()`：递归上报加速宽限期的静默状态（quiescent state），从叶节点向根节点传播。
  - `rcu_report_exp_rnp()`：`__rcu_report_exp_rnp()` 的带锁封装。
  - `rcu_report_exp_cpu_mult()`：批量上报多个 CPU 的静默状态。
  - `rcu_report_exp_rdp()`：上报指定 CPU（`rcu_data`）的静默状态。

- **辅助功能**
  - `sync_exp_work_done()`：检查加速宽限期工作是否完成，并记录跟踪事件。
  - `rcu_exp_handler()`：加速宽限期中断处理函数（声明）。
  - `rcu_print_task_exp_stall()` / `rcu_exp_print_detail_task_stall_rnp()`：加速宽限期卡顿诊断函数（声明）。

## 3. 关键实现

### 加速宽限期序列号机制
- 使用 `rcu_state.expedited_sequence` 序列号跟踪加速宽限期生命周期。
- `rcu_seq_start()`/`rcu_seq_end()` 标记宽限期边界，`rcu_seq_snap()`/`rcu_seq_done()` 用于检测完成状态。
- 内存屏障（`smp_mb()`）确保宽限期操作的严格顺序性，防止 CPU 乱序执行导致状态误判。

### RCU 节点树掩码管理
- `expmaskinit`：记录当前 `rcu_node` 覆盖范围内所有**曾在线**的 CPU 掩码（热插拔感知）。
- `expmask`：当前加速宽限期中**尚未报告静默状态**的 CPU 掩码。
- `sync_exp_reset_tree_hotplug()` 通过遍历叶节点，将新上线 CPU 的掩码向上传播至根节点，确保树结构一致性。

### 静默状态上报算法
- 采用**迭代式自底向上**传播：从叶节点开始，清除对应 CPU 掩码位，若节点 `expmask` 清零且无挂起任务，则向父节点传播。
- 根节点完成时唤醒 `rcu_state.expedited_wq` 等待队列，通知宽限期结束。
- 支持批量 CPU 上报（`rcu_report_exp_cpu_mult()`），优化多核场景性能。

### 热插拔处理
- 通过 `rcu_state.ncpus_snap` 快照检测 CPU 在线状态变化。
- 仅当新 CPU 上线时更新 `expmaskinit`，避免频繁遍历树结构，优化热路径性能。

## 4. 依赖关系

- **内部依赖**：
  - `rcu/tree.h`：提供 `rcu_node`、`rcu_data` 结构及树遍历宏（如 `rcu_for_each_leaf_node`）。
  - `kernel/rcu/tree.c`：实现 `rcu_seq_*` 序列号操作、`rcu_initiate_boost` 等核心逻辑。
  - `kernel/rcu/update.c`：提供 `rcu_state` 全局状态及跟踪点（`trace_rcu_exp_grace_period`）。
- **外部依赖**：
  - `linux/smp.h`：`smp_mb()` 内存屏障原语。
  - `linux/sched.h`：`swake_up_one_online()` 唤醒等待队列。
  - `linux/tick.h`：`tick_dep_clear_cpu()` 清除 CPU 时钟依赖（`CONFIG_NO_HZ_FULL` 场景）。
  - `linux/console.h` / `linux/lockdep.h`：调试与锁验证支持。

## 5. 使用场景

- **内核模块卸载**：`synchronize_rcu_expedited()` 快速等待所有 RCU 读者退出，避免长时间阻塞。
- **实时任务同步**：高优先级任务需最小化同步延迟时触发加速宽限期。
- **OOM Killer**：内存回收路径中快速完成 RCU 回调以释放内存。
- **CPU 热插拔**：在线/离线 CPU 时更新 RCU 拓扑状态，确保加速宽限期覆盖正确 CPU 集合。
- **调试与诊断**：通过 `rcu_print_task_exp_stall()` 检测加速宽限期卡顿问题。