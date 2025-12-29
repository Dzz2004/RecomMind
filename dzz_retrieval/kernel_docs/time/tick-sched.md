# time\tick-sched.c

> 自动生成时间: 2025-10-25 16:51:52
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `time\tick-sched.c`

---

# `time/tick-sched.c` 技术文档

## 1. 文件概述

`tick-sched.c` 是 Linux 内核中实现 **无滴答（tickless）调度** 的核心文件，主要用于支持 **NO_HZ（无周期性时钟中断）** 功能。该机制允许系统在空闲或特定负载条件下动态停止周期性的时钟中断（tick），从而降低功耗、减少 CPU 干扰，并提升实时性能。文件同时支持 **低分辨率定时器（NO_HZ_COMMON）** 和 **高分辨率定时器（HIGH_RES_TIMERS）** 场景下的无滴答行为。

## 2. 核心功能

### 主要数据结构

- `struct tick_sched`  
  每个 CPU 的无滴答调度控制结构，记录当前 CPU 的 tick 状态，包括是否处于空闲、tick 是否已停止、依赖项、空闲 jiffies 计数等。

- `tick_cpu_sched`（per-CPU 变量）  
  每个 CPU 对应的 `tick_sched` 实例。

- `last_jiffies_update`（全局）  
  记录上一次 jiffies 更新的时间点，用于在无滴答期间计算应推进的 jiffies 数量。

- `tick_nohz_full_mask`（仅 CONFIG_NO_HZ_FULL）  
  标识启用了 **完全无滴答（NO_HZ_FULL）** 模式的 CPU 集合。

- `tick_dep_mask`（原子变量，仅 CONFIG_NO_HZ_FULL）  
  全局 tick 依赖掩码，用于跟踪系统级阻止 tick 停止的原因（如 POSIX 定时器、RCU、调度器等）。

### 主要函数

- `tick_get_tick_sched(int cpu)`  
  获取指定 CPU 的 `tick_sched` 结构指针。

- `tick_do_update_jiffies64(ktime_t now)`  
  在无滴答模式下，根据当前时间 `now` 计算并更新全局 `jiffies_64` 值，确保时间推进的准确性。支持 32/64 位架构的内存序优化。

- `tick_init_jiffy_update(void)`  
  初始化 jiffies 更新机制，确保 `last_jiffies_update` 与 `TICK_NSEC` 对齐。

- `tick_sched_do_timer(struct tick_sched *ts, ktime_t now)`  
  处理与全局时间维护相关的逻辑，包括：
  - 在 `tick_do_timer_cpu` 为 `NONE` 时接管 jiffies 更新职责；
  - 调用 `tick_do_update_jiffies64()`；
  - 检测 jiffies 更新是否停滞（如因虚拟机暂停），并在停滞过久时强制更新。

- `tick_sched_handle(struct tick_sched *ts, struct pt_regs *regs)`  
  处理每个 tick 中断的常规任务，包括：
  - 更新进程时间统计（`update_process_times`）；
  - 触发性能剖析（`profile_tick`）；
  - 在 tick 停止期间维护软锁定看门狗（`touch_softlockup_watchdog_sched`）；
  - 更新空闲任务的 jiffies 计数。

- `check_tick_dependency(atomic_t *dep)`  
  （仅 CONFIG_NO_HZ_FULL）检查 tick 依赖掩码，判断是否存在阻止 tick 停止的条件（如 POSIX 定时器、RCU、调度器活动等）。

- `can_stop_full_tick(int cpu, struct tick_sched *ts)`  
  （片段未完整）用于判断在 NO_HZ_FULL 模式下是否可以安全停止指定 CPU 的 tick。

## 3. 关键实现

### 无滴答 Jiffies 更新机制

- 使用 `jiffies_lock` 和 `jiffies_seq`（顺序锁）保护 `jiffies_64` 和 `last_jiffies_update` 的更新。
- 在 64 位系统上，通过 `smp_load_acquire()` / `smp_store_release()` 实现无锁快速路径检查，避免不必要的锁竞争。
- 在 32 位系统上，由于 64 位变量非原子写入，必须通过 `seqcount` 保证读取一致性。
- 支持“慢路径”处理：当系统长时间睡眠（delta ≥ TICK_NSEC），通过除法计算应推进的 tick 数量。

### Jiffies 停滞检测

- 通过 `ts->last_tick_jiffies` 和 `ts->stalled_jiffies` 跟踪 jiffies 是否长时间未更新。
- 若连续 `MAX_STALLED_JIFFIES`（默认 5）次未更新，则强制调用 `tick_do_update_jiffies64()`，防止时间漂移（如虚拟机暂停或 stop_machine 场景）。

### NO_HZ_FULL 依赖管理

- 使用位掩码（`TICK_DEP_MASK_*`）标识阻止 tick 停止的原因。
- 每次尝试停止 tick 前，检查全局和 per-CPU 的依赖掩码。
- 通过 tracepoint `trace_tick_stop()` 记录阻止原因，便于调试。

### 空闲状态处理

- 当 `tick_stopped` 为真时（即处于无滴答空闲状态）：
  - 调用 `touch_softlockup_watchdog_sched()` 防止软锁定误报；
  - 若当前任务为空闲任务，则递增 `ts->idle_jiffies`，用于后续空闲时间统计校正；
  - 重置 `ts->next_tick = 0`，确保下次 tick 编程不会跳过。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/hrtimer.h>`：高分辨率定时器支持。
  - `<linux/sched/nohz.h>`：NO_HZ 相关调度接口。
  - `<linux/sched/clock.h>`、`<linux/kernel_stat.h>`：时间与统计信息。
  - `<linux/seqlock.h>`（隐含）：通过 `jiffies_seq` 实现顺序锁。
  - `"tick-internal.h"`：内部 tick 管理函数和变量（如 `tick_next_period`, `tick_do_timer_cpu`）。

- **内核子系统交互**：
  - **时间子系统**：与 `timekeeping.c` 协同更新 `wall_time`（通过 `update_wall_time()`）。
  - **调度器**：通过 `update_process_times()` 更新进程 CPU 时间。
  - **RCU**：NO_HZ_FULL 模式下需确保 RCU 宽限期推进。
  - **性能剖析**：触发 `CPU_PROFILING` 事件。
  - **软锁定检测**：维护看门狗状态。

## 5. 使用场景

- **移动/嵌入式设备**：在 CPU 空闲时停止 tick，显著降低功耗。
- **高性能计算/实时系统**：减少周期性中断对关键任务的干扰，提升确定性（尤其在 NO_HZ_FULL 模式下）。
- **虚拟化环境**：处理 VM 暂停导致的长时间无 tick 场景，通过停滞检测机制恢复时间同步。
- **服务器负载波动**：在低负载期间进入无滴答状态，提升能效比。
- **内核调试与追踪**：通过 `trace_tick_stop` 等 tracepoint 分析 tick 停止失败原因。