# trace\rv\rv_reactors.c

> 自动生成时间: 2025-10-25 17:11:06
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\rv\rv_reactors.c`

---

# `trace/rv/rv_reactors.c` 技术文档

## 1. 文件概述

`rv_reactors.c` 实现了 Linux 内核 Runtime Verification（运行时验证，RV）子系统中的 **反应器（reactor）接口**。该接口允许在监控模型检测到异常时触发预定义的响应动作（如打印日志、触发 panic 等）。默认情况下，异常通过 tracepoint 输出，但用户可通过此接口动态注册和切换不同的反应策略。该文件同时提供了用户空间接口，支持通过 sysfs 风格的文件系统控制反应器的启用与选择。

## 2. 核心功能

### 主要数据结构

- `struct rv_reactor`：定义反应器的核心结构，包含名称和回调函数 `react`。
- `struct rv_reactor_def`：反应器的内部封装，包含指向 `rv_reactor` 的指针和使用计数器 `counter`。
- `rv_reactors_list`：全局链表，维护所有已注册的反应器定义。

### 主要函数

- `rv_register_reactor(struct rv_reactor *reactor)`  
  向内核注册一个新的反应器，供模块动态加载使用。

- `rv_unregister_reactor(struct rv_reactor *reactor)`  
  注销已注册的反应器，若该反应器正被监控器使用则返回 `-EBUSY`。

- `get_reactor_rdef_by_name(char *name)`  
  根据名称在全局链表中查找对应的 `rv_reactor_def`。

- `monitor_swap_reactors(...)`  
  为指定监控器切换当前使用的反应器，并更新其启用状态。

- `monitor_reactors_write(...)`  
  处理用户向 `monitors/<monitor>/reactors` 文件写入的操作，用于切换反应器。

### 用户接口文件操作

- `available_reactors_ops`：提供 `/sys/kernel/debug/tracing/available_reactors` 文件操作，列出所有可用反应器。
- `monitor_reactors_ops`：提供 `/sys/kernel/debug/tracing/monitors/<monitor>/reactors` 文件操作，显示并设置特定监控器的反应器。

## 3. 关键实现

### 反应器注册与管理
- 所有注册的反应器通过 `rv_reactors_list` 链表统一管理。
- 注册时检查名称唯一性及长度合法性（不超过 `MAX_RV_REACTOR_NAME_SIZE`）。
- 注销时检查 `counter` 是否为 0，防止正在使用的反应器被移除。

### 用户空间接口设计
- **`available_reactors`**：只读文件，每行显示一个已注册反应器的名称。
- **`reacting_on`**（代码未完整展示）：全局开关，控制是否允许任何反应器触发。
- **`monitors/<monitor>/reactors`**：
  - 读取时显示所有可用反应器，当前选中的以 `[name]` 标记。
  - 写入时解析用户输入的反应器名称，调用 `monitor_swap_reactors` 切换。
  - 特殊处理 `"nop"` 反应器：将其视为禁用反应（`enable = false`）。

### 监控器与反应器绑定
- 每个 `rv_monitor_def` 维护一个指向当前 `rv_reactor_def` 的指针 `rdef`。
- 切换反应器时，若监控器处于启用状态，会先临时禁用，更新反应函数指针 `monitor->react`，再重新启用，确保原子性和一致性。
- 使用 `rv_interface_lock` 互斥锁保护所有注册、注销和切换操作，保证线程安全。

### 序列文件（seq_file）支持
- 使用标准 `seq_file` 机制实现大文件安全读取。
- `reactors_start/next/stop/show` 系列函数封装链表遍历逻辑，支持多监控器共享同一遍历接口。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/slab.h>`：用于 `kzalloc` 动态内存分配。
  - `"rv.h"`：包含 RV 子系统核心定义，如 `rv_reactor`、`rv_monitor_def`、`rv_interface_lock`、`rv_enable_monitor`/`rv_disable_monitor` 等。

- **内核子系统依赖**：
  - **Runtime Verification (RV)**：作为 RV 框架的一部分，依赖其监控器管理机制。
  - **DebugFS / Tracing**：用户接口挂载于 tracing 目录下，依赖内核 tracing 基础设施。
  - **模块系统**：`rv_register_reactor` 和 `rv_unregister_reactor` 被导出（`EXPORT_SYMBOL_GPL`），供内核模块动态加载反应器。

## 5. 使用场景

- **内核模块开发者**：可实现自定义反应器（如记录日志、触发警告、执行恢复操作），通过 `rv_register_reactor` 注册，在运行时根据监控结果执行特定逻辑。
- **系统调试与验证**：开发人员可通过 `available_reactors` 查看可用反应策略，通过 `monitors/<monitor>/reactors` 为特定监控模型（如死锁检测、状态机违规）选择响应方式（如 `panic` 用于严格验证，`printk` 用于调试）。
- **安全与可靠性增强**：在关键路径监控中启用 `panic` 反应器，确保违反安全属性时系统立即停止，防止状态污染。
- **动态策略调整**：无需重启系统或重新加载模块，即可在运行时切换反应行为，适用于生产环境中的渐进式验证策略部署。