# rcu\rcuscale.c

> 自动生成时间: 2025-10-25 15:40:25
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rcu\rcuscale.c`

---

# rcu/rcuscale.c 技术文档

## 1. 文件概述

`rcuscale.c` 是 Linux 内核中用于测试 **Read-Copy Update (RCU)** 机制可扩展性（scalability）的模块化压力测试工具。该文件通过创建多个读者线程和写者线程，模拟高并发读写负载，以评估不同 RCU 变体（如经典 RCU、SRCU、Tasks RCU 等）在多核系统下的性能表现和扩展能力。该测试主要用于内核开发和性能调优，属于 `torture` 测试框架的一部分。

## 2. 核心功能

### 主要数据结构

- **`struct rcu_scale_ops`**  
  定义了针对不同 RCU 类型的统一操作接口，包括初始化、清理、读锁/解锁、同步原语、异步回调等函数指针，支持 RCU、SRCU、Tasks RCU 等多种实现。

- **全局控制变量**  
  - `nrealreaders` / `nrealwriters`：实际创建的读者/写者线程数  
  - `writer_tasks` / `reader_tasks`：线程任务结构数组  
  - `writer_durations`：记录每个写者线程的延迟测量数据  
  - `atomic_t` 计数器：用于同步线程启动与结束状态  
  - `scale_type`：指定测试的 RCU 类型（如 "rcu"、"srcu"）

- **模块参数（通过 `torture_param` 定义）**  
  - `nreaders` / `nwriters`：读者/写者线程数量  
  - `gp_async` / `gp_exp`：是否使用异步或加速（expedited）宽限期  
  - `writer_holdoff`：写者间延迟控制  
  - `kfree_rcu_test`：是否测试 `kfree_rcu()` 的可扩展性  
  - `verbose`：是否启用详细日志输出

### 主要函数

- **RCU 操作封装函数**  
  - `rcu_scale_read_lock()` / `rcu_scale_read_unlock()`：封装 `rcu_read_lock/unlock`  
  - `srcu_scale_read_lock()` / `srcu_scale_read_unlock()`：封装 SRCU 读操作  
  - `tasks_scale_read_lock()`：Tasks RCU 无操作占位实现

- **初始化与清理函数**  
  - `rcu_sync_scale_init()`：空初始化（用于经典 RCU）  
  - `srcu_sync_scale_init()` / `srcu_sync_scale_cleanup()`：动态 SRCU 结构初始化与释放

- **日志宏**  
  - `SCALEOUT_STRING()` / `VERBOSE_SCALEOUT_STRING()` / `SCALEOUT_ERRSTRING()`：统一格式化测试输出

## 3. 关键实现

### 可扩展性测试架构

- 采用 **策略模式**：通过 `rcu_scale_ops` 结构体抽象不同 RCU 类型的操作，实现测试逻辑与具体 RCU 实现解耦。
- 支持 **混合负载模式**：根据 `nreaders` 和 `nwriters` 参数组合，可进行纯读、纯写或读写混合压力测试。
- **异步宽限期支持**：通过 `gp_async` 参数启用 `call_rcu()` 异步回调，并限制最大并发请求数（`gp_async_max`），避免资源耗尽。
- **延迟测量机制**：每个写者线程记录宽限期耗时（`writer_durations`），用于后续性能分析。

### 特殊测试模式

- **`kfree_rcu` 可扩展性测试**：通过分配不同大小对象并调用 `kfree_rcu()`（或模拟 `call_rcu()`），评估延迟释放机制在高负载下的表现。
- **SRCU 动态实例支持**：提供静态（`srcu_ctl_scale`）和动态（`srcud`）两种 SRCU 实例，分别对应 `srcu` 和 `srcud` 测试类型。

### 启动与关闭控制

- **启动延迟**：通过 `holdoff` 参数在测试开始前等待系统稳定。
- **自动关机**：若 `shutdown=1`（默认在 built-in 模式下启用），测试结束后触发系统关机，便于自动化测试流程。
- **线程同步**：使用原子计数器和等待队列（`shutdown_wq`）确保所有测试线程正确启动和终止。

## 4. 依赖关系

- **内核子系统依赖**：
  - `RCU 核心机制`：`<linux/rcupdate.h>`、`<linux/srcu.h>`、`<linux/rcupdate_trace.h>`
  - `调度与线程管理`：`<linux/kthread.h>`、`<linux/sched.h>`
  - `内存管理`：`<linux/slab.h>`、`<linux/vmalloc.h>`
  - `同步原语`：`<linux/spinlock.h>`、`<linux/completion.h>`
  - `CPU 热插拔`：`<linux/cpu.h>`
  - `Torture 测试框架`：`<linux/torture.h>`

- **配置依赖**：
  - `CONFIG_TASKS_RCU`：启用 Tasks RCU 测试支持
  - `CONFIG_SRCU`：SRCU 功能必需

## 5. 使用场景

- **内核 RCU 子系统开发**：验证 RCU 实现的可扩展性，特别是在大规模多核系统上的性能表现。
- **性能回归测试**：在内核版本迭代中监控 RCU 相关性能变化。
- **硬件平台评估**：测试不同 CPU 架构（如 x86、ARM64）下 RCU 的扩展效率。
- **参数调优**：通过调整 `writer_holdoff`、`gp_async` 等参数，研究 RCU 行为对系统负载的响应。
- **`kfree_rcu` 压力测试**：评估延迟内存释放机制在高频率分配/释放场景下的稳定性与延迟。