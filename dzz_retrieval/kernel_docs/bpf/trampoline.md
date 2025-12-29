# bpf\trampoline.c

> 自动生成时间: 2025-10-25 12:36:55
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\trampoline.c`

---

# bpf/trampoline.c 技术文档

## 1. 文件概述

`bpf/trampoline.c` 是 Linux 内核 BPF（Berkeley Packet Filter）子系统中用于实现 **BPF Trampoline（跳板）机制** 的核心文件。该机制主要用于支持 **FENTRY/FEXIT**、**MODIFY_RETURN** 以及 **LSM（Linux Security Module）** 类型的 BPF 程序，通过动态生成或修改内核函数入口处的跳转代码（trampoline），实现对目标函数的无侵入式拦截与增强。该文件负责管理 trampoline 的生命周期、哈希表存储、与 ftrace 的集成、以及 JIT 生成的 trampoline 镜像的内存管理。

## 2. 核心功能

### 主要数据结构
- `struct bpf_trampoline`：表示一个 trampoline 实例，包含目标函数地址、程序链表、引用计数、互斥锁等。
- `struct bpf_tramp_image`：表示 JIT 生成的 trampoline 机器码镜像，包含代码指针、大小、ksym 信息及引用计数。
- `bpf_trampoline_table[]`：全局哈希表，用于根据函数地址（key）快速查找或创建对应的 trampoline。

### 主要函数
- `bpf_trampoline_lookup(u64 key)`：根据目标函数地址查找或创建 trampoline 实例。
- `bpf_trampoline_update(struct bpf_trampoline *tr, bool lock_direct_mutex)`：更新 trampoline 的机器码以反映附加的 BPF 程序变更（声明但未在片段中定义）。
- `register_fentry()` / `unregister_fentry()` / `modify_fentry()`：封装对 ftrace direct 或 `bpf_arch_text_poke` 的调用，用于安装/卸载/修改跳转指令。
- `bpf_trampoline_get_progs()`：收集附加到 trampoline 上的所有 BPF 程序链接（按类型分类）。
- `bpf_tramp_image_free()` 及相关 RCU/工作队列回调：安全释放 JIT 生成的 trampoline 镜像内存。
- `bpf_prog_has_trampoline()`：判断给定 BPF 程序是否需要 trampoline 机制。
- `bpf_image_ksym_*()`：管理 trampoline 镜像的内核符号（ksym）注册与 perf 事件通知。

### 静态变量与常量
- `TRAMPOLINE_HASH_BITS` / `TRAMPOLINE_TABLE_SIZE`：定义 trampoline 哈希表大小（1024 项）。
- `trampoline_mutex`：保护全局 trampoline 哈希表的互斥锁。
- `bpf_extension_verifier_ops` / `bpf_extension_prog_ops`：占位符操作结构体。

### ftrace 集成回调（条件编译）
- `bpf_tramp_ftrace_ops_func()`：处理 ftrace direct 模式下与 IP 修改共享相关的命令（`FTRACE_OPS_CMD_*`），协调 trampoline 更新。

## 3. 关键实现

### Trampoline 哈希表管理
- 使用 `hash_64(key, TRAMPOLINE_HASH_BITS)` 将目标函数地址映射到 `trampoline_table` 的桶中。
- `trampoline_mutex` 保护整个哈希表的查找、创建和插入操作，确保线程安全。
- 每个 `bpf_trampoline` 实例通过 `refcount_t refcnt` 管理生命周期。

### 与 ftrace/direct calls 集成
- 在支持 `CONFIG_DYNAMIC_FTRACE_WITH_DIRECT_CALLS` 的架构上，优先使用 ftrace 的 direct call 机制安装跳转。
- `bpf_tramp_ftrace_ops_func()` 处理 ftrace 框架在启用 IP 修改共享时的特殊交互，通过返回 `-EAGAIN` 触发重试以协调 trampoline 更新。
- 锁定顺序：`tr->mutex` → ftrace 的 `direct_mutex` → `ftrace_lock`，使用 `mutex_trylock` 避免死锁。

### Trampoline 镜像生命周期管理
- 使用 **三层延迟释放机制** 确保安全回收 JIT 生成的代码页：
  1. **Per-CPU 引用计数 (`percpu_ref`)**：跟踪运行中的 trampoline 使用。
  2. **RCU (`call_rcu_tasks`)**：等待所有可能执行该代码的 CPU 上下文完成。
  3. **工作队列 (`schedule_work`)**：在进程上下文中执行最终的内存释放（包括 `arch_free_bpf_trampoline` 和 ksym 注销）。
- 通过 `perf_event_ksymbol` 向用户态 perf 工具通知 BPF trampoline 镜像的加载/卸载。

### 程序分类与收集
- BPF 程序按类型（`BPF_TRAMP_FENTRY`, `BPF_TRAMP_FEXIT`, `BPF_TRAMP_MODIFY_RETURN`, `BPF_TRAMP_FENTRY_OPS`）存储在 `tr->progs_hlist[4]` 中。
- `bpf_trampoline_get_progs()` 遍历这些链表，构建 `bpf_tramp_links` 结构供 JIT 编译器使用，并检查是否需要传递函数 IP 参数。

## 4. 依赖关系

- **BPF 核心**：依赖 `bpf.h`, `filter.h`, `bpf_verifier.h` 提供程序模型、验证器和通用操作。
- **ftrace 子系统**：依赖 `ftrace.h` 实现函数跟踪和 direct call 注册（`register_ftrace_direct` 等）。
- **BTF (BPF Type Format)**：依赖 `btf.h` 获取内核函数签名信息（虽未直接使用，但 trampoline 机制依赖 BTF 信息）。
- **内存管理**：依赖 `rcupdate_trace.h`, `rcupdate_wait.h` 实现安全的延迟释放。
- **架构相关代码**：依赖 `bpf_arch_text_poke()`（在 `arch/` 目录下实现）进行非 ftrace 路径的代码修补。
- **性能事件**：依赖 `perf_event.h` 发送 KSYMBOL 事件。
- **LSM 框架**：依赖 `bpf_lsm.h` 支持 LSM 类型的 BPF 程序。
- **静态调用优化**：依赖 `static_call.h`（虽未直接使用，但相关机制可能被优化）。

## 5. 使用场景

- **FENTRY/FEXIT 程序**：当用户附加 `BPF_TRACE_FENTRY` 或 `BPF_TRACE_FEXIT` 类型的 BPF 程序到内核函数时，内核为该函数创建或复用一个 trampoline，动态生成包含调用 BPF 程序逻辑的入口/出口桩代码。
- **MODIFY_RETURN 程序**：用于拦截并修改目标函数的返回值，同样通过 trampoline 机制实现。
- **LSM 程序**：`BPF_LSM_MAC` 类型的程序通过 trampoline 挂接到 LSM hooks。
- **动态更新**：当附加到同一函数的 BPF 程序集合发生变化（添加/删除）时，触发 `bpf_trampoline_update()` 重新生成 trampoline 代码。
- **资源回收**：当所有引用 trampoline 的 BPF 程序被 detach 且无执行实例后，通过 RCU 和工作队列安全释放其 JIT 代码和相关资源。