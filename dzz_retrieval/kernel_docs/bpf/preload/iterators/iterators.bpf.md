# bpf\preload\iterators\iterators.bpf.c

> 自动生成时间: 2025-10-25 12:25:02
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\preload\iterators\iterators.bpf.c`

---

# bpf/preload/iterators/iterators.bpf.c 技术文档

## 1. 文件概述

该文件是 Linux 内核 BPF（Berkeley Packet Filter）子系统中用于实现 **BPF 迭代器（BPF iterators）** 的 eBPF 程序。它定义了两个核心迭代器程序：`iter/bpf_map` 和 `iter/bpf_prog`，分别用于遍历系统中所有 BPF map 和 BPF program，并以结构化格式通过 seq_file 接口输出其元数据信息。该程序运行在内核态，利用 BPF CO-RE（Compile Once – Run Everywhere）机制安全地读取内核数据结构，为用户空间提供统一、高效的 BPF 资源监控能力。

## 2. 核心功能

### 主要数据结构

- `struct bpf_iter_meta`：BPF 迭代器元数据，包含 seq_file 指针、会话 ID 和序列号。
- `struct bpf_map`：BPF map 的简化视图，包含 ID、名称和最大条目数。
- `struct bpf_iter__bpf_map`：`iter/bpf_map` 迭代器的上下文结构，包含元数据和当前 map 指针。
- `struct btf` / `struct btf_type` / `struct btf_header`：BTF（BPF Type Format）相关结构，用于类型和符号信息解析。
- `struct bpf_prog_aux` / `struct bpf_prog`：BPF 程序及其辅助信息的简化表示。
- `struct bpf_iter__bpf_prog`：`iter/bpf_prog` 迭代器的上下文结构。

### 主要函数

- `static const char *get_name(struct btf *btf, long btf_id, const char *fallback)`  
  从 BTF 类型信息中安全读取函数或类型名称，若失败则返回备用名称。
  
- `__s64 bpf_map_sum_elem_count(struct bpf_map *map) __ksym`  
  声明为内核符号（`__ksym`），用于获取 BPF map 当前元素数量（由内核提供实现）。

- `int dump_bpf_map(struct bpf_iter__bpf_map *ctx)`  
  `SEC("iter/bpf_map")` 程序，遍历所有 BPF map 并输出其 ID、名称、最大条目数和当前条目数。

- `int dump_bpf_prog(struct bpf_iter__bpf_prog *ctx)`  
  `SEC("iter/bpf_prog")` 程序，遍历所有 BPF program 并输出其 ID、名称、附加函数名及目标程序名。

## 3. 关键实现

- **CO-RE 安全访问**：使用 `#pragma clang attribute push(__attribute__((preserve_access_index)))` 启用 BPF CO-RE，确保对内核结构体成员的访问在不同内核版本间兼容；通过 `BPF_CORE_READ()` 和 `bpf_probe_read_kernel()` 安全读取内核内存，避免直接解引用指针导致的崩溃。

- **Seq File 输出格式化**：利用 `BPF_SEQ_PRINTF()` 宏将格式化数据写入 `seq_file`，实现类似 `/proc` 文件系统的文本输出。首次调用（`seq_num == 0`）时输出表头。

- **BTF 名称解析**：`get_name()` 函数通过 BTF 字符串表和类型表动态解析函数名，优先使用 BTF 信息，失败时回退到 `aux->name`，提升可读性和调试能力。

- **迭代器上下文处理**：每个迭代器回调函数接收对应上下文结构（如 `bpf_iter__bpf_map`），从中提取 `seq_file` 和当前对象指针，实现逐对象遍历。

## 4. 依赖关系

- **内核 BPF 子系统**：依赖 `linux/bpf.h` 和 BPF 迭代器框架，由 `bpf_iter_*` 内核模块注册和调用。
- **BPF Helpers**：使用 `bpf_helpers.h` 中的 `BPF_SEQ_PRINTF` 和 `bpf_probe_read_kernel`。
- **BPF CO-RE 支持**：依赖 `bpf_core_read.h` 提供的 `BPF_CORE_READ` 宏，需 Clang >= 10 及内核 BTF 支持。
- **内核符号**：依赖内核导出的 `bpf_map_sum_elem_count` 函数（标记为 `__ksym`）。
- **BTF 基础设施**：依赖内核 BTF 类型信息（`struct btf` 等），用于符号解析。

## 5. 使用场景

- **BPF 资源监控**：用户可通过挂载 BPF 迭代器文件系统（如 `/sys/fs/bpf/` 下的 `iter/bpf_map` 和 `iter/bpf_prog`）直接读取系统中所有 BPF map 和 program 的状态，无需额外工具。
- **调试与诊断**：开发人员可快速查看 BPF 程序的附加点（`attach_func_name`）、目标程序及 map 使用情况，辅助性能分析和故障排查。
- **安全审计**：系统管理员可审计当前加载的 BPF 程序及其关联资源，检测异常或未授权的 BPF 活动。
- **工具链集成**：作为 `bpftool` 等用户态工具的底层数据源，提供标准化、高效的 BPF 对象枚举接口。