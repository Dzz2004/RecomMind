# locking\locktorture.c

> 自动生成时间: 2025-10-25 14:40:37
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `locking\locktorture.c`

---

# `locking/locktorture.c` 技术文档

## 1. 文件概述

`locking/locktorture.c` 是 Linux 内核中的一个模块化压力测试（torture test）设施，用于对各种内核锁机制（如 spinlock、mutex、rwsem、rtmutex 等）进行高强度并发压力测试，以验证其正确性、健壮性和性能。该模块通过创建多个读/写线程，在高竞争、长持有、CPU 热插拔、优先级提升等极端场景下持续操作锁，检测潜在的死锁、竞态条件、内存泄漏或锁实现缺陷。

该文件基于 RCU torture 测试框架（`kernel/rcu/torture.c`）构建，支持多种锁类型，并可通过内核模块参数灵活配置测试行为。

## 2. 核心功能

### 主要数据结构

- **`struct lock_torture_ops`**  
  锁操作抽象接口，定义了针对特定锁类型的初始化、加锁、解锁、延迟、RT 优先级提升等回调函数，支持不同锁机制的统一测试框架。
  
- **`struct lock_torture_cxt`**  
  全局测试上下文，包含当前使用的锁操作集（`cur_ops`）、读者/写者线程数量、错误计数器、统计信息等。

- **`struct lock_stress_stats`**  
  用于记录每个线程的锁获取成功/失败次数，用于性能和正确性分析。

- **`torture_param` 宏定义的模块参数**  
  提供丰富的运行时配置选项，如线程数量、长持有时间、CPU 热插拔间隔、RT 优先级提升策略等。

### 主要函数

- **锁操作实现函数**（按锁类型分类）：
  - `torture_spin_lock_write_lock()` / `torture_spin_lock_write_unlock()`：普通 spinlock 加/解锁。
  - `torture_spin_lock_write_lock_irq()` / `torture_lock_spin_write_unlock_irq()`：带中断保存/恢复的 spinlock。
  - `torture_lock_busted_*`：故意错误的“损坏”锁实现，用于验证测试框架能否检测异常行为。
  - （代码片段未完整展示 mutex、rwsem、rtmutex 等实现，但框架支持）

- **辅助函数**：
  - `torture_lock_busted_write_delay()` / `torture_spin_lock_write_delay()`：模拟真实场景中的锁持有延迟，包括短延迟（微秒级）和偶尔的长延迟（毫秒级），以制造高竞争。
  - `__torture_rt_boost()` / `torture_rt_boost()`：周期性将写线程提升为实时 FIFO 优先级，测试优先级继承（PI）和 RT 锁行为。
  - `lock_torture_cleanup()`：测试结束时的资源清理（前向声明）。

- **全局变量**：
  - `writer_tasks` / `reader_tasks`：指向写/读测试线程的 `task_struct` 指针数组。
  - `lock_is_write_held` / `lock_is_read_held`：用于检测锁状态一致性（如是否允许多个写者同时持有）。
  - `last_lock_release`：记录上次释放锁的时间戳。

## 3. 关键实现

### 锁类型抽象与扩展
通过 `lock_torture_ops` 结构体实现策略模式，不同锁类型只需实现对应的回调函数即可接入测试框架。当前支持：
- `spin_lock`
- `spin_lock_irq`
- （完整代码中还包括 `mutex_lock`, `rwsem`, `rtmutex`, `raw_spin_lock` 等）

默认锁类型根据 `CONFIG_PREEMPT_RT` 配置自动选择：RT 内核使用 `raw_spin_lock`，否则使用 `spin_lock`。

### 高强度压力生成
- **长持有延迟**：通过 `long_hold` 参数控制，偶尔让线程持有锁达数十至数百毫秒，极大增加竞争概率。
- **随机延迟与抢占**：在锁持有期间插入随机微秒级延迟，并调用 `torture_preempt_schedule()` 主动触发抢占，测试锁在抢占式内核下的行为。
- **嵌套锁支持**：通过 `nested_locks` 参数（最大 8 层）测试锁的嵌套使用，避免触发 lockdep 的 `MAX_LOCKDEP_CHAIN_HLOCKS` 限制。

### 实时（RT）行为测试
- **RT 优先级提升**：`rt_boost` 参数控制是否周期性将写线程设为 `SCHED_FIFO` 实时优先级。
  - 模式 1：仅对 `rtmutex` 生效
  - 模式 2：对所有锁类型生效
- **PI（优先级继承）压力**：通过频繁提升/恢复优先级，触发 RT 锁的 PI 机制，验证其正确性。

### 动态环境模拟
- **CPU 热插拔**：通过 `onoff_holdoff` 和 `onoff_interval` 参数，在测试过程中动态上线/下线 CPU，检验锁在 CPU 拓扑变化时的稳定性。
- **测试启停控制**：`stutter` 参数控制测试周期性暂停/恢复，模拟负载波动。

### 错误检测机制
- 使用 `atomic_t n_lock_torture_errors` 全局计数器记录检测到的错误（如违反锁互斥性）。
- 通过 `lock_is_write_held` 和 `atomic_t lock_is_read_held` 检测写锁是否被多个线程同时持有，或读写锁状态不一致。

## 4. 依赖关系

- **内核核心组件**：
  - `<linux/spinlock.h>`、`<linux/mutex.h>`、`<linux/rwsem.h>`、`<linux/rtmutex.h>`：提供被测试的锁原语。
  - `<linux/kthread.h>`、`<linux/sched.h>`：用于创建和管理测试线程。
  - `<linux/torture.h>`：提供通用 torture 测试框架（如随机数生成、线程控制、参数解析等）。
  - `<linux/atomic.h>`、`<linux/delay.h>`：用于同步和延迟操作。
- **配置依赖**：
  - `CONFIG_PREEMPT_RT`：影响默认锁类型选择。
  - `CONFIG_LOCKDEP`：嵌套锁深度受其 `MAX_LOCKDEP_CHAIN_HLOCKS` 限制。
- **模块参数系统**：通过 `module_param` 和 `torture_param` 宏集成内核模块参数机制。

## 5. 使用场景

- **内核开发与测试**：
  - 在开发新的锁实现或修改现有锁机制时，运行此模块进行回归测试。
  - 在合并关键锁相关补丁前，通过长时间 torture 测试验证稳定性。
- **实时系统验证**：
  - 在 PREEMPT_RT 补丁集开发中，重点测试 `rtmutex` 和优先级继承行为。
  - 验证系统在高优先级线程竞争锁时的响应性和正确性。
- **硬件/平台压力测试**：
  - 在新硬件平台或 NUMA 系统上运行，检测锁在复杂拓扑下的可扩展性和正确性。
  - 结合 CPU 热插拔测试，验证锁在动态 CPU 环境下的鲁棒性。
- **故障复现与调试**：
  - 当怀疑存在锁相关的死锁或竞态条件时，通过配置特定参数（如高 `long_hold`、高线程数）复现问题。
  - 利用 `verbose` 参数输出详细日志辅助调试。