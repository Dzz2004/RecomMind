# irq\internals.h

> 自动生成时间: 2025-10-25 13:56:46
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\internals.h`

---

# `irq/internals.h` 技术文档

## 1. 文件概述

`irq/internals.h` 是 Linux 内核中断子系统（IRQ subsystem）的内部头文件，**仅供 `kernel/irq/` 目录下的源文件使用**。该文件定义了中断描述符（`irq_desc`）和中断数据（`irq_data`）的内部状态标志、核心辅助函数、锁操作接口以及中断生命周期管理的关键函数。其内容属于中断子系统的实现细节，**严禁在非核心代码中直接引用或依赖**。

## 2. 核心功能

### 2.1 关键宏定义
- `MAX_SPARSE_IRQS`：根据是否启用 `CONFIG_SPARSE_IRQ`，定义最大支持的 IRQ 数量（`INT_MAX` 或 `NR_IRQS`）。
- `istate`：`irq_desc` 中内部状态字段的别名（`core_internal_state__do_not_mess_with_it`），强调其私有性。
- `IRQ_RESEND` / `IRQ_NORESEND`：控制中断是否需要重发的布尔常量。
- `IRQ_START_FORCE` / `IRQ_START_COND`：控制中断启动行为的标志。
- `_IRQ_DESC_CHECK` / `_IRQ_DESC_PERCPU`：用于描述符获取时的检查类型标志。

### 2.2 内部状态标志
- **线程处理标志（`IRQTF_*`）**：
  - `IRQTF_RUNTHREAD`：通知中断处理线程运行。
  - `IRQTF_WARNED`：已打印缺少线程函数的警告。
  - `IRQTF_AFFINITY`：请求调整线程亲和性。
  - `IRQTF_FORCED_THREAD`：该 action 被强制线程化。
  - `IRQTF_READY`：中断线程已就绪。
  
- **描述符核心状态标志（`IRQS_*`）**：
  - `IRQS_AUTODETECT`：自动检测进行中。
  - `IRQS_SPURIOUS_DISABLED`：因伪中断被禁用。
  - `IRQS_POLL_INPROGRESS`：轮询进行中。
  - `IRQS_ONESHOT`：主处理函数不自动解屏蔽。
  - `IRQS_REPLAY` / `IRQS_PENDING`：控制中断重发逻辑。
  - `IRQS_SUSPENDED`：中断处于挂起状态。
  - `IRQS_NMI`：该 IRQ 用于传递 NMI。
  - `IRQS_SYSFS`：已注册到 sysfs。

### 2.3 核心函数
- **中断生命周期管理**：
  - `irq_activate()` / `irq_activate_and_startup()` / `irq_startup()`：激活并启动中断。
  - `irq_shutdown()` / `irq_shutdown_and_deactivate()`：关闭并停用中断。
  - `irq_enable()` / `irq_disable()`：启用/禁用中断。
  - `irq_percpu_enable()` / `irq_percpu_disable()`：针对 per-CPU 中断的启停。
  - `mask_irq()` / `unmask_irq()` / `unmask_threaded_irq()`：屏蔽/解屏蔽中断。

- **中断处理与重发**：
  - `handle_irq_event()` / `handle_irq_event_percpu()`：处理中断事件。
  - `check_irq_resend()` / `clear_irq_resend()` / `irq_resend_init()`：管理中断重发逻辑。
  - `irq_wait_for_poll()`：等待轮询完成。

- **线程管理**：
  - `__irq_wake_thread()`：唤醒中断处理线程。
  - `wake_threads_waitq()`：唤醒所有等待的中断线程。
  - `irq_set_thread_affinity()`：设置中断线程的 CPU 亲和性。

- **描述符锁操作**：
  - `irq_get_desc_lock()` / `irq_put_desc_unlock()`：获取/释放描述符自旋锁。
  - `irq_get_desc_buslock()` / `irq_put_desc_busunlock()`：获取/释放带总线锁的描述符锁。

- **状态访问与操作**：
  - `irqd_set()` / `irqd_clear()` / `irqd_has_set()`：操作 `irq_data` 的状态位。
  - `irq_state_set_disabled()` / `irq_state_set_masked()`：设置描述符的禁用/屏蔽状态。

- **辅助功能**：
  - `kstat_irqs_desc()`：获取指定 CPU 掩码下的中断统计。
  - `irq_mark_irq()`：标记 IRQ（非稀疏 IRQ 模式下使用）。
  - `irq_can_set_affinity_usr()`：检查用户空间是否可设置亲和性。
  - `irq_setup_affinity()`：设置中断亲和性（SMP 模式下）。

### 2.4 总线锁支持
- `chip_bus_lock()` / `chip_bus_sync_unlock()`：调用 IRQ 芯片的总线锁/解锁回调，用于慢速总线（如 I2C）上的 IRQ 芯片操作同步。

### 2.5 Procfs 接口（条件编译）
- `register_irq_proc()` / `unregister_irq_proc()`：注册/注销 `/proc/interrupts` 条目。
- `register_handler_proc()` / `unregister_handler_proc()`：注册/注销中断处理函数的 proc 条目。

## 3. 关键实现

### 3.1 状态管理
- 使用位掩码（bitmask）高效管理中断描述符和数据的多种状态。
- 通过 `ACCESS_PRIVATE` 宏（在 `__irqd_to_state` 中）安全访问 `irq_data` 的私有状态字段，防止直接操作。

### 3.2 锁机制
- 提供两套描述符获取/释放接口：
  - 普通锁：仅获取描述符自旋锁。
  - 总线锁：在获取描述符锁前后调用芯片的 `irq_bus_lock`/`irq_bus_sync_unlock` 回调，确保慢速总线操作的原子性。

### 3.3 中断重发机制
- 通过 `IRQS_PENDING` 和 `IRQS_REPLAY` 标志协同工作：
  - 当中断在屏蔽状态下触发时，设置 `IRQS_PENDING`。
  - 在解屏蔽时检查 `IRQS_PENDING`，若置位则触发重发（`IRQS_REPLAY`），并在处理后清除。

### 3.4 线程化中断
- 使用 `IRQTF_*` 标志协调主处理函数与中断线程的交互。
- `__irq_wake_thread()` 负责唤醒对应的处理线程，并通过标志位传递控制信息（如亲和性调整请求）。

### 3.5 稀疏 IRQ 支持
- 通过 `CONFIG_SPARSE_IRQ` 条件编译，优化 IRQ 描述符的内存布局（稀疏模式下使用 radix tree，非稀疏模式下使用数组）。
- `irq_mark_irq()` 在非稀疏模式下用于标记已分配的 IRQ。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/irqdesc.h>`：中断描述符定义。
  - `<linux/kernel_stat.h>`：中断统计。
  - `<linux/pm_runtime.h>`：运行时电源管理。
  - `<linux/sched/clock.h>`：调度时钟。
  - `"debug.h"` / `"settings.h"`：IRQ 子系统内部调试和配置。

- **模块依赖**：
  - **IRQ Core**：所有函数均服务于中断核心逻辑。
  - **IRQ Chips**：通过 `irq_data.chip` 回调与具体硬件交互。
  - **SMP Subsystem**：亲和性设置依赖 SMP 支持。
  - **Procfs**：条件编译依赖 `CONFIG_PROC_FS`。
  - **Sparse IRQ**：条件编译依赖 `CONFIG_SPARSE_IRQ`。

## 5. 使用场景

- **中断子系统初始化**：在 `kernel/irq/` 目录下的初始化代码中调用 `irq_activate()` 等函数。
- **中断处理流程**：`handle_irq_event()` 等函数在中断上下文中被调用，处理中断事件。
- **中断配置**：设备驱动通过公共 API（如 `request_irq()`）间接调用内部函数（如 `__irq_set_trigger()`）配置中断。
- **电源管理**：在系统挂起/恢复时，通过 `irq_suspend()`/`irq_resume()`（未在本文件直接定义，但依赖本文件状态）管理 `IRQS_SUSPENDED` 状态。
- **调试与监控**：通过 `/proc/interrupts`（依赖 `register_irq_proc()`）和内核日志提供中断信息。
- **慢速总线设备**：I2C/SPI 等设备的 IRQ 芯片驱动使用 `chip_bus_lock()` 确保操作原子性。