# bpf\disasm.c

> 自动生成时间: 2025-10-25 12:09:31
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\disasm.c`

---

# bpf/disasm.c 技术文档

## 1. 文件概述

`bpf/disasm.c` 是 Linux 内核中用于反汇编 eBPF（extended Berkeley Packet Filter）字节码指令的核心模块。该文件提供将 eBPF 二进制指令转换为人类可读的汇编格式字符串的功能，主要用于调试、验证器日志输出、程序分析和用户空间工具（如 `bpftool`）的指令展示。它通过回调机制支持灵活的输出格式定制，并处理 eBPF 指令集中的各种操作类型，包括算术、跳转、内存访问、函数调用及原子操作等。

## 2. 核心功能

### 主要函数

- **`print_bpf_insn`**  
  核心反汇编函数，根据传入的 `bpf_insn` 指令和回调结构体 `bpf_insn_cbs`，格式化输出对应的人类可读汇编语句。

- **`func_id_name`**  
  根据 BPF 辅助函数 ID 返回其对应的字符串名称（如 `"bpf_map_lookup_elem"`）。

- **`__func_get_name`**（静态）  
  内部辅助函数，用于解析 `call` 指令的目标函数名，支持标准辅助函数、伪调用（`BPF_PSEUDO_CALL`）、内核函数调用（`BPF_PSEUDO_KFUNC_CALL`）以及用户自定义回调。

- **`__func_imm_name`**（静态）  
  用于格式化立即数（immediate value），支持用户通过回调自定义立即数的显示方式。

- **`print_bpf_end_insn` / `print_bpf_bswap_insn`**（静态）  
  专门用于反汇编字节序转换指令（`BPF_END`），区分 32 位（`endian`）和 64 位（`bswap`）操作。

### 主要数据结构与常量表

- **`func_id_str[]`**  
  静态字符串数组，通过宏 `__BPF_FUNC_MAPPER` 自动生成所有 BPF 辅助函数的名称映射。

- **`bpf_class_string[]`**  
  eBPF 指令类别（如 `ld`, `alu64`, `jmp32` 等）的字符串表示。

- **`bpf_alu_string[]` / `bpf_alu_sign_string[]`**  
  ALU/ALU64 操作符（如 `+=`, `s/=`）的字符串映射。

- **`bpf_movsx_string[]`**  
  有符号扩展移动指令（`movsx`）的类型后缀（如 `(s8)`, `(s16)`）。

- **`bpf_atomic_alu_string[]`**  
  原子操作（如 `add`, `xor`）的字符串表示。

- **`bpf_ldst_string[]` / `bpf_ldsx_string[]`**  
  内存加载/存储操作的数据宽度（如 `u32`, `s16`）字符串。

- **`bpf_jmp_string[]`**  
  跳转和比较操作（如 `==`, `s>`, `call`, `exit`）的字符串表示。

## 3. 关键实现

### 指令分类与反汇编逻辑
`print_bpf_insn` 函数首先通过 `BPF_CLASS()` 宏提取指令类别（如 `BPF_ALU64`, `BPF_STX`），然后按类别分支处理：
- **ALU/ALU64 指令**：区分立即数（`BPF_K`）与寄存器（`BPF_X`）源操作数，特殊处理 `NEG`、`END`、地址空间转换、per-CPU 地址解析、有符号除法/取模（`off == 1`）及符号扩展移动（`movsx`）。
- **STX 指令**：重点处理 `BPF_ATOMIC` 模式，支持普通原子操作、带 `FETCH` 语义的操作（如 `atomic_fetch_add`）以及 `cmpxchg`/`xchg`。

### 辅助函数名称解析
通过预定义的 `func_id_str` 数组快速映射标准 BPF 辅助函数 ID 到名称。若指令为伪调用（`BPF_PSEUDO_CALL`）或内核函数调用（`BPF_PSEUDO_KFUNC_CALL`），则生成相对偏移或通用标识；同时支持用户通过 `cbs->cb_call` 回调提供自定义函数名。

### 扩展语义支持
- **地址空间转换**：通过 `is_addr_space_cast()` 识别特殊 `mov` 指令，用于类型安全的指针转换。
- **Per-CPU 地址解析**：通过 `is_mov_percpu_addr()` 识别 `BPF_ADDR_PERCPU` 标记的指令，生成 `&(void __percpu *)` 形式的表达式。
- **有符号操作识别**：`is_sdiv_smod()` 通过检查 `insn->off == 1` 判断是否为有符号除法/取模，使用 `bpf_alu_sign_string` 输出 `s/=` 或 `s%=`。

### 安全与兼容性
- 使用 `BUILD_BUG_ON` 确保 `func_id_str` 数组大小与 `__BPF_FUNC_MAX_ID` 一致，防止映射越界。
- 所有字符串输出均通过用户提供的 `verbose` 回调函数完成，避免直接 I/O，提高模块通用性。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/bpf.h>`：定义 eBPF 指令结构体 `bpf_insn`、辅助函数枚举 `BPF_FUNC_*` 及宏（如 `BPF_CLASS`, `BPF_OP`）。
  - `"disasm.h"`：本地头文件，声明 `bpf_insn_cbs` 回调结构体、`bpf_insn_print_t` 类型及公共函数原型。

- **宏依赖**：
  - `__BPF_FUNC_MAPPER`：由 `linux/bpf.h` 定义，用于生成辅助函数名称映射表。
  - `__stringify`：内核通用宏，将符号转换为字符串。

- **内核子系统**：
  - **BPF 子系统**：作为 BPF 验证器（verifier）、JIT 编译器及调试工具链的一部分，为指令分析提供基础支持。
  - **用户空间工具**：`bpftool` 等工具通过 `bpf_prog_get_info_by_fd` 获取指令并调用此模块进行反汇编。

## 5. 使用场景

- **BPF 程序调试**：在内核日志或 `bpftool prog dump` 中展示人类可读的 eBPF 汇编代码。
- **验证器错误报告**：当 BPF 验证器拒绝程序时，通过反汇编定位问题指令。
- **JIT 调试**：辅助开发人员比对 JIT 生成的机器码与原始 eBPF 指令。
- **静态分析工具**：用户空间分析器（如 `bpftrace`）利用此模块解析 BPF 字节码逻辑。
- **内核自检**：在 `CONFIG_BPF_JIT_ALWAYS_ON` 等配置下，用于运行时指令流分析。