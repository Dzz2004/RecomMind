# exit.c

> 自动生成时间: 2025-10-25 13:27:18
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `exit.c`

---

# `exit.c` 技术文档

## 1. 文件概述

`exit.c` 是 Linux 内核中负责进程退出（termination）核心逻辑的关键源文件，位于 `kernel/` 目录下。该文件实现了进程终止时的资源回收、信号处理、线程组清理、引用计数释放以及与用户空间和内核其他子系统的协调机制。其主要职责包括：

- 安全地释放进程占用的内核资源（如内存、文件描述符、信号处理结构等）
- 更新进程组和会话的统计信息
- 通知父进程子进程已退出（通过 `SIGCHLD` 信号）
- 管理僵尸进程（zombie）的生命周期
- 支持线程组（thread group）的协同退出
- 提供与 oops（内核异常）相关的计数和限制机制

## 2. 核心功能

### 主要函数

| 函数名 | 功能描述 |
|--------|---------|
| `__unhash_process()` | 从内核的进程哈希表和链表中移除进程，减少线程计数 |
| `__exit_signal()` | 清理进程的信号相关资源，累加 CPU 时间和 I/O 统计到 `signal_struct` |
| `delayed_put_task_struct()` | RCU 回调函数，延迟释放 `task_struct` 及其关联资源 |
| `put_task_struct_rcu_user()` | 安全地减少 `task_struct` 的 RCU 用户引用计数，并在为零时调度延迟释放 |
| `release_thread()` | 架构相关的线程资源释放钩子（弱符号，可由架构代码覆盖） |
| `release_task()` | 主进程释放入口函数，协调整个退出流程，包括通知父进程、释放资源等 |
| `rcuwait_wake_up()` | 唤醒等待在 `rcuwait` 上的任务（代码片段未完整） |

### 关键数据结构与变量

| 名称 | 类型/说明 |
|------|----------|
| `oops_limit` | `unsigned int`，限制内核 oops 发生次数的阈值（默认 10000） |
| `oops_count` | `atomic_t`，原子计数器，记录系统发生 oops 的总次数 |
| `kern_exit_table` | `ctl_table`，用于 `/proc/sys/kernel/oops_limit` 的 sysctl 接口 |
| `oops_count_attr` | `kobj_attribute`，用于 `/sys/kernel/oops_count` 的 sysfs 接口 |

## 3. 关键实现

### 进程退出流程

1. **资源统计聚合**：  
   在 `__exit_signal()` 中，将退出线程的 CPU 时间（`utime`/`stime`）、I/O 操作、上下文切换次数等统计信息累加到所属线程组的 `signal_struct` 中，确保即使线程组 leader 尚未退出，也能被 `wait4()` 等系统调用正确获取。

2. **线程组协同退出**：  
   - 若当前退出的是线程组 leader（`group_dead == true`），则清理整个线程组的 PID 类型（TGID、PGID、SID），并从全局任务链表中移除。
   - 若非 leader，则仅减少线程组计数，并可能更新 `curr_target`（用于信号投递）。

3. **僵尸进程处理**：  
   在 `release_task()` 中，检查线程组 leader 是否已变为僵尸状态。若是且当前线程是最后一个成员，则调用 `do_notify_parent()` 通知其父进程。若父进程忽略 `SIGCHLD`，则直接将 leader 状态置为 `EXIT_DEAD` 并递归释放。

4. **延迟释放机制**：  
   通过 RCU（Read-Copy-Update）机制安全释放 `task_struct`。`put_task_struct_rcu_user()` 在引用计数归零时调用 `call_rcu()`，由 `delayed_put_task_struct()` 在 RCU 宽限期后执行实际释放，确保并发读取安全。

5. **Oops 计数与限制**：  
   提供 `oops_count`（只读）和 `oops_limit`（可调）两个接口，用于监控和限制内核异常次数，防止因频繁崩溃导致资源耗尽或引用计数溢出。

### 锁与同步

- **`tasklist_lock`**：写锁保护进程链表和 PID 哈希表的修改。
- **`sighand->siglock`**：自旋锁保护信号处理结构。
- **`signal->stats_lock`**：顺序锁（seqlock）保护线程组统计信息的聚合。
- **RCU**：用于安全地延迟释放 `task_struct`，避免在遍历任务链表时访问已释放内存。

## 4. 依赖关系

`exit.c` 与内核多个子系统紧密耦合，主要依赖包括：

- **调度器（SCHED）**：`<linux/sched/*.h>`，用于任务状态管理、CPU 时间统计、任务链表操作。
- **内存管理（MM）**：`<linux/mm.h>`、`<linux/slab.h>`，用于内存释放和 slab 分配器交互。
- **文件系统（VFS）**：`<linux/file.h>`、`<linux/fdtable.h>`、`<linux/fs_struct.h>`，用于关闭文件描述符和释放文件系统上下文。
- **进程间通信（IPC）**：`<linux/shm.h>`、`<linux/posix-timers.h>`，用于清理共享内存和定时器资源。
- **安全与审计**：`<linux/audit.h>`、`<linux/seccomp.h>`（通过 `seccomp_filter_release`），用于释放安全策略和审计上下文。
- **cgroup 与资源控制**：`<linux/cgroup.h>`、`<linux/resource.h>`，用于资源计数释放和限制检查。
- **跟踪与性能**：`<linux/perf_event.h>`、`<trace/events/sched.h>`，用于性能事件清理和调度跟踪点。
- **架构相关代码**：`<asm/mmu_context.h>`、`release_thread()` 弱符号，允许架构层定制线程释放逻辑。

## 5. 使用场景

- **进程正常退出**：当用户程序调用 `exit()` 或 `exit_group()` 系统调用时，内核通过此文件执行清理。
- **进程被信号终止**：如收到 `SIGKILL` 或 `SIGTERM` 后，内核调度退出路径。
- **线程退出**：POSIX 线程（通过 `pthread_exit()` 或线程函数返回）触发 `release_task()` 清理单个线程。
- **内核 Oops/panic 处理**：每次内核异常会递增 `oops_count`，用于监控系统稳定性。
- **僵尸进程回收**：父进程调用 `wait()` 系列系统调用后，内核最终通过 `release_task()` 释放僵尸进程的内核结构。
- **容器/命名空间退出**：在 PID 命名空间或 cgroup 中进程退出时，协调资源释放和通知机制。