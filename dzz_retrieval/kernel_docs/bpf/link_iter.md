# bpf\link_iter.c

> 自动生成时间: 2025-10-25 12:14:14
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\link_iter.c`

---

# bpf/link_iter.c 技术文档

## 1. 文件概述

`bpf/link_iter.c` 实现了 BPF（Berkeley Packet Filter）链接对象（`bpf_link`）的迭代器（iterator）功能，允许用户空间通过 seq_file 接口遍历系统中所有活跃的 BPF 链接对象。该迭代器支持与 BPF 迭代器程序（BPF iterator program）集成，使得用户可以通过 BPF 程序自定义遍历逻辑和输出格式，用于调试、监控或审计 BPF 链接的使用情况。

## 2. 核心功能

### 主要数据结构

- **`struct bpf_iter_seq_link_info`**  
  存储迭代器私有状态，包含当前遍历的 `link_id`，用于在 `bpf_link_get_curr_or_next()` 中定位下一个 BPF 链接。

- **`struct bpf_iter__bpf_link`**  
  BPF 迭代器程序的上下文结构体，包含指向元数据（`meta`）和当前 `bpf_link` 对象的指针，供 BPF 程序访问。

- **`bpf_link_seq_ops`**  
  `seq_operations` 结构体实例，定义了 seq_file 接口的四个回调函数：`start`、`next`、`stop` 和 `show`。

- **`bpf_link_seq_info`**  
  `bpf_iter_seq_info` 结构体，描述该迭代器的 seq_file 操作、私有数据大小及初始化/清理函数。

- **`bpf_link_reg_info`**  
  `bpf_iter_reg` 结构体，用于向 BPF 迭代器子系统注册名为 `"bpf_link"` 的目标迭代器，包含上下文参数信息和 BTF 类型 ID。

### 主要函数

- **`bpf_link_seq_start`**  
  seq_file 的起始回调，获取第一个有效的 `bpf_link` 对象。

- **`bpf_link_seq_next`**  
  seq_file 的下一个元素回调，递增 `link_id` 并获取下一个 `bpf_link`。

- **`bpf_link_seq_show`**  
  seq_file 的显示回调，调用 BPF 迭代器程序处理当前 `bpf_link`。

- **`bpf_link_seq_stop`**  
  seq_file 的终止回调，释放当前 `bpf_link` 引用，或在无有效对象时触发 BPF 程序的 `in_stop` 阶段。

- **`__bpf_link_seq_show`**  
  内部辅助函数，封装 BPF 迭代器程序的调用逻辑，支持正常遍历和停止阶段。

- **`bpf_link_iter_init`**  
  模块初始化函数，注册 BPF 链接迭代器到内核 BPF 迭代器框架。

## 3. 关键实现

- **迭代机制**：  
  使用全局递增的 `link_id` 作为索引，通过 `bpf_link_get_curr_or_next(&link_id)` 查找下一个有效的 BPF 链接。该函数由 BPF 子系统提供，确保线程安全地遍历链接 ID 空间。

- **引用计数管理**：  
  在 `start` 和 `next` 中获取 `bpf_link` 时增加引用，在 `next` 和 `stop` 中调用 `bpf_link_put()` 释放引用，防止对象在遍历过程中被销毁。

- **BPF 程序集成**：  
  通过 `bpf_iter_get_info()` 获取关联的 BPF 迭代器程序，并使用 `bpf_iter_run_prog()` 执行该程序。上下文 `bpf_iter__bpf_link` 提供对当前链接和 seq_file 的访问。

- **BTF 类型支持**：  
  使用 `BTF_ID_LIST` 和 `BTF_ID(struct, bpf_link)` 声明 `bpf_link` 结构的 BTF ID，并在注册时绑定到上下文参数，使 BPF 程序能安全地访问 `bpf_link` 字段。

- **初始化时机**：  
  通过 `late_initcall` 注册迭代器，确保在 BPF 子系统完全初始化后再注册该迭代目标。

## 4. 依赖关系

- **`<linux/bpf.h>` / `<linux/filter.h>`**：  
  提供 BPF 核心接口，包括 `bpf_link` 管理、迭代器注册（`bpf_iter_reg_target`）、程序执行（`bpf_iter_run_prog`）等。

- **`<linux/fs.h>`**：  
  依赖 seq_file 机制实现 `/sys/fs/bpf/` 或类似虚拟文件系统的遍历接口。

- **`<linux/btf_ids.h>`**：  
  支持 BTF（BPF Type Format）类型 ID 的声明与解析，用于类型安全的 BPF 程序上下文访问。

- **BPF 链接子系统**：  
  依赖 `bpf_link_get_curr_or_next()` 和 `bpf_link_put()` 等函数，这些由 `kernel/bpf/link.c` 实现。

- **BPF 迭代器框架**：  
  依赖 `bpf_iter_get_info()`、`bpf_iter_reg_target()` 等通用迭代器基础设施，位于 `kernel/bpf/iter.c`。

## 5. 使用场景

- **系统监控与调试**：  
  用户可通过挂载 BPF 迭代器程序到 `bpf_link` 目标，遍历所有 BPF 链接并输出其类型、关联程序、附加点等信息，用于诊断 BPF 程序部署状态。

- **安全审计**：  
  安全工具可利用此迭代器检查是否有异常或未授权的 BPF 链接被创建，例如挂钩到敏感内核路径的链接。

- **性能分析**：  
  结合 BPF 程序，可统计各类 BPF 链接的数量、生命周期或资源占用，辅助性能调优。

- **用户空间工具集成**：  
  `bpftool` 等工具可通过读取 `/sys/kernel/debug/tracing/iter/bpf_link`（或类似路径）获取链接列表，无需直接调用内核 API。