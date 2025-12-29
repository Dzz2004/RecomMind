# scs.c

> 自动生成时间: 2025-10-25 16:22:19
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `scs.c`

---

# scs.c 技术文档

## 文件概述

`scs.c` 是 Linux 内核中实现 **Shadow Call Stack（SCS，影子调用栈）** 功能的核心文件。SCS 是一种安全机制，用于在支持的架构（如 ARM64）上防止函数返回地址被栈溢出等攻击篡改。该机制通过将函数返回地址存储在独立于常规内核栈的“影子栈”中，从而增强控制流完整性（CFI）。本文件负责 SCS 内存的分配、释放、初始化及资源管理。

## 核心功能

### 主要函数

| 函数名 | 功能描述 |
|--------|--------|
| `scs_alloc(int node)` | 为任务分配一个 SCS 区域，优先从每 CPU 缓存中获取，否则通过 `vmalloc` 分配 |
| `scs_free(void *s)` | 释放 SCS 区域，尝试缓存到每 CPU 缓存，否则异步释放 |
| `scs_init(void)` | 初始化 SCS 子系统，注册 CPU 热插拔清理回调 |
| `scs_prepare(struct task_struct *tsk, int node)` | 为新任务准备 SCS，调用 `scs_alloc` 并设置任务结构体中的 SCS 指针 |
| `scs_release(struct task_struct *tsk)` | 释放任务的 SCS，检查栈末尾魔数是否被破坏，并记录最大使用量（调试模式） |
| `scs_check_usage(struct task_struct *tsk)` | （仅在 `CONFIG_DEBUG_STACK_USAGE` 启用时）统计并报告 SCS 使用峰值 |

### 主要数据结构与宏

- `NR_CACHED_SCS`：每 CPU 缓存的 SCS 数量，设为 2，与 `VMAP_STACK` 的 `NR_CACHED_STACKS` 一致
- `scs_cache[NR_CACHED_SCS]`：每 CPU 的 SCS 缓存数组，用于快速重用已分配的 SCS
- `dynamic_scs_enabled`：静态键（static key），用于动态启用/禁用 SCS（仅当 `CONFIG_DYNAMIC_SCS` 启用）
- `SCS_SIZE`：单个 SCS 的大小（定义在头文件中）
- `SCS_END_MAGIC`：写入 SCS 末尾的魔数，用于检测栈溢出破坏

## 关键实现

### 1. 内存分配策略
- **缓存优先**：`__scs_alloc` 首先尝试从当前 CPU 的 `scs_cache` 中获取空闲 SCS，避免频繁调用 `vmalloc`。
- **非阻塞释放**：`scs_free` 在中断上下文也可安全调用，使用 `this_cpu_cmpxchg` 原子更新缓存；若缓存满，则调用 `vfree_atomic` 异步释放。
- **KASAN 集成**：分配时通过 `kasan_unpoison_vmalloc` 解毒，使用后通过 `kasan_poison_vmalloc` 毒化，防止非法访问。

### 2. 资源统计
- `__scs_account` 函数通过 `mod_node_page_state` 更新 `NR_KERNEL_SCS_KB` 统计项，跟踪每个 NUMA 节点上 SCS 内存使用量（以 KB 为单位）。

### 3. 安全校验
- **魔数保护**：每个 SCS 末尾写入 `SCS_END_MAGIC`，`scs_release` 时检查该值是否被覆盖，若损坏则触发 `WARN`。
- **使用量监控**：在 `CONFIG_DEBUG_STACK_USAGE` 模式下，`scs_check_usage` 扫描 SCS 中非零区域，估算实际使用深度，并全局记录历史最大值。

### 4. CPU 热插拔支持
- 通过 `cpuhp_setup_state` 注册 `scs_cleanup` 回调，在 CPU offline 时释放该 CPU 缓存中的 SCS，防止内存泄漏。

## 依赖关系

- **内存管理**：依赖 `vmalloc` 子系统进行非连续内存分配（`__vmalloc_node_range`、`vfree_atomic`）。
- **KASAN**：与内核地址消毒器（KASAN）深度集成，使用 `kasan_poison_vmalloc` / `kasan_unpoison_vmalloc` 管理虚拟内存毒化状态。
- **Per-CPU 机制**：使用 `DEFINE_PER_CPU` 和 `this_cpu_xchg`/`this_cpu_cmpxchg` 实现每 CPU 缓存。
- **CPU 热插拔**：依赖 `cpuhotplug.h` 提供的 CPU 状态管理接口。
- **配置选项**：
  - `CONFIG_SHADOW_CALL_STACK`：启用 SCS 功能
  - `CONFIG_DYNAMIC_SCS`：支持运行时动态开关 SCS
  - `CONFIG_DEBUG_STACK_USAGE`：启用 SCS 使用量调试统计

## 使用场景

- **任务创建/销毁**：在 `copy_process` 流程中调用 `scs_prepare` 为新内核线程或进程分配 SCS；在任务退出时通过 `scs_release` 释放。
- **中断与软中断上下文**：由于 `scs_free` 使用 `vfree_atomic`，可在中断上下文安全释放 SCS。
- **安全加固系统**：在启用 SCS 的 ARM64 系统中，编译器（如 Clang）会将函数返回地址写入 SCS 而非常规栈，内核需为此提供运行时支持。
- **内存调试**：配合 KASAN 和 `CONFIG_DEBUG_STACK_USAGE`，帮助开发者检测 SCS 溢出和内存使用异常。