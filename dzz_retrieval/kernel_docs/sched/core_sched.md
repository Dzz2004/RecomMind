# sched\core_sched.c

> 自动生成时间: 2025-10-25 16:00:47
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\core_sched.c`

---

# `sched/core_sched.c` 技术文档

## 1. 文件概述

`sched/core_sched.c` 是 Linux 内核调度器中用于实现 **核心调度（Core Scheduling）** 功能的核心文件之一。核心调度是一种安全机制，旨在防止来自不同安全上下文的任务在同一个物理 CPU 核心（特别是超线程/SMT 共享核心）上并发执行，从而缓解侧信道攻击（如 Spectre、MDS 等）。

该文件主要负责管理任务的 **调度 cookie**（`core_cookie`），通过引用计数的 cookie 对象将具有相同安全上下文的任务分组，确保只有拥有相同 cookie 的任务才能在同一个 CPU 核心上并发运行。

## 2. 核心功能

### 数据结构

- **`struct sched_core_cookie`**  
  表示一个调度 cookie，仅包含一个引用计数器 `refcnt`。其内存地址本身即作为 cookie 值使用。

### 主要函数

| 函数 | 功能描述 |
|------|--------|
| `sched_core_alloc_cookie()` | 分配一个新的 `sched_core_cookie` 对象，初始化引用计数为 1，并启用核心调度全局状态。返回 cookie 地址（转换为 `unsigned long`）。 |
| `sched_core_put_cookie(unsigned long cookie)` | 释放 cookie 引用；若引用计数归零，则释放内存并关闭核心调度全局状态。 |
| `sched_core_get_cookie(unsigned long cookie)` | 增加 cookie 引用计数，返回原 cookie 值。 |
| `sched_core_update_cookie(struct task_struct *p, unsigned long cookie)` | 原子地更新任务 `p` 的 `core_cookie`，处理任务在运行队列中的入队/出队，并在必要时触发重调度。 |
| `sched_core_clone_cookie(struct task_struct *p)` | 安全地复制任务 `p` 的当前 cookie（带锁保护），用于 fork 或共享操作。 |
| `sched_core_fork(struct task_struct *p)` | 在 `fork()` 时初始化子任务的核心调度状态，继承父进程的 cookie。 |
| `sched_core_free(struct task_struct *p)` | 在任务退出时释放其持有的 cookie 引用。 |
| `__sched_core_set(struct task_struct *p, unsigned long cookie)` | 设置任务 `p` 的 cookie，自动处理引用计数的获取与释放。 |
| `sched_core_share_pid(...)` | 用户空间通过 `prctl(PR_SCHED_CORE, ...)` 调用的核心接口，支持创建、查询、共享 cookie。 |
| `__sched_core_account_forceidle(struct rq *rq)` | （仅当 `CONFIG_SCHEDSTATS` 启用）统计核心强制空闲（force-idle）时间，并分摊到相关任务。 |
| `__sched_core_tick(struct rq *rq)` | 在调度 tick 中调用，用于更新强制空闲时间统计。 |

## 3. 关键实现

### Cookie 生命周期管理
- Cookie 通过 `kmalloc` 动态分配，其地址作为唯一标识。
- 使用 `refcount_t` 实现线程安全的引用计数。
- `sched_core_get()` / `sched_core_put()` 控制全局核心调度使能状态。

### 任务 Cookie 更新
- 在 `task_rq_lock()` 保护下更新 `p->core_cookie`，确保调度器一致性。
- 若任务已在运行队列中，先出队再根据新 cookie 决定是否重新入队。
- 若任务正在 CPU 上运行，调用 `resched_curr()` 触发重调度，以确保新 cookie 策略立即生效。

### 安全访问控制
- 通过 `ptrace_may_access()` 检查调用者是否有权限操作目标进程的 cookie。
- 仅当系统存在 SMT（超线程）时（`sched_smt_present` 为真），才允许使用核心调度功能。

### prctl 接口支持
- 支持四种命令：
  - `PR_SCHED_CORE_CREATE`：创建新 cookie。
  - `PR_SCHED_CORE_SHARE_TO`：将当前进程的 cookie 应用于目标进程（或进程组）。
  - `PR_SCHED_CORE_SHARE_FROM`：将目标进程的 cookie 应用于当前进程。
  - `PR_SCHED_CORE_GET`：获取目标进程的 cookie 哈希值（用于用户空间识别）。
- 支持作用域：线程（`PIDTYPE_PID`）、线程组（`PIDTYPE_TGID`）、进程组（`PIDTYPE_PGID`）。

### 强制空闲时间统计（`CONFIG_SCHEDSTATS`）
- 当核心因 cookie 不兼容而进入强制空闲状态时，记录空闲时间。
- 时间按 `core_forceidle_count / core_forceidle_occupation` 比例分摊到所有相关 CPU 上的非 idle 任务。
- 通过 `__account_forceidle_time()` 更新任务的调度统计信息。

## 4. 依赖关系

- **调度器核心**：依赖 `kernel/sched/` 下的通用调度器基础设施，如 `task_rq_lock()`、`resched_curr()`、`rq` 结构等。
- **SMT 检测**：依赖 `sched_smt_present` 静态分支判断系统是否支持超线程。
- **内存管理**：使用 `kmalloc`/`kfree` 进行动态内存分配。
- **进程管理**：依赖 `find_task_by_vpid()`、`tasklist_lock`、`do_each_pid_thread` 等进程遍历机制。
- **安全机制**：依赖 `ptrace_may_access()` 进行权限检查。
- **调度统计**：`__sched_core_account_forceidle` 依赖 `CONFIG_SCHEDSTATS` 和 `__account_forceidle_time`。

## 5. 使用场景

- **安全敏感应用**：如浏览器、虚拟机监控器（VMM）、加密服务等，需防止跨任务的侧信道攻击。
- **用户空间控制**：通过 `prctl(PR_SCHED_CORE, ...)` 接口，应用程序可显式创建和共享调度 cookie，将信任的任务分组。
- **进程 fork 行为**：子进程自动继承父进程的 cookie，确保同源任务保持调度兼容性。
- **系统资源隔离**：在多租户或容器环境中，确保不同租户的任务不会在同一个物理核心上并发执行。
- **性能调优与监控**：通过 `CONFIG_SCHEDSTATS` 收集核心强制空闲开销，评估安全策略对性能的影响。