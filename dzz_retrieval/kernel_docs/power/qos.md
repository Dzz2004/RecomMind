# power\qos.c

> 自动生成时间: 2025-10-25 15:24:30
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `power\qos.c`

---

# `power/qos.c` 技术文档

## 1. 文件概述

`power/qos.c` 是 Linux 内核中实现 **电源管理服务质量**（Power Management Quality of Service, PM QoS）机制的核心文件。它提供了一套通用框架，用于注册、聚合和分发系统级或设备级的 QoS 约束请求（如 CPU 延迟上限、频率下限、设备功耗标志等）。该机制允许内核子系统或驱动程序动态表达对系统性能或延迟的需求，内核据此计算出全局有效的约束值，并通过轮询或通知机制供其他组件响应。

文件同时提供了针对 **CPU 延迟 QoS** 的专用接口，是 PM QoS 框架在 CPU 电源管理场景下的具体应用。

## 2. 核心功能

### 主要数据结构

- **`struct pm_qos_constraints`**  
  表示一类 PM QoS 约束的聚合状态，包含：
  - `plist list`：使用优先级链表（`plist`）存储所有请求节点，按请求值排序。
  - `s32 target_value`：当前聚合后的有效约束值（通过 `READ_ONCE`/`WRITE_ONCE` 访问）。
  - `s32 default_value`：无请求时的默认值。
  - `s32 no_constraint_value`：空请求列表时返回的值（通常等于 `default_value`）。
  - `enum pm_qos_type type`：约束类型（`PM_QOS_MIN` 或 `PM_QOS_MAX`）。
  - `struct blocking_notifier_head *notifiers`：当有效值变化时触发的通知链。

- **`struct pm_qos_flags`**  
  用于管理 **位标志型** QoS 请求（如设备唤醒能力标志），包含：
  - `struct list_head list`：存储 `pm_qos_flags_request` 的普通链表。
  - `s32 effective_flags`：所有请求标志的按位或结果。

- **`struct pm_qos_request`**  
  用户持有的请求句柄，包含：
  - `struct plist_node node`：用于插入到 `pm_qos_constraints` 的优先级链表中。
  - `struct pm_qos_constraints *qos`：指向所属的约束对象。

- **`struct pm_qos_flags_request`**  
  位标志型请求的句柄，包含：
  - `struct list_head node`：链表节点。
  - `s32 flags`：请求的标志位。

### 主要函数

- **通用 PM QoS 接口**
  - `pm_qos_read_value()`：原子读取当前有效约束值。
  - `pm_qos_update_target()`：核心函数，处理 ADD/UPDATE/REMOVE 请求，更新约束值并触发通知。
  - `pm_qos_update_flags()`：更新位标志型 QoS 请求集，返回是否发生变化。

- **CPU 延迟 QoS 专用接口**
  - `cpu_latency_qos_limit()`：获取当前系统级 CPU 延迟上限（单位：微秒）。
  - `cpu_latency_qos_request_active()`：检查请求是否已注册。
  - `cpu_latency_qos_add_request()`：添加新的 CPU 延迟约束请求。
  - `cpu_latency_qos_update_request()`：更新现有请求（代码片段中未完整展示，但逻辑类似 `add`）。
  - `cpu_latency_qos_remove_request()`：移除请求（代码片段中未展示，但由 `pm_qos_update_target` 支持）。

## 3. 关键实现

### 约束值聚合算法
- **最小值约束**（`PM_QOS_MIN`）：如 CPU 延迟上限，取所有请求中的 **最小值**（最严格限制），通过 `plist_first()` 获取。
- **最大值约束**（`PM_QOS_MAX`）：如 CPU 频率下限，取所有请求中的 **最大值**，通过 `plist_last()` 获取。
- **位标志约束**：对所有请求的 `flags` 字段执行 **按位或**（`|=`）操作，聚合有效标志。

### 并发控制
- 全局自旋锁 `pm_qos_lock` 保护所有约束列表、标志列表及 `pm_qos_objects` 的修改操作。
- 锁在中断上下文中使用（`_irqsave`/`_irqrestore`），确保在中断处理或调度器路径中的安全性。
- 有效值 `target_value` 使用 `READ_ONCE`/`WRITE_ONCE` 保证无锁读取的内存可见性。

### 通知机制
- 当聚合值发生变化时，若约束对象注册了 `notifiers`，则调用 `blocking_notifier_call_chain()` 异步通知订阅者。
- CPU 延迟 QoS 在值变化时额外调用 `wake_up_all_idle_cpus()`，唤醒所有空闲 CPU 以应用新的延迟策略。

### CPU 延迟 QoS 特化
- 全局静态对象 `cpu_latency_constraints` 初始化为 `PM_QOS_MIN` 类型，默认值为 `PM_QOS_CPU_LATENCY_DEFAULT_VALUE`（通常为 `-1`，表示无限制）。
- 请求值有效性检查：仅允许非负值或特殊值 `PM_QOS_DEFAULT_VALUE`（表示移除约束）。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/pm_qos.h>`：定义 PM QoS 核心数据结构和 API。
  - `<linux/plist.h>`：通过 `plist` 实现优先级队列（隐式包含）。
  - `<linux/notifier.h>`：支持通知链机制（通过 `blocking_notifier_call_chain`）。
  - `<trace/events/power.h>`：提供 `trace_pm_qos_*` 跟踪点。
- **内核子系统**：
  - **CPU Idle**（`CONFIG_CPU_IDLE`）：CPU 延迟 QoS 用于控制 CPU 空闲状态的退出延迟。
  - **调度器**（`<linux/sched.h>`）：`wake_up_all_idle_cpus()` 依赖调度器唤醒逻辑。
  - **设备模型**（`<linux/device.h>`）：设备级 PM QoS 请求的基础（虽未在本文件实现，但框架支持）。
- **导出符号**：
  - `cpu_latency_qos_request_active()` 和 `cpu_latency_qos_add_request()` 通过 `EXPORT_SYMBOL_GPL` 导出，供其他 GPL 模块使用。

## 5. 使用场景

- **实时任务调度**：实时进程通过 `cpu_latency_qos_add_request()` 请求低 CPU 延迟（如 10μs），防止进入深 C-state，确保快速响应。
- **音频/视频播放**：多媒体框架设置 CPU 延迟上限，避免因 CPU 唤醒延迟导致音视频卡顿。
- **设备驱动约束**：网络或存储驱动在高吞吐场景下请求更高 CPU 频率（通过频率 QoS，逻辑类似但未在本文件实现）。
- **电源管理策略**：系统级电源管理器（如用户空间 `powerd`）动态调整全局 QoS 约束以平衡性能与功耗。
- **内核子系统协调**：多个子系统（如 CPUFreq、CPUIdle、Runtime PM）通过 PM QoS 框架协商统一的性能目标。