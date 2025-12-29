# trace\rethook.c

> 自动生成时间: 2025-10-25 17:06:37
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\rethook.c`

---

# `trace/rethook.c` 技术文档

## 1. 文件概述

`rethook.c` 实现了 Linux 内核中的 **rethook（Return Hook）** 机制，这是一种通用的函数返回拦截框架，用于在函数返回时执行回调处理。该机制为 kretprobes、ftrace 等动态追踪工具提供底层支持，允许在函数返回点安全地插入处理逻辑，同时管理返回地址的重写与恢复。rethook 使用 per-task 的无锁链表（LLIST）作为“影子栈”来跟踪活跃的 hook 节点，并结合 RCU 和引用计数实现内存安全的生命周期管理。

## 2. 核心功能

### 主要数据结构
- `struct rethook`：rethook 实例，包含回调函数指针、私有数据、节点池（freelist）和引用计数。
- `struct rethook_node`：单个 hook 节点，嵌入在用户数据结构中，包含返回地址、帧指针、所属 rethook 指针及链表/空闲链表节点。

### 主要函数
| 函数 | 功能描述 |
|------|--------|
| `rethook_alloc()` | 分配并初始化一个新的 `rethook` 实例 |
| `rethook_free()` / `rethook_stop()` | 停止并异步释放 `rethook` 实例 |
| `rethook_add_node()` | 向 rethook 添加预分配的节点 |
| `rethook_try_get()` | 从 rethook 的空闲池中获取一个未使用的节点（需禁用抢占） |
| `rethook_hook()` | 在函数入口处注册返回 hook，将节点加入当前任务的 rethook 链表 |
| `rethook_recycle()` | 回收 hook 节点：若 rethook 有效则归还到空闲池，否则异步释放 |
| `rethook_find_ret_addr()` | 在指定任务的 rethook 链表中查找与给定帧指针对应的真实返回地址 |
| `rethook_flush_task()` | 在任务退出时清理其所有未返回的 rethook 节点 |

## 3. 关键实现

### 影子栈与任务绑定
- 每个 `task_struct` 包含一个 `rethooks` 字段（`struct llist_head`），用于存储该任务当前活跃的所有 `rethook_node`。
- 使用无锁链表（LLIST）实现高效、并发安全的插入（`__llist_add`）和批量删除（`__llist_del_all`）。

### 内存与生命周期管理
- **引用计数**：`rethook` 的 `ref` 字段初始为 1，每添加一个节点加 1；节点回收时减 1。当引用归零且节点池清空后，`rethook` 本体被释放。
- **RCU 安全**：通过 `rcu_assign_pointer()` 和 `rcu_dereference_check()` 管理 `handler` 指针的读写，确保在 RCU 读侧临界区内安全访问。
- **延迟释放**：`rethook_free()` 和无效节点的回收均通过 `call_rcu()` 异步执行，避免在中断或原子上下文中释放内存。

### 上下文感知的 Hook 注入
- `rethook_hook()` 接收 `mcount` 参数区分调用上下文（ftrace vs kprobe），由架构相关代码（`arch_rethook_prepare()`）决定如何修改返回地址（例如插入 trampoline）。
- 要求调用者处于 RCU 可用上下文（`rcu_is_watching()`），确保后续的 RCU 回调能正确执行。

### 返回地址恢复
- `rethook_find_ret_addr()` 遍历任务的 rethook 链表，跳过 trampoline 地址，返回与指定栈帧匹配的真实返回地址，用于栈回溯修正。

## 4. 依赖关系

- **架构依赖**：依赖 `arch_rethook_prepare()` 和 `arch_rethook_trampoline`（由各架构实现），用于实际修改返回地址和提供 trampoline 函数。
- **内核子系统**：
  - `<linux/rcu.h>`：RCU 同步机制
  - `<linux/slab.h>`：动态内存分配
  - `<linux/preempt.h>`：抢占控制
  - `<linux/kprobes.h>`：与 kretprobes 集成
  - `<linux/freelist.h>`：无锁空闲链表实现
- **任务管理**：依赖 `task_struct::rethooks` 字段和 `delayed_put_task_struct()` 回调。

## 5. 使用场景

- **kretprobes 实现**：作为 kretprobe 的底层机制，拦截函数返回并执行用户定义的处理函数。
- **ftrace 动态追踪**：在 function graph tracer 等场景中，用于捕获函数返回事件。
- **内核栈回溯修正**：当函数返回地址被 trampoline 覆盖时，通过 `rethook_find_ret_addr()` 恢复原始调用栈。
- **安全监控与性能分析**：第三方模块可基于 rethook 框架实现函数级的返回行为监控或统计。