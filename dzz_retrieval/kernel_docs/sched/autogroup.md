# sched\autogroup.c

> 自动生成时间: 2025-10-25 15:56:17
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\autogroup.c`

---

# `sched/autogroup.c` 技术文档

## 1. 文件概述

`sched/autogroup.c` 实现了 Linux 内核中的 **自动任务组（autogroup）调度机制**。该机制旨在提升桌面交互式应用的响应性，通过为每个会话（session）自动创建独立的调度任务组（task group），并基于进程的 nice 值动态调整该组的 CPU 带宽分配。当启用时（默认开启），所有属于同一会话的进程共享相同的调度权重，从而避免一个 CPU 密集型任务拖慢整个用户会话的响应速度。

## 2. 核心功能

### 主要数据结构

- **`struct autogroup`**（隐式定义，通过成员推断）：
  - `tg`：指向关联的 `task_group`，用于 CFS 调度器的组调度。
  - `kref`：引用计数，管理 autogroup 生命周期。
  - `lock`：读写信号量，保护 autogroup 内部状态（如 nice 值）。
  - `id`：唯一标识符，用于 `/proc` 接口显示。
  - `nice`：当前 autogroup 的 nice 值（范围 -20 到 19）。

- **全局变量**：
  - `sysctl_sched_autogroup_enabled`：控制 autogroup 功能开关（可通过 `/proc/sys/kernel/sched_autogroup_enabled` 配置）。
  - `autogroup_default`：默认 autogroup，初始任务（如 init）使用。
  - `autogroup_seq_nr`：原子计数器，用于生成 autogroup 的唯一 ID。

### 主要函数

- **初始化与销毁**：
  - `autogroup_init()`：初始化默认 autogroup 并关联到 init 任务。
  - `autogroup_free()`：释放 task_group 关联的 autogroup 内存。
  - `autogroup_destroy()`：当引用计数归零时，销毁 autogroup 及其 task_group。
  
- **Autogroup 管理**：
  - `autogroup_create()`：创建新的 autogroup 及其 task_group。
  - `autogroup_move_group()`：将任务及其线程组迁移到指定 autogroup。
  - `autogroup_task_get()`：安全获取任务当前的 autogroup（带引用计数）。

- **任务生命周期钩子**：
  - `sched_autogroup_create_attach()`：为新会话创建并绑定 autogroup（如 shell 启动新进程组）。
  - `sched_autogroup_detach()`：将任务移回默认 autogroup（当前无使用者）。
  - `sched_autogroup_fork()`：fork 时子进程继承父进程的 autogroup。
  - `sched_autogroup_exit()`：进程退出时释放 autogroup 引用。
  - `sched_autogroup_exit_task()`：任务退出前确保调度器状态同步。

- **用户接口**：
  - `proc_sched_autogroup_set_nice()`：通过 `/proc/<pid>/autogroup` 设置 autogroup 的 nice 值。
  - `proc_sched_autogroup_show_task()`：在 `/proc/<pid>/autogroup` 中显示 autogroup 信息。
  - `autogroup_path()`：生成 autogroup 在 cgroup 层级中的路径名（如 `/autogroup-123`）。

- **辅助函数**：
  - `task_wants_autogroup()`：判断任务是否应使用 autogroup（排除非 root task_group 或退出中任务）。

## 3. 关键实现

### Autogroup 创建与绑定
- 当新会话启动（如终端执行命令），`sched_autogroup_create_attach()` 被调用：
  1. 调用 `autogroup_create()` 分配新 `autogroup` 结构。
  2. 通过 `sched_create_group()` 创建关联的 `task_group`。
  3. 对于 `CONFIG_RT_GROUP_SCHED`，实时任务被重定向到 root task_group，避免带宽分配复杂性。
  4. 调用 `autogroup_move_group()` 将当前任务及其所有线程迁移到新 autogroup。
  5. 释放 `autogroup_create()` 返回的额外引用。

### 引用计数与生命周期
- 每个 `autogroup` 使用 `kref` 管理生命周期：
  - `autogroup_task_get()` 获取时增加引用。
  - `autogroup_kref_put()` 释放时减少引用，归零则调用 `autogroup_destroy()`。
- `signal_struct->autogroup` 指向会话的 autogroup，fork 时子进程通过 `sched_autogroup_fork()` 继承父进程的引用。
- 进程退出时，`sched_autogroup_exit()` 释放 `signal_struct` 持有的引用。

### 调度权重调整
- 通过 `/proc/<pid>/autogroup` 写入 nice 值（-20~19）：
  - 调用 `proc_sched_autogroup_set_nice()`。
  - 非 root 用户需具备 `CAP_SYS_ADMIN` 或遵守速率限制（每 100ms 一次）。
  - 将 nice 值转换为 CFS 调度权重（`sched_prio_to_weight`），通过 `sched_group_set_shares()` 应用到 autogroup 的 `task_group`。

### 退出处理
- 任务退出时，`sched_autogroup_exit_task()` 确保在 `exit_notify()` 前调用 `sched_move_task()`，避免调度器使用已失效的 `signal->autogroup`。
- `task_wants_autogroup()` 通过检查 `PF_EXITING` 标志防止退出中任务被错误迁移。

## 4. 依赖关系

- **调度器核心**：
  - 依赖 `kernel/sched/core.c` 提供的 `task_group` 管理接口（如 `sched_create_group()`, `sched_destroy_group()`）。
  - 依赖 CFS 调度器的组调度功能（`CONFIG_FAIR_GROUP_SCHED`）。
- **实时调度**：
  - 若启用 `CONFIG_RT_GROUP_SCHED`，autogroup 会绕过 RT 带宽分配，将 RT 任务重定向到 root task_group。
- **安全模块**：
  - 调用 `security_task_setnice()` 进行权限检查（LSM 钩子）。
- **系统控制**：
  - 通过 `CONFIG_SYSCTL` 注册 `/proc/sys/kernel/sched_autogroup_enabled` 开关。
- **Proc 文件系统**：
  - 依赖 `CONFIG_PROC_FS` 提供 `/proc/<pid>/autogroup` 接口。

## 5. 使用场景

- **桌面交互式环境**：
  - 默认启用时，每个终端会话（如 GNOME Terminal、xterm）自动获得独立的 autogroup。
  - 用户在终端运行 CPU 密集型任务（如 `make -j`）不会显著影响其他会话（如浏览器、音乐播放器）的响应性。
- **动态优先级调整**：
  - 用户可通过 `echo 10 > /proc/<pid>/autogroup` 降低整个会话的 CPU 优先级（等效于对会话内所有进程设置 nice=10）。
- **容器与轻量级隔离**：
  - 在未使用 cgroup v1/v2 的场景下，autogroup 提供基于会话的轻量级 CPU 资源隔离。
- **系统启动与关闭**：
  - init 进程使用默认 autogroup（绑定到 root task_group）。
  - 所有用户进程通过 fork/会话创建机制自动纳入 autogroup 管理。