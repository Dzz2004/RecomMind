# rcu\tiny.c

> 自动生成时间: 2025-10-25 15:45:52
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rcu\tiny.c`

---

# `rcu/tiny.c` 技术文档

## 1. 文件概述

`rcu/tiny.c` 是 Linux 内核中 **RCU（Read-Copy Update）机制的“精简版”（Tiny RCU）实现**，专为单处理器（UP）或资源受限系统（如嵌入式设备）设计。该实现去除了复杂的状态机、CPU 间通信和动态负载均衡等开销，仅保留 RCU 的核心语义：**在读端无锁、写端延迟回收**。由于系统只有一个 CPU，任何上下文切换或中断返回用户态都天然构成“宽限期”（Grace Period），因此无需复杂的跨 CPU 同步逻辑。

## 2. 核心功能

### 主要数据结构

- **`struct rcu_ctrlblk`**：RCU 控制块，全局唯一，用于管理回调链表和宽限期状态。
  - `rcucblist`：待处理的 RCU 回调链表头。
  - `donetail`：指向最后一个已完成宽限期的回调的 `next` 指针。
  - `curtail`：指向链表最后一个回调的 `next` 指针。
  - `gp_seq`：宽限期序列号，每次宽限期结束递增 2（偶数表示完成状态）。

### 主要函数

| 函数 | 功能说明 |
|------|--------|
| `rcu_qs(void)` | 记录当前 CPU 的静默状态（Quiescent State），推进已完成回调指针并触发软中断处理回调。 |
| `rcu_sched_clock_irq(int user)` | 调度时钟中断处理函数，若处于用户态则调用 `rcu_qs()`；否则标记当前任务需重新调度以尽快进入静默状态。 |
| `call_rcu(struct rcu_head *head, rcu_callback_t func)` | 注册一个 RCU 回调，在下一个宽限期结束后执行。 |
| `synchronize_rcu(void)` | 等待当前宽限期结束（在 UP 系统中立即完成，仅更新 `gp_seq`）。 |
| `rcu_process_callbacks(struct softirq_action *unused)` | RCU 软中断处理函数，批量执行已完成宽限期的回调。 |
| `rcu_barrier(void)` | 等待所有已注册的 RCU 回调执行完毕。 |
| `get_state_synchronize_rcu()` / `start_poll_synchronize_rcu()` / `poll_state_synchronize_rcu()` | 支持轮询式宽限期检测的 API。 |
| `rcu_init(void)` | RCU 子系统初始化，注册 RCU 软中断处理函数。 |

## 3. 关键实现

### 宽限期管理
- **单 CPU 假设**：由于系统只有一个 CPU，任何从内核态返回用户态、发生上下文切换或空闲任务运行，都视为一个完整的宽限期。
- **`gp_seq` 计数器**：初始值为 `0 - 300UL`（负数，确保早期调用 `get_state_synchronize_rcu()` 返回有效值）。每次调用 `rcu_qs()` 或 `synchronize_rcu()` 时递增 2，偶数值表示宽限期已完成。
- **无实际等待**：`synchronize_rcu()` 不阻塞，仅更新 `gp_seq`，因为调用者本身已处于静默状态。

### 回调队列管理
- **双指针链表**：使用 `donetail` 和 `curtail` 实现无锁（在中断禁用下）的回调入队和出队。
  - 新回调通过 `curtail` 追加到链表尾部。
  - `rcu_qs()` 将 `donetail` 移至 `curtail`，表示此前所有回调已完成宽限期。
  - 软中断 `rcu_process_callbacks()` 将 `donetail` 之前的所有回调移出并执行。

### 回调执行
- **软中断上下文**：回调在 `RCU_SOFTIRQ` 中执行，确保不在原子上下文。
- **支持 `kvfree`**：通过 `__is_kvfree_rcu_offset` 判断是否为 `kvfree_rcu` 回调，若是则直接释放内存而非调用函数指针。
- **调试支持**：包含双释放检测（`debug_rcu_head_queue`）和内存泄漏防护（`tiny_rcu_leak_callback`）。

### 轮询 API 实现
- `get_state_synchronize_rcu()` 返回当前 `gp_seq`。
- `poll_state_synchronize_rcu(oldstate)` 判断 `oldstate` 是否已完成：若 `oldstate == RCU_GET_STATE_COMPLETED`（特殊值）或当前 `gp_seq != oldstate`，则返回 `true`。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/rcupdate_wait.h>`：提供 `wait_rcu_gp()` 实现 `rcu_barrier()`。
  - `"rcu.h"`：RCU 内部头文件，定义调试宏、trace 点等。
  - 其他通用内核头文件（如 `sched.h`, `softirq.h`, `slab.h` 等）。
- **内核配置**：
  - 仅在 `CONFIG_TINY_RCU` 或 `CONFIG_TINY_SRCU` 启用时编译。
  - 与 `CONFIG_PREEMPT`、`CONFIG_SMP` 互斥（Tiny RCU 用于非抢占式 UP 系统）。
- **软中断子系统**：依赖 `open_softirq()` 注册 `RCU_SOFTIRQ`。
- **内存管理**：`kvfree_call_rcu()` 依赖 KASAN 的辅助栈记录（`CONFIG_KASAN_GENERIC`）。

## 5. 使用场景

- **单处理器嵌入式系统**：资源受限设备（如 IoT 设备、微控制器）中替代 Tree RCU，显著减少代码体积和运行时开销。
- **内核测试与调试**：作为 RCU 行为的简化模型，用于验证 RCU 语义正确性。
- **RCU 基础功能提供**：
  - 为内核其他子系统（如网络、文件系统、设备驱动）提供 `call_rcu()` 和 `synchronize_rcu()` 接口。
  - 支持延迟内存回收（如 `kfree_rcu()`）。
  - 通过 `rcu_barrier()` 确保模块卸载前所有回调完成。
- **轮询式同步**：适用于不能阻塞的上下文（如中断处理程序），通过 `poll_state_synchronize_rcu()` 轮询宽限期状态。