# cgroup\cgroup-internal.h

> 自动生成时间: 2025-10-25 12:40:45
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cgroup\cgroup-internal.h`

---

# cgroup/cgroup-internal.h 技术文档

## 1. 文件概述

`cgroup-internal.h` 是 Linux 内核控制组（cgroup）子系统的内部头文件，定义了 cgroup 核心实现所需的内部数据结构、宏、辅助函数和接口。该文件仅供 cgroup 子系统内部模块使用，不对外暴露给其他内核子系统。其主要作用包括：

- 提供 cgroup 文件系统挂载上下文管理
- 支持 cgroup 路径追踪与调试
- 管理 cgroup 与 css_set 之间的多对多关联
- 实现任务迁移（task migration）机制
- 封装 cgroup 生命周期、引用计数和锁操作等底层细节

## 2. 核心功能

### 主要数据结构

| 结构体 | 说明 |
|--------|------|
| `struct cgroup_fs_context` | cgroup 文件系统挂载上下文，包含挂载参数、命名空间、根节点等信息 |
| `struct cgroup_file_ctx` | cgroup 文件操作上下文，用于 `/proc/<pid>/cgroup`、`cgroup.procs` 等文件的读写状态管理 |
| `struct cgrp_cset_link` | 表示 cgroup 与 css_set 之间多对多关联的链接结构 |
| `struct cgroup_taskset` | 任务迁移过程中源/目标 css_set 和任务集合的抽象 |
| `struct cgroup_mgctx` | cgroup 任务迁移上下文，包含预加载的 css_set 和迁移任务集 |

### 关键宏定义

| 宏 | 说明 |
|----|------|
| `TRACE_CGROUP_PATH(type, cgrp, ...)` | 安全地在 tracepoint 中获取并记录 cgroup 路径，避免在中断上下文中持有自旋锁 |
| `for_each_root(root)` | 遍历所有已注册的 cgroup 根节点（hierarchy） |
| `for_each_subsys(ss, ssid)` | 遍历所有已启用的 cgroup 子系统 |
| `CGROUP_TASKSET_INIT` / `CGROUP_MGCTX_INIT` / `DEFINE_CGROUP_MGCTX` | 初始化迁移上下文的辅助宏 |

### 重要内联函数

| 函数 | 功能 |
|------|------|
| `cgroup_fc2context()` | 从 `fs_context` 转换为 `cgroup_fs_context` |
| `cgroup_is_dead()` | 判断 cgroup 是否已离线 |
| `notify_on_release()` | 检查 cgroup 是否启用 release 通知 |
| `get_css_set()` / `put_css_set()` | css_set 的引用计数管理（带锁安全释放） |

### 核心外部函数声明

| 函数 | 功能 |
|------|------|
| `cgroup_migrate*()` 系列 | 实现任务在 cgroup 间的原子迁移 |
| `cgroup_attach_task()` | 将任务（或线程组）附加到目标 cgroup |
| `cgroup_procs_write_start/finish()` | 安全地处理 `cgroup.procs` 写入操作（获取线程组读写锁） |
| `cgroup_kn_lock_live()` / `cgroup_kn_unlock()` | 安全访问存活的 cgroup kernfs 节点 |
| `cgroup_path_ns_locked()` | 在指定命名空间下获取 cgroup 路径（需持有 `cgroup_mutex`） |
| `init_cgroup_root()` / `cgroup_setup_root()` | 初始化和设置 cgroup 根节点 |
| `rebind_subsystems()` | 在根节点间重新绑定子系统 |

## 3. 关键实现

### 路径追踪安全机制

`TRACE_CGROUP_PATH` 宏通过以下方式确保 tracepoint 安全性：
- 使用静态分支 `trace_cgroup_##type##_enabled()` 避免未启用时的开销
- 在获取路径前获取全局自旋锁 `trace_cgroup_path_lock`
- 使用全局缓冲区 `trace_cgroup_path` 避免栈上大内存分配
- 保证 `cgroup_path()`（可能持有 `kernfs_rename_lock`）不在 trace handler 中直接调用

### css_set 引用计数管理

`put_css_set()` 实现了类似 `atomic_dec_and_lock()` 的语义：
- 先尝试无锁递减引用计数
- 仅当引用计数可能归零时才获取 `css_set_lock`
- 在锁保护下调用 `put_css_set_locked()` 完成实际释放
- 避免在常见路径上持有全局锁，提升并发性能

### 任务迁移机制

cgroup 任务迁移采用两阶段提交模型：
1. **准备阶段**：通过 `cgroup_migrate_add_src()` 收集源 css_set 和目标 cgroup，`cgroup_migrate_prepare_dst()` 预加载目标 css_set
2. **执行阶段**：`cgroup_migrate()` 原子地将任务从源 css_set 移动到目标 css_set
3. **清理阶段**：`cgroup_migrate_finish()` 释放临时资源

迁移上下文 `cgroup_mgctx` 保证操作的原子性：要么全部成功，要么全部回滚。

### 多对多关联模型

通过 `cgrp_cset_link` 实现 cgroup 与 css_set 的 M:N 关系：
- 每个 cgroup 通过 `cset_links` 链表关联多个 css_set
- 每个 css_set 通过 `cgrp_links` 链表关联多个 cgroup
- 支持高效遍历任一方向的关联关系

## 4. 依赖关系

### 头文件依赖
- `<linux/cgroup.h>`：cgroup 公共接口定义
- `<linux/kernfs.h>`：kernfs 文件系统抽象（cgroup 基于 kernfs 实现）
- `<linux/workqueue.h>`：工作队列支持（用于异步操作）
- `<linux/list.h>`：链表操作
- `<linux/refcount.h>`：引用计数实现
- `<linux/fs_parser.h>`：文件系统参数解析

### 内核模块依赖
- **kernfs**：cgroup 的底层文件系统实现
- **VFS**：通过 `fs_context` 与虚拟文件系统交互
- **调度器/内存管理等子系统**：通过 `cgroup_subsys[]` 注册的控制器
- **RCU 机制**：用于 `for_each_root` 等遍历操作的并发安全
- **tracepoint 子系统**：支持 cgroup 路径追踪

## 5. 使用场景

### cgroup 文件系统挂载
- `cgroup_do_get_tree()` 被 VFS 调用以挂载 cgroup 文件系统
- `cgroup_fs_context` 保存挂载选项（如子系统选择、release_agent 路径等）
- `init_cgroup_root()` 和 `cgroup_setup_root()` 初始化根节点

### 任务迁移与附加
- 用户写入 `cgroup.procs` 触发 `cgroup_procs_write_start()` → `cgroup_attach_task()`
- 内核通过 `cgroup_migrate()` 将任务移动到新 cgroup
- 迁移过程保证子系统回调（如 `can_attach`/`attach`）的原子执行

### 调试与追踪
- 启用 cgroup 相关 tracepoint 时，`TRACE_CGROUP_PATH` 安全记录路径
- `enable_debug_cgroup()` 初始化调试支持

### 资源回收
- `cgroup_rmdir()` 删除空 cgroup 时，通过 `cgroup_lock_and_drain_offline()` 确保无并发访问
- `put_css_set()` 在任务退出或迁移后释放 css_set 资源

### 子系统管理
- `rebind_subsystems()` 支持动态重新绑定子系统到不同 hierarchy（cgroup v1）
- `for_each_subsys` 用于遍历所有启用的控制器（如内存、CPU 等）