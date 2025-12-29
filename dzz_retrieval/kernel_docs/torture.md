# torture.c

> 自动生成时间: 2025-10-25 16:59:16
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `torture.c`

---

# torture.c 技术文档

## 文件概述

`torture.c` 是 Linux 内核中用于实现通用“torture 测试”（压力/极限测试）的公共支持代码。该文件提供了一套可复用的基础设施，用于在内核中对各种子系统（如 RCU、锁机制等）进行高强度、长时间、高并发的压力测试，以暴露潜在的竞态条件、死锁、内存泄漏或正确性问题。它最初基于 `kernel/rcu/torture.c`，现已成为多个内核 torture 测试模块的共享基础。

## 核心功能

### 模块参数（可调优）
- `disable_onoff_at_boot`：启动时禁用 CPU 热插拔测试。
- `ftrace_dump_at_shutdown`：系统关闭时自动 dump ftrace 跟踪数据。
- `verbose_sleep_frequency` / `verbose_sleep_duration`：控制 verbose 输出时的睡眠频率和时长，用于减缓输出节奏。
- `random_shuffle`：启用随机打乱测试行为（具体用途由上层测试定义）。
- `verbose`：全局 verbose 级别（通过 `torture_type` 间接设置）。

### 全局状态管理
- `fullstop`：协调模块卸载（rmmod）与系统关机的互斥状态机（`FULLSTOP_DONTSTOP`/`SHUTDOWN`/`RMMOD`）。
- `fullstop_mutex`：保护 `fullstop` 状态的互斥锁。

### 高精度延时函数（带随机扰动）
- `torture_hrtimeout_ns()`：纳秒级高精度定时器睡眠，支持随机扰动。
- `torture_hrtimeout_us()`：微秒级睡眠（扰动单位为纳秒）。
- `torture_hrtimeout_ms()`：毫秒级睡眠（扰动单位为微秒）。
- `torture_hrtimeout_jiffies()`：jiffies 级睡眠（扰动为 1 jiffy）。
- `torture_hrtimeout_s()`：秒级睡眠（扰动单位为毫秒）。

### CPU 热插拔测试支持（`CONFIG_HOTPLUG_CPU`）
- `torture_num_online_cpus()`：返回 torture 测试视角下的在线 CPU 数量。
- `torture_offline()`：尝试将指定 CPU 离线，并记录统计信息。
- `torture_online()`：尝试将指定 CPU 上线，并记录统计信息。

### 辅助函数
- `verbose_torout_sleep()`：根据频率参数在 verbose 输出时插入不可中断睡眠。

## 关键实现

### 高精度延时与去同步化
所有 `torture_hrtimeout_*` 函数均基于 `schedule_hrtimeout()` 实现高精度睡眠，并通过 `torture_random()` 引入随机扰动（fuzz）。这种设计**故意打破测试线程与系统定时器的同步性**，增加并发场景的随机性和压力，更容易触发边界条件问题。

### CPU 热插拔测试的健壮性处理
- **启动阶段宽容**：在内核启动未完成时（`rcu_inkernel_boot_has_ended()` 返回 false），若热插拔返回 `-EBUSY`（常见于 PCI 探测期间），则不计入失败次数。
- **安全防护**：禁止离线最后一个 CPU（`num_online_cpus() <= 1`）。
- **状态跟踪**：维护 `torture_online_cpus` 全局变量，供测试模块感知当前“有效”CPU 数量，用于负载均衡。
- **性能统计**：记录热插拔操作的尝试次数、成功次数、耗时（最小/最大/总和）。

### 模块生命周期与系统事件协调
通过 `fullstop` 状态机和 `fullstop_mutex`，确保 torture 测试模块在**系统关机**和**手动卸载**两种场景下能正确终止，避免并发操作导致状态混乱。

### Verbose 输出节流
`verbose_torout_sleep()` 通过原子计数器和模运算，按指定频率插入短暂睡眠，防止大量 verbose 日志淹没控制台或日志系统。

## 依赖关系

- **内核核心组件**：
  - 高精度定时器（`<linux/hrtimer.h>`）
  - 内核线程（`<linux/kthread.h>`）
  - CPU 热插拔（`<linux/cpu.h>`，条件编译）
  - RCU（`rcu_inkernel_boot_has_ended()`）
  - 调度器（`TASK_IDLE`, `schedule_*`）
- **头文件依赖**：
  - `linux/torture.h`：定义 torture 测试通用接口（如 `torture_random_state`）。
  - `rcu/rcu.h`：提供 RCU 相关辅助函数。
- **被依赖模块**：
  - RCU torture 测试（`kernel/rcu/torture.c`）
  - 锁 torture 测试（如 `kernel/locking/locktorture.c`）
  - 其他使用 `linux/torture.h` 接口的子系统测试模块。

## 使用场景

1. **RCU 子系统验证**：作为 RCU torture 测试的基础库，提供 CPU 热插拔、高精度延时、状态管理等功能。
2. **锁机制压力测试**：用于测试各种内核锁（mutex、rwsem、spinlock 等）在极端并发和 CPU 动态变化下的正确性。
3. **内存屏障与同步原语测试**：配合自定义测试逻辑，验证内存顺序和同步操作的可靠性。
4. **系统稳定性长期运行测试**：在服务器或嵌入式设备上长时间运行 torture 测试，暴露偶发性内核 bug。
5. **新硬件/架构验证**：在新平台上线前，通过 torture 测试验证 CPU 热插拔、调度器、定时器等底层功能的稳定性。