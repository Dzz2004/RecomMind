# bpf\core.c

> 自动生成时间: 2025-10-25 12:05:43
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\core.c`

---

# `bpf/core.c` 技术文档

## 1. 文件概述

`bpf/core.c` 是 Linux 内核中 BPF（Berkeley Packet Filter）子系统的核心实现文件之一，主要负责 BPF 程序的内存分配、生命周期管理、辅助函数支持以及与 JIT（Just-In-Time）编译器的交互。该文件为 eBPF（extended BPF）程序提供基础运行时支持，包括程序结构体的分配与释放、统计信息管理、调试信息（如行号信息 linfo）填充、程序标签（tag）计算等关键功能。其设计融合了经典 BPF 的兼容性与现代 eBPF 的扩展能力，是连接用户空间 BPF 程序加载与内核执行环境的重要桥梁。

## 2. 核心功能

### 主要数据结构
- `struct bpf_prog`：eBPF 程序的核心结构体，包含指令数组、辅助信息（`aux`）、JIT 编译后的函数指针等。
- `struct bpf_prog_aux`：BPF 程序的辅助数据结构，用于存储映射（maps）、外部函数（kfuncs）、调试信息（linfo）、引用计数等。
- `struct bpf_prog_stats`：每 CPU 的 BPF 程序执行统计信息（如执行次数、运行时间）。
- `bpf_global_ma`：全局 BPF 内存分配器实例，用于内存控制组（memcg）感知的内存分配。

### 主要函数
- `bpf_internal_load_pointer_neg_helper()`：为经典 BPF 程序提供负偏移量的数据包指针加载辅助函数。
- `bpf_prog_alloc_no_stats()`：分配不包含统计信息的 BPF 程序结构体。
- `bpf_prog_alloc()`：分配包含每 CPU 统计信息的完整 BPF 程序结构体（导出符号，供模块使用）。
- `bpf_prog_alloc_jited_linfo()`：为 JIT 编译分配行号信息（linfo）映射数组。
- `bpf_prog_jit_attempt_done()`：清理 JIT 编译尝试后的临时资源（如未使用的 linfo 或 kfunc 表）。
- `bpf_prog_fill_jited_linfo()`：根据 JIT 指令偏移映射填充调试用的行号信息。
- `bpf_prog_realloc()`：重新分配更大的 BPF 程序内存空间（用于程序转换或扩展）。
- `__bpf_prog_free()`：释放 BPF 程序及其所有关联资源。
- `bpf_prog_calc_tag()`：计算 BPF 程序的 SHA1 哈希标签（用于唯一标识程序内容，排除不稳定字段如 map fd）。

## 3. 关键实现

### 内存分配与管理
- BPF 程序主体（`struct bpf_prog`）使用 `__vmalloc()` 分配，按页对齐（`round_up(size, PAGE_SIZE)`），支持大程序。
- 辅助结构（`aux`）、每 CPU 统计（`stats`）和活跃状态（`active`）使用 `kzalloc()` 和 `alloc_percpu_gfp()` 分配，并集成内存控制组（memcg）支持（通过 `bpf_memcg_flags()`）。
- 全局内存分配器 `bpf_global_ma` 用于统一管理 BPF 相关内存，支持 memcg 隔离。

### JIT 调试信息支持
- `bpf_prog_fill_jited_linfo()` 实现了从 BPF 指令偏移到 JIT 机器码偏移的映射，用于将源码行号信息（`linfo`）关联到 JIT 编译后的代码地址，便于调试和性能分析。
- 该函数依赖 JIT 引擎提供的 `insn_to_jit_off` 数组，确保调试信息与实际执行代码对齐。

### 程序标签计算
- `bpf_prog_calc_tag()` 在计算 SHA1 哈希前，会复制程序指令并**移除不稳定的字段**（如 `BPF_LD_MAP_FD` 指令中的 map 文件描述符），确保相同逻辑的程序生成相同的标签，用于程序去重和验证缓存。

### 安全与兼容性
- `bpf_internal_load_pointer_neg_helper()` 处理经典 BPF 的负偏移访问（如 `SKF_NET_OFF`、`SKF_LL_OFF`），严格检查指针是否在 `sk_buff` 数据范围内，防止越界访问。
- 所有内存分配均使用 `__GFP_ZERO` 初始化，避免信息泄露。
- 支持细粒度锁（如 `used_maps_mutex`、`ext_mutex`）保护共享资源。

## 4. 依赖关系

- **头文件依赖**：
  - BPF 核心接口：`<linux/bpf.h>`, `<linux/filter.h>`
  - 验证器：`<linux/bpf_verifier.h>`
  - 内存管理：`<linux/vmalloc.h>`, `<linux/memcontrol.h>`, `<linux/bpf_mem_alloc.h>`
  - 网络子系统：`<linux/skbuff.h>`（用于经典 BPF 辅助函数）
  - 调试与符号：`<linux/kallsyms.h>`, `<linux/perf_event.h>`
  - 架构相关：`<asm/barrier.h>`, `<asm/unaligned.h>`
- **模块依赖**：
  - BPF JIT 编译器（通过 `ebpf_jit_enabled()` 和 `bpf_jit_blinding_enabled()` 交互）
  - BPF 验证器（`bpf_check_classic()` 在其他文件中，但与此文件协同工作）
  - cgroup BPF（`CONFIG_CGROUP_BPF` 条件编译）
  - 内存控制组（memcg）子系统

## 5. 使用场景

- **BPF 程序加载**：当用户空间通过 `bpf(BPF_PROG_LOAD, ...)` 系统调用加载程序时，内核调用 `bpf_prog_alloc()` 分配程序结构。
- **JIT 编译流程**：JIT 编译器在编译前后调用 `bpf_prog_alloc_jited_linfo()` 和 `bpf_prog_fill_jited_linfo()` 管理调试信息；编译失败时调用 `bpf_prog_jit_attempt_done()` 清理资源。
- **程序转换与优化**：验证器或 JIT 在优化过程中可能需要更大的内存空间，调用 `bpf_prog_realloc()` 扩展程序存储。
- **程序卸载**：当 BPF 程序引用计数归零时，调用 `__bpf_prog_free()` 释放所有资源。
- **程序标识与缓存**：`bpf_prog_calc_tag()` 生成的标签用于内核内部缓存（如 verifier log 缓存）和用户空间工具（如 bpftool）识别程序。
- **经典 BPF 兼容**：网络抓包工具（如 tcpdump）使用经典 BPF 时，内核通过 `bpf_internal_load_pointer_neg_helper()` 安全访问数据包头。