# sched\clock.c

> 自动生成时间: 2025-10-25 15:58:20
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\clock.c`

---

# `sched/clock.c` 技术文档

## 1. 文件概述

`sched/clock.c` 实现了 Linux 内核中用于调度器的高分辨率时间戳机制 `sched_clock()`，特别针对 **不稳定 CPU 时钟源**（如 TSC 在某些硬件上不可靠）的场景。该文件提供了一个在单 CPU 上单调递增、高精度（纳秒级）、可在任意上下文（包括 NMI）中调用的时间源，并通过混合全局时间（GTOD）与本地时钟（如 TSC）来在多核系统中尽量减少时钟漂移。

**重要警告**：不同 CPU 上的 `cpu_clock(i)` 与 `cpu_clock(j)`（i ≠ j）之间 **不保证全局单调性**，时间可能“倒退”。

## 2. 核心功能

### 主要函数

| 函数 | 说明 |
|------|------|
| `sched_clock()` | 弱符号默认实现，基于 jiffies 提供低精度时间戳；架构可覆盖 |
| `local_clock()` | 宏定义，等价于当前 CPU 的 `cpu_clock(smp_processor_id())` |
| `cpu_clock(int cpu)` | 返回指定 CPU 的高分辨率时间戳（纳秒） |
| `sched_clock_stable()` | 判断当前系统是否已进入“稳定时钟”模式（TSC 可靠） |
| `clear_sched_clock_stable()` | 标记时钟为不稳定（如检测到 TSC 异常），触发修复流程 |
| `sched_clock_init()` / `sched_clock_init_late()` | 初始化时钟子系统，分早期和晚期阶段 |

### 关键数据结构

```c
struct sched_clock_data {
    u64 tick_raw;   // 上次更新时的原始 sched_clock() 值（如 TSC）
    u64 tick_gtod;  // 上次更新时的全局时间（ktime_get_ns()）
    u64 clock;      // 当前推算出的本地高精度单调时间
};
```

- 每个 CPU 拥有一个 `sched_clock_data` 实例（`per_cpu` 变量）
- 全局偏移量：
  - `__sched_clock_offset`：原始时钟到稳定时间的偏移
  - `__gtod_offset`：GTOD 到稳定时间的偏移

### 静态键（Static Keys）

- `sched_clock_running`：标记时钟子系统是否已初始化
- `__sched_clock_stable`：标记时钟源是否稳定（TSC 可靠）
- `__sched_clock_stable_early`：启动早期假设时钟稳定，避免多次切换

## 3. 关键实现

### 3.1 两种模式

- **稳定模式**（`CONFIG_HAVE_UNSTABLE_SCHED_CLOCK` 未定义）：  
  直接使用架构提供的 `sched_clock()`，假定其全局同步且高精度（如 ARM64 的 arch counter）。

- **不稳定模式**（`CONFIG_HAVE_UNSTABLE_SCHED_CLOCK` 定义）：  
  混合 GTOD（`ktime_get_ns()`）与原始 `sched_clock()`（如 TSC）：
  - 以 GTOD 为基准，利用 `sched_clock()` 的高分辨率 delta 提升精度
  - 通过 `__sched_clock_offset` 和 `__gtod_offset` 对齐两个时钟源

### 3.2 时钟对齐与漂移控制

- 初始化时通过 `__sched_clock_gtod_offset()` 计算初始偏移量，确保切换时连续
- `sched_clock_local()` 函数实现核心逻辑：
  - 计算自上次更新以来的原始时钟增量（`delta = now - tick_raw`）
  - 将 GTOD 基准时间（`tick_gtod + __gtod_offset`）加上 `delta` 得到新时间
  - 使用 `wrap_min`/`wrap_max` 处理 64 位回绕，并限制时间跳跃范围（防止 TSC 异常）

### 3.3 稳定性动态切换

- **启动时假设稳定**：`__sched_clock_stable_early = 1`
- **晚期初始化**（`late_initcall`）：
  - 若仍认为稳定，则调用 `__set_sched_clock_stable()` 完成对齐并启用稳定模式
  - 若驱动（如 ACPI/Intel Idle）标记 TSC 不稳定，则调用 `clear_sched_clock_stable()`
- **不稳定处理**：
  - 调度工作队列 `sched_clock_work`
  - 重新以 GTOD 为基准重置所有 CPU 的 `sched_clock_data`

### 3.4 中断与抢占安全

- 关键操作（如 stamp、offset 计算）使用 `local_irq_disable()` 保证原子性
- `notrace` 属性避免被 ftrace 拦截，确保在 NMI 等上下文中可用

## 4. 依赖关系

- **时间子系统**：
  - 依赖 `ktime_get_ns()`（GTOD，来自 `kernel/time/`）
  - 依赖 `jiffies` 和 `HZ`（用于默认 `sched_clock` 实现）
- **调度器**：为 `kernel/sched/` 提供高精度时间戳（如 `rq->clock` 更新）
- **时钟事件/源**：与 `tick` 子系统交互（`TICK_DEP_BIT_CLOCK_UNSTABLE`）
- **架构支持**：
  - 若架构定义 `CONFIG_HAVE_UNSTABLE_SCHED_CLOCK`，则启用混合模式
  - 架构可提供自己的 `sched_clock()` 实现（如 x86 使用 TSC）

## 5. 使用场景

- **调度器时间统计**：计算任务运行时间、就绪队列时钟等
- **延迟跟踪**：`ftrace`、`perf` 等性能工具依赖 `local_clock()` 获取精确时间戳
- **锁竞争分析**：`lockdep` 使用 `sched_clock()` 记录锁持有时间
- **RCU、中断处理**：需要高精度、低开销时间戳的内核子系统
- **虚拟化与电源管理**：在 CPU 进入/退出 idle 时校正时钟（通过 `sched_clock_idle_*` 钩子，虽未在本文件实现但相关）