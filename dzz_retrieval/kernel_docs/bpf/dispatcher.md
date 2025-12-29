# bpf\dispatcher.c

> 自动生成时间: 2025-10-25 12:10:06
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\dispatcher.c`

---

# `bpf/dispatcher.c` 技术文档

## 1. 文件概述

`bpf/dispatcher.c` 实现了 BPF（Berkeley Packet Filter）调度器（dispatcher）机制，其核心目标是通过生成多路分支的直接调用代码，避免在启用 retpoline（用于缓解 Spectre v2 攻击的间接跳转防护机制）时因间接调用带来的性能开销。该调度器通过劫持一个 trampoline 函数的 `__fentry__` 入口，动态生成包含多个 BPF 程序直接调用的跳转逻辑，从而将原本的间接调用转换为高效的直接调用。

## 2. 核心功能

### 主要数据结构
- `struct bpf_dispatcher`：BPF 调度器主结构体，包含：
  - `progs[BPF_DISPATCHER_MAX]`：最多支持 `BPF_DISPATCHER_MAX` 个 BPF 程序的注册项
  - `num_progs`：当前注册的程序数量
  - `image` 和 `rw_image`：分别指向只读可执行（RO+X）和可读写（RW）的代码页
  - `image_off`：用于双缓冲机制的偏移量
  - `mutex`：保护调度器状态的互斥锁
  - `ksym`：用于内核符号管理的 ksym 结构
- `struct bpf_dispatcher_prog`：调度器中每个 BPF 程序的注册项，包含：
  - `prog`：指向注册的 `struct bpf_prog`
  - `users`：引用计数

### 主要函数
- `bpf_dispatcher_find_prog()`：在调度器中查找指定 BPF 程序的注册项
- `bpf_dispatcher_find_free()`：查找空闲的注册槽位
- `bpf_dispatcher_add_prog()`：向调度器注册一个 BPF 程序（带引用计数）
- `bpf_dispatcher_remove_prog()`：从调度器注销一个 BPF 程序（引用计数减一，若为零则真正移除）
- `arch_prepare_bpf_dispatcher()`（弱符号）：架构相关函数，用于生成实际的多路分支机器码
- `bpf_dispatcher_prepare()`：准备调度器代码镜像，收集所有已注册 BPF 程序的入口地址
- `bpf_dispatcher_update()`：更新调度器的可执行代码，使用双缓冲机制避免执行时修改代码
- `bpf_dispatcher_change_prog()`：主入口函数，用于将一个 BPF 程序替换为另一个，并触发调度器代码更新

## 3. 关键实现

### 调度器工作原理
调度器维护一个最多包含 `BPF_DISPATCHER_MAX` 个 BPF 程序的列表。当有程序注册或注销时，调度器会重新生成一段包含所有有效程序直接调用的机器码（多路分支），并通过 trampoline 机制被调用。

### 双缓冲代码更新机制
为避免在 CPU 执行调度器代码时修改代码页导致崩溃，采用双缓冲策略：
- 调度器分配两个半页（共一页）的内存：`image`（RO+X）和 `rw_image`（RW）
- `image_off` 在 `0` 和 `PAGE_SIZE/2` 之间切换，指示当前活跃的半页
- 新代码先在 `rw_image` 的非活跃半页中生成，再通过 `bpf_arch_text_copy` 原子复制到 `image` 的对应位置
- 调用 `synchronize_rcu()` 确保所有 CPU 退出旧代码后再切换活跃半页

### 引用计数管理
每个注册的 BPF 程序通过 `refcount_t users` 管理引用计数，允许多次注册同一程序（仅增加引用计数），只有当引用归零时才真正从调度器中移除并释放程序。

### 架构无关与相关分离
- 架构无关逻辑（如程序管理、缓冲区切换）在本文件实现
- 架构相关代码生成由 `arch_prepare_bpf_dispatcher()` 实现（通常在 `arch/xxx/net/bpf_dispatcher.c` 中），若未实现则返回 `-ENOTSUPP`

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/hash.h>`：哈希辅助（虽未直接使用，但可能为未来扩展预留）
  - `<linux/bpf.h>` 和 `<linux/filter.h>`：BPF 核心数据结构（`bpf_prog`、`bpf_insn` 等）
  - `<linux/static_call.h>`：静态调用优化支持（用于 `__BPF_DISPATCHER_UPDATE` 宏）
- **内核模块依赖**：
  - BPF JIT 子系统：通过 `bpf_prog_pack_alloc()`、`bpf_jit_alloc_exec()` 分配可执行内存
  - 内存管理：使用 `bpf_prog_inc()`/`bpf_prog_put()` 管理 BPF 程序生命周期
  - RCU 机制：通过 `synchronize_rcu()` 实现安全的代码更新
  - 架构特定代码复制：依赖 `bpf_arch_text_copy()`（通常基于 `text_poke()`）

## 5. 使用场景

- **BPF 程序热替换**：当 attach 到 tracepoint、kprobe、perf event 等的 BPF 程序被替换时，通过 `bpf_dispatcher_change_prog()` 更新调度器，避免间接调用开销。
- **高性能 BPF 执行路径**：在需要极致性能的场景（如网络数据包处理、系统调用跟踪），调度器可显著提升 BPF 程序调用效率，尤其在启用 retpoline 的系统上。
- **多程序共享调度器**：多个相同类型的 BPF 程序（如多个 socket filter）可共享同一个调度器实例，统一管理直接调用入口。