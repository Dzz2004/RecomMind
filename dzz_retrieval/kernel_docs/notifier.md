# notifier.c

> 自动生成时间: 2025-10-25 15:11:27
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `notifier.c`

---

# notifier.c 技术文档

## 1. 文件概述

`notifier.c` 是 Linux 内核中实现通知链（notifier chain）机制的核心文件。通知链是一种回调机制，允许内核子系统在特定事件发生时（如系统关机、硬件状态变化等）注册回调函数并被依次调用。该文件提供了原子通知链（atomic notifier chain）和阻塞通知链（blocking notifier chain）的通用注册、注销和调用逻辑，并定义了系统关机时使用的 `reboot_notifier_list`。

## 2. 核心功能

### 主要数据结构
- `struct notifier_block`：通知回调的基本单元，包含回调函数指针 `notifier_call`、优先级 `priority` 和下一个节点指针 `next`。
- `struct atomic_notifier_head`：原子通知链头结构，包含自旋锁 `lock` 和链表头 `head`。
- `struct blocking_notifier_head`：阻塞通知链头结构，包含读写信号量 `rwsem` 和链表头 `head`。
- `reboot_notifier_list`：全局阻塞通知链，用于系统关机/重启时通知各子系统。

### 主要函数
- **通用内部函数**：
  - `notifier_chain_register()`：将通知块插入链表（按优先级排序）。
  - `notifier_chain_unregister()`：从链表中移除指定通知块。
  - `notifier_call_chain()`：遍历并调用通知链中的回调函数。
  - `notifier_call_chain_robust()`：支持错误回滚的通知调用（先 `val_up`，失败则 `val_down`）。

- **原子通知链接口（导出）**：
  - `atomic_notifier_chain_register()`
  - `atomic_notifier_chain_register_unique_prio()`
  - `atomic_notifier_chain_unregister()`
  - `atomic_notifier_call_chain()`
  - `atomic_notifier_call_chain_is_empty()`

- **阻塞通知链接口（部分在文件后续定义）**：
  - `__blocking_notifier_chain_register()`（内部辅助函数）

## 3. 关键实现

### 通知链注册逻辑
- 通知块按 `priority` 字段**降序插入**链表（高优先级在前）。
- `notifier_chain_register()` 支持 `unique_priority` 模式：若启用，则不允许相同优先级的多个通知块共存（返回 `-EBUSY`）。
- 使用 `rcu_assign_pointer()` 安全地更新指针，确保 RCU 读端可见性。
- 重复注册同一回调函数会触发 `WARN()` 并返回 `-EEXIST`。

### 通知调用机制
- `notifier_call_chain()` 遍历链表，依次调用每个 `notifier_call` 回调。
- 若回调返回值包含 `NOTIFY_STOP_MASK`（如 `NOTIFY_STOP` 或 `NOTIFY_BAD`），则立即终止调用。
- 支持限制调用数量（`nr_to_call`）和记录已调用数量（`nr_calls`）。
- 在 `CONFIG_DEBUG_NOTIFIERS` 启用时，会验证回调函数地址是否在内核代码段，防止非法调用。

### 同步机制
- **原子通知链**：注册/注销使用 `spinlock`（`spin_lock_irqsave`），调用使用 `rcu_read_lock()`，适用于中断上下文。
- **阻塞通知链**：注册/注销使用 `rwsem`（读写信号量），但**在系统启动阶段**（`SYSTEM_BOOTING`）会绕过锁，直接调用底层注册函数以避免死锁。
- 注销原子通知块后调用 `synchronize_rcu()` 确保所有读者完成。

### 回滚机制
- `notifier_call_chain_robust()` 先尝试 `val_up` 事件，若中途失败（返回 `NOTIFY_STOP_MASK`），则反向调用前 `nr-1` 个回调并传入 `val_down` 事件，实现资源回滚。

### 跟踪点支持
- 通过 `trace/events/notifier.h` 定义了三个跟踪点：
  - `notifier_register`：注册时触发
  - `notifier_unregister`：注销时触发  
  - `notifier_run`：调用回调时触发

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/notifier.h>`：定义通知链核心数据结构和宏（如 `BLOCKING_NOTIFIER_HEAD`）
  - `<linux/rcupdate.h>`：提供 RCU 同步原语（`rcu_assign_pointer`, `rcu_dereference_raw` 等）
  - `<linux/spinlock.h>` / `<linux/rwsem.h>`：通过 `notifier.h` 间接依赖，用于同步
  - `<linux/tracepoint.h>`：通过 `trace/events/notifier.h` 实现跟踪点
  - `<linux/kdebug.h>`：提供 `func_ptr_is_kernel_text()` 用于调试验证
  - `<linux/reboot.h>`：声明 `reboot_notifier_list` 的外部使用者

- **导出符号**：
  - 所有 `atomic_notifier_*` 函数通过 `EXPORT_SYMBOL_GPL` 导出，供其他内核模块使用。

- **架构约束**：
  - `notifier_call_chain` 和 `atomic_notifier_call_chain` 标记为 `NOKPROBE_SYMBOL`，禁止 kprobes 插桩，确保关键路径稳定性。

## 5. 使用场景

- **系统关机/重启**：`reboot_notifier_list` 被 `kernel/reboot.c` 使用，在 `kernel_restart()`、`kernel_halt()` 等路径中通知驱动停止 DMA、保存状态等。
- **硬件事件通知**：如 CPU 热插拔、内存热插拔等子系统通过原子或阻塞通知链广播状态变化。
- **内核子系统解耦**：允许模块在不直接依赖的情况下响应全局事件（如网络子系统监听设备状态变化）。
- **错误恢复**：`notifier_call_chain_robust()` 用于需要事务性语义的场景（如设备初始化失败时回滚已分配资源）。
- **调试与追踪**：通过 ftrace 跟踪通知链的注册、注销和调用行为，辅助内核调试。