# bpf\task_iter.c

> 自动生成时间: 2025-10-25 12:33:05
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\task_iter.c`

---

# `bpf/task_iter.c` 技术文档

## 1. 文件概述

`bpf/task_iter.c` 是 Linux 内核中 BPF（Berkeley Packet Filter）子系统的一部分，实现了基于 BPF 的任务（task）迭代器（iterator）。该文件提供了两种 BPF 迭代器：

- **`task` 迭代器**：用于遍历内核中的 `task_struct`（即进程/线程）对象。
- **`task_file` 迭代器**：用于遍历指定任务（或所有任务）打开的文件描述符及其对应的 `file` 对象。

这些迭代器允许 BPF 程序以安全、高效的方式遍历内核中的任务和文件资源，常用于系统监控、安全审计和性能分析等场景。

## 2. 核心功能

### 主要数据结构

- `struct bpf_iter_seq_task_common`  
  任务迭代器的通用上下文，包含 PID 命名空间、迭代类型（ALL/TID/PID）、目标 PID 和当前访问的 PID。

- `struct bpf_iter_seq_task_info`  
  用于 `task` 迭代器的私有数据，继承自 `bpf_iter_seq_task_common`，并记录当前线程 ID（TID）。

- `struct bpf_iter_seq_task_file_info`  
  用于 `task_file` 迭代器的私有数据，包含当前任务、TID 和当前文件描述符（fd）。

- `struct bpf_iter__task` / `struct bpf_iter__task_file`  
  BPF 程序的元数据上下文结构，分别用于向 BPF 程序传递 `task_struct` 或 `task_struct + file` 信息。

### 主要函数

- `task_seq_get_next()`  
  根据迭代类型（ALL/TID/TGID）获取下一个有效的 `task_struct`。

- `task_group_seq_get_next()`  
  专门用于遍历指定线程组（TGID）内的所有线程。

- `task_seq_start()` / `task_seq_next()` / `task_seq_stop()` / `task_seq_show()`  
  实现标准 `seq_file` 接口，用于 `task` 迭代器的序列化遍历。

- `task_file_seq_get_next()`  
  遍历当前任务的文件描述符表，返回下一个有效的 `file` 对象。

- `task_file_seq_start()` / `task_file_seq_next()`  
  实现 `task_file` 迭代器的 `seq_file` 接口。

- `bpf_iter_attach_task()`  
  解析 BPF 迭代器链接时传入的参数（如 TID、PID 或 pidfd），初始化迭代器上下文。

- `__task_seq_show()` / `DEFINE_BPF_ITER_FUNC(task, ...)`  
  调用关联的 BPF 程序，并传入当前任务（或任务+文件）作为上下文。

## 3. 关键实现

### 迭代类型支持

迭代器支持三种模式：
- **`BPF_TASK_ITER_ALL`**：遍历命名空间中所有任务（按 PID 递增顺序）。
- **`BPF_TASK_ITER_TID`**：仅遍历指定线程 ID（TID）对应的任务。
- **`BPF_TASK_ITER_TGID`**：遍历指定线程组 ID（TGID，即主线程 PID）下的所有线程。

### 安全遍历机制

- 使用 `rcu_read_lock()` 保护对任务和 PID 哈希表的访问。
- 通过 `get_pid_task()` 和 `put_task_struct()` 管理任务引用计数，防止遍历过程中任务被释放。
- 在 `task_file` 迭代器中使用 `task_lookup_next_fdget_rcu()` 安全地遍历文件描述符表。

### 文件去重逻辑

在 `task_file` 迭代器中，若启用 `skip_if_dup_files`（实际在 `task_file_seq_get_next` 中硬编码为 `true`），会跳过与线程组 leader 共享 `files` 结构的非主线程，避免重复遍历同一组文件描述符。

### PID 命名空间支持

所有 PID 查找均通过 `find_pid_ns()` 和 `pid_nr_ns()` 在指定的 `pid_namespace` 中进行，确保容器环境下的正确性。

### BPF 程序回调

通过 `bpf_iter_run_prog()` 在每次 `show` 阶段调用用户态加载的 BPF 程序，传递当前任务（或任务+文件）作为上下文。`stop` 阶段也会调用一次 BPF 程序（`in_stop=true`），用于清理或最终处理。

## 4. 依赖关系

- **内核核心模块**：
  - `<linux/pid_namespace.h>`：PID 命名空间管理。
  - `<linux/sched.h>`（隐式）：`task_struct`、`next_thread()`、`thread_group_leader()` 等任务操作。
  - `<linux/file.h>` / `<linux/fdtable.h>`：文件描述符表遍历。
  - `<linux/bpf.h>` / `<linux/filter.h>`：BPF 核心框架和迭代器接口。
  - `<linux/bpf_mem_alloc.h>`：BPF 内存分配。
  - `"mmap_unlock_work.h"`：可能用于处理 mmap 锁相关上下文（具体用途需结合其他代码）。

- **BPF 子系统**：
  - 依赖 `bpf_iter_get_info()` 和 `bpf_iter_run_prog()` 等通用迭代器运行时支持。
  - 使用 `DEFINE_BPF_ITER_FUNC` 宏注册 `task` 类型的 BPF 迭代器。

## 5. 使用场景

- **系统监控工具**：如 `bpftool` 可通过 `task` 迭代器收集所有进程的内存、CPU 或安全上下文信息。
- **安全策略实施**：BPF 程序可遍历任务并检查其凭证（cred）、命名空间或打开的文件，实现运行时策略。
- **资源审计**：`task_file` 迭代器可用于审计进程打开的文件、套接字或设备，检测异常行为。
- **容器环境调试**：在容器（PID namespace）中精确遍历特定进程组的任务和资源。
- **性能分析**：高效遍历任务结构，避免传统 `/proc` 文件系统解析开销。