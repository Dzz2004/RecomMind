# rcu\update.c

> 自动生成时间: 2025-10-25 15:50:38
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rcu\update.c`

---

# `rcu/update.c` 技术文档

## 1. 文件概述

`rcu/update.c` 是 Linux 内核中 Read-Copy Update (RCU) 机制的核心实现文件之一，主要负责 RCU 宽限期（grace period）控制策略、运行时模式切换、异步回调调度策略以及与调试和测试相关的辅助功能。该文件不直接实现宽限期的检测逻辑（由 `tree.c`、`tiny.c` 等处理），而是提供全局控制接口，用于动态调整 RCU 行为，例如是否启用加速（expedited）宽限期、是否启用延迟（lazy）回调处理等。此外，它还包含用于锁依赖检查（lockdep）的 RCU 读侧临界区状态判断函数。

## 2. 核心功能

### 主要函数

- **`rcu_read_lock_sched_held()`**  
  在启用 `CONFIG_DEBUG_LOCK_ALLOC` 时，用于判断当前是否处于 RCU-sched 读侧临界区内。考虑 CPU 是否在线、是否处于空闲状态（extended quiescent state）等因素。

- **`rcu_gp_is_normal()`**  
  判断当前是否应使用普通（非加速）宽限期。受 `rcu_normal` 模块参数和调度器初始化状态影响。

- **`rcu_gp_is_expedited()`**  
  判断当前是否应使用加速宽限期。综合考虑 `rcu_expedited` 模块参数和 `rcu_expedite_gp()` 的嵌套调用。

- **`rcu_expedite_gp()` / `rcu_unexpedite_gp()`**  
  分别用于启用和禁用后续 RCU 同步操作的加速模式。通过原子计数器 `rcu_expedited_nesting` 实现嵌套控制。

- **`rcu_async_should_hurry()`**  
  判断异步 RCU 回调（如 `call_rcu()`）是否应被及时执行（非延迟）。

- **`rcu_async_hurry()` / `rcu_async_relax()`**  
  控制异步 RCU 回调的执行策略：及时处理或延迟处理。通过原子计数器 `rcu_async_hurry_nesting` 实现。

- **`rcu_end_inkernel_boot()`**  
  标记内核启动阶段结束，恢复 RCU 到正常运行模式（取消加速、启用延迟回调等）。

- **`rcu_inkernel_boot_has_ended()`**  
  查询内核启动阶段是否已结束，供测试模块（如 `rcutorture`）使用。

- **`rcu_test_sync_prims()`**  
  （代码片段未完整）用于在模式切换或早期启动阶段测试所有非 SRCU 的同步原语。

### 主要数据结构与变量

- **`rcu_expedited_nesting`** (`atomic_t`)  
  嵌套计数器，控制是否强制使用加速宽限期。

- **`rcu_async_hurry_nesting`** (`atomic_t`)  
  嵌套计数器，控制异步 RCU 回调是否应被及时处理。

- **`rcu_boot_ended`** (`bool`, `__read_mostly`)  
  标志位，指示内核启动阶段是否结束。

- **模块参数**：
  - `rcu_expedited`：强制所有宽限期为加速模式。
  - `rcu_normal`：强制所有宽限期为普通模式。
  - `rcu_normal_after_boot`：在启动结束后自动切换到普通模式（特定配置下）。

## 3. 关键实现

- **加速/普通模式切换逻辑**：  
  通过 `rcu_expedited_nesting` 和 `rcu_normal` 参数共同决定宽限期类型。若 `rcu_normal` 为真且调度器已激活，则使用普通模式；否则若 `rcu_expedited` 为真或 `rcu_expedited_nesting > 0`，则使用加速模式。`rcu_normal` 优先级高于 `rcu_expedited`。

- **启动阶段特殊处理**：  
  在 `rcu_scheduler_active == RCU_SCHEDULER_INIT` 阶段（即首个用户任务启动前），所有宽限期默认为加速模式。`rcu_end_inkernel_boot()` 被调用后，恢复为运行时配置（可能切换为普通模式并启用延迟回调）。

- **异步回调延迟策略（RCU Lazy）**：  
  当 `CONFIG_RCU_LAZY` 启用时，`call_rcu()` 回调默认可被延迟执行以节省能耗。`rcu_async_hurry()`/`rcu_async_relax()` 允许临时覆盖此行为，适用于需要及时释放资源的场景。

- **Lockdep 集成**：  
  `rcu_read_lock_sched_held()` 在 lockdep 启用时，不仅检查显式的 RCU 锁，还将不可抢占状态（如关中断、关抢占）视为 RCU-sched 读侧临界区。同时，若 CPU 处于空闲状态（`rcu_is_watching() == false`）或离线，则视为不在 RCU 临界区内，以避免阻塞宽限期。

- **空闲状态处理**：  
  CPU 在 `ct_idle_enter()` 到 `ct_idle_exit()` 之间被视为处于“扩展静默状态”（extended quiescent state），此时即使调用了 `rcu_read_lock()`，也被 RCU 忽略，以确保宽限期能及时完成。

## 4. 依赖关系

- **头文件依赖**：
  - `rcu.h`：RCU 内部核心头文件，定义关键数据结构和宏。
  - `rcupdate_wait.h`、`rcupdate_trace.h`：RCU 等待和跟踪支持。
  - `sched/`、`irq/`、`cpu/` 相关头文件：用于获取调度、中断、CPU 状态信息。
  - `lockdep` 相关接口：用于 `rcu_read_lock_sched_held()` 的实现。

- **配置依赖**：
  - `CONFIG_TINY_RCU`：若启用，则跳过大部分运行时控制逻辑（仅保留基础功能）。
  - `CONFIG_PREEMPT_RT`、`CONFIG_NO_HZ_FULL`：影响 `rcu_normal_after_boot` 参数的可用性。
  - `CONFIG_RCU_LAZY`：控制异步回调延迟策略是否启用。
  - `CONFIG_DEBUG_LOCK_ALLOC`：决定是否编译 `rcu_read_lock_sched_held()`。

- **与其他 RCU 文件交互**：
  - 与 `tree.c`（Tree RCU）、`tiny.c`（Tiny RCU）协同工作，提供统一的运行时控制接口。
  - 被 `synchronize_rcu()`、`call_rcu()` 等 API 间接调用以决定执行策略。

## 5. 使用场景

- **系统启动与初始化**：  
  在内核早期启动阶段自动使用加速宽限期以加快初始化；启动完成后通过 `rcu_end_inkernel_boot()` 切换至节能或高性能模式。

- **实时性要求高的子系统**：  
  通过 `rcu_expedite_gp()` 临时启用加速宽限期，确保关键路径的低延迟（如实时任务、中断处理）。

- **电源管理**：  
  在空闲或低功耗场景下，利用 RCU Lazy 特性延迟回调执行，减少 CPU 唤醒次数。

- **调试与验证**：  
  `rcu_read_lock_sched_held()` 被 `lockdep` 用于检测 RCU 读侧临界区内的非法阻塞操作；`rcu_test_sync_prims()` 用于验证 RCU 同步原语的正确性。

- **测试框架集成**：  
  `rcu_inkernel_boot_has_ended()` 供 `rcutorture` 等压力测试模块判断何时可开始高强度测试。