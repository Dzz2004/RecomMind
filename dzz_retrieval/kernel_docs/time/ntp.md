# time\ntp.c

> 自动生成时间: 2025-10-25 16:41:49
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `time\ntp.c`

---

# `time/ntp.c` 技术文档

## 1. 文件概述

`time/ntp.c` 是 Linux 内核中实现网络时间协议（NTP）状态机和时间同步逻辑的核心文件。该文件负责维护系统时钟的频率和相位调整，支持通过 NTP 或 PPS（Pulse Per Second）信号进行高精度时间同步。其主要功能包括：

- 管理 NTP 状态（同步状态、错误标志等）
- 实现 PLL（锁相环）和 FLL（频率锁定环）算法进行时钟校正
- 处理闰秒事件
- 支持 PPS 信号输入（当 `CONFIG_NTP_PPS` 启用时）
- 提供用户空间通过 `adjtimex()` 系统调用访问和控制时间同步状态的接口

该文件原为 `kernel/timer.c` 和 `kernel/time.c` 中相关逻辑的拆分整合，现专注于 NTP 时间同步的核心状态维护与算法实现。

## 2. 核心功能

### 主要全局变量

| 变量名 | 类型 | 说明 |
|--------|------|------|
| `tick_usec` | `unsigned long` | 用户空间 HZ 对应的微秒周期（默认 10000，即 10ms） |
| `tick_nsec` | `unsigned long` | 内核实际使用的纳秒 tick 周期 |
| `tick_length` | `u64` | 当前 tick 长度（纳秒，已缩放） |
| `tick_length_base` | `u64` | 基准 tick 长度（用于频率调整） |
| `time_state` | `int` | 时钟同步状态（如 `TIME_OK`、`TIME_ERROR`） |
| `time_status` | `int` | NTP 状态标志位（如 `STA_UNSYNC`、`STA_PPSSIGNAL`） |
| `time_offset` | `s64` | 当前相位偏移（纳秒） |
| `time_constant` | `long` | PLL 时间常数（控制收敛速度） |
| `time_maxerror` / `time_esterror` | `long` | 最大/估计时间误差（微秒） |
| `time_freq` | `s64` | 频率偏移（缩放后的纳秒/秒） |
| `time_reftime` | `time64_t` | 上次调整时间（秒） |
| `ntp_tick_adj` | `s64` | 启动参数配置的固定 tick 调整值 |
| `ntp_next_leap_sec` | `time64_t` | 下一个闰秒发生的时间（`TIME64_MAX` 表示无） |

### PPS 相关变量（`CONFIG_NTP_PPS` 启用时）

- `pps_valid`：PPS 信号有效性计数器
- `pps_tf[3]`：相位中值滤波器
- `pps_jitter`：当前抖动（纳秒）
- `pps_fbase`：频率校准区间起始时间
- `pps_shift`：当前校准区间长度（以 2 的幂表示秒数）
- `pps_freq`：PPS 控制下的频率偏移
- 各类计数器：`pps_calcnt`, `pps_jitcnt`, `pps_stbcnt`, `pps_errcnt`

### 主要内联函数

| 函数 | 功能 |
|------|------|
| `ntp_synced()` | 判断 NTP 是否处于同步状态（非 `STA_UNSYNC`） |
| `ntp_offset_chunk()` | 计算每次调整应修正的相位偏移量（PPS 模式下全量修正，否则按 PLL 衰减） |
| `pps_reset_freq_interval()` | 重置 PPS 频率校准区间 |
| `pps_clear()` | 清除所有 PPS 状态 |
| `pps_dec_valid()` | 递减 PPS 有效性计数器，超时则清除 PPS 状态 |
| `pps_set_freq()` | 设置 PPS 频率偏移 |
| `is_error_status()` | 判断当前 `time_status` 是否表示错误状态 |
| `pps_fill_timex()` | 将 PPS 统计信息填充到 `timex` 结构体供用户空间查询 |

### 主要静态函数

| 函数 | 功能 |
|------|------|
| `ntp_update_frequency()` | 根据 `tick_usec`、`ntp_tick_adj` 和 `time_freq` 更新 `tick_length` 等频率相关变量 |
| `ntp_update_offset_fll()` | 在 FLL 模式下根据相位偏移和时间间隔计算频率调整量 |
| `ntp_update_offset()` | （代码截断）实现 PLL 模式下的相位偏移处理和频率调整 |

## 3. 关键实现

### 3.1 时间频率调整机制

内核通过 `tick_length` 控制系统 tick 的实际长度。`ntp_update_frequency()` 函数综合以下三部分计算每秒总长度：

1. **基准长度**：`tick_usec * NSEC_PER_USEC * USER_HZ`（即 1 秒的理想纳秒数）
2. **启动参数调整**：`ntp_tick_adj`（由 `tick_adj` 内核参数设置）
3. **动态频率偏移**：`time_freq`（由 NTP 算法计算得出）

总长度经缩放（`NTP_SCALE_SHIFT`）后，除以 `HZ` 得到 `tick_nsec`，除以 `NTP_INTERVAL_FREQ`（通常为 1000）得到 `tick_length_base`。`tick_length` 会立即应用新值，实现频率的平滑调整。

### 3.2 PLL/FLL 算法

- **PLL（Phase-Locked Loop）**：默认模式，通过 `ntp_offset_chunk()` 按 `SHIFT_PLL + time_constant` 位右移来衰减相位修正量，实现稳定收敛。
- **FLL（Frequency-Locked Loop）**：在长时间偏移或大偏移场景下启用（通过 `STA_FLL` 标志），直接根据 `offset / time_interval` 计算频率修正（见 `ntp_update_offset_fll()`）。

### 3.3 PPS 支持

当启用 `CONFIG_NTP_PPS` 时：
- 若同时设置 `STA_PPSTIME` 和 `STA_PPSSIGNAL`，相位偏移会**立即全量修正**（`ntp_offset_chunk()` 直接返回原偏移）
- 实现了自适应频率校准区间（`pps_shift` 在 `PPS_INTMIN` 到 `PPS_INTMAX` 之间动态调整）
- 使用三值中值滤波器（`pps_tf[3]`）抑制 PPS 信号的“爆米花”噪声（`PPS_POPCORN` 阈值）
- 维护多个质量指标计数器供诊断使用

### 3.4 状态管理

- `time_status` 使用位标志（`STA_*`）表示同步状态、错误条件和 PPS 状态
- `is_error_status()` 综合判断是否处于错误状态（包括 PPS 相关错误）
- `time_state` 控制是否允许写入 CMOS 时钟（`TIME_ERROR` 时禁止）

## 4. 依赖关系

### 头文件依赖
- `<linux/timex.h>`：定义 `timex` 结构体和 `STA_*` 状态常量
- `<linux/time.h>`、`<linux/time64.h>`：时间表示和转换
- `<linux/math64.h>`：64 位除法等数学运算
- `"ntp_internal.h"`：NTP 内部接口（如 `NTP_SCALE_SHIFT`、`MAXPHASE` 等常量）
- `"timekeeping_internal.h"`：与时间保持子系统交互

### 内核模块交互
- **时间保持子系统（`timekeeping.c`）**：共享 `timekeeper` 锁，`tick_length` 被 `timekeeping` 用于更新系统时钟
- **系统调用层**：通过 `do_adjtimex()`（在 `kernel/time/ntp.c` 或 `kernel/time/time.c` 中）访问本文件的状态变量
- **PPS 子系统**：当 `CONFIG_NTP_PPS` 启用时，PPS 事件处理器会调用本文件的 PPS 状态更新函数
- **RTC 驱动**：受 `time_state` 控制是否允许更新 CMOS 时钟

## 5. 使用场景

1. **NTP 客户端同步**：用户空间 NTP 守护进程（如 `ntpd`、`chronyd`）通过 `adjtimex()` 系统调用定期提供偏移量和状态，内核据此调整系统时钟频率和相位。

2. **高精度时间源接入**：当连接 GPS 或原子钟等提供 PPS 信号的设备时，内核 PPS 子系统将信号传递给本模块，实现纳秒级时间同步。

3. **闰秒处理**