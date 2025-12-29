# trace\trace_events_trigger.c

> 自动生成时间: 2025-10-25 17:21:52
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_events_trigger.c`

---

# trace_events_trigger.c 技术文档

## 文件概述

`trace_events_trigger.c` 是 Linux 内核 ftrace 子系统中用于实现 **事件触发器（event triggers）** 的核心模块。该文件提供了在特定 trace event 被记录时自动执行自定义操作（如打印、堆栈跟踪、快照、启用/禁用其他事件等）的机制。触发器通过 tracefs 接口配置，支持运行时动态添加、删除和查询。

## 核心功能

### 主要数据结构

- `struct event_trigger_data`：表示一个事件触发器实例，包含操作函数指针、命令操作、过滤器、状态标志等。
- `struct event_command`：表示一种触发器命令类型（如 `stacktrace`、`snapshot`、`enable_event` 等），包含解析、注册、注销等回调。
- `trigger_commands`：全局链表，注册所有可用的触发器命令类型。
- `enum event_trigger_type`：用于标识触发器类型，特别是区分是否为“后置触发器”（post-trigger）。

### 主要函数

- `event_triggers_call()`：在事件发生时调用所有关联的触发器，根据过滤条件和触发器类型决定是否立即执行或延迟执行。
- `event_triggers_post_call()`：执行被标记为延迟（post-trigger）的触发器。
- `__trace_trigger_soft_disabled()`：在事件记录前检查是否应跳过记录（如因触发器或 PID 过滤）。
- `trigger_process_regex()`：解析用户通过 tracefs 写入的触发器命令字符串。
- `event_trigger_regex_write()` / `event_trigger_regex_open()`：tracefs 文件操作接口，用于配置和管理触发器。
- `trigger_data_free()`：安全释放触发器数据结构，确保 RCU 同步。

## 关键实现

### 触发器执行流程

1. **事件发生时**：`event_triggers_call()` 被调用（在 tracepoint handler 中，持有 `rcu_read_lock_sched()`）。
2. **过滤检查**：若事件记录 `rec` 非空且触发器关联了过滤器，则调用 `filter_match_preds()` 进行匹配。
3. **执行策略**：
   - 若为 **后置触发器**（如 `snapshot`），仅设置返回值中的对应位，不立即执行。
   - 否则，立即调用 `data->ops->trigger()` 执行触发动作。
4. **后置执行**：事件写入 ring buffer 后，调用 `event_triggers_post_call()` 执行所有标记的后置触发器。

### 触发器注册与管理

- 所有触发器命令类型通过 `register_trigger_cmds()` 注册到全局链表 `trigger_commands`。
- 用户通过向 `tracefs/events/<subsys>/<event>/trigger` 写入命令（如 `echo 'stacktrace:100' > trigger`）来添加触发器。
- 命令解析由 `trigger_process_regex()` 完成，调用对应 `event_command` 的 `parse()` 方法。
- 支持通过写入 `!command` 或清空文件（`O_TRUNC`）来移除触发器。

### 并发与同步

- **RCU 保护**：触发器链表遍历使用 `list_for_each_entry_rcu()`，确保在读取路径无锁。
- **互斥锁保护**：
  - `event_mutex`：保护 trace event 文件的触发器链表修改。
  - `trigger_cmd_mutex`：保护全局触发器命令链表的遍历和修改。
- **安全释放**：`trigger_data_free()` 调用 `tracepoint_synchronize_unregister()` 确保所有 CPU 退出 tracepoint handler 后才释放内存。

### 特殊状态处理

- **暂停状态**：`data->paused` 为真时跳过触发器执行。
- **软禁用**：`__trace_trigger_soft_disabled()` 在事件记录前检查：
  - 若设置了 `EVENT_FILE_FL_TRIGGER_MODE`，先执行无条件触发器（`rec=NULL`）。
  - 若设置了 `EVENT_FILE_FL_SOFT_DISABLED` 或 PID 过滤不匹配，则跳过事件记录。

## 依赖关系

- **核心依赖**：
  - `trace.h`：ftrace 核心头文件，定义 trace event、ring buffer、过滤器等基础结构。
  - `trace_events.h`：事件触发器相关数据结构定义。
- **子系统依赖**：
  - **Tracepoint**：触发器挂载在 tracepoint 事件上，依赖 tracepoint 注册/注销机制。
  - **Ring Buffer**：事件记录和触发器执行依赖 ring buffer 基础设施。
  - **Security Framework**：通过 `security_locked_down(LOCKDOWN_TRACEFS)` 限制触发器配置。
- **其他模块**：
  - 具体触发器命令实现（如 `trace_events_filter.c` 中的 `enable_event`、`snapshot` 等）通过 `register_trigger_cmds()` 注册到本模块。

## 使用场景

1. **动态调试**：
   - 在特定事件发生时自动捕获内核栈（`stacktrace` 触发器）。
   - 在事件触发时保存当前 ring buffer 快照（`snapshot` 触发器）。

2. **事件联动**：
   - 当事件 A 发生时启用/禁用事件 B（`enable_event`/`disable_event` 触发器）。
   - 实现复杂的事件链式响应。

3. **性能分析**：
   - 统计特定事件的发生次数（`hist` 触发器，需配合其他模块）。
   - 在满足特定条件（通过过滤器）时记录事件上下文。

4. **安全监控**：
   - 在关键系统调用或内核路径触发时记录详细信息。
   - 结合 lockdown 机制限制非特权用户配置触发器。

5. **用户接口**：
   - 通过 tracefs 文件系统（`/sys/kernel/tracing/events/.../trigger`）提供运行时配置接口。
   - 支持查询可用触发器列表（读取 `trigger` 文件）。