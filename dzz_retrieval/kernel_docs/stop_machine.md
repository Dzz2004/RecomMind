# stop_machine.c

> 自动生成时间: 2025-10-25 16:30:03
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `stop_machine.c`

---

# `stop_machine.c` 技术文档

## 1. 文件概述

`stop_machine.c` 实现了 Linux 内核中用于在所有（或指定）CPU 上同步执行特定函数的机制，即 **stop_machine** 机制。该机制通过为每个 CPU 创建一个高优先级的内核线程（称为 stopper），在需要时唤醒这些线程以执行指定任务，并确保在执行期间其他任务无法抢占，从而实现对整个系统或部分 CPU 的“冻结”式同步操作。此机制常用于需要全局一致状态的关键内核操作，如 CPU 热插拔、模块加载、内核热补丁（livepatch）等。

## 2. 核心功能

### 主要数据结构

- **`struct cpu_stop_done`**  
  用于协调多个 CPU 上 stop 任务的完成状态，包含待完成任务计数（`nr_todo`）、返回值（`ret`）和完成信号量（`completion`）。

- **`struct cpu_stopper`**  
  每个 CPU 对应一个 stopper 实例，包含：
  - `thread`：stopper 内核线程
  - `lock`：保护 pending works 链表的自旋锁
  - `enabled`：该 stopper 是否启用（对应 CPU 是否在线）
  - `works`：待执行的 `cpu_stop_work` 链表
  - `stop_work`、`caller`、`fn`：用于 `stop_cpus` 的临时字段

- **`struct multi_stop_data`**  
  用于多 CPU 同步执行的共享控制结构，包含：
  - `fn` 和 `data`：要执行的函数及其参数
  - `num_threads`：参与同步的线程数
  - `active_cpus`：指定哪些 CPU 需要实际执行函数
  - `state`：全局状态机（`MULTI_STOP_*` 枚举）
  - `thread_ack`：用于状态同步的原子计数器

- **`enum multi_stop_state`**  
  多 CPU 同步执行的状态机，包括：
  - `MULTI_STOP_NONE`
  - `MULTI_STOP_PREPARE`
  - `MULTI_STOP_DISABLE_IRQ`
  - `MULTI_STOP_RUN`
  - `MULTI_STOP_EXIT`

### 主要函数

- **`stop_one_cpu(cpu, fn, arg)`**  
  在指定 CPU 上执行函数 `fn(arg)`，阻塞等待执行完成。若 CPU 离线则返回 `-ENOENT`。

- **`cpu_stop_queue_work(cpu, work)`**  
  将 stop 任务加入指定 CPU 的 stopper 队列，若 CPU 在线则唤醒其 stopper 线程。

- **`multi_cpu_stop(data)`**  
  stopper 线程的主函数，实现多 CPU 同步状态机，负责禁用中断、执行函数、状态同步等。

- **`print_stop_info(log_lvl, task)`**  
  调试辅助函数，若 `task` 是 stopper 线程，则打印其当前执行函数及调用者信息。

- **`set_state()` / `ack_state()`**  
  控制多 CPU 同步状态机的推进：`set_state` 设置新状态并重置 ack 计数器，`ack_state` 用于线程确认状态，最后一个确认者推进到下一状态。

## 3. 关键实现

### Stopper 线程模型
- 每个可能的 CPU 都有一个 `cpu_stopper` 实例，其中包含一个专用内核线程。
- 该线程运行 `multi_cpu_stop` 函数，处于高优先级实时调度策略（由 `smpboot` 框架设置），可抢占普通任务。
- 当有 stop 任务时，通过 `wake_up_process` 唤醒对应 stopper 线程。

### 多 CPU 同步状态机
- 使用共享的 `multi_stop_data` 结构协调所有参与 CPU。
- 状态转换通过 `set_state` 触发，所有线程通过轮询 `msdata->state` 检测状态变化。
- 每个状态变更需所有线程调用 `ack_state` 确认，最后一个确认者推进到下一状态，确保严格同步。
- 在 `MULTI_STOP_DISABLE_IRQ` 状态下，所有参与 CPU 禁用本地中断（包括硬中断），ARM64 还会屏蔽 SDEI 事件。
- 仅 `active_cpus` 中的 CPU 在 `MULTI_STOP_RUN` 状态执行实际函数。

### 中断与 NMI 安全
- 执行期间禁用本地中断，防止中断处理程序干扰关键操作。
- 在等待状态循环中调用 `touch_nmi_watchdog()` 防止 NMI watchdog 误报硬锁死。
- 使用 `rcu_momentary_dyntick_idle()` 通知 RCU 系统当前 CPU 处于空闲状态，避免 RCU stall。

### CPU 热插拔处理
- `cpu_stopper.enabled` 标志反映 CPU 在线状态。
- 若 CPU 离线时提交 stop 任务，则立即完成（调用 `cpu_stop_signal_done`），避免阻塞。
- 支持从非活动 CPU（如 CPU hotplug 的 bringup 路径）调用 `stop_machine`，此时中断可能已禁用，需保存/恢复中断状态。

### 死锁预防
- `cpu_stop_queue_two_works` 函数通过嵌套锁（`SINGLE_DEPTH_NESTING`）和重试机制，确保两个 stopper 的入队操作原子性，避免与 `stop_cpus` 并发导致的死锁。
- 使用 `preempt_disable()` 保证唤醒操作在不可抢占上下文中完成，防止唤醒丢失。

## 4. 依赖关系

- **调度子系统**：依赖 `kthread` 创建 stopper 线程，使用 `wake_up_process` 唤醒。
- **SMP 子系统**：依赖 `smpboot.h` 的 CPU 热插拔通知机制来启用/禁用 stopper。
- **中断子系统**：调用 `local_irq_disable/restore`、`hard_irq_disable` 控制中断。
- **RCU 子系统**：通过 `rcu_momentary_dyntick_idle` 与 RCU 交互。
- **NMI 子系统**：调用 `touch_nmi_watchdog` 避免 watchdog 误报。
- **ARM64 架构**：条件编译包含 SDEI（Software Delegated Exception Interface）屏蔽/解除屏蔽。
- **Per-CPU 基础设施**：使用 `DEFINE_PER_CPU` 和 `per_cpu_ptr` 管理 per-CPU stopper 实例。

## 5. 使用场景

- **CPU 热插拔**：在 CPU 上线/下线过程中执行需要全局同步的操作。
- **内核模块加载/卸载**：某些架构或功能（如 ftrace）需要 stop_machine 来安全修改内核文本。
- **内核热补丁（Livepatch）**：在应用补丁时冻结所有 CPU 以确保一致性。
- **动态 tracing（如 ftrace）**：修改函数入口指令时需 stop_machine 保证原子性。
- **内存热插拔**：某些内存操作需要全局同步。
- **内核调试与诊断**：通过 `print_stop_info` 辅助分析 stopper 行为。
- **架构特定操作**：如 ARM64 的 SDEI 事件处理需要在 stop_machine 上下文中屏蔽。