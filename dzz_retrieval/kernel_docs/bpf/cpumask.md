# bpf\cpumask.c

> 自动生成时间: 2025-10-25 12:07:30
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\cpumask.c`

---

# `bpf/cpumask.c` 技术文档

## 1. 文件概述

`bpf/cpumask.c` 实现了 BPF（Berkeley Packet Filter）子系统中用于 CPU 掩码（cpumask）操作的一组内核函数（kfuncs）。该文件定义了一个引用计数的 `struct bpf_cpumask` 结构体，并提供了一系列安全、非阻塞的 BPF 可调用接口，用于创建、操作、查询和释放 cpumask 对象。这些接口专为 BPF 程序设计，确保与 BPF 验证器兼容，并通过 BPF 内存分配器实现 RCU 安全的内存管理。

## 2. 核心功能

### 数据结构

- **`struct bpf_cpumask`**  
  引用计数的 BPF cpumask 包装结构体：
  - `cpumask_t cpumask`：嵌入的实际 cpumask 位图。
  - `refcount_t usage`：引用计数器，归零时通过 RCU 回调释放内存。

### 主要函数（BPF kfuncs）

| 函数 | 功能 |
|------|------|
| `bpf_cpumask_create()` | 创建一个新的可变 BPF cpumask 对象 |
| `bpf_cpumask_acquire()` | 增加 cpumask 引用计数 |
| `bpf_cpumask_release()` | 减少引用计数，归零时异步释放内存 |
| `bpf_cpumask_first()` | 返回 cpumask 中第一个设置的 CPU 编号 |
| `bpf_cpumask_first_zero()` | 返回 cpumask 中第一个未设置的 CPU 编号 |
| `bpf_cpumask_first_and()` | 返回两个 cpumask 按位与后第一个设置的 CPU 编号 |
| `bpf_cpumask_set_cpu()` | 设置指定 CPU 位 |
| `bpf_cpumask_clear_cpu()` | 清除指定 CPU 位 |
| `bpf_cpumask_test_cpu()` | 测试指定 CPU 是否被设置 |
| `bpf_cpumask_test_and_set_cpu()` | 原子地测试并设置指定 CPU 位 |
| `bpf_cpumask_test_and_clear_cpu()` | 原子地测试并清除指定 CPU 位 |
| `bpf_cpumask_setall()` | 设置所有有效 CPU 位 |
| `bpf_cpumask_clear()` | 清除所有 CPU 位 |
| `bpf_cpumask_and()` | 对两个 cpumask 执行按位与操作并存入目标 |

> 所有函数均使用 `__bpf_kfunc` 标记，表示其为 BPF 程序可安全调用的内核函数。

## 3. 关键实现

### 内存管理与引用计数
- 使用 `bpf_mem_alloc` 子系统（`bpf_cpumask_ma`）进行非阻塞内存分配。
- `bpf_cpumask_release()` 在引用计数归零时调用 `bpf_mem_cache_free_rcu()`，确保在 RCU 宽限期后释放内存，避免并发访问问题。
- 释放前调用 `migrate_disable()`/`migrate_enable()` 禁用 CPU 迁移，保证 RCU 回调上下文安全。

### 与 cpumask 类型兼容性
- 显式嵌入 `cpumask_t`（而非 `cpumask_var_t`），避免因 `CONFIG_CPUMASK_OFFSTACK` 配置差异导致 BPF 验证器类型混淆。
- 通过 `BUILD_BUG_ON(offsetof(...) != 0)` 确保 `cpumask` 成员位于结构体起始位置，允许安全地将 `struct bpf_cpumask *` 强制转换为 `struct cpumask *`。

### CPU 有效性检查
- 所有涉及 CPU 编号的操作（如 `set_cpu`、`test_cpu` 等）均先调用 `cpu_valid(u32 cpu)` 验证 `cpu < nr_cpu_ids`，防止越界访问。

### BPF 验证器兼容性
- 所有导出函数使用 `__bpf_kfunc` 宏声明，确保被 BPF 验证器识别为合法调用目标。
- 参数类型设计（如接受 `const struct cpumask *`）允许 BPF 程序传入 `struct bpf_cpumask *` 指针，利用结构体布局兼容性。

## 4. 依赖关系

- **`<linux/bpf.h>`**：BPF 核心头文件，提供 kfunc 声明宏。
- **`<linux/bpf_mem_alloc.h>`**：BPF 内存分配器接口，用于 RCU 安全的对象分配与释放。
- **`<linux/cpumask.h>`**：标准 cpumask 操作函数（如 `cpumask_set_cpu`、`cpumask_first` 等）。
- **`<linux/refcount.h>`**：引用计数原语（通过 `refcount_t` 和相关操作）。
- **`<linux/btf.h>` / `<linux/btf_ids.h>`**：支持 BTF（BPF Type Format）类型信息生成，用于 kfunc 元数据。

## 5. 使用场景

- **BPF 程序中的 CPU 亲和性控制**：例如在调度器 BPF 程序中动态构造或修改任务的 CPU 亲和掩码。
- **资源隔离与负载均衡**：网络或跟踪 BPF 程序可根据系统状态动态生成 CPU 掩码，用于指导工作线程绑定。
- **安全策略实施**：限制某些 BPF 程序仅在特定 CPU 集合上执行。
- **与 BPF map 集成**：通过 `kptr`（内核指针）将 `struct bpf_cpumask` 存入 BPF map，实现跨 BPF 程序实例共享或持久化 cpumask 状态。
- **原子操作支持**：`test_and_set`/`test_and_clear` 等接口适用于需要无锁并发修改 cpumask 的场景。