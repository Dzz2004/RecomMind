# bpf\bpf_task_storage.c

> 自动生成时间: 2025-10-25 12:02:38
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\bpf_task_storage.c`

---

# bpf_task_storage.c 技术文档

## 文件概述

`bpf_task_storage.c` 实现了 BPF（Berkeley Packet Filter）任务本地存储（task-local storage）机制，允许 BPF 程序为内核中的 `task_struct`（即进程/线程）关联自定义的私有数据。该机制基于 BPF 本地存储（`bpf_local_storage`）框架，为每个任务提供键值对形式的存储能力，支持通过 `pidfd` 或直接通过 `task_struct` 指针进行数据的查找、更新和删除操作。该功能主要用于 eBPF 程序在追踪、监控或安全策略中为特定任务附加元数据。

## 核心功能

### 主要数据结构
- `DEFINE_BPF_STORAGE_CACHE(task_cache)`：为任务存储定义专用的内存缓存，用于高效分配/释放存储节点。
- `bpf_task_storage_busy`（per-CPU 变量）：用于实现轻量级的 per-CPU 自旋锁，防止递归或并发访问导致的死锁。

### 主要函数

#### 存储访问控制
- `bpf_task_storage_lock()` / `bpf_task_storage_unlock()`：获取/释放任务存储的 per-CPU 锁，禁止 CPU 迁移以保证原子性。
- `bpf_task_storage_trylock()`：尝试获取锁，若当前 CPU 已持有锁则失败，用于支持递归调用场景。

#### 存储操作接口
- `task_storage_ptr()`：返回 `task_struct` 中 `bpf_storage` 字段的地址，供通用本地存储框架使用。
- `task_storage_lookup()`：在指定任务中查找与给定 BPF map 关联的存储数据。
- `bpf_task_storage_free()`：在任务销毁时释放其所有 BPF 本地存储数据。

#### BPF Map 操作方法（通过 pidfd）
- `bpf_pid_task_storage_lookup_elem()`：通过 `pidfd`（文件描述符形式的进程 ID）查找任务存储数据。
- `bpf_pid_task_storage_update_elem()`：通过 `pidfd` 更新任务存储数据。
- `bpf_pid_task_storage_delete_elem()`：通过 `pidfd` 删除任务存储数据。

#### BPF 辅助函数（Helper Functions）
- `bpf_task_storage_get()` / `bpf_task_storage_get_recur()`：BPF 程序调用的辅助函数，用于获取或创建任务存储数据；`_recur` 版本支持在已持有锁的上下文中安全调用。
- `bpf_task_storage_delete()` / `bpf_task_storage_delete_recur()`：BPF 程序调用的辅助函数，用于删除任务存储数据；同样提供递归安全版本。

#### BPF Map 操作结构
- `task_storage_map_alloc()` / `task_storage_map_free()`：分配和释放任务存储类型的 BPF map。
- `task_storage_map_ops`：定义该类型 BPF map 的操作方法集合，包括分配、释放、查找等。

## 关键实现

### 1. 任务存储的组织结构
每个 `task_struct` 包含一个 `bpf_storage` 字段（类型为 `struct bpf_local_storage __rcu *`），指向一个通用的本地存储结构。该结构内部维护一个哈希表，将 BPF map 与对应的存储数据（`bpf_local_storage_data`）关联起来。

### 2. 并发控制机制
- 使用 per-CPU 计数器 `bpf_task_storage_busy` 实现轻量级锁，避免传统自旋锁开销。
- `migrate_disable()` / `migrate_enable()` 禁用 CPU 迁移，确保临界区在同一个 CPU 上执行。
- 提供“尝试锁”机制（`trylock`），用于支持 BPF 辅助函数在可能已持有锁的上下文（如 tracepoint 回调）中安全调用，避免死锁。

### 3. 生命周期管理
- 任务销毁时（`bpf_task_storage_free`），在 RCU 保护下安全释放所有关联的 BPF 存储数据。
- 存储数据的分配使用 `GFP_ATOMIC` 标志，确保在原子上下文（如中断、软中断）中安全分配内存。

### 4. pidfd 支持
通过 `pidfd_get_pid()` 将用户空间传入的 `pidfd`（文件描述符）转换为内核 `pid` 结构，再通过 `pid_task()` 获取对应的 `task_struct`，从而实现基于进程 ID 的跨进程存储访问。

### 5. 递归安全设计
提供两套辅助函数（普通版和 `_recur` 版），普通版总是加锁，而 `_recur` 版先尝试加锁，若失败则以“非忙”（`nobusy`）模式操作，避免在已持有锁的上下文中死锁。

## 依赖关系

- **核心依赖**：
  - `linux/bpf_local_storage.h`：提供通用的 BPF 本地存储框架（`bpf_local_storage_*` 系列函数）。
  - `linux/pid.h` / `linux/sched.h`：提供 `pidfd_get_pid()`、`pid_task()` 和 `task_struct` 相关操作。
  - `linux/rcupdate_trace.h`：提供 `bpf_rcu_lock_held()` 用于验证 RCU 上下文。
  - `linux/bpf.h` / `linux/filter.h`：BPF 核心基础设施和辅助函数注册机制。

- **内存管理**：
  - 使用 `DEFINE_BPF_STORAGE_CACHE` 宏创建专用 SLAB 缓存，提升内存分配效率。
  - 依赖 RCU 机制实现无锁读取和安全延迟释放。

- **BPF 子系统**：
  - 通过 `BPF_CALL_*` 宏注册 BPF 辅助函数，供 eBPF 字节码调用。
  - 实现 `bpf_map_ops` 接口，使任务存储 map 可通过 BPF map 系统调用操作。

## 使用场景

1. **进程追踪与监控**：eBPF 程序可在进程创建/执行/退出时为其附加自定义元数据（如安全标签、资源使用统计），并通过 `bpf_task_storage_get()` 在后续事件中快速访问。

2. **安全策略实施**：LSM（Linux Security Module）或自定义安全模块可通过 BPF 为任务关联策略数据，在系统调用或资源访问时进行策略检查。

3. **性能分析**：性能分析工具（如 BCC、bpftrace）可利用该机制为每个线程存储调用栈、延迟信息等上下文数据。

4. **跨进程数据共享**：通过 `pidfd` 机制，一个进程可安全地访问另一个进程的 BPF 存储数据（需具备相应权限），适用于调试器、监控代理等场景。

5. **内核子系统扩展**：其他内核模块可通过注册 BPF 程序，在任务生命周期中动态注入和查询数据，而无需修改核心调度器或进程管理代码。