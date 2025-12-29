# cgroup\cgroup-v1.c

> 自动生成时间: 2025-10-25 12:41:31
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cgroup\cgroup-v1.c`

---

# cgroup/cgroup-v1.c 技术文档

## 1. 文件概述

`cgroup-v1.c` 是 Linux 内核中控制组（cgroup）v1 版本的核心实现文件之一，负责提供 cgroup v1 特有的功能接口和机制。该文件主要实现了任务迁移、进程/线程 PID 列表管理、cgroup v1 控制器屏蔽逻辑以及与用户空间交互所需的文件操作支持（如 `tasks` 和 `cgroup.procs` 文件的读取）。它构建在通用 cgroup 基础设施之上，专用于维护 cgroup v1 的兼容性和行为一致性。

## 2. 核心功能

### 主要函数

- **`cgroup1_ssid_disabled(int ssid)`**  
  检查指定子系统 ID（ssid）是否被命令行参数禁用（通过 `cgroup_no_v1_mask`）。

- **`cgroup_attach_task_all(struct task_struct *from, struct task_struct *tsk)`**  
  将任务 `tsk` 附加到 `from` 任务所属的所有 cgroup v1 层级中，实现跨层级的一致性迁移。

- **`cgroup_transfer_tasks(struct cgroup *to, struct cgroup *from)`**  
  将 `from` cgroup 中的所有任务原子地迁移到 `to` cgroup，确保迁移过程中 fork 的子进程不会“逃逸”。

- **`cgroup1_pidlist_destroy_all(struct cgroup *cgrp)`**  
  销毁指定 cgroup 中所有延迟释放的 PID 列表，用于 cgroup 销毁前的清理。

- **`cgroup_pidlist_destroy_work_fn(struct work_struct *work)`**  
  延迟工作队列回调函数，异步释放不再使用的 `cgroup_pidlist` 结构。

- **`pidlist_uniq(pid_t *list, int length)`**  
  对已排序的 PID 数组去重，返回唯一 PID 的数量。

- **`cgroup_pidlist_find(struct cgroup *cgrp, enum cgroup_filetype type)`**  
  在指定 cgroup 中查找匹配当前 PID 命名空间和文件类型的 PID 列表。

### 主要数据结构

- **`enum cgroup_filetype`**  
  枚举类型，标识 PID 列表对应的是 `CGROUP_FILE_PROCS`（进程）还是 `CGROUP_FILE_TASKS`（线程）。

- **`struct cgroup_pidlist`**  
  表示一个 PID 列表的缓存结构，包含：
  - `key`：标识类型（procs/tasks）和所属 PID 命名空间
  - `list`：存储 PID 的动态数组（使用 `kvfree` 分配）
  - `length`：有效 PID 数量
  - `links`：挂载到 cgroup 的 `pidlists` 链表
  - `owner`：所属 cgroup
  - `destroy_dwork`：延迟销毁的工作项

### 全局变量

- **`cgroup_no_v1_mask`**  
  位掩码，记录被命令行（如 `cgroup_no_v1=`）禁用的 v1 控制器。

- **`cgroup_no_v1_named`**  
  布尔值，控制是否禁止命名的 v1 cgroup 挂载。

- **`cgroup_pidlist_destroy_wq`**  
  专用工作队列，用于异步销毁 PID 列表，避免阻塞关键路径。

- **`release_agent_path_lock`**  
  自旋锁，保护 `cgroup_subsys->release_agent_path` 的并发访问。

## 3. 关键实现

### PID 列表缓存机制

为高效读取 `tasks` 和 `cgroup.procs` 文件，内核采用按 **cgroup + PID 命名空间 + 文件类型** 三元组缓存 PID 列表的策略。由于不同 PID 命名空间中 PID 映射不同，且文件要求输出**排序且去重**的 PID，无法使用全局数据结构（如红黑树），故引入 `cgroup_pidlist` 共享池。

- 列表生成后缓存一段时间（`CGROUP_PIDLIST_DESTROY_DELAY = 1秒`），避免连续读操作重复构建。
- 使用 `delayed_work` 延迟释放，若在延迟期间再次被访问，则取消销毁。
- 通过专用工作队列 `cgroup_pidlist_destroy_wq` 确保销毁操作可被 flush，保证 cgroup 销毁时无残留。

### 任务迁移原子性保障

`cgroup_transfer_tasks` 实现了安全的任务批量迁移：

1. 使用 `cgroup_migrate` 框架，先收集所有源 css_set（`cgroup_migrate_add_src`），再准备目标（`cgroup_migrate_prepare_dst`）。
2. 逐个迁移任务，跳过 `PF_EXITING` 的退出中任务。
3. 依赖 `cgroup_attach_lock` 和 fork 路径的同步机制，确保迁移过程中 fork 的子进程要么留在源 cgroup（迁移完成后可见），要么直接进入目标 cgroup，**杜绝任务“丢失”**。

### 排序与去重

- PID 列表通过 `sort()` + `cmppid()` 进行升序排序。
- `pidlist_uniq()` 对已排序数组原地去重，利用相邻元素比较实现 O(n) 时间复杂度。

## 4. 依赖关系

- **内部依赖**：
  - `cgroup-internal.h`：cgroup 内部通用接口和数据结构
  - `css_set_lock`、`cgroup_lock()` 等同步原语
  - `cgroup_migrate_*` 系列迁移框架函数
  - `task_cgroup_from_root()` 等任务-cgroup 映射函数

- **外部依赖**：
  - `<linux/pid_namespace.h>`：PID 命名空间支持
  - `<linux/sched/task.h>`、`<linux/sched/signal.h>`：任务结构和状态访问
  - `<linux/vmalloc.h>`：大内存分配（`kvfree`）
  - `<trace/events/cgroup.h>`：cgroup 追踪事件
  - 各 cgroup v1 子系统（如 cpu、memory）通过 `cgroup_subsys` 与本文件交互

## 5. 使用场景

- **用户空间读取 `tasks`/`cgroup.procs` 文件**：触发 PID 列表生成、缓存和输出。
- **容器运行时迁移进程**：调用 `cgroup_attach_task_all` 或 `cgroup_transfer_tasks` 实现跨 cgroup 的进程移动。
- **系统启动时控制器屏蔽**：通过内核参数 `cgroup_no_v1=...` 设置 `cgroup_no_v1_mask`，禁用特定 v1 控制器。
- **cgroup v1 层级销毁**：调用 `cgroup1_pidlist_destroy_all` 清理所有缓存的 PID 列表。
- **release agent 路径更新**：通过 `release_agent_path_lock` 保护并发写入。