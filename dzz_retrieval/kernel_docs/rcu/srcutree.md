# rcu\srcutree.c

> 自动生成时间: 2025-10-25 15:43:41
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rcu\srcutree.c`

---

# `rcu/srcutree.c` 技术文档

## 1. 文件概述

`rcu/srcutree.c` 是 Linux 内核中 **Sleepable Read-Copy Update (SRCU)** 机制的核心实现文件之一。SRCU 是 RCU（Read-Copy Update）的一种变体，专为**允许在读端临界区内睡眠**的场景设计，适用于需要在持有读锁时执行可能阻塞操作（如内存分配、文件 I/O 等）的子系统。

该文件主要负责 SRCU 结构体的动态初始化、层级树（combining tree）构建、每 CPU 数据结构管理，以及与宽限期（grace period）和回调处理相关的底层支持逻辑。它实现了可扩展的、基于树状结构的 SRCU，以支持大规模多核系统下的高效同步。

## 2. 核心功能

### 主要数据结构
- `struct srcu_struct`：SRCU 同步域的顶层结构，用户通过它调用 `srcu_read_lock()`、`synchronize_srcu()` 等接口。
- `struct srcu_data`：每 CPU 数据结构，用于记录本地读端计数、回调链表、宽限期状态等。
- `struct srcu_node`：SRCU 树的内部节点，用于聚合子节点的宽限期完成状态，减少全局同步开销。
- `struct srcu_usage`（通过 `ssp->srcu_sup` 指向）：包含 SRCU 实例的共享元数据，如互斥锁、树节点指针、大小状态等。

### 主要函数
- `init_srcu_struct_data()`：初始化 `srcu_struct` 的每 CPU `srcu_data` 实例。
- `init_srcu_struct_nodes()`：动态分配并初始化 SRCU 的层级树（`srcu_node` 数组），建立父子关系和 CPU 覆盖范围。
- `init_srcu_struct_fields()`：初始化 `srcu_struct` 的非静态字段，包括分配 `srcu_usage` 结构、初始化互斥锁等。
- `srcu_invoke_callbacks()` / `srcu_reschedule()` / `process_srcu()` / `srcu_delay_timer()`：回调处理与延迟调度相关的工作队列和定时器函数（部分在代码片段中声明但未完整定义）。

### 关键宏定义
- `spin_lock_rcu_node()` 等系列宏：封装对 `srcu_node` 或 `srcu_data` 中自旋锁的安全访问，并插入必要的内存屏障（`smp_mb__after_unlock_lock()`）。
- `SRCU_SIZING_*` 系列常量与宏：控制 SRCU 实例是否从“小模式”（无树结构）动态转换为“大模式”（带树结构）的策略。

## 3. 关键实现

### 动态树结构初始化
- `init_srcu_struct_nodes()` 根据系统 CPU 数量和 RCU 几何配置（`rcu_num_lvls`, `num_rcu_lvl`, `levelspread`）动态构建多层 `srcu_node` 树。
- 叶子层（`level = rcu_num_lvls - 1`）的每个 `srcu_node` 覆盖若干 CPU，每个 CPU 的 `srcu_data->mynode` 指向其对应的叶子节点。
- 通过 `grplo`/`grphi` 字段记录每个 `srcu_node` 所覆盖的 CPU 范围，`grpmask` 表示该 CPU 在其叶子节点中的位掩码。
- 初始化时，所有 `srcu_have_cbs[]` 和 `srcu_gp_seq_needed_exp` 被设为特殊值 `SRCU_SNP_INIT_SEQ`（`0x2`），表示无效状态，避免早期误判。

### 大小模式转换策略（SRCU Size Scaling）
- 支持从轻量级“小模式”（仅每 CPU 计数器）动态升级到可扩展“大模式”（带树结构），以平衡小系统开销与大系统可扩展性。
- 通过模块参数 `convert_to_big` 控制转换策略：
  - `0`：永不转换；
  - `1`：在 `init_srcu_struct()` 时立即转换；
  - `2`：由 `rcutorture` 测试触发；
  - `3`（默认）：根据系统 CPU 数量（`big_cpu_lim=128`）自动决定；
  - `0x1x`：在检测到高锁争用（`small_contention_lim=100` 次/每 jiffy）时转换。
- `srcu_size_state` 字段跟踪当前模式状态（如 `SRCU_SIZE_SMALL`, `SRCU_SIZE_WAIT_BARRIER`）。

### 安全锁封装与内存序
- 所有对 `srcu_node` 和 `srcu_data` 中自旋锁的操作均通过宏封装（如 `spin_lock_rcu_node()`）。
- 这些宏在获取锁后调用 `smp_mb__after_unlock_lock()`，确保后续内存访问不会被重排到锁获取之前，满足 RCU 对内存顺序的严格要求。

### 早期启动支持
- 使用 `srcu_boot_list` 链表和 `srcu_init_done` 标志支持在内核早期启动阶段（尚无锁机制）注册 SRCU 结构，待初始化完成后批量处理。

## 4. 依赖关系

- **内部依赖**：
  - `rcu.h`：RCU 通用头文件，包含几何配置（`rcu_num_lvls` 等）和辅助宏。
  - `rcu_segcblist.h`：提供分段回调链表（`rcu_segcblist`）实现，用于管理 SRCU 回调。
- **内核子系统依赖**：
  - `<linux/rcupdate_wait.h>`：提供宽限期等待基础设施。
  - `<linux/smp.h>` / `<linux/preempt.h>`：SMP 和抢占控制原语。
  - `<linux/workqueue.h>` / `<linux/timer.h>`：用于回调延迟处理（通过 `work_struct` 和 `timer_list`）。
  - `<linux/slab.h>`：动态内存分配（`kzalloc`, `kcalloc`）。
- **用户**：被需要睡眠读端的子系统使用，如设备驱动、文件系统（如 Btrfs）、虚拟化（KVM）等。

## 5. 使用场景

- **需要在 RCU 读端临界区内睡眠的场景**：标准 RCU 禁止在 `rcu_read_lock()`/`rcu_read_unlock()` 之间睡眠，而 SRCU 允许。
- **高并发读端 + 低频同步**：适用于读操作远多于写操作（调用 `synchronize_srcu()`）的场景，如配置更新、模块卸载检查。
- **大规模 NUMA 系统**：通过树状结构减少宽限期同步的全局开销，提升可扩展性。
- **动态资源管理**：如内核模块动态创建/销毁 SRCU 域，或子系统根据负载自动调整同步策略（通过大小模式转换）。