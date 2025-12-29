# bpf\arraymap.c

> 自动生成时间: 2025-10-25 11:55:39
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\arraymap.c`

---

# `bpf/arraymap.c` 技术文档

## 1. 文件概述

`bpf/arraymap.c` 是 Linux 内核中 BPF（Berkeley Packet Filter）子系统的核心实现文件之一，负责实现 **BPF 数组映射（Array Map）** 及其变体（如 per-CPU 数组、可 mmap 数组等）。该文件提供了对固定大小、基于整数索引的键值存储结构的支持，是 BPF 程序中最基础、高效的映射类型之一。数组映射具有 O(1) 的查找/更新性能，适用于需要快速随机访问的场景。

## 2. 核心功能

### 主要数据结构
- `struct bpf_array`：BPF 数组映射的内部表示，包含：
  - `index_mask`：用于边界检查和投机执行防护的掩码
  - `elem_size`：对齐后的元素大小（8 字节对齐）
  - `value`：指向实际数据存储区域的指针（普通数组）
  - `pptrs`：per-CPU 指针数组（用于 `BPF_MAP_TYPE_PERCPU_ARRAY`）

### 主要函数
| 函数名 | 功能描述 |
|--------|--------|
| `array_map_alloc_check()` | 在创建映射前校验用户传入的属性（`bpf_attr`）是否合法 |
| `array_map_alloc()` | 分配并初始化 `bpf_array` 实例 |
| `array_map_lookup_elem()` | 普通数组映射的元素查找接口 |
| `percpu_array_map_lookup_elem()` | per-CPU 数组映射的元素查找接口 |
| `array_map_gen_lookup()` | 为 JIT 编译器生成等效于 `array_map_lookup_elem()` 的 BPF 指令序列 |
| `percpu_array_map_gen_lookup()` | 为 JIT 编译器生成等效于 `percpu_array_map_lookup_elem()` 的 BPF 指令序列 |
| `bpf_array_alloc_percpu()` / `bpf_array_free_percpu()` | per-CPU 数组的内存分配与释放辅助函数 |
| `array_map_direct_value_addr()` / `array_map_direct_value_meta()` | 支持直接访问单元素数组值的地址（用于特定优化场景） |

## 3. 关键实现

### 3.1 边界检查与投机执行防护
- 使用 `index_mask` 实现 **恒定时间访问**，防止 Spectre v1 攻击：
  - 若未启用 `bpf_bypass_spec_v1`，`max_entries` 会被向上对齐到 2 的幂
  - 实际访问时使用 `index & index_mask` 而非直接使用原始索引
  - JIT 生成的代码包含边界检查跳转逻辑

### 3.2 内存布局优化
- **普通数组**：
  - 元数据（`struct bpf_array`）与数据区（`value`）连续分配
  - 若启用 `BPF_F_MMAPABLE`，使用 `vmalloc` 分配页对齐内存以支持用户态 mmap
- **per-CPU 数组**：
  - 每个条目是一个 per-CPU 指针（`pptrs[i]`）
  - 通过 `this_cpu_ptr()` 获取当前 CPU 的数据副本

### 3.3 JIT 指令生成
- `array_map_gen_lookup()` 动态生成 BPF 指令序列，模拟 C 代码逻辑：
  - 计算 `value` 字段偏移
  - 加载 32 位索引并进行边界检查
  - 根据元素大小选择左移（2 的幂）或乘法计算偏移
  - 返回元素地址或 NULL
- per-CPU 版本额外包含：
  - per-CPU 指针解引用（`BPF_LDX_MEM(BPF_DW, ...)`）
  - 架构特定的 per-CPU 寄存器操作（`BPF_MOV64_PERCPU_REG`）

### 3.4 属性校验规则
- 强制要求 `key_size == 4`（32 位无符号整数索引）
- `BPF_F_MMAPABLE` 仅支持普通 `BPF_MAP_TYPE_ARRAY`
- `BPF_F_PRESERVE_ELEMS` 仅用于 `BPF_MAP_TYPE_PERF_EVENT_ARRAY`
- per-CPU 数组禁止指定 NUMA 节点（`numa_node != NUMA_NO_NODE`）

## 4. 依赖关系

| 依赖模块 | 用途 |
|---------|------|
| `<linux/bpf.h>` | BPF 核心 API 和数据结构定义 |
| `<linux/btf.h>` | BPF 类型格式（BTF）支持 |
| `<linux/percpu.h>` | per-CPU 内存分配（`alloc_percpu`/`free_percpu`） |
| `<linux/mm.h>` | 内存管理（`vmalloc`/`vfree`） |
| `<linux/filter.h>` | BPF JIT 相关宏（如 `BPF_MOV64_PERCPU_REG`） |
| `"map_in_map.h"` | 支持嵌套映射（`BPF_F_INNER_MAP`） |
| `<linux/rcupdate_trace.h>` | RCU 同步机制（间接依赖） |

## 5. 使用场景

1. **高性能计数器**  
   BPF 程序使用 `BPF_MAP_TYPE_ARRAY` 存储统计信息（如包计数、错误码计数），通过索引快速更新。

2. **配置参数存储**  
   用户态程序通过 `bpf_map_update_elem()` 预置配置，BPF 程序通过索引读取（如限速阈值、过滤规则）。

3. **per-CPU 聚合**  
   `BPF_MAP_TYPE_PERCPU_ARRAY` 用于避免原子操作开销，每个 CPU 独立累加数据，用户态聚合结果。

4. **用户态共享内存**  
   启用 `BPF_F_MMAPABLE` 的数组可被用户态程序直接 mmap，实现零拷贝数据交换（如 XDP 统计）。

5. **JIT 优化**  
   内核 JIT 编译器调用 `*_gen_lookup()` 生成内联查找代码，消除函数调用开销，提升 BPF 程序性能。