# time\jiffies.c

> 自动生成时间: 2025-10-25 16:39:58
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `time\jiffies.c`

---

# time/jiffies.c 技术文档

## 1. 文件概述

`time/jiffies.c` 实现了一个基于 `jiffies` 的低精度时钟源（clocksource），作为 Linux 内核中最基础、兼容性最强的时钟源。该时钟源适用于所有系统，但精度受限于系统定时器中断频率（HZ），且在无滴答（tickless）系统中不推荐使用。文件还提供了 64 位 jiffies 值的原子读取机制（在 32 位系统上），并支持注册一个经过校准的“refined-jiffies”时钟源以提升精度。

## 2. 核心功能

### 主要数据结构
- `clocksource_jiffies`：基础 jiffies 时钟源实例，评分为 1（最低有效评分）
- `jiffies_lock`：用于保护 jiffies 更新的原始自旋锁，SMP 下缓存行对齐
- `jiffies_seq`：与 `jiffies_lock` 关联的序列计数器（seqcount），用于无锁读取 64 位 jiffies
- `refined_jiffies`：经校准后的 jiffies 时钟源，评分为 2

### 主要函数
- `jiffies_read()`：时钟源读取回调函数，返回当前 `jiffies` 值
- `get_jiffies_64()`（仅 32 位系统）：安全地读取 64 位 `jiffies_64` 值，使用 seqcount 机制避免撕裂读
- `init_jiffies_clocksource()`：初始化并注册基础 jiffies 时钟源
- `clocksource_default_clock()`：弱符号函数，提供默认时钟源（回退到 jiffies）
- `register_refined_jiffies()`：注册一个基于实际定时器频率校准的 refined-jiffies 时钟源

## 3. 关键实现

### Jiffies 时钟源参数
- **mult/shift**：使用 `TICK_NSEC << JIFFIES_SHIFT` 作为 mult，配合 `JIFFIES_SHIFT` 实现纳秒转换。`TICK_NSEC` 是每个 jiffy 对应的纳秒数（`NSEC_PER_SEC / HZ`）。
- **mask**：设为 32 位掩码（`CLOCKSOURCE_MASK(32)`），因为 jiffies 本质是 32 位计数器（即使在 64 位系统上，低 32 位也足够表示周期性溢出）。
- **uncertainty_margin**：设为 32 毫秒，反映其低精度特性。
- **max_cycles**：限制为 10，防止在高 HZ 系统上因 mult/shift 计算溢出。

### 64 位 Jiffies 安全读取（32 位系统）
在 `BITS_PER_LONG < 64` 的系统上，`jiffies_64` 是 64 位变量，但无法原子读取。通过 `jiffies_seq` 序列锁实现无锁读取：
1. 读取序列号
2. 读取 `jiffies_64`
3. 检查序列号是否变化（写操作会递增序列号）
4. 若变化则重试，确保读取一致性

### Refined Jiffies 校准算法
`register_refined_jiffies()` 根据实际定时器硬件频率（`cycles_per_second`）动态计算更精确的 `mult` 值：
1. 计算每 tick 的硬件周期数：`cycles_per_tick = (cycles_per_second + HZ/2) / HZ`（四舍五入）
2. 通过定点运算（<<8 提高精度）计算实际 HZ：`shift_hz = (cycles_per_second << 8) / cycles_per_tick`
3. 计算每 tick 的纳秒数：`nsec_per_tick = (NSEC_PER_SEC << 8) / shift_hz`
4. 更新 `refined_jiffies.mult = nsec_per_tick << JIFFIES_SHIFT`

此机制允许在无法提供高精度时钟源的平台上，利用已知的定时器硬件频率提升 jiffies 时钟源的精度。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/clocksource.h>`：时钟源核心接口
  - `<linux/jiffies.h>`：jiffies 宏定义和全局变量声明
  - `"timekeeping.h"` 和 `"tick-internal.h"`：内核时间子系统内部接口
- **符号依赖**：
  - `jiffies` / `jiffies_64`：由 `kernel/time/timer.c` 定义
  - `__clocksource_register()`：时钟源注册接口
  - `TICK_NSEC` / `JIFFIES_SHIFT`：jiffies 转换常量
- **导出符号**：
  - `jiffies`（所有架构）
  - `get_jiffies_64()`（仅 32 位架构）

## 5. 使用场景

- **系统启动早期**：作为默认时钟源，在高精度时钟源（如 TSC、HPET）初始化前提供基础时间服务。
- **无高精度时钟硬件平台**：在缺乏可靠硬件计时器的嵌入式或老旧系统中作为后备时钟源。
- **调试与兼容性**：用于验证时间子系统基础功能，或在高精度时钟源失效时降级使用。
- **Refined Jiffies 场景**：当平台可提供精确的定时器频率（如某些 ARM SoC）但无独立 clocksource 时，通过 `register_refined_jiffies()` 提升时间精度。
- **32 位系统**：通过 `get_jiffies_64()` 为需要 64 位时间戳的子系统（如文件系统、网络协议栈）提供安全的长时间计数。