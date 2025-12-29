# kallsyms_internal.h

> 自动生成时间: 2025-10-25 14:13:49
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kallsyms_internal.h`

---

# kallsyms_internal.h 技术文档

## 1. 文件概述

`kallsyms_internal.h` 是 Linux 内核中用于支持内核符号表（kallsyms）功能的内部头文件。该文件声明了在内核链接阶段由链接脚本生成的一系列只读全局符号数组和变量，这些数据结构共同构成了内核运行时可查询的符号表，用于将内存地址映射到对应的函数或变量名称。此头文件仅供内核内部使用，不对外暴露给模块或用户空间。

## 2. 核心功能

该文件不包含函数定义，仅声明以下关键的全局只读数据结构：

- `kallsyms_addresses[]`：存储内核符号的绝对地址（在较新内核中可能被 `kallsyms_offsets[]` 取代）
- `kallsyms_offsets[]`：存储符号相对于基准地址的偏移量（用于节省空间）
- `kallsyms_names[]`：压缩存储的符号名称数据
- `kallsyms_num_syms`：内核中符号的总数
- `kallsyms_relative_base`：用于计算符号实际地址的基准地址
- `kallsyms_token_table[]`：用于符号名压缩的 token 字符串表
- `kallsyms_token_index[]`：指向 `token_table` 中各 token 起始位置的索引表
- `kallsyms_markers[]`：用于快速定位 `kallsyms_names[]` 中特定符号名的索引标记
- `kallsyms_seqs_of_names[]`：存储符号名称的 token 序列编码

## 3. 关键实现

- **两阶段链接机制**：所有声明的符号在第一次链接时由链接脚本通过 `PROVIDE()` 指令提供临时值，确保链接成功；在第二次链接阶段，由 `scripts/kallsyms` 工具生成真实符号数据并替换这些临时值。
- **符号压缩存储**：符号名称并非以完整字符串形式存储，而是通过 token 化压缩。`kallsyms_token_table` 存储常用子串（tokens），`kallsyms_seqs_of_names` 使用 token 索引序列重构原始符号名，大幅减少内存占用。
- **地址相对化**：为节省空间，符号地址以相对于 `kallsyms_relative_base` 的偏移量形式存储于 `kallsyms_offsets[]` 中，运行时通过加法还原真实地址。
- **快速查找支持**：`kallsyms_markers[]` 提供对 `kallsyms_names[]` 的分段索引，加速按序号查找符号名的过程。

## 4. 依赖关系

- **链接脚本依赖**：依赖于 `vmlinux.lds.S` 等链接脚本中通过 `PROVIDE()` 定义的符号占位符。
- **构建工具依赖**：依赖 `scripts/kallsyms` 构建工具在内核编译过程中解析 `System.map` 并生成最终的符号数据。
- **内核模块依赖**：被 `kernel/kallsyms.c` 等实现符号解析和查询功能的源文件包含，用于提供底层数据访问。
- **头文件依赖**：包含 `<linux/types.h>` 以使用标准内核类型（如 `u8`、`u16`）。

## 5. 使用场景

- **内核 Oops/panic 调试**：当内核发生严重错误时，通过 kallsyms 将回溯地址转换为可读的函数名，辅助定位问题。
- **动态符号查询**：内核中需要根据地址查找符号名的功能（如 ftrace、perf、kprobes）依赖此数据结构。
- **/proc/kallsyms 接口**：用户空间通过读取 `/proc/kallsyms` 获取内核符号表，其数据源即为本文件声明的这些数组。
- **内核自省与调试**：内核调试器（如 kgdb）或运行时分析工具利用这些符号信息进行函数级调试和性能分析。