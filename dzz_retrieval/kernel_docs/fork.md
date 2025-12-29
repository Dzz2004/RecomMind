# fork.c

> 自动生成时间: 2025-10-25 13:30:07
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `fork.c`

---

# fork.c 技术文档

## 1. 文件概述

`fork.c` 是 Linux 内核中实现进程创建（fork）系统调用的核心源文件。该文件包含了创建新进程所需的所有辅助例程，负责复制父进程的资源（如内存、文件描述符、信号处理等）以生成子进程。虽然 fork 逻辑本身概念简单，但其涉及的内存管理（尤其是写时复制 COW 机制）极为复杂，实际内存页的复制由 `mm/memory.c` 中的 `copy_page_range()` 等函数处理。

## 2. 核心功能

### 主要全局变量
- `total_forks`: 累计系统自启动以来创建的进程总数
- `nr_threads`: 当前系统中的线程总数（不包括 idle 线程）
- `max_threads`: 可配置的线程数量上限（默认为 `FUTEX_TID_MASK`）
- `process_counts`: 每 CPU 的进程计数器（per-CPU 变量）
- `tasklist_lock`: 保护任务链表的读写锁（全局任务列表的同步原语）

### 关键辅助函数
- `nr_processes()`: 计算系统中所有进程的总数（聚合各 CPU 的 `process_counts`）
- `arch_release_task_struct()`: 架构相关的 task_struct 释放钩子（弱符号，默认为空）
- `alloc_task_struct_node()` / `free_task_struct()`: 分配/释放 `task_struct` 结构（基于 slab 分配器）
- `alloc_thread_stack_node()` / `thread_stack_delayed_free()`: 分配/延迟释放线程内核栈（支持 `CONFIG_VMAP_STACK`）

### 核心数据结构
- `resident_page_types[]`: 用于内存统计的页面类型名称映射数组
- `vm_stack`: 用于 RCU 延迟释放的虚拟内存栈封装结构
- `cached_stacks[NR_CACHED_STACKS]`: 每 CPU 的内核栈缓存（减少频繁 vmalloc/vfree 开销）

## 3. 关键实现

### 进程/线程计数管理
- 使用 per-CPU 变量 `process_counts` 避免全局锁竞争
- 全局计数器 `nr_threads` 和 `total_forks` 由 `tasklist_lock` 保护
- `nr_processes()` 通过遍历所有可能的 CPU 聚合计数

### 内核栈分配策略（`CONFIG_VMAP_STACK`）
- **缓存机制**：每个 CPU 缓存最多 2 个已释放的栈（`NR_CACHED_STACKS`），减少 TLB 刷新和 vmalloc 开销
- **内存分配**：
  - 优先从本地缓存获取栈
  - 缓存未命中时使用 `__vmalloc_node_range()` 分配连续虚拟地址空间
  - 显式禁用 `__GFP_ACCOUNT`（因后续手动进行 memcg 计费）
- **安全清理**：
  - 重用栈时清零内存（`memset(stack, 0, THREAD_SIZE)`）
  - KASAN 消毒（`kasan_unpoison_range`）和标签重置
- **延迟释放**：
  - 通过 RCU 机制延迟释放栈（`call_rcu`）
  - 释放时尝试回填缓存，失败则直接 `vfree`

### 内存控制组（memcg）集成
- 手动对栈的每个物理页进行 memcg 计费（`memcg_kmem_charge_page`）
- 计费失败时回滚已计费页面（`memcg_kmem_uncharge_page`）
- 确保内核栈内存纳入 cgroup 内存限制

### 锁与同步
- `tasklist_lock` 作为全局任务列表的保护锁（读写锁）
- 提供 `lockdep_tasklist_lock_is_held()` 供 RCU 锁验证使用
- RCU 用于安全延迟释放内核栈资源

## 4. 依赖关系

### 内核子系统依赖
- **内存管理 (MM)**：`<linux/mm.h>`, `<linux/vmalloc.h>`, `<linux/memcontrol.h>`
- **调度器 (Scheduler)**：`<linux/sched/*.h>`, 任务状态和 CPU 绑定
- **安全模块**：`<linux/security.h>`, `<linux/capability.h>`, `<linux/seccomp.h>`
- **命名空间**：`<linux/nsproxy.h>`（UTS, IPC, PID, 网络等）
- **文件系统**：`<linux/fs.h>`, `<linux/fdtable.h>`（文件描述符复制）
- **跟踪与调试**：`<trace/events/sched.h>`, `<linux/ftrace.h>`, KASAN/KMSAN

### 架构相关依赖
- `<asm/pgalloc.h>`：页表分配
- `<asm/mmu_context.h>`：MMU 上下文切换
- `<asm/tlbflush.h>`：TLB 刷新操作
- 架构特定的 `THREAD_SIZE` 和栈对齐要求

### 配置选项依赖
- `CONFIG_VMAP_STACK`：启用虚拟内存分配内核栈
- `CONFIG_PROVE_RCU`：RCU 锁验证支持
- `CONFIG_ARCH_TASK_STRUCT_ALLOCATOR`：架构自定义 task_struct 分配器
- `CONFIG_MEMCG_KMEM`：内核内存 cgroup 支持

## 5. 使用场景

### 进程创建路径
- **系统调用入口**：`sys_fork()`, `sys_vfork()`, `sys_clone()` 最终调用 `_do_fork()`
- **内核线程创建**：`kthread_create()` 通过 `kernel_thread()` 触发 fork 逻辑
- **容器/命名空间初始化**：新 PID/UTS/IPC 命名空间创建时伴随进程 fork

### 资源复制关键点
- **内存描述符 (mm_struct)**：通过 `dup_mm()` 复制地址空间（COW 页表）
- **文件描述符表**：`dup_fd()` 复制打开文件表
- **信号处理**：复制信号掩码和处理函数
- **POSIX 定时器/异步 I/O**：复制相关上下文（如 `aio`, `posix-timers`）

### 特殊场景处理
- **写时复制优化**：避免物理内存立即复制，提升 fork 性能
- **OOM Killer 集成**：在内存不足时参与进程选择
- **审计与监控**：通过 `audit_alloc()` 和 `proc` 文件系统暴露进程信息
- **实时性保障**：RT 任务 fork 时保持调度策略和优先级