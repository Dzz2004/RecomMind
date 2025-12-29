# cgroup\cgroup.c

> 自动生成时间: 2025-10-25 12:42:31
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cgroup\cgroup.c`

---

# cgroup/cgroup.c 技术文档

## 1. 文件概述

`cgroup/cgroup.c` 是 Linux 内核中控制组（Control Group, cgroup）子系统的核心实现文件。它提供了通用的进程分组机制，用于对进程进行资源限制、优先级分配、资源统计和进程控制。该文件实现了 cgroup v2 统一层次结构（unified hierarchy）的基础框架，包括 cgroup 的创建、销毁、层级管理、子系统（subsystem/controller）注册与回调、文件系统接口、命名空间支持以及与 RCU、工作队列等内核机制的集成。

## 2. 核心功能

### 主要全局数据结构

- **`cgroup_mutex`**：cgroup 系统的主互斥锁，任何对 cgroup 层级结构或配置的修改都必须持有此锁。
- **`css_set_lock`**：自旋锁，保护任务的 `task->cgroups` 指针、`css_set` 对象链表以及每个 `css_set` 关联的任务链。
- **`cgroup_subsys[]`**：指向所有已注册 cgroup 子系统的指针数组，通过 `cgroup_subsys.h` 自动生成。
- **`cgroup_subsys_name[]`**：各子系统的名称字符串数组。
- **`cgroup_subsys_enabled_key[]` / `cgroup_subsys_on_dfl_key[]`**：静态键（static_key）数组，用于高效判断子系统是否启用或是否在默认层级（v2）上启用。
- **`cgrp_dfl_root`**：默认 cgroup 层级（v2）的根节点。
- **`cgroup_roots`**：所有已挂载 cgroup 层级根节点的链表。
- **`init_cgroup_ns`**：初始 cgroup 命名空间，供 init 进程使用。
- **`cgroup_destroy_wq`**：专用工作队列，用于异步销毁 cgroup，避免阻塞系统工作队列。

### 关键静态变量

- **`cgrp_dfl_visible`**：标志默认层级是否已挂载（首次挂载后可见）。
- **`cgrp_dfl_inhibit_ss_mask` / `cgrp_dfl_implicit_ss_mask` / `cgrp_dfl_threaded_ss_mask`**：位掩码，分别表示在默认层级中被禁止、隐式启用和可线程化的子系统。
- **`have_fork_callback` 等**：位掩码，记录哪些子系统实现了特定生命周期回调（如 fork、exit、release、can_fork）。
- **`css_serial_nr_next`**：全局递增序列号，用于保证 cgroup 创建顺序和兄弟节点排序。

### 核心函数（声明/定义）

- **`cgroup_apply_control()`**：应用对 cgroup 的控制策略变更。
- **`cgroup_finalize_control()`**：完成控制策略变更的最终处理。
- **`cgroup_destroy_locked()`**：在持有 `cgroup_mutex` 的情况下销毁 cgroup。
- **`css_create()`**：为指定 cgroup 和子系统创建 `cgroup_subsys_state`（css）。
- **`css_release()`**：css 引用计数归零时的释放回调。
- **`kill_css()`**：终止并清理一个 css。
- **`css_task_iter_skip()`**：在遍历任务时跳过特定任务。
- **`cgroup_addrm_files()`**：向 cgroup 目录动态添加或移除控制文件。

## 3. 关键实现

### 锁机制设计
- **`cgroup_mutex`** 作为主锁，保护所有结构性变更（如创建/销毁 cgroup、挂载/卸载层级）。
- **`css_set_lock`** 保护任务与 css_set 的关联关系，允许在不持有主锁的情况下快速读取任务的 cgroup 成员关系。
- **`cgroup_idr_lock`** 保护 ID 分配器（`cgroup_idr` 和 `css_idr`），允许在不持有 `cgroup_mutex` 的情况下释放 ID。
- **`cgroup_file_kn_lock`** 同步通知机制与文件节点（kn）的创建/销毁，尤其在 css 隐藏/显示时。
- **`cgroup_threadgroup_rwsem`**（percpu rwsem）用于线程组操作的同步。

### 子系统管理
- 通过宏 `SUBSYS()` 和头文件 `linux/cgroup_subsys.h` 自动生成子系统数组、名称数组和静态键数组，实现编译期配置。
- 使用 `static_key` 优化运行时检查（如 `cgroup_subsys_enabled()`），避免分支预测开销。
- 位掩码（如 `have_fork_callback`）用于快速判断哪些子系统需要调用特定回调，避免遍历所有子系统。

### 默认层级（v2）支持
- `cgrp_dfl_root` 代表统一的 cgroup v2 层级，初始隐藏，首次挂载后变为可见。
- 通过 `cgrp_dfl_inhibit_ss_mask` 等掩码控制哪些子系统可在 v2 中使用、是否自动启用或支持线程化模式。

### 资源销毁与异步处理
- 使用专用工作队列 `cgroup_destroy_wq` 处理 cgroup 销毁，防止大量并发销毁操作阻塞 `system_wq` 导致死锁。
- css 的生命周期通过 `percpu_ref` 管理，`css_release()` 在引用归零时触发异步清理。

### 调试与追踪
- `trace_cgroup_path` 和 `trace_cgroup_path_lock` 用于追踪事件中记录 cgroup 路径。
- `cgroup_debug` 全局开关控制调试输出。
- 定义了 `CREATE_TRACE_POINTS` 以生成 cgroup 相关的 tracepoint。

## 4. 依赖关系

- **头文件依赖**：
  - `cgroup-internal.h`：cgroup 内部实现头文件。
  - 多个内核子系统头文件：`sched.h`（调度）、`cred.h`（凭证）、`nsproxy.h`（命名空间）、`bpf-cgroup.h`（BPF 集成）、`psi.h`（压力指标）等。
- **子系统依赖**：
  - 所有 cgroup 子系统（如 `cpuset`、`memory`、`cpu` 等）通过 `cgroup_subsys.h` 注册到此框架。
  - 依赖 `sysfs` 的设计思想（源自 Patrick Mochel）。
- **内核机制依赖**：
  - RCU（读-拷贝-更新）用于无锁读取。
  - IDR（整数 ID 管理器）用于分配 cgroup 和 css 的唯一 ID。
  - 工作队列（workqueue）用于异步销毁。
  - 静态键（static_key）用于运行时优化。
  - percpu 变量用于性能敏感数据（如 `cgrp_dfl_root_rstat_cpu`）。

## 5. 使用场景

- **容器运行时**（如 Docker、containerd）：通过挂载 cgroup v2 文件系统并写入进程 PID 到 `cgroup.procs`，实现对容器内进程的资源隔离与限制。
- **系统资源管理器**（如 systemd）：使用 cgroup 层级组织服务进程，实施 CPU、内存、IO 等资源配额。
- **内核子系统集成**：各资源控制器（如内存、CPU 调度器、blkio）通过注册 cgroup 子系统，将其资源管理策略与 cgroup 框架绑定。
- **性能监控与调试**：通过 cgroup 提供的接口（如 `memory.stat`、`cpu.stat`）获取进程组的资源使用统计。
- **安全隔离**：结合用户命名空间（user namespace）和 cgroup，实现多租户环境下的资源隔离。
- **BPF 程序挂载**：通过 `bpf-cgroup` 接口，将 BPF 程序附加到 cgroup 上，实现网络、安全等策略的分组应用。