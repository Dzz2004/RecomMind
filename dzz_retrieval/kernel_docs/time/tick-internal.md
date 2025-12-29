# time\tick-internal.h

> 自动生成时间: 2025-10-25 16:50:12
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `time\tick-internal.h`

---

# `time/tick-internal.h` 技术文档

## 1. 文件概述

`tick-internal.h` 是 Linux 内核时间子系统中的一个内部头文件，主要用于定义与 **tick（时钟滴答）管理** 相关的内部变量、函数原型和辅助宏。该文件为高精度定时器（high-resolution timers）和低分辨率周期性 tick 提供统一的底层支持，是 `tick` 子系统在周期模式（periodic）和单次触发模式（oneshot）之间切换、广播机制（broadcast）、NO_HZ（动态 tick）等功能的核心接口定义文件。

该头文件仅供内核时间子系统内部使用，不对外暴露给其他子系统直接调用。

## 2. 核心功能

### 2.1 全局变量

- `DECLARE_PER_CPU(struct tick_device, tick_cpu_device)`  
  每个 CPU 上的 tick 设备实例，封装了底层 `clock_event_device`。
- `extern ktime_t tick_next_period`  
  下一个周期性 tick 的绝对时间点。
- `extern int tick_do_timer_cpu __read_mostly`  
  指定哪个 CPU 负责全局时间更新（如 jiffies 更新），特殊值：
  - `TICK_DO_TIMER_NONE (-1)`：无 CPU 负责
  - `TICK_DO_TIMER_BOOT (-2)`：启动阶段使用
- `extern unsigned long tick_nohz_active`（条件编译）  
  标识 NO_HZ 模式是否激活。
- `DECLARE_PER_CPU(struct hrtimer_cpu_base, hrtimer_bases)`  
  每个 CPU 的高精度定时器基结构。

### 2.2 主要函数（按功能分类）

#### 周期性 Tick 管理（`CONFIG_GENERIC_CLOCKEVENTS`）
- `tick_setup_periodic()`：配置设备为周期模式
- `tick_handle_periodic()`：周期 tick 的事件处理函数
- `tick_check_new_device()`：检查并注册新的 clock event 设备
- `tick_shutdown()`：CPU 离线时关闭 tick
- `tick_suspend()` / `tick_resume()`：系统挂起/恢复时的 tick 处理
- `tick_install_replacement()`：替换当前 tick 设备
- `tick_get_device()`：获取指定 CPU 的 tick 设备

#### 单次触发模式（`CONFIG_TICK_ONESHOT`）
- `tick_setup_oneshot()`：配置设备为 oneshot 模式
- `tick_program_event()`：编程下一次事件
- `tick_oneshot_notify()`：通知 oneshot 事件发生
- `tick_switch_to_oneshot()`：切换到 oneshot 模式
- `tick_resume_oneshot()`：恢复 oneshot 模式
- `tick_oneshot_mode_active()`：检查是否处于 oneshot 模式
- `tick_check_oneshot_change()`：检查是否可切换到 oneshot（用于 NO_HZ）

#### 广播支持（`CONFIG_GENERIC_CLOCKEVENTS_BROADCAST`）
- `tick_install_broadcast_device()`：安装广播设备
- `tick_device_uses_broadcast()`：判断设备是否依赖广播
- `tick_suspend_broadcast()` / `tick_resume_broadcast()`：广播设备的挂起/恢复
- `tick_get_broadcast_device()` / `tick_get_broadcast_mask()`：获取广播设备和 CPU 掩码
- `tick_set_periodic_handler()`：设置周期处理函数（区分广播/本地）

#### Oneshot 广播（`BROADCAST && ONESHOT`）
- `tick_broadcast_switch_to_oneshot()`：广播设备切换到 oneshot
- `tick_broadcast_oneshot_active()`：检查广播 oneshot 是否激活
- `tick_get_broadcast_oneshot_mask()`：获取使用 oneshot 广播的 CPU 掩码

#### NO_HZ 支持
- `tick_nohz_init()`：初始化 NO_HZ_FULL 功能
- `timers_update_nohz()`：更新 NO_HZ 状态对定时器的影响
- `timer_clear_idle()`：清除 CPU 空闲状态（用于中断唤醒）

#### 时钟设置通知
- `clock_was_set()` / `clock_was_set_delayed()`：通知系统时钟被修改
- `hrtimers_resume_local()`：本地恢复高精度定时器
- `get_next_timer_interrupt()`：获取下一个定时器中断时间

#### 辅助函数
- `tick_device_is_functional()`：判断设备是否为有效设备（非 DUMMY）
- `clockevent_get_state()` / `clockevent_set_state()`：安全访问设备状态
- `clockevents_shutdown()` / `clockevents_switch_state()`：管理 clock event 设备状态
- `__clockevents_update_freq()`：更新设备频率

## 3. 关键实现

### 3.1 Tick 设备抽象
通过 `struct tick_device` 封装 `clock_event_device`，实现 tick 逻辑与底层硬件解耦。每个 CPU 拥有独立的 `tick_cpu_device`，支持 per-CPU tick 管理。

### 3.2 全局 Tick 责任分配
`tick_do_timer_cpu` 用于指定唯一一个负责更新全局时间（如 `jiffies`）的 CPU，避免多核竞争。在 NO_HZ 或 CPU hotplug 场景下动态迁移。

### 3.3 广播机制
当某些 CPU 的本地 timer 在深度睡眠时失效，系统使用一个“广播设备”（通常为 HPET 或全局 timer）向所有 CPU 发送中断。通过 `tick_get_broadcast_mask()` 跟踪哪些 CPU 需要广播。

### 3.4 Oneshot 与周期模式切换
- 周期模式：固定间隔触发，用于传统 tick
- Oneshot 模式：每次编程下一次事件时间，用于高精度定时和 NO_HZ
- `tick_check_oneshot_change()` 决定是否可安全切换到 oneshot（需无活跃周期 timer）

### 3.5 NO_HZ 支持
- `tick_nohz_active` 全局标志控制动态 tick
- `timers_update_nohz()` 在 NO_HZ 状态变化时调整定时器行为
- `timer_clear_idle()` 用于中断唤醒时退出空闲状态

### 3.6 时钟修改通知
`CLOCK_SET_WALL` 和 `CLOCK_SET_BOOT` 定义了受系统时钟修改影响的 hrtimer 基类型。`clock_was_set()` 通知这些基重新计算到期时间。

### 3.7 Jiffies 精度与 NTP
通过 `JIFFIES_SHIFT`（通常为 8）确保 jiffies 的 NTP 调整精度，避免 HZ 较低时 32 位溢出。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/hrtimer.h>`：高精度定时器接口
  - `<linux/tick.h>`：tick 子系统公共接口
  - `"timekeeping.h"`：时间维护核心逻辑
  - `"tick-sched.h"`：tick 调度相关结构

- **配置依赖**：
  - `CONFIG_GENERIC_CLOCKEVENTS`：通用 clock event 框架
  - `CONFIG_TICK_ONESHOT`：单次触发 tick 支持
  - `CONFIG_GENERIC_CLOCKEVENTS_BROADCAST`：广播 tick 支持
  - `CONFIG_NO_HZ_COMMON` / `CONFIG_NO_HZ_FULL`：动态 tick 支持
  - `CONFIG_HOTPLUG_CPU`：CPU 热插拔对广播的影响

- **模块交互**：
  - 与 `clockevents` 子系统紧密耦合（设备注册、状态管理）
  - 被 `tick-sched.c`、`tick-broadcast.c`、`tick-oneshot.c` 等源文件包含
  - 为 `hrtimer` 和 `timekeeping` 提供底层 tick 支持

## 5. 使用场景

1. **系统启动初始化**  
   `tick_broadcast_init()` 初始化广播机制；`tick_nohz_init()` 初始化 NO_HZ。

2. **CPU 热插拔**  
   `tick_shutdown()` 在 CPU offline 时清理资源；`tick_broadcast_offline()` 处理广播掩码更新。

3. **电源管理（挂起/恢复）**  
   `tick_suspend()` / `tick_resume()` 保存和恢复 tick 状态；广播版本处理全局设备。

4. **动态 Tick（NO_HZ）**  
   当系统空闲时，通过 `tick_switch_to_oneshot()` 切换到 oneshot 模式停止周期 tick；`tick_oneshot_notify()` 在事件发生时唤醒。

5. **高精度定时器启用**  
   `tick_init_highres()` 尝试切换到高精度模式，依赖 oneshot 能力。

6. **时钟修改处理**  
   当用户通过 `settimeofday()` 修改系统时间时，调用 `clock_was_set()` 通知 hrtimer 重新调度。

7. **多核系统广播**  
   在 CPU 进入 C3+ 睡眠状态时，本地 timer 停止，依赖广播设备维持 tick 中断。