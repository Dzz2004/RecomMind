# rcu\tree_nocb.h

> 自动生成时间: 2025-10-25 15:48:05
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rcu\tree_nocb.h`

---

# `rcu/tree_nocb.h` 技术文档

## 1. 文件概述

`rcu/tree_nocb.h` 是 Linux 内核 RCU（Read-Copy Update）子系统中用于实现 **无回调（No-CB）CPU 机制** 的内部头文件。该机制允许将指定 CPU 上的 RCU 回调处理任务从本地 CPU 卸载（offload）到专用内核线程（kthread）中执行，从而减少主 CPU 的中断和调度开销，提升实时性、降低 OS 抖动（jitter），并有助于节能（通过更积极地进入 dyntick-idle 状态）。该文件仅在 `CONFIG_RCU_NOCB_CPU` 配置选项启用时生效。

## 2. 核心功能

### 全局变量
- `rcu_nocb_mask`：`cpumask_var_t` 类型，指定哪些 CPU 启用 No-CB 模式（即回调被卸载）。
- `rcu_nocb_poll`：布尔值，若为 `true`，表示 No-CB kthread 采用轮询而非休眠等待。
- `nocb_nobypass_lim_per_jiffy`：模块参数，控制在低 `call_rcu()` 调用率下是否绕过 bypass 机制。
- `jiffies_till_flush`：定义 lazy 回调的最大延迟时间（默认 10 秒）。

### 主要函数

#### 初始化与解析
- `rcu_nocb_setup(char *str)`：解析内核启动参数 `rcu_nocbs=`，设置 `rcu_nocb_mask`。
- `parse_rcu_nocb_poll(char *arg)`：解析 `rcu_nocb_poll` 启动参数。
- `rcu_init_one_nocb(struct rcu_node *rnp)`：初始化 `rcu_node` 的 No-CB 等待队列。

#### 锁操作
- `rcu_nocb_bypass_lock/unlock/trylock()`：操作 `nocb_bypass_lock`，用于保护 bypass 队列。
- `rcu_nocb_lock/unlock/unlock_irqrestore()`：条件性操作 `nocb_lock`，仅对 No-CB CPU 生效。
- `rcu_lockdep_assert_cblist_protected()`：Lockdep 断言，确保 `cblist` 访问受保护。

#### 线程管理与唤醒
- `rcu_current_is_nocb_kthread()`：判断当前任务是否为 No-CB kthread。
- `wake_nocb_gp()` / `__wake_nocb_gp()`：唤醒 GP（Grace Period）kthread。
- `wake_nocb_gp_defer()`：延迟唤醒 GP kthread（代码未完整，但功能明确）。
- `rcu_nocb_gp_cleanup()`：清理 GP 等待队列。
- `rcu_nocb_gp_get()`：获取当前 GP 序号对应的等待队列。

#### 调试与锁依赖
- `rcu_lockdep_is_held_nocb()`：Lockdep 检查 `nocb_lock` 是否已被持有。

#### Lazy 回调控制（仅当 `CONFIG_RCU_LAZY` 启用）
- `rcu_lazy_set_jiffies_till_flush()` / `rcu_lazy_get_jiffies_till_flush()`：设置/获取 lazy 回调刷新超时时间（主要用于测试）。

## 3. 关键实现

### No-CB 架构
- **双线程模型**：每个 No-CB CPU 组关联两个 kthread：
  - **GP kthread**：负责管理回调队列、等待宽限期结束、唤醒 CB kthread。
  - **CB kthread**：仅负责执行回调函数。
- **唤醒策略**：
  - 默认：当 CPU 向空回调队列插入回调时，唤醒 GP kthread。
  - 若启用 `rcu_nocb_poll`：kthread 主动轮询，减少本地 CPU 开销但牺牲能效。
- **延迟唤醒**：通过 `nocb_defer_wakeup` 和定时器实现批量唤醒，避免频繁唤醒开销。

### 锁设计
- 使用两个自旋锁：
  - `nocb_lock`：保护主回调链表（`cblist`）。
  - `nocb_bypass_lock`：保护 bypass 队列（用于高吞吐场景避免锁竞争）。
- 所有锁操作均要求中断关闭（`lockdep_assert_irqs_disabled()`）。

### Grace Period 同步
- 使用 `swait_queue_head`（simple wait queue）实现轻量级等待。
- 通过 `rcu_seq_ctr(gp_seq) & 0x1` 实现双缓冲等待队列，避免 ABA 问题。

### Lazy 回调处理
- 在 `CONFIG_RCU_LAZY` 下，延迟执行低优先级回调，最多延迟 `LAZY_FLUSH_JIFFIES`（默认 10 秒）。

## 4. 依赖关系

- **内核配置**：
  - 依赖 `CONFIG_RCU_NOCB_CPU` 编译。
  - 可选依赖 `CONFIG_RCU_LAZY`（lazy 回调支持）。
- **数据结构**：
  - 依赖 `struct rcu_data` 中的 No-CB 相关字段（如 `nocb_cb_kthread`, `nocb_gp_kthread`, `nocb_lock` 等）。
  - 依赖 `struct rcu_node` 中的 `nocb_gp_wq[2]`。
- **子系统**：
  - 与 RCU 树形实现（`tree.c`）紧密集成。
  - 使用内核调度器（`wake_up_process`）、定时器（`del_timer`）、cpumask 和 lockdep 机制。

## 5. 使用场景

- **实时系统**：卸载 RCU 回调可减少 CPU-bound 任务的 OS 抖动，提升实时性。
- **节能场景**：No-CB CPU 可更早进入 dyntick-idle 状态，降低功耗。
- **高吞吐系统**：通过 bypass 机制和专用 kthread 减少 `call_rcu()` 的锁竞争。
- **调试与测试**：通过启动参数（如 `rcu_nocbs=`, `rcu_nocb_poll`）和 lazy 回调接口进行行为调优和验证。