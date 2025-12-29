# time\sched_clock.c

> 自动生成时间: 2025-10-25 16:46:17
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `time\sched_clock.c`

---

# `time/sched_clock.c` 技术文档

## 1. 文件概述

`time/sched_clock.c` 实现了 Linux 内核中通用的 `sched_clock()` 机制，用于将底层硬件计数器（如 TSC、ARM arch timer 等）扩展为 64 位纳秒级单调时间戳。该机制为调度器、延迟跟踪、性能分析等子系统提供高精度、低开销的时间基准。文件通过双缓冲（双副本）+ 序列锁（`seqcount_latch_t`）的方式，确保即使在 NMI（不可屏蔽中断）上下文中调用 `sched_clock()` 也能获得一致、无撕裂的时间读数。

## 2. 核心功能

### 主要数据结构

- **`struct clock_data`**  
  全局状态结构体，包含：
  - `seq`: `seqcount_latch_t` 类型的序列计数器，用于同步读写。
  - `read_data[2]`: 双缓冲数组，分别存储当前有效和更新中的读取参数。
  - `wrap_kt`: 计数器溢出前的最大持续时间（ktime_t 格式）。
  - `rate`: 当前注册的时钟源频率（Hz）。
  - `actual_read_sched_clock`: 指向底层硬件读取函数的指针。

- **`struct clock_read_data`**（定义在头文件中）  
  包含读取 `sched_clock` 所需的关键参数：
  - `read_sched_clock`: 当前使用的读取函数（可能为挂起状态下的特殊函数）。
  - `sched_clock_mask`: 计数器位宽掩码（如 `CLOCKSOURCE_MASK(bits)`）。
  - `mult/shift`: 用于将计数器周期转换为纳秒的乘法/移位因子。
  - `epoch_cyc/epoch_ns`: 上次校准时刻的计数器值和对应的纳秒时间戳。

### 主要函数

- **`sched_clock_noinstr(void)`**  
  无插桩（noinstr）版本的 `sched_clock()`，在禁用抢占的上下文中直接读取并计算纳秒时间，使用序列锁保证一致性。

- **`sched_clock(void)`**  
  对外公开的 `sched_clock()` 接口，内部调用 `sched_clock_noinstr()` 并确保抢占被禁用。

- **`sched_clock_register(read, bits, rate)`**  
  注册新的底层硬件时钟源。计算 `mult/shift` 转换参数，更新全局 `clock_data`，并启动防溢出定时器。

- **`generic_sched_clock_init(void)`**  
  初始化通用 `sched_clock` 机制。若未注册硬件时钟，则回退到基于 `jiffies` 的实现，并启动周期性更新定时器。

- **`sched_clock_suspend()/sched_clock_resume()`**  
  系统挂起/恢复时的回调函数。挂起时切换读取函数为返回最后校准值的静态函数，恢复时重新同步并启用硬件读取。

- **`update_sched_clock()`**  
  更新 `epoch_cyc` 和 `epoch_ns`，防止因计数器长时间运行导致转换溢出。

- **`sched_clock_poll()`**  
  高精度定时器（hrtimer）回调函数，周期性调用 `update_sched_clock()`。

## 3. 关键实现

### 双缓冲 + Latch 序列锁机制

- 使用 `seqcount_latch_t` 实现无锁读取：读操作通过 `sched_clock_read_begin()` 获取当前有效副本索引（`seq & 1`），并在末尾通过 `sched_clock_read_retry()` 验证读取期间未发生更新。
- 写操作（如 `update_clock_read_data()`）先更新奇数副本（索引 1），通过 `raw_write_seqcount_latch()` 切换读者到奇数副本；再更新偶数副本（索引 0），再次切换回偶数副本。确保读者始终看到一致的旧数据或新数据，不会看到中间状态。

### 时间转换与防溢出

- 使用 `clocks_calc_mult_shift()` 计算最优的 `mult/shift` 对，将硬件计数器周期高效转换为纳秒（公式：`ns = (cyc * mult) >> shift`）。
- 通过 `clocks_calc_max_nsecs()` 计算计数器在溢出前可安全表示的最大纳秒数，并以此设置 `hrtimer` 的超时时间（`wrap_kt`），定期调用 `update_sched_clock()` 重置 `epoch`，避免 64 位中间结果溢出。

### 挂起/恢复处理

- 系统挂起时，将 `read_sched_clock` 替换为 `suspended_sched_clock_read()`，该函数返回最后一次校准的 `epoch_cyc`，使 `sched_clock()` 在挂起期间表现为“冻结”。
- 恢复时重新读取硬件计数器作为新的 `epoch_cyc`，并恢复原始读取函数。

### 中断上下文安全

- 所有读路径（`sched_clock*`）标记为 `notrace` 和 `noinstr`，避免在关键路径引入追踪或插桩开销。
- 写操作（如注册、更新）在关中断（`local_irq_save`）下执行，确保与 NMI 上下文的读操作互斥。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/clocksource.h>`：提供 `CLOCKSOURCE_MASK`、`clocks_calc_mult_shift` 等时钟源工具。
  - `<linux/hrtimer.h>`：用于实现防溢出定时器。
  - `<linux/seqlock.h>`：提供 `seqcount_latch_t` 及相关操作。
  - `"timekeeping.h"`：内核时间管理内部头文件。
  - `<linux/sched/clock.h>`：定义 `sched_clock()` 接口及 `enable_sched_clock_irqtime()`。

- **模块交互**：
  - **调度器（scheduler）**：`sched_clock()` 是 `rq_clock()` 等调度时间基准的底层实现。
  - **时间子系统（timekeeping）**：与 `ktime_get()` 等接口协同，但 `sched_clock()` 更侧重低开销、单调性。
  - **电源管理（PM）**：通过 `syscore_ops` 注册挂起/恢复回调。
  - **中断子系统**：若时钟频率 ≥ 1MHz 且 `irqtime` 未禁用，则启用中断时间统计（`enable_sched_clock_irqtime()`）。

## 5. 使用场景

- **调度延迟测量**：调度器使用 `sched_clock()` 计算任务运行时间、睡眠时间及调度延迟。
- **性能分析工具**：如 `ftrace`、`perf` 使用 `sched_clock()` 作为事件时间戳。
- **内核延迟跟踪**：`irqsoff`、`preemptoff` 等 tracer 依赖高精度单调时钟。
- **硬件计数器抽象**：为架构特定的高精度计数器（如 x86 TSC、ARM arch timer）提供统一的 64 位纳秒接口。
- **系统挂起/恢复**：在 Suspend-to-RAM 等场景下保持时间连续性，避免挂起期间时间“跳跃”。