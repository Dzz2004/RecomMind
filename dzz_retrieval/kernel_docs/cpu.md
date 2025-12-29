# cpu.c

> 自动生成时间: 2025-10-25 12:55:09
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cpu.c`

---

# cpu.c 技术文档

## 1. 文件概述

`cpu.c` 是 Linux 内核中 CPU 热插拔（CPU Hotplug）子系统的核心实现文件，负责管理 CPU 的在线（online）与离线（offline）状态转换。该文件实现了 CPU 热插拔状态机、回调函数调用机制、多实例支持、原子状态处理以及与 SMP（对称多处理）架构的协同工作。通过定义一系列有序的状态步骤（steps），内核可以在 CPU 上下电过程中安全地执行初始化和清理操作，确保系统稳定性。

## 2. 核心功能

### 主要数据结构

- **`struct cpuhp_cpu_state`**  
  每个 CPU 的热插拔状态存储结构，包含当前状态、目标状态、失败状态、热插拔线程指针、同步信号量、多实例回滚信息等，用于驱动状态机执行。

- **`struct cpuhp_step`**  
  热插拔状态机的单个步骤定义，包含启动（startup）和拆除（teardown）回调函数（支持单实例或多实例模式）、步骤名称、是否可中断、是否支持多实例等属性。

### 关键函数

- **`cpuhp_invoke_callback()`**  
  核心回调调用函数，根据指定 CPU、状态、方向（bringup/teardown）及节点信息，执行对应的单实例或多实例回调，并支持失败时的自动回滚。

- **`cpuhp_get_step()`**  
  根据 `cpuhp_state` 枚举值获取对应的 `cpuhp_step` 结构。

- **`cpuhp_step_empty()`**  
  判断指定方向（bringup/teardown）下某状态步骤是否为空（即无回调函数）。

- **`wait_for_ap_thread()` / `complete_ap_thread()`**  
  用于主线程与 AP（Application Processor）热插拔线程之间的同步，通过 completion 机制等待操作完成。

- **`cpuhp_is_ap_state()` / `cpuhp_is_atomic_state()`**  
  判断某状态是否属于 AP 状态或原子状态（需在 IRQ 禁用下执行且不可失败）。

### 全局变量

- **`cpuhp_state`**  
  每 CPU 变量，存储各 CPU 的热插拔运行时状态。

- **`cpus_booted_once_mask`**  
  记录曾经成功启动过的 CPU 位图（仅在 CONFIG_SMP 下定义）。

- **`cpuhp_hp_states[]`**  
  全局状态步骤数组，由其他子系统注册回调填充。

- **`cpuhp_state_mutex`**  
  保护状态注册和修改的互斥锁。

## 3. 关键实现

### 热插拔状态机

CPU 热插拔通过预定义的 `enum cpuhp_state` 枚举实现线性状态机。每个状态对应一个 `cpuhp_step`，包含 bringup 和 teardown 两个方向的回调。状态转换按序执行，确保依赖关系正确。

### 多实例支持

对于需要动态添加/删除多个实例的子系统（如中断域、设备驱动），`cpuhp_step` 支持 `multi_instance` 模式。实例通过 `hlist_head list` 管理，`cpuhp_invoke_callback()` 可遍历所有实例执行回调，并在失败时按逆序回滚已成功执行的实例。

### 原子状态处理

部分状态（如 `CPUHP_AP_IDLE_DEAD` 到 `CPUHP_AP_ONLINE`）被标记为“原子状态”，要求在 IRQ 禁用上下文中执行且**不可失败**。这些状态通常用于 CPU 核心底层初始化/销毁，失败将导致系统不稳定。

### AP 线程同步

在 SMP 系统中，CPU 上下电操作由专用内核线程（`cpuhp_thread`）在目标 CPU 上执行。主线程通过 `completion`（`done_up`/`done_down`）等待操作完成，确保状态转换的串行性和可见性。

### 锁依赖检测（Lockdep）

在 `CONFIG_LOCKDEP` 启用时，通过 `cpuhp_state_up_map` 和 `cpuhp_state_down_map` 为热插拔路径提供锁依赖分析，帮助检测潜在的死锁问题。

### 回调执行与回滚

`cpuhp_invoke_callback()` 在执行多实例回调时，若某实例失败：
1. 记录失败节点（通过 `lastp`）
2. 切换回调方向（bringup 失败则执行 teardown 回滚）
3. 逆序执行已成功实例的回滚操作
4. 触发 `WARN_ON_ONCE` 若回滚本身失败（因回滚必须成功）

### 跟踪点（Tracepoints）

集成 `trace/events/cpuhp.h`，在回调进入/退出时记录 trace 事件（如 `trace_cpuhp_enter`、`trace_cpuhp_multi_enter`），便于调试和性能分析。

## 4. 依赖关系

- **SMP 子系统**：依赖 `smp.h`、`smpboot.h` 实现 CPU 间通信和启动流程。
- **调度器**：使用 `sched/mm.h`、`sched/hotplug.h`、`sched/isolation.h` 等接口管理 CPU 亲和性和隔离。
- **内存管理**：通过 `slab.h`、`gfp.h` 分配多实例节点内存。
- **中断子系统**：在原子状态中操作 IRQ（`irq.h`、`nmi.h`）。
- **电源管理**：与 `suspend.h` 协同处理系统挂起时的 CPU 状态。
- **RCU**：使用 `rcupdate.h` 确保回调注册/注销的安全性。
- **Lockdep**：在调试配置下集成锁依赖检测。
- **Per-CPU 机制**：依赖 `percpu-rwsem.h` 和 per-CPU 变量管理状态。

## 5. 使用场景

- **CPU 热插拔**：用户通过 `/sys/devices/system/cpu/cpuX/online` 接口动态启用/禁用 CPU 时，触发状态机执行 bringup/teardown 流程。
- **系统启动/关机**：内核初始化时 bringup 所有 CPU；关机时 teardown 非引导 CPU。
- **Suspend/Resume**：系统挂起时 offline 非引导 CPU，恢复时重新 online。
- **内核模块注册**：驱动或子系统通过 `cpuhp_setup_state()` 等 API 注册自己的 CPU 热插拔回调，在 CPU 状态变化时执行特定操作（如重绑中断、迁移任务）。
- **CPU 隔离**：配合 `isolcpus` 内核参数，在启动时将某些 CPU 从调度器中隔离，但仍需执行底层 bringup。
- **错误恢复**：当某热插拔步骤失败时，自动回滚已执行的操作，维持系统一致性。