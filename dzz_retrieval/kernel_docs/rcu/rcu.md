# rcu\rcu.h

> 自动生成时间: 2025-10-25 15:38:58
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rcu\rcu.h`

---

# `rcu/rcu.h` 技术文档

## 1. 文件概述

`rcu/rcu.h` 是 Linux 内核中 RCU（Read-Copy Update）机制的核心头文件之一，定义了多个 RCU 实现（如 TREE_RCU、SRCU、 polled RCU 等）共享的通用数据结构、宏和内联函数。该文件主要负责 **grace-period（宽限期）序列号的管理逻辑**，通过将序列号的低两位用作状态标志、高位用作计数器，实现对 RCU 宽限期生命周期的精确跟踪和同步控制。

## 2. 核心功能

### 主要宏定义
- `RCU_SEQ_CTR_SHIFT`：序列号中计数器部分的偏移位（值为 2）。
- `RCU_SEQ_STATE_MASK`：低 2 位掩码，用于提取状态标志。
- `RCU_GET_STATE_COMPLETED`：用于 polled RCU 的特殊完成状态值（0x1）。
- `SRCU_SNP_INIT_SEQ` / `SRCU_STATE_IDLE` / `SRCU_STATE_SCAN1` / `SRCU_STATE_SCAN2`：SRCU 特定的状态值（注释中定义，实际值在其他文件中）。

### 主要内联函数
- **序列号解析**：
  - `rcu_seq_ctr()`：提取序列号中的计数器部分。
  - `rcu_seq_state()`：提取序列号中的状态标志部分。
- **序列号更新**：
  - `rcu_seq_set_state()`：设置序列号的状态位。
  - `rcu_seq_start()`：标记宽限期开始。
  - `rcu_seq_end()`：标记宽限期结束。
  - `rcu_seq_endval()`：计算宽限期结束时的目标序列号。
- **快照与判断**：
  - `rcu_seq_snap()`：获取一个“安全快照”，用于判断未来何时宽限期完成。
  - `rcu_seq_current()`：获取当前序列号（无内存屏障）。
  - `rcu_seq_started()`：判断对应操作是否已开始。
  - `rcu_seq_done()` / `rcu_seq_done_exact()`：判断宽限期是否已完成。
  - `rcu_seq_completed_gp()`：判断自旧序列号以来是否已完成至少一个宽限期。
  - `rcu_seq_new_gp()`：判断自旧序列号以来是否有新宽限期开始。
  - `rcu_seq_diff()`：估算两个序列号之间经过的完整宽限期数量。
- **调试支持**：
  - `debug_rcu_head_queue()` / `debug_rcu_head_unqueue()`：在启用 `CONFIG_DEBUG_OBJECTS_RCU_HEAD` 时，用于调试 RCU 回调对象的状态转换。
  - `debug_rcu_head_callback()`：检查 RCU 回调函数指针是否为空，若为空则打印对象信息用于调试。
- **启动抑制**：
  - `rcu_stall_is_suppressed_at_boot()`：判断是否在启动阶段抑制 RCU CPU 停滞检测。

### 全局变量声明
- `sysctl_sched_rt_runtime`：外部声明，与调度器相关（此处仅为引用）。
- `rcu_cpu_stall_suppress_at_boot`：控制启动期间是否抑制 RCU 停滞警告。

## 3. 关键实现

### Grace-Period 序列号编码
序列号 `unsigned long s` 被划分为两部分：
- **高 `(sizeof(long)*8 - 2)` 位**：宽限期计数器（每次完整宽限期结束后递增）。
- **低 2 位**：状态标志，用于表示宽限期的当前阶段：
  - `00`：无宽限期进行中（空闲）。
  - 非零（如 `01` 或 `10`）：宽限期正在进行中。

### 宽限期生命周期管理
- **开始**：`rcu_seq_start()` 将序列号加 1，使状态变为 `01`，并插入写内存屏障确保后续更新操作在计数器递增之后。
- **结束**：`rcu_seq_end()` 先插入读内存屏障确保之前更新完成，然后将序列号设置为 `(当前值 | 0x3) + 1`，即清除状态位并递增计数器。

### 快照机制 (`rcu_seq_snap`)
该函数返回一个“未来安全值”：
```c
s = (当前序列号 + 2*RCU_SEQ_STATE_MASK + 1) & ~RCU_SEQ_STATE_MASK;
```
此值确保：当实际序列号 ≥ `s` 时，至少有一个完整的宽限期已覆盖调用 `rcu_seq_snap()` 之后的所有读端临界区。

### 宽限期完成判断
- `rcu_seq_done(sp, s)`：若当前序列号 ≥ 快照值 `s`，则认为宽限期已完成。
- `rcu_seq_done_exact()`：在不考虑 `ULONG_MAX/2` 安全裕度的情况下进行精确判断，用于特定场景。

### 宽限期差异计算 (`rcu_seq_diff`)
通过位运算估算两个序列号之间经过的完整宽限期数量，考虑了状态位的影响，并保证最小返回值为 1（若确实未经过完整宽限期）。

### 调试对象支持
当启用 `CONFIG_DEBUG_OBJECTS_RCU_HEAD` 时，通过 `debug_obj` 框架跟踪 `struct rcu_head` 对象的状态（`READY` ↔ `QUEUED`），防止重复入队或非法释放。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/slab.h>`：用于 `kmem_dump_obj()`（调试回调函数为空时打印对象信息）。
  - `<trace/events/rcu.h>`：RCU 相关的 tracepoint 定义（尽管本文件未直接使用，但为一致性包含）。
- **配置依赖**：
  - `CONFIG_DEBUG_OBJECTS_RCU_HEAD`：启用 RCU 回调对象的调试跟踪。
- **外部符号**：
  - `rcuhead_debug_descr`：调试对象描述符（定义在 `rcupdate.c`）。
  - `rcu_cpu_stall_suppress_at_boot`：全局变量（定义在 RCU 主实现文件中）。

## 5. 使用场景

- **所有 RCU 实现共享**：TREE_RCU、TINY_RCU、SRCU、Tasks RCU 等均使用本文件提供的序列号管理原语。
- **宽限期跟踪**：RCU 核心代码使用 `rcu_seq_start()`/`rcu_seq_end()` 标记宽限期边界，使用 `rcu_seq_snap()` 获取读者安全点。
- **回调调度判断**：`call_rcu()` 及其变体使用 `rcu_seq_done()` 判断是否可安全执行回调。
- **调试与诊断**：
  - 启用 `CONFIG_DEBUG_OBJECTS` 时，防止 RCU 回调对象的误用。
  - 启动阶段通过 `rcu_stall_is_suppressed_at_boot()` 避免误报 CPU 停滞。
- **Polled RCU 支持**：`RCU_GET_STATE_COMPLETED` 用于 `get_state_synchronize_rcu()` / `poll_state_synchronize_rcu()` 等轮询 API。