# trace\trace_event_perf.c

> 自动生成时间: 2025-10-25 17:17:36
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_event_perf.c`

---

# `trace/trace_event_perf.c` 技术文档

## 1. 文件概述

`trace/trace_event_perf.c` 是 Linux 内核中连接 **ftrace 事件子系统** 与 **perf 性能监控子系统** 的关键桥梁。该文件实现了将 ftrace 定义的 tracepoint、kprobe 和 uprobe 事件作为 perf event 使用的能力，使得用户空间可以通过 `perf_event_open()` 系统调用对内核 trace 事件进行采样、计数或原始数据采集。同时，该文件负责权限控制、资源管理、生命周期维护以及安全策略实施，确保 trace 事件在 perf 上下文中的安全和高效使用。

## 2. 核心功能

### 主要数据结构

- **`perf_trace_buf[PERF_NR_CONTEXTS]`**  
  每 CPU 的预分配缓冲区数组，用于在 perf 上下文中暂存 trace 事件数据，避免动态分配开销。类型为 `perf_trace_t`（对齐的 `unsigned long` 数组），大小为 `PERF_MAX_TRACE_SIZE`。

- **`total_ref_count`**  
  全局引用计数器，跟踪当前系统中所有通过 perf 使用的 trace 事件实例总数，用于管理全局缓冲区的分配与释放。

- **`trace_event_call::perf_refcount`**  
  每个 trace 事件的 perf 引用计数，用于管理该事件在 perf 上下文中的注册状态。

- **`trace_event_call::perf_events`**  
  指向 per-CPU 的 `hlist_head` 数组，用于存储与该 trace 事件关联的所有 perf event 实例。

### 主要函数

- **`perf_trace_event_perm()`**  
  执行 trace 事件在 perf 上下文中的权限检查，包括 root 权限要求、函数 trace 的特殊限制（如禁止用户态调用链和栈采样）等。

- **`perf_trace_event_reg()` / `perf_trace_event_unreg()`**  
  负责 trace 事件在 perf 中的注册与注销，包括分配 per-CPU 列表、调用事件类的注册回调、管理全局缓冲区生命周期。

- **`perf_trace_event_open()` / `perf_trace_event_close()`**  
  对应 perf event 的打开与关闭操作，调用 trace 事件类的相应回调。

- **`perf_trace_init()` / `perf_trace_destroy()`**  
  perf event 初始化与销毁的入口函数，用于标准 tracepoint 事件。

- **`perf_kprobe_init()` / `perf_kprobe_destroy()`**  
  支持通过 perf 接口动态创建和销毁 kprobe/kretprobe 事件。

- **`perf_uprobe_init()` / `perf_uprobe_destroy()`**  
  支持通过 perf 接口动态创建和销毁 uprobe/uretprobe 事件。

## 3. 关键实现

### 权限与安全控制
- **函数 trace 限制**：`ftrace_event_is_function()` 标记的事件（如 `function` tracepoint）仅允许 root 用户使用，且禁止启用 `PERF_SAMPLE_CALLCHAIN`（用户态部分）和 `PERF_SAMPLE_STACK_USER`，以避免在页错误处理路径中发生嵌套页错误。
- **原始数据访问控制**：当 perf event 请求 `PERF_SAMPLE_RAW` 时，若非 `PERF_ATTACH_TASK` 模式或事件未设置 `TRACE_EVENT_FL_CAP_ANY` 标志，则必须为 root 用户。
- **权限检查时机**：仅在 `perf_event_open()` 路径下检查当前进程权限，子事件（`p_event->parent`）继承父事件权限。

### 资源管理
- **Per-CPU 缓冲区池**：全局 `perf_trace_buf` 数组在首次有 perf trace 事件注册时分配，所有事件共享，按上下文（`PERF_NR_CONTEXTS`）区分，避免频繁分配。
- **引用计数机制**：
  - `total_ref_count` 控制全局缓冲区的生命周期。
  - 每个 `trace_event_call` 的 `perf_refcount` 控制其 per-CPU 事件列表和底层 tracepoint 注册状态。
- **同步注销**：`perf_trace_event_unreg()` 调用 `tracepoint_synchronize_unregister()` 确保所有 CPU 上的 tracepoint 回调执行完毕后再释放资源。

### 动态探针支持
- **Kprobe/Uprobe 集成**：通过 `create_local_trace_kprobe/uprobe()` 动态创建临时 trace 事件，绑定到 perf event 生命周期，销毁时自动清理。
- **用户空间参数处理**：使用 `strndup_user()` 安全拷贝用户提供的函数名或文件路径，并进行长度和空值校验。

### 事件注册流程
1. **权限检查** (`perf_trace_event_perm`)
2. **事件注册** (`perf_trace_event_reg`)：分配 per-CPU 列表，首次使用时分配全局缓冲区，调用 `TRACE_REG_PERF_REGISTER`
3. **事件打开** (`perf_trace_event_open`)：调用 `TRACE_REG_PERF_OPEN`

## 4. 依赖关系

- **核心依赖**：
  - `<linux/perf_event.h>`：perf event 核心接口（通过 `trace.h` 间接包含）
  - `"trace.h"`：ftrace 核心基础设施，包括 `trace_event_call`、`trace_event_class`、`ftrace_events` 列表等
  - `"trace_probe.h"`：kprobe/uprobe 动态事件创建接口（`create_local_trace_kprobe/uprobe`）
- **可选依赖**：
  - `CONFIG_KPROBE_EVENTS`：启用 kprobe perf 支持
  - `CONFIG_UPROBE_EVENTS`：启用 uprobe perf 支持
- **同步原语**：
  - `event_mutex`：保护 ftrace 事件列表的并发访问
  - `tracepoint_synchronize_unregister()`：RCU 同步，确保 tracepoint 回调安全注销

## 5. 使用场景

- **用户空间 perf 工具**：`perf record -e 'tracepoint:*'` 或 `perf record -e 'kprobe:func'` 等命令通过此模块将 trace 事件转换为 perf event。
- **动态内核探针**：应用程序通过 `perf_event_open()` 动态插入 kprobe/uprobe 监控特定函数或用户态地址，无需预定义 tracepoint。
- **安全审计与性能分析**：结合 perf 的采样能力，对内核关键路径（如调度、内存管理）进行低开销监控，同时通过权限控制防止敏感数据泄露。
- **eBPF 程序附加**：eBPF 程序可附加到 perf event 对应的 tracepoint/kprobe，此模块为 eBPF 提供底层事件源支持。