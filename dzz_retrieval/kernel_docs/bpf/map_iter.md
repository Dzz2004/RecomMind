# bpf\map_iter.c

> 自动生成时间: 2025-10-25 12:18:18
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\map_iter.c`

---

# `bpf/map_iter.c` 技术文档

## 1. 文件概述

`bpf/map_iter.c` 是 Linux 内核 BPF（Berkeley Packet Filter）子系统中的一个核心文件，用于实现对 BPF map 的迭代器（iterator）支持。该文件提供了两种类型的 BPF 迭代器：

- **`bpf_map` 迭代器**：用于遍历系统中所有已注册的 BPF map。
- **`bpf_map_elem` 迭代器**：用于遍历指定 BPF map 中的所有键值对元素。

此外，该文件还定义了一个 BPF kfunc（内核函数）`bpf_map_sum_elem_count`，用于安全地获取 per-CPU 类型 map 的总元素数量。整个实现基于内核的 seq_file 机制和 BPF 迭代器框架，允许用户空间通过 BPF 程序安全、高效地访问 map 元数据或内容。

## 2. 核心功能

### 主要数据结构

- **`struct bpf_iter_seq_map_info`**  
  用于在 seq_file 迭代过程中保存当前遍历的 map ID。

- **`struct bpf_iter__bpf_map`**  
  BPF 程序上下文结构，作为 `bpf_map` 迭代器的元数据传递给 BPF 程序，包含指向当前 `bpf_map` 的指针。

- **`struct bpf_iter__bpf_map_elem`**（隐式定义）  
  由 `DEFINE_BPF_ITER_FUNC(bpf_map_elem, ...)` 宏生成，用于 `bpf_map_elem` 迭代器，包含 `map`、`key` 和 `value` 指针。

- **`bpf_map_seq_ops`**  
  实现 `seq_operations` 接口，用于遍历所有 BPF map。

- **`bpf_map_reg_info` 与 `bpf_map_elem_reg_info`**  
  分别注册 `bpf_map` 和 `bpf_map_elem` 两种 BPF 迭代器目标。

- **`bpf_map_iter_kfunc_set`**  
  注册 BPF kfunc `bpf_map_sum_elem_count`，供 BPF 程序调用。

### 主要函数

- **`bpf_map_seq_start/next/stop/show`**  
  实现 seq_file 接口，用于遍历所有 BPF map。

- **`__bpf_map_seq_show`**  
  调用关联的 BPF 程序处理当前 map。

- **`bpf_iter_attach_map` / `bpf_iter_detach_map`**  
  在 `bpf_map_elem` 迭代器 attach/detach 时管理 map 引用计数，并验证访问权限。

- **`bpf_iter_map_show_fdinfo` / `bpf_iter_map_fill_link_info`**  
  提供迭代器链接的调试信息和用户空间查询接口。

- **`bpf_map_sum_elem_count`**  
  BPF kfunc，安全累加 per-CPU map 的元素计数。

- **`bpf_map_iter_init`**  
  模块初始化函数，注册两个 BPF 迭代器目标。

- **`init_subsystem`**  
  注册 BPF kfunc 到 BTF 系统。

## 3. 关键实现

### BPF Map 全局遍历（`bpf_map` 迭代器）

- 使用 `bpf_map_get_curr_or_next(&map_id)` 按 ID 顺序遍历所有 map。
- `seq_file` 的 `start`/`next` 函数通过递增 `map_id` 实现迭代。
- 每次访问 map 后通过 `bpf_map_put()` 释放引用，确保资源安全。
- 在 `stop` 阶段，若 `v == NULL`（表示迭代结束），会再次调用 `__bpf_map_seq_show` 并传入 `in_stop=true`，用于通知 BPF 程序迭代已结束。

### BPF Map 元素遍历（`bpf_map_elem` 迭代器）

- 通过 `bpf_iter_attach_map` 从用户传入的 `map_fd` 获取 map 实例。
- 支持的 map 类型包括：`HASH`、`LRU_HASH`、`ARRAY` 及其 per-CPU 变体。
- 在 attach 时验证 BPF 程序对 key/value 的最大访问尺寸是否超过 map 定义的尺寸，防止越界访问。
- 对 per-CPU map，value 大小计算为 `round_up(value_size, 8) * num_possible_cpus()`，符合内核 per-CPU 布局。

### BPF kfunc：`bpf_map_sum_elem_count`

- 仅当 `map->elem_count` 非空时（通常由支持计数的 map 类型提供）才进行累加。
- 使用 `for_each_possible_cpu` 遍历所有 CPU，通过 `per_cpu_ptr` 安全读取 per-CPU 计数。
- 使用 `READ_ONCE` 避免编译器优化导致的非原子读取问题。
- 标记为 `KF_TRUSTED_ARGS`，表示参数来自内核可信上下文。

### BTF 与类型安全

- 通过 `BTF_ID_LIST_GLOBAL_SINGLE` 获取 `struct bpf_map` 的 BTF ID，用于类型验证。
- `ctx_arg_info` 中使用 `PTR_TO_BTF_ID_OR_NULL | PTR_TRUSTED` 确保传递给 BPF 程序的 map 指针类型安全且可信。
- kfunc 通过 `BTF_SET8` 注册，并关联 `KFUNC` 类型标志。

## 4. 依赖关系

- **`<linux/bpf.h>` / `<linux/filter.h>`**：BPF 核心接口和程序执行框架。
- **`<linux/fs.h>`**：seq_file 机制，用于实现迭代器输出。
- **`<linux/btf_ids.h>`**：BTF（BPF Type Format）支持，用于类型验证和 kfunc 注册。
- **`bpf_map_get_curr_or_next` / `bpf_map_put`**：来自 BPF map 管理子系统（`kernel/bpf/syscall.c` 等）。
- **`bpf_iter_get_info` / `bpf_iter_run_prog`**：BPF 迭代器运行时支持（`kernel/bpf/bpf_iter.c`）。
- **`register_btf_kfunc_id_set`**：BPF kfunc 注册机制。

## 5. 使用场景

- **系统监控与调试**：用户可通过 BPF 程序遍历所有 BPF map，收集其类型、ID、引用计数等元信息，用于性能分析或调试。
- **Map 内容导出**：通过 `bpf_map_elem` 迭代器，用户空间可安全遍历指定 map 的所有键值对，实现 map 数据导出（如 `bpftool map dump` 的底层机制）。
- **安全审计**：结合 BPF 程序，可对 map 访问模式进行监控或策略检查。
- **Per-CPU 统计聚合**：BPF 程序可调用 `bpf_map_sum_elem_count` 快速获取 per-CPU map 的总元素数，用于指标采集。
- **内核自省**：作为 BPF 迭代器框架的一部分，为内核提供标准化的 map 遍历能力，避免直接暴露内部数据结构。