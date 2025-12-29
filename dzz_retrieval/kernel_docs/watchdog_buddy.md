# watchdog_buddy.c

> 自动生成时间: 2025-10-25 17:51:46
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `watchdog_buddy.c`

---

# watchdog_buddy.c 技术文档

## 1. 文件概述

`watchdog_buddy.c` 实现了 Linux 内核硬锁定检测（hardlockup detection）机制中的“伙伴检查”（buddy checking）逻辑。该机制通过让一个 CPU 负责监控其“下一个”CPU 的高精度定时器（hrtimer）中断是否正常触发，从而检测目标 CPU 是否陷入硬锁定状态（即完全停止响应中断）。该文件通过维护一个在线 CPU 掩码（`watchdog_cpus`）并定义 CPU 之间的监控关系，避免在 CPU 上下线过程中产生误报。

## 2. 核心功能

### 数据结构
- `watchdog_cpus`：静态的 `cpumask_t` 类型变量，记录当前参与硬锁定检测的所有在线 CPU，使用 `__read_mostly` 优化缓存访问。

### 主要函数
- `watchdog_next_cpu(unsigned int cpu)`：根据 `watchdog_cpus` 掩码，返回指定 CPU 的下一个参与监控的 CPU；若已到末尾则回绕到第一个；若掩码中仅有一个 CPU，则返回 `nr_cpu_ids`（表示无效）。
- `watchdog_hardlockup_probe(void)`：硬锁定探测初始化函数（当前实现为空，返回 0）。
- `watchdog_hardlockup_enable(unsigned int cpu)`：启用指定 CPU 的硬锁定检测功能，将其加入 `watchdog_cpus` 掩码，并通过“触摸”（touch）机制防止上下线过程中的误报。
- `watchdog_hardlockup_disable(unsigned int cpu)`：禁用指定 CPU 的硬锁定检测功能，将其从 `watchdog_cpus` 掩码中移除，并同样通过“触摸”机制防止误报。
- `watchdog_buddy_check_hardlockup(int hrtimer_interrupts)`：由当前 CPU 调用，周期性检查其“伙伴”（下一个）CPU 是否发生硬锁定。

## 3. 关键实现

### 伙伴监控机制
- 每个 CPU 不监控自身，而是监控 `watchdog_cpus` 掩码中逻辑上的“下一个”CPU（通过 `watchdog_next_cpu()` 确定）。
- 检查频率为每 3 次 hrtimer 中断执行一次（`hrtimer_interrupts % 3 == 0`），对应时间约为 `watchdog_thresh * 1.2` 秒，略大于默认阈值，以平衡灵敏度与开销。

### 防止误报的“触摸”策略
- **CPU 上线时**：新上线的 CPU 和其下一个 CPU 都会被“触摸”（调用 `watchdog_hardlockup_touch_cpu()`），确保它们的看门狗计数器被重置，避免其他 CPU 在其 hrtimer 首次运行前误判为锁定。
- **CPU 下线时**：下线 CPU 的下一个 CPU 会被“触摸”，防止前一个 CPU 立即检查该目标而触发误报。

### 内存屏障同步
- 在修改 `watchdog_cpus` 掩码前后使用 `smp_wmb()`（写内存屏障），确保“触摸”操作在掩码更新前对其他 CPU 可见。
- 在读取伙伴 CPU 状态前使用 `smp_rmb()`（读内存屏障），确保能观察到最新的掩码状态和触摸操作，维持检查逻辑的一致性。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/cpu.h>`：CPU 热插拔相关接口。
  - `<linux/cpumask.h>`：CPU 掩码操作函数（如 `cpumask_next`, `cpumask_first`）。
  - `<linux/kernel.h>`：基础内核定义。
  - `<linux/nmi.h>`：包含硬锁定检测相关函数声明（如 `watchdog_hardlockup_touch_cpu`, `watchdog_hardlockup_check`）。
  - `<linux/percpu-defs.h>`：每 CPU 变量支持。
- **外部函数依赖**：
  - `watchdog_hardlockup_touch_cpu()` 和 `watchdog_hardlockup_check()`：由其他 watchdog 模块（如 `nmi_watchdog.c`）实现，用于重置看门狗计数器和执行实际锁定检测。
- **配置依赖**：该文件通常在 `CONFIG_HARDLOCKUP_DETECTOR` 或相关看门狗配置启用时编译。

## 5. 使用场景

- **硬锁定检测**：作为内核 NMI 看门狗（NMI watchdog）的一部分，在启用了硬锁定检测功能的系统中运行。
- **CPU 热插拔**：在 CPU 动态上线（`CPU_ONLINE`）或下线（`CPU_DEAD`）事件中被调用，确保监控拓扑正确更新且不产生误报。
- **高可靠性系统**：在服务器、实时系统等对稳定性要求高的环境中，用于及时发现并处理 CPU 完全挂死的严重故障。
- **调试与诊断**：当系统疑似因内核 bug 导致某 CPU 停止响应时，该机制可触发 panic 或记录日志，辅助问题定位。