# async.c

> 自动生成时间: 2025-10-25 11:49:14
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `async.c`

---

# async.c 技术文档

## 1. 文件概述

`async.c` 实现了 Linux 内核中的异步函数调用机制，主要用于优化系统启动性能。该机制允许在内核初始化阶段将原本串行执行的、相互独立的硬件探测和初始化操作并行化，从而显著缩短启动时间。其核心思想是在保持对外可见操作顺序一致性的前提下，内部执行过程可乱序进行，类似于乱序执行 CPU 的“按序提交”语义。

## 2. 核心功能

### 主要数据结构

- **`struct async_entry`**：表示一个异步任务条目，包含：
  - `domain_list` / `global_list`：分别链接到所属域和全局的待处理链表
  - `work`：关联的 workqueue 工作项
  - `cookie`：序列号，用于同步控制
  - `func` / `data`：要执行的函数及其参数
  - `domain`：所属的异步域

- **`struct async_domain`**：异步执行域，用于将异步任务分组管理，默认使用 `async_dfl_domain`

- **全局变量**：
  - `next_cookie`：单调递增的序列号生成器
  - `async_global_pending`：所有已注册域的全局待处理任务链表
  - `async_dfl_domain`：默认异步域
  - `async_lock`：保护异步任务队列的自旋锁
  - `entry_count`：当前挂起的异步任务计数

### 主要函数

- **`async_schedule_node_domain()`**：在指定 NUMA 节点和异步域中调度异步函数
- **`async_schedule_node()`**：在指定 NUMA 节点上调度异步函数（使用默认域）
- **`async_schedule_dev_nocall()`**：基于设备的 NUMA 信息调度异步函数（失败时不回退到同步执行）
- **`lowest_in_progress()`**：获取指定域或全局中最早（最小 cookie）的未完成任务
- **`async_run_entry_fn()`**：workqueue 回调函数，实际执行异步任务并清理资源

## 3. 关键实现

### 序列 Cookie 机制
- 每个异步任务分配一个单调递增的 `async_cookie_t`（64 位无符号整数）
- 任务执行前可通过 `async_synchronize_cookie()` 等待所有小于等于指定 cookie 的任务完成
- 保证对外部可见操作（如设备注册）的顺序一致性

### 内存与负载控制
- 使用 `GFP_ATOMIC` 分配内存，支持原子上下文调用
- 当内存不足或挂起任务超过 `MAX_WORK`（32768）时，自动回退到同步执行
- 通过 `entry_count` 原子计数器跟踪挂起任务数量

### 双链表管理
- 每个任务同时链接到：
  - 所属域的 `domain->pending` 链表（按 cookie 顺序）
  - 全局 `async_global_pending` 链表（仅当域已注册）
- 保证域内和全局的同步操作都能正确等待

### NUMA 感知调度
- 通过 `queue_work_node()` 将任务调度到指定 NUMA 节点
- 若节点无效则自动分发到可用 CPU

### 资源清理与通知
- 任务执行完成后从链表移除并释放内存
- 通过 `wake_up(&async_done)` 唤醒等待同步完成的线程

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/async.h>`：异步 API 定义
  - `<linux/workqueue.h>`：工作队列机制
  - `"workqueue_internal.h"`：内部 workqueue 接口
  - 其他基础内核头文件（atomic、slab、wait 等）

- **核心子系统**：
  - **Workqueue 子系统**：实际执行异步任务的底层机制
  - **内存管理子系统**：任务结构体内存分配
  - **调度器**：NUMA 节点感知的任务调度

- **导出符号**：
  - `async_schedule_node_domain`
  - `async_schedule_node`

## 5. 使用场景

- **内核启动优化**：
  - 并行执行设备探测（如 PCI、USB 控制器初始化）
  - 异步加载固件或执行硬件自检

- **驱动初始化**：
  - 驱动可将耗时的初始化操作（如 PHY 配置、固件加载）放入异步任务
  - 通过 `async_synchronize_full()` 确保在模块初始化完成前所有异步任务结束

- **NUMA 优化**：
  - 将设备相关的初始化任务调度到设备所在 NUMA 节点，减少远程内存访问

- **资源受限环境**：
  - 在内存压力下自动回退到同步执行，保证系统稳定性
  - 通过 `MAX_WORK` 限制防止异步任务无限堆积