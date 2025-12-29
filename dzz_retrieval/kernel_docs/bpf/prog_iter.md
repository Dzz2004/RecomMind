# bpf\prog_iter.c

> 自动生成时间: 2025-10-25 12:27:31
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\prog_iter.c`

---

# bpf/prog_iter.c 技术文档

## 1. 文件概述

`bpf/prog_iter.c` 实现了 BPF（Berkeley Packet Filter）程序迭代器（iterator）功能，用于遍历系统中所有已加载的 BPF 程序。该文件通过 Linux 内核的 seq_file 机制暴露 BPF 程序列表，并支持通过 BPF 迭代器程序（BPF iterator program）对每个 BPF 程序进行自定义处理。此功能是 BPF 迭代器框架的一部分，允许用户空间通过 BPF 程序安全、高效地遍历内核中的 BPF 对象。

## 2. 核心功能

### 数据结构

- `struct bpf_iter_seq_prog_info`  
  用于 seq_file 私有数据，保存当前遍历的 BPF 程序 ID（`prog_id`）。

- `struct bpf_iter__bpf_prog`  
  BPF 迭代器上下文结构体，包含元数据指针（`meta`）和当前 BPF 程序指针（`prog`），供 BPF 程序访问。

### 主要函数

- `bpf_prog_seq_start()`  
  seq_file 的 `start` 回调，获取第一个或指定位置的 BPF 程序。

- `bpf_prog_seq_next()`  
  seq_file 的 `next` 回调，获取下一个 BPF 程序并更新 `prog_id`。

- `bpf_prog_seq_show()`  
  seq_file 的 `show` 回调，在遍历过程中调用关联的 BPF 迭代器程序处理当前 BPF 程序。

- `bpf_prog_seq_stop()`  
  seq_file 的 `stop` 回调，释放当前 BPF 程序引用，或在遍历结束时触发 BPF 程序的清理逻辑。

- `__bpf_prog_seq_show()`  
  内部辅助函数，封装 BPF 迭代器程序的执行逻辑，支持正常遍历和停止阶段调用。

- `bpf_prog_iter_init()`  
  模块初始化函数，注册 BPF 程序迭代器目标到 BPF 迭代器框架。

### 全局对象

- `bpf_prog_seq_ops`  
  `seq_operations` 结构体实例，定义 seq_file 的操作方法。

- `bpf_prog_seq_info`  
  `bpf_iter_seq_info` 结构体实例，描述迭代器的 seq_file 配置。

- `bpf_prog_reg_info`  
  `bpf_iter_reg` 结构体实例，用于向 BPF 迭代器子系统注册 "bpf_prog" 目标。

- `btf_bpf_prog_id`  
  BTF（BPF Type Format）ID 列表，用于类型安全验证。

## 3. 关键实现

- **遍历机制**：  
  使用 `bpf_prog_get_curr_or_next(&info->prog_id)` 实现按 `prog_id` 顺序遍历所有 BPF 程序。该函数在内核 BPF 子系统中维护一个全局 BPF 程序哈希表，支持根据 ID 查找或获取下一个有效程序。

- **引用计数管理**：  
  在 `start` 和 `next` 中获取 BPF 程序时增加引用计数，在 `stop` 中调用 `bpf_prog_put()` 减少引用，确保程序在遍历期间不会被释放。

- **BPF 迭代器集成**：  
  通过 `DEFINE_BPF_ITER_FUNC(bpf_prog, ...)` 宏定义 BPF 迭代器辅助函数，并在 `show` 阶段调用 `bpf_iter_run_prog()` 执行用户提供的 BPF 程序，传入当前 `bpf_prog` 对象。

- **上下文类型安全**：  
  利用 BTF 类型信息（`btf_bpf_prog_id`）和 `ctx_arg_info` 配置，确保 BPF 程序访问 `prog` 字段时类型正确，支持 `PTR_TO_BTF_ID_OR_NULL` 验证。

- **双阶段调用支持**：  
  `__bpf_prog_seq_show()` 支持 `in_stop` 参数，在 `stop` 阶段（`v == NULL`）仍可调用 BPF 程序进行资源清理或最终处理。

## 4. 依赖关系

- **BPF 核心子系统**：  
  依赖 `bpf_prog_get_curr_or_next()`、`bpf_prog_put()`、`bpf_iter_run_prog()` 等函数，位于 `kernel/bpf/` 目录。

- **seq_file 机制**：  
  使用 Linux 内核的 `seq_file` 接口（`<linux/fs.h>`）实现顺序遍历。

- **BTF（BPF Type Format）**：  
  通过 `BTF_ID_LIST` 和 `BTF_ID` 宏注册 `struct bpf_prog` 的类型 ID，用于 BPF 验证器的类型检查。

- **BPF 迭代器框架**：  
  依赖 `bpf_iter_reg_target()` 注册迭代器目标，该框架定义在 `include/linux/bpf.h` 和 `kernel/bpf/iter.c` 中。

## 5. 使用场景

- **用户空间监控工具**：  
  用户可通过挂载 BPF 迭代器程序（如使用 `bpftool iter`）遍历所有 BPF 程序，收集统计信息、调试状态或进行安全审计。

- **内核自省（Introspection）**：  
  支持在内核中通过 BPF 程序安全地访问 BPF 子系统内部状态，避免直接暴露内核指针或复杂数据结构。

- **动态分析与调试**：  
  开发者可编写 BPF 迭代器程序，在不修改内核代码的情况下动态检查 BPF 程序的属性（如类型、附件点、JIT 状态等）。

- **资源管理**：  
  系统管理员可利用此接口识别未使用的 BPF 程序，辅助资源回收或性能调优。