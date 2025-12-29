# sched\idle.c

> 自动生成时间: 2025-10-25 16:10:30
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\idle.c`

---

# `sched/idle.c` 技术文档

## 1. 文件概述

`sched/idle.c` 是 Linux 内核调度子系统中负责实现 **CPU 空闲（idle）线程** 的核心文件。它提供了通用的 idle 循环入口点，并实现了 idle 任务的调度类（idle scheduling class）。该文件管理 CPU 在无任务可执行时的行为，包括进入低功耗状态、处理中断唤醒、与 cpuidle 框架交互等。

> **注意**：此文件中的 idle 任务与 `SCHED_IDLE` 调度策略（在 `sched/fair.c` 中实现）无关。前者是每个 CPU 上的特殊内核线程（`swapper`/`idle`），后者是一种低优先级的用户任务调度策略。

## 2. 核心功能

### 主要函数

| 函数 | 功能说明 |
|------|--------|
| `sched_idle_set_state()` | 为当前 CPU 设置 cpuidle 状态，供调度器或调试使用 |
| `cpu_idle_poll_ctrl()` | 控制是否强制使用轮询（polling）模式而非进入睡眠状态 |
| `cpu_idle_poll()` | 实现纯轮询模式的 idle 循环：不进入睡眠，仅执行 `cpu_relax()` |
| `arch_cpu_idle_*()`（弱符号） | 架构相关的 idle 钩子函数（prepare/enter/exit/dead），可由架构代码覆盖 |
| `default_idle_call()` | 默认的 idle 回调函数，当 cpuidle 框架不可用时使用 |
| `cpuidle_idle_call()` | 主 idle 函数，集成 cpuidle 框架，选择并进入合适的 idle 状态 |
| `do_idle()` | 通用 idle 循环主入口，协调 tick、RCU、负载均衡与 cpuidle |

### 关键数据结构与变量

- `cpu_idle_force_poll`：全局标志，控制是否强制使用轮询模式（通过内核参数 `nohlt`/`hlt` 控制）
- `__cpuidle_text_start/end`：链接器符号，标记 cpuidle 相关代码段（用于热补丁或内存管理）

## 3. 关键实现

### Idle 循环流程 (`do_idle`)
1. **进入 idle 前准备**：
   - 执行 NO_HZ 负载均衡（`nohz_run_idle_balance`）
   - 设置当前任务为 polling 状态（`__current_set_polling`）
   - 进入 NO_HZ idle 模式（`tick_nohz_idle_enter`）

2. **主循环**（当 `!need_resched()` 时）：
   - 禁用本地中断（防止中断处理程序遗漏 tick 重编程）
   - 检查 CPU 是否离线，若是则进入死亡状态
   - 调用架构钩子 `arch_cpu_idle_enter()`
   - 刷新 RCU nocb 延迟唤醒
   - 调用 `cpuidle_idle_call()` 进入实际 idle 状态

3. **退出 idle**：
   - 设置 polling 状态
   - 确保中断已启用（否则触发警告）

### cpuidle 集成 (`cpuidle_idle_call`)
- **状态选择**：
  - 若系统处于 **suspend-to-idle (s2idle)** 状态，直接选择最深 idle 状态
  - 否则由 cpuidle governor 选择合适状态（`cpuidle_select`）
- **Tick 管理**：
  - 根据是否停止 tick 决定调用 `tick_nohz_idle_stop_tick()` 或 `retain_tick()`
- **状态进入**：
  - 调用 `call_cpuidle()` 或 `call_cpuidle_s2idle()` 进入硬件 idle 状态
  - 退出后调用 `cpuidle_reflect()` 供 governor 学习

### 轮询模式 (`cpu_idle_poll`)
- 在中断关闭状态下轮询 `tif_need_resched()` 和广播 tick 超时
- 不进入任何低功耗状态，适用于调试或特定硬件限制场景
- 通过内核启动参数控制：
  - `nohlt`：启用轮询（`cpu_idle_force_poll = 1`）
  - `hlt`：禁用轮询（恢复默认行为）

### 架构适配
- 提供弱符号（`__weak`）的架构钩子函数，允许架构代码覆盖默认行为
- 默认 `arch_cpu_idle()` 会强制启用轮询（兼容旧架构）

## 4. 依赖关系

| 依赖模块 | 作用 |
|---------|------|
| `kernel/sched/` | 使用 runqueue (`this_rq()`)、调度标志 (`need_resched`)、idle 任务管理 |
| `drivers/cpuidle/` | 调用 cpuidle 框架 API（`cpuidle_enter`, `cpuidle_select` 等） |
| `kernel/time/tick-sched.c` | NO_HZ tick 管理（`tick_nohz_idle_stop_tick` 等） |
| `kernel/rcu/` | RCU idle 通知（`rcu_nocb_flush_deferred_wakeup`） |
| `kernel/cpuhotplug.c` | CPU 离线处理（`cpuhp_report_idle_dead`） |
| 架构特定代码 | 通过 `arch_cpu_idle*` 钩子集成硬件 idle 指令（如 `wfi`, `mwait`） |

## 5. 使用场景

1. **正常系统空闲**：
   - 当 CPU 无 runnable 任务时，调度器切换到 idle 任务，执行 `do_idle()`
   - 根据负载和功耗策略，通过 cpuidle 进入 C-state 低功耗状态

2. **系统挂起（Suspend-to-Idle）**：
   - 在 s2idle 状态下，绕过 cpuidle governor，直接进入最深 idle 状态
   - 停止本地 tick 和时间子系统，等待唤醒中断

3. **调试与故障排查**：
   - 通过 `nohlt` 内核参数强制轮询，避免 CPU 进入睡眠，便于调试中断或时序问题

4. **CPU 热插拔**：
   - CPU 离线时，在 idle 循环中检测离线状态，调用 `arch_cpu_idle_dead()` 进入永久睡眠

5. **实时性要求场景**：
   - 通过 `forced_idle_latency_limit_ns` 限制最大延迟，确保快速响应中断