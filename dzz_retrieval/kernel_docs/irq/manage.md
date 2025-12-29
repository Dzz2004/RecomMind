# irq\manage.c

> 自动生成时间: 2025-10-25 14:01:52
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\manage.c`

---

# `irq/manage.c` 技术文档

## 1. 文件概述

`irq/manage.c` 是 Linux 内核通用中断子系统（Generic IRQ Subsystem）的核心管理文件之一，主要提供驱动程序与中断子系统交互的 API 接口。该文件实现了中断同步、CPU 亲和性（affinity）设置、中断线程化控制等关键功能，用于确保中断处理的安全性、可调度性和可配置性。其目标是在多核系统中协调硬中断（hardirq）与线程化中断（threaded IRQ）的执行，并支持从用户空间或内核空间动态调整中断的 CPU 分配策略。

## 2. 核心功能

### 主要函数

- `synchronize_hardirq(unsigned int irq)`  
  等待指定中断号的硬中断处理程序（在其他 CPU 上）执行完毕，但不等待线程化中断处理程序。返回值指示是否存在活跃的线程化处理程序。

- `synchronize_irq(unsigned int irq)`  
  等待指定中断的所有处理程序（包括硬中断和线程化中断）完成。该函数可能睡眠，仅可在可抢占上下文中调用。

- `irq_can_set_affinity(unsigned int irq)`  
  检查指定中断是否支持设置 CPU 亲和性（即是否具备有效的 `irq_set_affinity` 回调且未被禁止平衡）。

- `irq_can_set_affinity_usr(unsigned int irq)`  
  在 `irq_can_set_affinity` 基础上，额外检查中断是否未被标记为 `AFFINITY_MANAGED`，用于判断用户空间是否可修改其亲和性。

- `irq_set_thread_affinity(struct irq_desc *desc)`  
  通知与中断关联的内核线程更新其 CPU 亲和性，通过设置 `IRQTF_AFFINITY` 标志延迟执行。

- `irq_do_set_affinity(struct irq_data *data, const struct cpumask *mask, bool force)`  
  实际执行中断亲和性设置，调用底层 `irq_chip` 的 `irq_set_affinity` 方法，并处理受管中断（managed IRQ）与 housekeeping CPU 的交互逻辑。

### 关键数据结构与变量

- `force_irqthreads_key`（条件编译）  
  静态分支键，用于在启动参数 `threadirqs` 启用时强制将所有中断处理程序线程化（非 PREEMPT_RT 配置下）。

- `irq_default_affinity`（SMP 下）  
  全局默认中断亲和性掩码，通常初始化为所有在线 CPU。

- `IRQTF_AFFINITY`  
  中断线程标志位，用于通知线程需更新其 CPU 亲和性。

## 3. 关键实现

### 中断同步机制

- `__synchronize_hardirq()` 通过双重检查机制确保硬中断处理完成：
  1. 先通过 `irqd_irq_inprogress()` 忙等待退出临界区；
  2. 再加锁检查，若启用 `sync_chip` 且底层芯片支持，还会查询硬件级中断是否仍处于活跃状态（通过 `__irq_get_irqchip_state`）。
- `synchronize_irq()` 在硬中断同步基础上，通过 `wait_event()` 等待 `threads_active` 计数归零，确保线程化处理程序也完成。

### 中断亲和性管理

- **受管中断（Managed IRQ）处理**：当 `irqd_affinity_is_managed` 为真且启用了 `HK_TYPE_MANAGED_IRQ` housekeeping 时，`irq_do_set_affinity` 会将请求的亲和性掩码与 housekeeping CPU 掩码求交集，防止 I/O 中断被路由到隔离 CPU（isolated CPU），除非 I/O 本身由该隔离 CPU 发起。
- **在线 CPU 过滤**：除非 `force` 参数为真，否则实际传递给 `irq_chip` 的掩码会与 `cpu_online_mask` 求交，确保仅指定在线 CPU。
- **线程亲和性延迟更新**：由于 `irq_set_thread_affinity` 可能在硬中断上下文调用，无法直接调用 `set_cpus_allowed_ptr()`，故通过设置标志位，由中断线程自行处理。

### 强制线程化支持

- 在 `CONFIG_IRQ_FORCED_THREADING` 且非 `CONFIG_PREEMPT_RT` 配置下，通过 `early_param("threadirqs", ...)` 解析内核启动参数，启用 `force_irqthreads_key` 静态分支，使所有中断默认以线程方式执行。

### 有效亲和性验证

- 若启用 `CONFIG_GENERIC_IRQ_EFFECTIVE_AFF_MASK`，在设置亲和性后会验证 `effective_affinity_mask` 是否非空，若为空则警告，确保底层 `irq_chip` 正确更新有效掩码。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/irq.h>`、`<linux/interrupt.h>`：提供中断子系统核心 API 和数据结构。
  - `"internals.h"`：包含中断子系统内部实现细节（如 `irq_desc` 操作宏）。
  - `<linux/irqdomain.h>`：支持 IRQ domain 映射。
  - `<linux/sched/isolation.h>`：用于 housekeeping CPU 掩码获取。
  - `<linux/task_work.h>`、`<linux/kthread.h>`：支持中断线程管理。

- **模块交互**：
  - 依赖底层 `irq_chip` 驱动实现 `irq_set_affinity` 和 `irq_get_irqchip_state` 回调。
  - 与调度器子系统交互（通过 `set_cpus_allowed_ptr`、`wait_event` 等）。
  - 与 CPU 热插拔子系统协同处理中断迁移（当 housekeeping CPU 离线/上线时）。

## 5. 使用场景

- **驱动卸载/模块移除**：调用 `synchronize_irq()` 确保所有中断处理完成后再释放资源，避免 UAF。
- **实时性调优**：通过 `irq_set_affinity()` 将特定中断绑定到专用 CPU，减少干扰。
- **系统隔离配置**：在启用了 CPU 隔离（如 `isolcpus`）的系统中，`irq_do_set_affinity` 自动将受管中断限制在 housekeeping CPU 上，保障隔离 CPU 的确定性。
- **调试与诊断**：`synchronize_hardirq()` 用于仅同步硬中断路径，适用于对延迟敏感的场景。
- **用户空间工具**：如 `irqbalance` 或 `/proc/irq/*/smp_affinity` 写入操作，依赖 `irq_can_set_affinity_usr()` 判断是否允许修改。