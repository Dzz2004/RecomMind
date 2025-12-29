# time\itimer.c

> 自动生成时间: 2025-10-25 16:39:13
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `time\itimer.c`

---

# `time/itimer.c` 技术文档

## 1. 文件概述

`time/itimer.c` 是 Linux 内核中实现 POSIX 间隔定时器（interval timers，简称 itimers）的核心文件。该文件提供了对三种经典 Unix 间隔定时器的支持：

- **ITIMER_REAL**：基于真实时间（墙上时钟）的定时器，到期时发送 `SIGALRM` 信号
- **ITIMER_VIRTUAL**：基于进程用户态 CPU 时间的定时器，到期时发送 `SIGVTALRM` 信号
- **ITIMER_PROF**：基于进程总 CPU 时间（用户态+内核态）的定时器，到期时发送 `SIGPROF` 信号

该文件实现了 `getitimer()`、`setitimer()` 系统调用以及 `alarm()` 系统调用（在架构支持的情况下），为用户空间程序提供间隔定时器功能。

## 2. 核心功能

### 主要函数

- **`itimer_get_remtime()`**：获取高精度实时定时器的剩余时间
- **`get_cpu_itimer()`**：获取 CPU 时间相关的定时器（虚拟/性能）状态
- **`do_getitimer()`**：内部实现获取指定类型定时器状态的逻辑
- **`put_itimerval()`**：将内核内部的 `itimerspec64` 格式转换为用户空间的 `old_itimerval` 格式
- **`getitimer()` 系统调用**：用户空间获取定时器状态的入口
- **`it_real_fn()`**：ITIMER_REAL 定时器到期时的回调函数
- **`set_cpu_itimer()`**：设置 CPU 时间相关的定时器
- **`do_setitimer()`**：内部实现设置指定类型定时器的逻辑
- **`clear_itimer()`**：在 SELinux 环境下清除所有定时器（安全相关）
- **`alarm_setitimer()`**：实现 `alarm()` 系统调用的内部函数
- **`alarm()` 系统调用**：设置单次实时定时器的简化接口

### 数据结构

- **`struct cpu_itimer`**：存储 CPU 时间定时器的状态（在 `signal_struct` 中）
- **`struct hrtimer`**：高精度定时器，用于实现 ITIMER_REAL
- **`struct itimerspec64`**：64 位时间规格结构，内核内部使用
- **`struct __kernel_old_itimerval`**：用户空间兼容的定时器值结构

## 3. 关键实现

### 定时器类型实现差异

- **ITIMER_REAL**：使用高精度定时器（`hrtimer`）实现，基于真实时间，通过 `hrtimer_start()` 启动，到期时调用 `it_real_fn()` 发送 `SIGALRM` 信号
- **ITIMER_VIRTUAL/ITIMER_PROF**：基于 CPU 时间采样实现，通过 `thread_group_sample_cputime()` 获取当前进程组的 CPU 时间，与设定的过期时间比较来判断是否到期

### 时间精度处理

- 使用纳秒级精度的 `ktime_t` 和 `timespec64` 进行内部计算
- 用户空间接口使用微秒精度（`tv_usec`），通过 `NSEC_PER_USEC` 进行单位转换
- 对于即将到期的定时器，返回 `TICK_NSEC`（1 微秒）作为剩余时间，避免返回 0 导致用户误判

### 并发安全

- 使用 `siglock` 自旋锁保护信号结构体中的定时器状态
- ITIMER_REAL 的设置操作需要处理定时器可能正在执行的竞态条件，通过 `hrtimer_try_to_cancel()` 和重试机制确保安全
- CPU 定时器操作在 `siglock` 保护下进行，确保线程组内的一致性

### 兼容性支持

- 提供 32 位兼容接口（`COMPAT_SYSCALL_DEFINE2`）
- 支持 `alarm()` 系统调用（在 `__ARCH_WANT_SYS_ALARM` 定义时）
- 处理 32 位系统上的时间值溢出问题（限制为 `INT_MAX`）

## 4. 依赖关系

### 头文件依赖

- **`<linux/hrtimer.h>`**：高精度定时器框架，用于 ITIMER_REAL 实现
- **`<linux/sched/cputime.h>`**：CPU 时间采样功能，用于虚拟和性能定时器
- **`<linux/posix-timers.h>`**：POSIX 定时器相关定义
- **`<linux/sched/signal.h>`**：信号处理和 `signal_struct` 结构定义
- **`<linux/time.h>`**：时间转换和操作函数
- **`<trace/events/timer.h>`**：定时器事件跟踪支持

### 内核子系统依赖

- **调度子系统**：通过 `current` 获取当前任务，使用 `thread_group_sample_cputime()` 采样 CPU 时间
- **信号子系统**：通过 `kill_pid_info()` 发送信号，使用 `siglock` 进行同步
- **高精度定时器子系统**：ITIMER_REAL 的底层实现依赖 hrtimer 框架
- **安全子系统**：SELinux 相关的 `clear_itimer()` 函数

## 5. 使用场景

### 用户空间编程

- **定时任务**：应用程序使用 `setitimer()` 设置周期性或一次性定时器
- **超时控制**：网络编程中设置 I/O 操作超时
- **性能监控**：使用 ITIMER_PROF 监控程序 CPU 使用情况
- **简单定时**：使用 `alarm()` 系统调用设置简单的秒级定时器

### 内核内部使用

- **进程管理**：在进程退出或权限变更时清除定时器（SELinux 场景）
- **信号处理**：定时器到期时向进程发送相应信号
- **时间跟踪**：通过 tracepoint 记录定时器状态变化和到期事件
- **兼容层**：为不同架构和位数提供统一的定时器接口

### 系统调用路径

- **`getitimer()`** → `do_getitimer()` → 对应定时器类型的具体获取函数
- **`setitimer()`** → `do_setitimer()` → 对应定时器类型的具体设置函数  
- **`alarm()`** → `alarm_setitimer()` → `do_setitimer(ITIMER_REAL, ...)`

该文件是 Linux 内核 POSIX 定时器功能的重要组成部分，为用户空间提供了经典的 Unix 间隔定时器接口。