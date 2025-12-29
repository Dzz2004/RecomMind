# debug\kdb\kdb_private.h

> 自动生成时间: 2025-10-25 13:06:42
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `debug\kdb\kdb_private.h`

---

# `debug/kdb/kdb_private.h` 技术文档

## 1. 文件概述

`kdb_private.h` 是 Linux 内核调试器（KDB）的架构无关私有头文件，定义了 KDB 内部使用的常量、宏、数据结构和函数声明。该文件为 KDB 的核心功能（如断点管理、命令解析、符号处理、状态控制等）提供统一的内部接口，同时支持 32 位与 64 位平台的差异适配。它被 KDB 的实现模块（如 `kdb_main.c`、`kdb_bp.c` 等）包含，但不对外暴露给普通内核模块。

## 2. 核心功能

### 主要宏定义
- **命令码**：`KDB_CMD_GO`、`KDB_CMD_CPU`、`KDB_CMD_SS`、`KDB_CMD_KGDB`，用于标识内部命令类型。
- **调试标志**：`KDB_DEBUG_FLAG_*` 系列标志，用于启用不同子系统的调试输出（如断点、基本块分析、激活记录等）。
- **平台格式宏**：根据 `BITS_PER_LONG` 定义地址、寄存器、ELF 地址等的打印格式（如 `kdb_machreg_fmt0`）。
- **状态标志操作宏**：`KDB_STATE()`、`KDB_STATE_SET()`、`KDB_STATE_CLEAR()` 用于查询/设置全局状态位。
- **内存访问宏**：`kdb_getarea()`、`kdb_putarea()` 封装安全的内核内存读写。

### 关键数据结构
- **`kdb_symtab_t`**：封装内核符号信息，包含地址、模块名、节区信息、符号名及范围。
- **`kdb_bp_t`**：表示一个断点，包含地址、启用状态、类型、安装状态、延迟处理标志及硬件断点长度。
- **`kdb_dbtrap_t`**（枚举）：描述调试陷阱类型（断点、单步、单步跳过断点等）。

### 核心函数声明
- **符号处理**：`kdbgetsymval()`、`kdbnearsym()`、`kdb_symbol_print()` 用于符号查找与格式化输出。
- **内存访问**：`kdb_getarea_size()`、`kdb_putarea_size()`、`kdb_getword()`、`kdb_putword()` 提供安全的内核空间读写。
- **参数解析**：`kdbgetularg()`、`kdbgetu64arg()`、`kdbgetaddrarg()` 解析命令行参数。
- **断点管理**：`kdb_initbptab()`、`kdb_bp_install()`、`kdb_bp_remove()` 管理断点表。
- **主循环与状态**：`kdb_main_loop()` 驱动调试器主逻辑；`kdb_print_state()` 调试状态输出。
- **任务与输入**：`kdb_task_state()`、`kdb_ps1()` 处理任务状态；`kdb_getchar()`、`kdb_getstr()` 处理用户输入。
- **辅助功能**：`kdb_strdup()` 安全字符串复制；`kdb_gdb_state_pass()` 用于 KDB 与 KGDB 状态传递。

### 全局变量
- **`kdb_state`**：32 位整数，存储 KDB 的当前运行状态（如是否在单步、是否抑制错误等）。
- **`kdb_breakpoints[]`**：全局断点数组（大小为 `KDB_MAXBPT=16`）。
- **`kdb_grepping_flag` 等**：支持 `grep` 式过滤输出的全局状态。

## 3. 关键实现

### 调试标志机制
通过 `KDB_DEBUG_FLAG_SHIFT=16` 将调试标志左移 16 位后与 `kdb_flags`（未在本文件定义，但由其他 KDB 模块维护）进行位与操作，实现按需启用子系统调试输出。例如 `KDB_DEBUG(BP)` 展开为检查 `kdb_flags` 的第 18 位（`0x0002 << 16`）。

### 平台无关格式化
利用 `#if BITS_PER_LONG == 32/64` 条件编译，为不同架构定义统一的格式字符串宏（如 `kdb_machreg_fmt0` 在 32 位下为 `0x%08lx`，64 位下为 `0x%016lx`），确保地址打印对齐且可读。

### 安全内存访问
`kdb_getarea()`/`kdb_putarea()` 宏封装了带大小检查的内存访问函数（`kdb_getarea_size()`/`kdb_putarea_size()`），避免因无效地址导致内核崩溃，是 KDB 安全读写内核内存的关键。

### 状态机管理
`kdb_state` 使用位掩码管理复杂状态（如 `KDB_STATE_DOING_SS` 表示单步执行，`KDB_STATE_REENTRY` 允许合法重入）。状态宏提供原子操作接口，确保多 CPU 环境下状态一致性。

### 断点数据结构
`kdb_bp_t` 结构体紧凑设计，使用位域（如 `bp_free:1`）节省空间，并包含硬件断点所需字段（`bph_length`）。`kdb_breakpoints[]` 数组全局维护所有断点，由 `kdb_initbptab()` 初始化。

### 符号表抽象
`kdb_symtab_t` 统一表示内核及模块符号，支持通过 `kallsyms` 接口查询。`kdb_symbol_print()` 根据标志（如 `KDB_SP_VALUE`、`KDB_SP_PAREN`）灵活格式化符号输出。

## 4. 依赖关系

- **内核头文件**：
  - `<linux/kgdb.h>`：提供 KGDB 相关定义（KDB 与 KGDB 可集成）。
  - `"../debug_core.h"`：包含调试核心通用定义（如 `kdbtab_t` 命令表结构）。
- **KDB 内部模块**：
  - 依赖 `kdb_main.c` 实现主循环、状态管理。
  - 依赖 `kdb_bp.c` 实现断点安装/移除。
  - 依赖 `kdb_support.c` 实现符号解析、内存访问等。
- **内核子系统**：
  - 依赖 `kallsyms` 子系统获取符号信息（通过 `kallsyms_symbol_next()` 等）。
  - 依赖内存管理子系统进行安全内存访问。
  - 依赖调度器获取任务状态（`task_struct` 相关函数）。

## 5. 使用场景

- **内核调试会话**：当通过串口、键盘或 NMI 触发 KDB 时，该头文件定义的接口被用于解析用户命令（如 `go`、`bp`、`bt`）、管理断点、显示符号信息。
- **断点处理**：在硬件/软件断点触发时，`kdb_bp_t` 结构和相关函数用于安装/移除断点，并处理延迟断点逻辑。
- **KGDB 集成**：当 KDB 与 KGDB 联合使用时（`CONFIG_KGDB_KDB=y`），`KDB_CMD_KGDB` 和 `kdb_gdb_state_pass()` 支持在两者间切换。
- **符号解析**：执行 `sym`、`bt` 等命令时，通过 `kdb_symtab_t` 和符号函数解析地址对应的函数名。
- **安全诊断**：在内核崩溃或死锁时，KDB 利用该文件定义的内存访问宏安全读取内存，避免二次崩溃。
- **多 CPU 调试**：`kdb_state` 中的 CPU 相关标志（如 `KDB_STATE_HOLD_CPU`）协调多核系统的调试控制流。