# module\dups.c

> 自动生成时间: 2025-10-25 15:00:29
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `module\dups.c`

---

# `module/dups.c` 技术文档

## 1. 文件概述

`module/dups.c` 实现了 Linux 内核模块自动加载（`request_module()`）过程中的**重复请求抑制机制**。该机制旨在防止多个并发线程对同一模块发起重复的自动加载请求，从而避免不必要的用户空间 `modprobe` 调用、减少 `vmalloc()` 内存碎片，并优化系统启动或模块加载期间的性能。

该功能通过维护一个受互斥锁保护的重复请求跟踪列表，对首次请求进行记录，并让后续重复请求等待首个请求的结果，最终共享其返回值，从而实现去重与同步。

## 2. 核心功能

### 主要数据结构

- **`struct kmod_dup_req`**  
  表示一个模块加载请求的跟踪条目，包含：
  - `list`：链表节点，用于加入全局 `dup_kmod_reqs` 列表
  - `name[MODULE_NAME_LEN]`：模块名称
  - `first_req_done`：完成量（`completion`），用于通知等待者首个请求已完成
  - `complete_work`：工作队列项，用于异步完成所有等待者的通知
  - `delete_work`：延迟工作队列项，用于在请求完成后一段时间（60秒）自动清理条目
  - `dup_ret`：首个请求的返回值，供后续重复请求复用

### 主要函数

- **`kmod_dup_request_lookup(char *module_name)`**  
  在 `dup_kmod_reqs` 列表中查找是否存在指定模块名的请求条目（需持有 `kmod_dup_mutex` 锁）。

- **`kmod_dup_request_delete(struct work_struct *work)`**  
  延迟工作回调函数，从列表中安全删除请求条目并释放内存（使用 RCU 同步）。

- **`kmod_dup_request_complete(struct work_struct *work)`**  
  工作队列回调函数，调用 `complete_all()` 唤醒所有等待该模块加载完成的线程，并调度延迟删除。

- **`kmod_dup_request_exists_wait(char *module_name, bool wait, int *dup_ret)`**  
  **核心入口函数**。检查是否存在对 `module_name` 的重复请求：
  - 若不存在且当前为 `request_module()`（`wait == true`），则创建新条目并返回 `false`（表示非重复）。
  - 若为 `request_module_nowait()`（`wait == false`）且无现有条目，则不跟踪，返回 `false`。
  - 若存在重复请求：
    - 对 `nowait` 请求，直接返回成功（`*dup_ret = 0`）。
    - 对 `wait` 请求，等待首个请求完成并复用其返回值。
  - 若启用 `enable_dups_trace`，对重复请求触发 `WARN()` 警告。

- **`kmod_dup_request_announce(char *module_name, int ret)`**  
  由首个请求的调用者在 `request_module()` 返回后调用，用于记录返回值 `ret` 并触发完成通知（通过工作队列异步执行）。

### 模块参数

- **`module.enable_dups_trace`**（布尔型，只读写 `true`）  
  控制是否对重复请求使用 `WARN()`（否则仅 `pr_warn`）。默认值由 `CONFIG_MODULE_DEBUG_AUTOLOAD_DUPS_TRACE` 决定。

## 3. 关键实现

### 重复请求检测与同步机制

1. **首次请求处理**：
   - `request_module()`（`wait=true`）调用 `kmod_dup_request_exists_wait()`。
   - 若无重复条目，则分配 `kmod_dup_req` 并加入全局列表，返回 `false`，继续执行用户空间加载。
   - `request_module_nowait()`（`wait=false`）若为首个请求，则不创建条目，直接返回 `false`（不参与去重）。

2. **重复请求处理**：
   - 后续相同模块名的请求命中已有条目。
   - `nowait` 请求立即返回成功（`0`）。
   - `wait` 请求调用 `wait_for_completion_state()` 等待首个请求完成。

3. **结果广播与清理**：
   - 首个请求完成后调用 `kmod_dup_request_announce()`，记录返回值并调度 `complete_work`。
   - `complete_work` 调用 `complete_all()` 唤醒所有等待者。
   - 随后调度 `delete_work`，60 秒后自动清理条目（避免内存泄漏，同时容忍短暂窗口内的新请求）。

### 并发与内存安全

- **互斥锁保护**：`kmod_dup_mutex` 保护列表的增删操作。
- **RCU 读取**：`kmod_dup_request_lookup()` 使用 `list_for_each_entry_rcu()`，允许无锁读取（需持有锁或处于 RCU 读侧临界区）。
- **延迟删除**：通过 `synchronize_rcu()` 确保所有读者完成后再释放内存。
- **预分配优化**：在获取锁前预分配 `new_kmod_req`，减少锁持有时间。

### 设计权衡

- **不跟踪 `nowait` 首请求**：因无法提供有效返回值给后续 `wait` 请求。
- **容忍短暂重复窗口**：删除条目前允许新请求直接调用 `modprobe`（仅返回 0），认为这是用户空间的责任。
- **异步完成通知**：避免在 `kmod_dup_request_announce()` 中阻塞首个请求的调用路径。

## 4. 依赖关系

- **内部头文件**：`#include "internal.h"`（模块子系统内部接口）
- **内核核心组件**：
  - `linux/kmod.h`：`request_module()` 相关接口
  - `linux/completion.h`：完成量同步原语
  - `linux/workqueue.h`：工作队列机制
  - `linux/rcupdate.h`（隐式）：RCU 同步
  - `linux/mutex.h`：互斥锁
  - `linux/slab.h`：内存分配
- **配置依赖**：`CONFIG_MODULE_DEBUG_AUTOLOAD_DUPS_TRACE` 控制调试行为

## 5. 使用场景

- **内核模块自动加载**：当多个子系统（如设备驱动、文件系统、网络协议）几乎同时尝试通过 `request_module()` 加载同一模块时，避免多次调用用户空间 `modprobe`。
- **系统启动优化**：在初始化阶段减少因模块重复加载导致的 `vmalloc()` 内存碎片和不必要的上下文切换。
- **防止滥用**：检测并警告开发人员对 `request_module()` 的低效重复调用，鼓励使用 `try_then_request_module()` 或集中加载策略。
- **异步加载兼容**：支持 `request_module_nowait()` 与 `request_module()` 混合调用场景下的合理去重。