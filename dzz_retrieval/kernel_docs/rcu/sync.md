# rcu\sync.c

> 自动生成时间: 2025-10-25 15:44:18
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rcu\sync.c`

---

# rcu/sync.c 技术文档

## 文件概述

`rcu/sync.c` 实现了一个基于 RCU（Read-Copy-Update）机制的轻量级读写同步基础设施，称为 `rcu_sync`。该机制允许写者（更新者）在需要时强制所有读者切换到“慢路径”（slow path），并在更新完成后经过一个 RCU 宽限期（grace period）后，允许读者重新使用“快路径”（fast path）。该设计特别适用于需要频繁但短暂地禁用读者快路径的场景，避免了传统读写锁的开销，同时利用 RCU 的无锁读取特性提升性能。

## 核心功能

### 数据结构

- **`struct rcu_sync`**  
  核心同步控制结构，包含以下关键字段：
  - `gp_state`：当前同步状态（`GP_IDLE`, `GP_ENTER`, `GP_PASSED`, `GP_EXIT`, `GP_REPLAY`）
  - `gp_count`：嵌套的 `rcu_sync_enter()` 调用计数
  - `cb_head`：用于 RCU 回调的 `rcu_head`
  - `gp_wait`：等待队列，用于阻塞等待状态转换完成

### 主要函数

| 函数 | 功能描述 |
|------|--------|
| `rcu_sync_init()` | 初始化 `rcu_sync` 结构体 |
| `rcu_sync_enter_start()` | 预激活同步机制，使 `rcu_sync_is_idle()` 返回 false，且后续 enter/exit 成为 NO-OP |
| `rcu_sync_enter()` | 强制读者进入慢路径，确保后续读者不会使用快路径 |
| `rcu_sync_exit()` | 标记更新结束，安排在宽限期后恢复读者快路径 |
| `rcu_sync_dtor()` | 销毁 `rcu_sync` 结构，确保所有 RCU 回调已完成 |
| `rcu_sync_func()` | RCU 回调函数，根据当前状态推进状态机 |

## 关键实现

### 状态机设计

`rcu_sync` 使用五种状态实现高效的状态转换：

- **`GP_IDLE`**：初始状态，读者可使用快路径。
- **`GP_ENTER`**：正在进入同步状态，需等待宽限期。
- **`GP_PASSED`**：宽限期已过，读者已全部进入慢路径。
- **`GP_EXIT`**：正在退出同步，需等待另一个宽限期以恢复快路径。
- **`GP_REPLAY`**：在退出过程中又有新的 enter/exit 对发生，需重新调度回调。

### 嵌套与优化

- **嵌套支持**：通过 `gp_count` 支持 `rcu_sync_enter()` 的嵌套调用。只有当 `gp_count` 从 1 递减到 0 时，才触发退出流程。
- **宽限期合并**：连续的 `enter/exit` 调用可避免多次等待宽限期。例如：
  - 若在 `GP_PASSED` 状态下调用 `exit`，直接进入 `GP_EXIT` 并调度回调。
  - 若在回调执行前再次调用 `enter/exit`，状态转为 `GP_REPLAY`，并在回调中重新调度，避免冗余宽限期。
- **快速路径优化**：首次 `enter` 时若处于 `GP_IDLE`，直接调用 `synchronize_rcu()` 而非异步 `call_rcu()`，可利用 `rcu_expedited` 或 `rcu_blocking_is_gp()` 加速。

### 同步与唤醒

- 写者调用 `rcu_sync_enter()` 后，若非首次进入，会阻塞在 `wait_event()`，直到状态变为 `GP_PASSED` 或更高。
- `rcu_sync_func()` 在宽限期后执行，根据 `gp_count` 和当前状态决定是唤醒等待者、重调度回调，还是恢复到 `GP_IDLE`。

## 依赖关系

- **`<linux/rcu_sync.h>`**：定义 `struct rcu_sync` 及相关 API。
- **`<linux/sched.h>`**：提供 `wait_event()`、`wake_up_locked()` 等调度和等待队列原语。
- **RCU 子系统**：
  - `call_rcu_hurry()` / `call_rcu()`：用于注册宽限期后的回调。
  - `synchronize_rcu()`：用于同步等待宽限期。
  - `rcu_barrier()`：在析构时确保所有回调完成。
- **自旋锁**：使用 `spin_lock_irqsave()` 保护状态和计数器，确保中断上下文安全。

## 使用场景

- **文件系统元数据更新**：如 overlayfs、btrfs 等在修改共享元数据结构时，临时禁止读者使用快路径缓存。
- **动态配置更新**：内核模块或子系统在热更新全局配置时，确保读者看到一致状态。
- **轻量级写者同步**：适用于写操作较少但需高效读者路径的场景，避免传统 rwlock 的读者竞争开销。
- **替代 `synchronize_rcu()` 的批量操作**：当多个连续更新可合并为一次宽限期等待时，提升性能。