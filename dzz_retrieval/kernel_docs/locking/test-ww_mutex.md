# locking\test-ww_mutex.c

> 自动生成时间: 2025-10-25 14:55:51
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `locking\test-ww_mutex.c`

---

# `locking/test-ww_mutex.c` 技术文档

## 1. 文件概述

`test-ww_mutex.c` 是 Linux 内核中用于测试 **Wound/Wait 互斥锁（ww_mutex）** 机制的模块化单元测试文件。该文件通过模拟多种并发场景（如自锁、ABBA 死锁、循环死锁等），验证 ww_mutex 的正确性、互斥性以及死锁检测与恢复机制是否按预期工作。该测试模块主要用于内核开发和调试阶段，确保 ww_mutex 的实现符合设计规范。

## 2. 核心功能

### 主要数据结构

- `struct test_mutex`  
  用于测试基本互斥行为的结构体，包含工作项、ww_mutex、完成量（completion）和测试标志。

- `struct test_abba`  
  用于模拟 ABBA 死锁场景的结构体，包含两个 ww_mutex、完成量、解析标志、trylock 标志及结果。

- `struct test_cycle`  
  用于测试多线程循环依赖死锁场景的结构体，支持 N 个线程形成环形依赖。

- `ww_class`  
  全局定义的 `ww_class`，用于标识 ww_mutex 所属的锁类，是 ww_mutex 正常工作的必要条件。

### 主要函数

- `test_mutex_work()`  
  工作队列回调函数，执行 ww_mutex 的加锁/尝试加锁操作。

- `__test_mutex()` / `test_mutex()`  
  测试基本互斥语义，覆盖多种标志组合（自旋、trylock、带上下文等）。

- `test_aa()`  
  测试同一上下文对同一 ww_mutex 的重复加锁行为，验证 `-EALREADY` 返回值。

- `test_abba_work()` / `test_abba()`  
  测试经典的 ABBA 死锁场景，支持是否启用死锁解析（resolve）。

- `test_cycle_work()` / `__test_cycle()`  
  测试 N 线程环形依赖死锁，并验证 ww_mutex 的死锁自动解析能力。

## 3. 关键实现

### Wound/Wait 机制测试

- 所有测试均基于 `ww_acquire_ctx` 上下文进行加锁，确保符合 ww_mutex 的使用规范。
- 通过 `ww_mutex_lock()` 和 `ww_mutex_trylock()` 的组合，验证不同加锁路径的行为一致性。

### 死锁检测与解析

- 在 `test_abba()` 和 `__test_cycle()` 中，当检测到 `-EDEADLK` 时，主动调用 `ww_mutex_unlock()` 释放已持有锁，再通过 `ww_mutex_lock_slow()` 重新按顺序获取锁，模拟死锁恢复流程。
- `test_abba()` 支持两种模式：  
  - **不解析**：期望两个线程均返回 `-EDEADLK`；  
  - **解析**：期望死锁被成功解除，返回 0。

### 防止测试干扰

- 使用 `CONFIG_DEBUG_WW_MUTEX_SLOWPATH` 宏控制是否禁用死锁注入（`deadlock_inject_countdown = ~0U`），确保测试结果可复现。
- 所有工作项均使用 `INIT_WORK_ONSTACK` 初始化，并在测试结束时调用 `destroy_work_on_stack()`，避免内存泄漏。

### 超时与同步机制

- 使用 `completion` 机制协调主线程与工作线程的执行顺序。
- 设置 `TIMEOUT = HZ / 16` 作为最大等待时间，防止测试挂起。
- 在 `TEST_MTX_SPIN` 模式下，主动轮询完成状态并调用 `cond_resched()`，避免软死锁。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/ww_mutex.h>`：提供 ww_mutex 核心 API。
  - `<linux/completion.h>`、`<linux/workqueue.h>`：用于线程同步与调度。
  - `<linux/kthread.h>`、`<linux/slab.h>`：支持动态内存分配与内核线程。
  - `<linux/prandom.h>`：虽未直接使用，但为潜在扩展预留。

- **内核配置依赖**：
  - 依赖 `CONFIG_WW_MUTEX` 编译选项。
  - 调试模式下依赖 `CONFIG_DEBUG_WW_MUTEX_SLOWPATH`。

- **运行时依赖**：
  - 使用全局工作队列 `wq`（在文件外初始化），用于并发执行测试任务。

## 5. 使用场景

- **内核开发与回归测试**：在修改 ww_mutex 实现后，运行此模块验证功能正确性。
- **死锁行为验证**：用于确认 ww_mutex 能正确检测并处理 ABBA、循环依赖等复杂死锁。
- **API 兼容性测试**：确保 `ww_mutex_lock`、`ww_mutex_trylock`、`ww_mutex_lock_slow` 等接口行为符合预期。
- **调试辅助**：当系统出现 ww_mutex 相关死锁时，可参考此测试逻辑复现问题。