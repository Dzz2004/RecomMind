# taskstats.c

> 自动生成时间: 2025-10-25 16:34:26
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `taskstats.c`

---

# taskstats.c 技术文档

## 1. 文件概述

`taskstats.c` 是 Linux 内核中用于向用户空间导出每个任务（task）统计信息的核心实现文件。该模块通过通用 Netlink（Generic Netlink, genetlink）接口，提供对进程和线程组（TGID）的详细资源使用统计，包括 CPU 时间、上下文切换、延迟会计（delay accounting）、扩展会计（extended accounting）以及可执行文件元数据等。此外，还支持基于 CPU 掩码的监听器注册机制，允许用户空间程序订阅特定 CPU 上任务退出时的统计信息。

## 2. 核心功能

### 主要数据结构

- **`struct listener`**：表示一个注册的监听器，包含 PID 和有效性标志。
- **`struct listener_list`**：每个 CPU 上的监听器链表，受读写信号量保护。
- **`taskstats_cache`**：用于分配 `struct taskstats` 的 slab 缓存。
- **`family`**：Generic Netlink 通信家族实例。

### 主要函数

- **`prepare_reply()`**：为 Generic Netlink 消息准备回复缓冲区。
- **`send_reply()`**：向请求者发送单播回复。
- **`send_cpu_listeners()`**：向注册在特定 CPU 上的所有监听器广播任务统计信息。
- **`fill_stats()`**：填充单个任务的完整统计信息。
- **`fill_stats_for_pid()`**：根据 PID 填充对应任务的统计。
- **`fill_stats_for_tgid()`**：聚合线程组内所有活跃线程的统计信息。
- **`fill_tgid_exit()`**：在线程退出时，将其统计累加到所属线程组的汇总结构中。
- **`add_del_listener()`**：注册或注销监听特定 CPU 任务退出事件的用户空间进程。
- **`exe_add_tsk()`**：提取任务可执行文件的设备号和 inode 号。

### Netlink 策略定义

- `taskstats_cmd_get_policy[]`：定义 `TASKSTATS_CMD_ATTR_*` 属性的解析规则。
- `cgroupstats_cmd_get_policy[]`：定义 `CGROUPSTATS_CMD_ATTR_FD` 属性的解析规则。

## 3. 关键实现

### 统计信息聚合机制

- **单任务统计**：通过 `fill_stats()` 调用多个子系统（如 `delayacct_add_tsk`、`bacct_add_tsk`、`xacct_add_tsk`）分别填充延迟、基础会计、扩展会计等字段。
- **线程组统计**：`fill_stats_for_tgid()` 遍历线程组内所有非退出线程，累加 CPU 时间、上下文切换次数，并计算运行时长（`ac_etime`）。
- **退出时聚合**：当线程退出时，`fill_tgid_exit()` 将其统计信息累加到 `task_struct->signal->stats` 中，供后续查询使用。

### 监听器管理

- 每个 CPU 维护一个独立的 `listener_list`，使用 per-CPU 变量 `listener_array` 存储。
- 监听器通过 `add_del_listener()` 注册/注销，仅允许在初始用户命名空间和 PID 命名空间中操作。
- 发送消息时采用“克隆 skb”策略：除最后一个监听器外，其余均使用 `skb_clone()` 保证每个接收者获得独立副本。
- 自动清理无效监听器：若 `genlmsg_unicast()` 返回 `-ECONNREFUSED`，标记该监听器无效，并在后续批量删除。

### 安全与命名空间限制

- 仅允许 `init_user_ns` 和 `init_pid_ns` 中的进程注册监听器，防止容器内进程干扰全局统计。
- 对注册的 CPU 掩码进行合法性校验（必须是 `cpu_possible_mask` 的子集）。

### 内存与并发控制

- 使用 `rw_semaphore` 保护监听器链表，读操作（发送）并发，写操作（增删）互斥。
- `taskstats_seqnum` 为 per-CPU 序列号，用于无请求上下文时的消息标识。
- 所有动态分配均考虑 NUMA 节点亲和性（`kmalloc_node`）。

## 4. 依赖关系

- **Generic Netlink (`<net/genetlink.h>`)**：提供用户空间通信通道。
- **延迟会计 (`<linux/delayacct.h>`)**：提供 I/O、调度等延迟统计。
- **进程会计 (`<linux/acct.h>`, `<linux/tsacct_kern.h>`)**：提供基础和扩展会计信息。
- **CGroup 统计 (`<linux/cgroupstats.h>`)**：虽未在截断代码中完整体现，但头文件包含表明支持 cgroup 级别统计。
- **调度与任务管理 (`<linux/sched/cputime.h>`, `<linux/pid_namespace.h>`)**：获取任务 CPU 时间、PID 命名空间信息。
- **内存管理 (`<linux/slab.h>`, `<linux/percpu.h>`)**：slab 缓存和 per-CPU 数据结构支持。

## 5. 使用场景

- **性能分析工具**：如 `pidstat`、`perf` 等可通过 taskstats 获取高精度任务资源使用数据。
- **资源监控系统**：实时收集进程 CPU、上下文切换、延迟等指标，用于系统调优或异常检测。
- **作业调度器**：根据历史任务统计信息优化任务放置策略。
- **容器运行时**：虽受限于命名空间，但宿主机监控工具可利用此接口获取容器内进程统计（需通过宿主机 PID）。
- **内核调试**：开发人员可通过监听任务退出事件，分析进程生命周期行为。