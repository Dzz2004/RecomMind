# rcu\rcutorture.c

> 自动生成时间: 2025-10-25 15:41:29
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rcu\rcutorture.c`

---

# `rcu/rcutorture.c` 技术文档

## 1. 文件概述

`rcu/rcutorture.c` 是 Linux 内核中用于对 **Read-Copy Update (RCU)** 机制进行压力测试和正确性验证的模块化“折磨测试”（torture test）设施。该文件通过模拟高并发、异常路径、CPU 热插拔、中断上下文读取、延迟释放等多种极端场景，主动探测 RCU 实现中的潜在缺陷（如内存顺序错误、宽限期推进失败、死锁、优先级反转等）。测试结果可用于验证 RCU 子系统在各种配置（如 `rcu`, `srcu`, `tasks-rcu` 等）下的健壮性和正确性。

该模块是内核自检（selftest）体系的重要组成部分，通常在开发、回归测试或稳定性验证阶段启用。

## 2. 核心功能

### 主要数据结构

- **`struct rcu_torture`**  
  更新侧（writer）使用的测试对象，包含 `rcu_head` 用于回调、`rtort_pipe_count` 用于检测宽限期延迟、`rtort_mbtest` 用于内存屏障验证、以及指向读者检查结构的指针。

- **`struct rcu_torture_reader_check`**  
  读者侧用于验证全局内存顺序的“邮箱”结构，记录读者循环次数、分配者信息等，用于检测 RCU 读侧临界区是否正确观察到更新。

- **`rcu_torture_freelist`**  
  全局空闲对象链表，供 writer 线程分配和 reader 线程释放测试对象。

### 主要线程/任务

- **Writer 任务**：周期性分配新对象、更新全局指针、将旧对象加入 RCU 回调链。
- **Fake Writer 任务**：模拟写者行为，增加并发压力。
- **Reader 任务**：在各种上下文（进程、软中断、硬中断）中执行 RCU 读侧临界区，验证数据一致性。
- **FQS（Force Quiescent State）任务**：周期性调用 `rcu_force_quiescent_state()` 加速宽限期推进。
- **Forward Progress 任务**：检测 RCU 宽限期是否能持续向前推进，防止死锁。
- **CPU Hotplug 任务**：动态启停 CPU，测试 RCU 在拓扑变化下的行为。
- **Stats 任务**：定期输出测试统计信息（如错误计数、延迟分布）。
- **Stall 任务**：故意造成 CPU 或 RCU 宽限期停滞，测试内核的 stall 检测机制。
- **Boost 任务**：验证 RCU 优先级提升（priority boosting）机制是否正常工作。
- **Barrier / NOCB / Read-exit 等专项任务**：针对特定 RCU 特性进行测试。

### 关键模块参数（`torture_param`）

- **`torture_type`**：指定要测试的 RCU 类型（如 `"rcu"`, `"srcu"`）。
- **`extendables`**：控制读者如何扩展临界区（禁用 BH/IRQ/抢占、嵌套 RCU 等）。
- **`fqs_*`**：配置强制宽限期推进的频率和持续时间。
- **`fwd_progress*`**：控制前向进度检测任务的行为。
- **`gp_*`**：选择使用的宽限期等待原语（同步、异步、轮询、加速等）。
- **`onoff_interval`**：启用 CPU 热插拔测试。
- **`stall_cpu*`**：配置 CPU 停滞测试。
- **`test_boost*`**：启用优先级提升测试。
- **`verbose`**：控制调试日志输出级别。

## 3. 关键实现

### RCU 正确性验证机制

- **Pipe Testing（管道测试）**：  
  每个被释放的 `rcu_torture` 对象携带一个 `rtort_pipe_count` 字段，表示自分配以来经历的宽限期数量。Reader 在读取时记录该值。若发现 `pipe_count > RCU_TORTURE_PIPE_LEN`，说明宽限期推进过慢或失败，视为错误。

- **Memory-Barrier Testing（内存屏障测试）**：  
  利用 `rtort_mbtest` 字段和特定的读写顺序，验证 RCU 读侧与写侧之间的内存顺序是否符合预期，防止编译器或 CPU 重排序破坏 RCU 语义。

- **Reader Consistency Check（读者一致性检查）**：  
  通过 `rcu_torture_reader_check` 结构在 reader 和 writer 之间传递状态，确保 reader 能及时观察到 writer 的更新，验证 RCU 的“发布-订阅”语义。

### 多种 RCU 使用模式模拟

- **嵌套与扩展读者**：通过 `extendables` 参数，reader 可在 RCU 临界区内进一步调用 `rcu_read_lock_bh()`、`preempt_disable()`、甚至嵌套进入另一个 RCU 读侧，测试复杂嵌套场景。
- **中断上下文读者**：若 `irqreader=1`，部分 reader 会在模拟的中断处理函数中执行 RCU 读操作。
- **指针泄漏测试**：`leakpointer` 参数使 reader 在退出临界区后仍访问已释放指针，用于检测 use-after-free（需配合 KASAN）。

### 异常与压力场景注入

- **CPU Stall**：`stall_task` 会故意在关中断或睡眠状态下长时间占用 CPU，触发 RCU stall 检测。
- **Grace-Period Stall**：`stall_gp_kthread` 模拟 RCU 宽限期线程卡死。
- **Tickless Idle 测试**：`test_no_idle_hz` 验证 RCU 在无时钟滴答的空闲 CPU 上是否仍能正确推进宽限期。
- **OOM 与内存压力**：结合 `vmalloc` 和内存分配，测试 RCU 在低内存条件下的行为。

### 动态配置与模块化

- 通过 `torture_type` 支持多种 RCU 变体（如 `rcu`, `srcu`, `tasks` 等），实际 RCU 操作通过函数指针抽象。
- 所有测试行为均可通过内核模块参数动态调整，无需重新编译。

## 4. 依赖关系

- **核心 RCU 子系统**：依赖 `kernel/rcu/` 下的实现（如 `rcu.h`, `rcupdate.h`, `srcu.h`）。
- **内核基础组件**：
  - 调度器（`sched/`）：用于创建/管理内核线程、`cond_resched()`。
  - 中断与软中断（`irq/`, `softirq.h`）：用于中断上下文测试。
  - CPU 热插拔（`cpu.h`）：用于动态 CPU 启停。
  - 内存管理（`slab.h`, `vmalloc.h`）：用于分配测试对象。
  - 调试设施（`debugobjects.h`, `lockdep.h`）：用于检测双重释放、死锁等。
  - 电源管理（`freezer.h`）：处理系统挂起/恢复。
- **Torture 测试框架**：依赖 `linux/torture.h` 提供的通用测试基础设施（如参数解析、线程管理、统计输出）。
- **追踪与诊断**：使用 `trace_clock.h`、`rcupdate_trace.h`、`nmi.h` 等进行高精度时间戳和 NMI 测试。

## 5. 使用场景

- **RCU 开发与维护**：开发者在修改 RCU 核心代码后，运行 `rcutorture` 验证变更未引入回归。
- **内核 CI/CD 流水线**：作为自动化测试的一部分，在多种架构和配置下持续验证 RCU 稳定性。
- **系统稳定性评估**：在部署前对内核进行长时间压力测试，确保 RCU 在高负载、频繁 CPU 热插拔等场景下可靠。
- **新硬件平台验证**：在新型 CPU 或 NUMA 系统上测试 RCU 的可扩展性和正确性。
- **安全与可靠性研究**：用于探测 RCU 相关的并发漏洞或死锁条件。
- **教学与文档**：作为理解 RCU 语义和边界条件的参考实现（详见 `Documentation/RCU/torture.rst`）。