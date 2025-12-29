# time\timekeeping.c

> 自动生成时间: 2025-10-25 16:55:18
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `time\timekeeping.c`

---

# timekeeping.c 技术文档

## 1. 文件概述

`timekeeping.c` 是 Linux 内核中负责时间保持（timekeeping）的核心实现文件。它维护系统时间的连续性和准确性，提供高精度的时间读取接口，并处理与 NTP（网络时间协议）、时钟源（clocksource）、系统挂起/恢复等相关的时间同步逻辑。该文件实现了单调时钟（monotonic）、原始时钟（raw）、实时时钟（wall-clock）等多种时间视图，并确保在中断上下文、NMI（不可屏蔽中断）等特殊场景下也能安全读取时间。

## 2. 核心功能

### 主要数据结构

- **`struct timekeeper`**  
  核心时间保持结构体，包含当前时间、时钟偏移、TAI 偏移、启动时间偏移等关键字段。

- **`struct tk_read_base`**  
  用于快速时间读取的基础结构，包含时钟源指针、乘数（mult）、移位（shift）、掩码（mask）和上次周期值（cycle_last）等。

- **`struct tk_fast`**  
  专为 NMI 和中断上下文设计的快速时间读取结构，使用双缓冲（latch-based seqcount）机制实现无锁安全读取。

- **`tk_core`**  
  全局核心时间保持对象，包含一个 `seqcount_raw_spinlock_t` 序列锁和 `timekeeper` 实例，对齐到 64 字节缓存行以优化性能。

- **`shadow_timekeeper`**  
  时间保持器的影子副本，用于在更新过程中暂存新值，避免直接修改主结构导致不一致。

- **`dummy_clock`**  
  早期启动阶段使用的虚拟时钟源，基于 `local_clock()`，在真实时钟源注册前提供基本时间服务。

### 主要函数与宏

- **`tk_normalize_xtime()`**  
  将纳秒部分规范化，确保 `xtime_nsec` 不超过每秒纳秒数的表示范围。

- **`tk_xtime()` / `tk_set_xtime()` / `tk_xtime_add()`**  
  用于获取、设置和累加系统实时时钟（wall time）。

- **`tk_set_wall_to_mono()`**  
  设置 wall-to-monotonic 偏移，并同步更新 `offs_real` 和 `offs_tai`。

- **`tk_update_sleep_time()`**  
  在系统从挂起状态恢复时，更新启动时间偏移（`offs_boot`）。

- **`tk_clock_read()`**  
  安全读取当前时钟源的周期值，防止在时钟源切换过程中发生崩溃。

- **`timekeeping_check_update()`（仅调试模式）**  
  检查时钟周期偏移是否超出安全范围，防止溢出或下溢。

- **`update_fast_timekeeper()`（未完整显示但被引用）**  
  更新 `tk_fast_mono` 和 `tk_fast_raw`，用于 NMI 安全的时间读取。

### 全局变量

- `timekeeper_lock`：保护 `tk_core` 的原始自旋锁。
- `timekeeping_suspended`：标志系统时间保持是否处于挂起状态。
- `cycles_at_suspend`：系统挂起时记录的时钟周期值。
- `tk_fast_mono` / `tk_fast_raw`：分别用于单调时间和原始时间的快速读取路径。

## 3. 关键实现

### 时间读取的无锁安全机制

为支持在 NMI、中断等不可睡眠上下文中安全读取时间，内核引入了 `tk_fast` 结构。它使用 `seqcount_latch_t`（一种双缓冲序列计数器），通过切换两个 `tk_read_base` 实例（索引由序列计数器最低位决定）来实现更新与读取的分离。读取时只需读取当前有效的副本，无需加锁。

### 时间规范化与溢出处理

`tk_normalize_xtime()` 确保纳秒字段不会超过 `NSEC_PER_SEC << shift`，避免在时间计算中出现逻辑错误。同时，`CONFIG_DEBUG_TIMEKEEPING` 启用时会检查周期偏移是否超过时钟源的 `max_cycles`，防止因时钟源回绕或频率异常导致时间跳变。

### 早期启动支持

在系统早期启动阶段，真实时钟源尚未注册，此时使用 `dummy_clock` 作为占位时钟源。其 `read` 函数返回 `local_clock()`（通常基于 TSC 或 jiffies），并设置 `mult=1, shift=0`，因为 `local_clock()` 直接返回纳秒值，无需转换。

### 挂起/恢复处理

当系统挂起时，`timekeeping_suspend()` 会记录当前时钟周期值到 `cycles_at_suspend`，并将 `dummy_clock` 的 `read` 函数改为返回该固定值，防止挂起期间时间继续推进。恢复时再切换回真实时钟源并补偿睡眠时间。

### 序列锁保护

主时间保持结构 `tk_core` 使用 `seqcount_raw_spinlock_t` 保护。写操作需持有 `timekeeper_lock`，读操作通过 `read_seqcount_begin()` / `read_seqcount_retry()` 实现无锁但一致的读取，适用于大多数用户空间时间查询路径（如 VDSO）。

## 4. 依赖关系

- **`<linux/clocksource.h>`**：依赖时钟源抽象，用于获取高精度硬件计时器。
- **`<linux/tick.h>` / `tick-internal.h`**：与 tick 管理子系统交互，处理周期性时间更新。
- **`ntp_internal.h`**：集成 NTP 频率调整和闰秒处理逻辑。
- **`timekeeping_internal.h`**：包含内部辅助函数和结构定义。
- **`<linux/vdso.h>` / `pvclock_gtod.h`**：为 VDSO 和虚拟化环境（如 Xen、KVM）提供高效时间读取支持。
- **`<linux/sched/clock.h>`**：使用 `local_clock()` 作为早期启动和虚拟时钟源。
- **`<linux/stop_machine.h>`**：在某些关键更新路径中可能使用 stop-machine 机制确保全局一致性。

## 5. 使用场景

- **系统调用时间查询**：如 `clock_gettime(CLOCK_REALTIME)`、`CLOCK_MONOTONIC` 等通过此模块获取高精度时间。
- **VDSO 加速**：用户空间通过 VDSO 直接读取 `tk_fast` 结构，避免陷入内核。
- **NMI 和中断处理**：在不可睡眠上下文中安全获取时间戳（如 perf、ftrace、oops 打印）。
- **系统挂起/恢复**：在 suspend/resume 流程中冻结和恢复时间推进。
- **NTP 时间同步**：接收用户空间 `adjtimex` 调用，调整时钟频率和偏移。
- **内核日志时间戳**：`printk` 等日志系统依赖此模块提供单调或实时时钟。
- **调度器和负载计算**：`update_wall_time()` 被 tick 中断定期调用，驱动时间推进，影响调度、负载均衡等子系统。