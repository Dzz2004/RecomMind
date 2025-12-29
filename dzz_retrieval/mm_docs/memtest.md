# memtest.c

> 自动生成时间: 2025-12-07 16:46:14
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `memtest.c`

---

# memtest.c 技术文档

## 1. 文件概述

`memtest.c` 是 Linux 内核中用于在启动早期阶段对物理内存进行测试的模块。其主要功能是在内核初始化过程中，通过写入特定模式数据并回读验证的方式检测物理内存中的坏块（bad memory regions）。一旦发现错误，会将对应的物理内存区域通过 `memblock_reserve()` 标记为保留，防止后续被分配使用，并通过 `/proc/meminfo` 向用户空间报告坏内存的大小。

## 2. 核心功能

### 主要全局变量
- `early_memtest_done`：布尔值，标记是否已执行过早期内存测试。
- `early_memtest_bad_size`：记录检测到的坏内存总字节数。
- `patterns[]`：预定义的测试模式数组，包含多种位模式（如全0、全1、交替位等），用于写入内存以检测不同类型的故障。
- `memtest_pattern`：控制执行多少轮内存测试，可通过内核启动参数 `memtest=` 配置。

### 主要函数
- `reserve_bad_mem()`：将检测到的坏内存区域通过 `memblock_reserve()` 保留，并累加坏内存大小。
- `memtest()`：对指定物理地址范围执行单次内存测试，使用给定模式写入并验证。
- `do_one_pass()`：遍历所有当前可用的空闲内存区域（通过 `for_each_free_mem_range`），并对每个与指定范围 `[start, end)` 重叠的部分执行 `memtest()`。
- `parse_memtest()`：解析内核启动参数 `memtest=`，设置测试轮数。
- `early_memtest()`：对外提供的主入口函数，在早期初始化阶段调用，执行指定次数的内存测试。
- `memtest_report_meminfo()`：向 `/proc/meminfo` 输出坏内存统计信息（单位为 kB）。

## 3. 关键实现

### 内存测试算法
- **对齐处理**：测试前将起始物理地址按 `sizeof(u64)` 对齐，确保访问自然对齐的 64 位字。
- **两阶段操作**：
  1. **写入阶段**：将整个测试区域按 8 字节步长写入指定模式。
  2. **验证阶段**：逐字读回并与预期模式比较。
- **坏块合并**：连续出错的地址会被合并为一个连续区间，仅在区间结束时调用 `reserve_bad_mem()` 一次，减少 `memblock` 操作次数。
- **原子访问**：使用 `WRITE_ONCE()` 和 `READ_ONCE()` 确保编译器不优化内存访问，保证测试有效性。

### 测试模式循环
- 若 `memtest_pattern` 设为 N，则从 `patterns` 数组末尾开始向前执行 N 次测试（实际通过模运算循环使用模式）。
- 默认 `memtest_pattern = 0` 表示禁用测试；若未指定参数但启用该功能，则默认使用全部模式（`ARRAY_SIZE(patterns)` 轮）。

### 坏内存报告
- 通过 `memtest_report_meminfo()` 向 `/proc/meminfo` 添加 `EarlyMemtestBad` 字段。
- 即使坏内存小于 1KB，也至少报告为 1kB，避免显示为 0（0 表示无坏块或未执行测试）。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/memblock.h>`：用于内存块管理，特别是 `memblock_reserve()` 和 `for_each_free_mem_range()`。
  - `<linux/seq_file.h>`：用于 `/proc/meminfo` 的输出支持。
  - `<linux/init.h>`：提供 `__init`、`early_param` 等初始化相关宏。
- **配置依赖**：
  - `CONFIG_PROC_FS`：控制是否编译 `memtest_report_meminfo()` 函数。
- **调用关系**：
  - `early_memtest()` 通常由体系结构相关的初始化代码（如 x86 的 `setup_arch()`）在 `memblock` 初始化完成后、页表建立前调用。
  - `memtest_report_meminfo()` 被 `show_meminfo()`（在 `fs/proc/meminfo.c` 中）调用以填充 `/proc/meminfo`。

## 5. 使用场景

- **系统启动早期诊断**：在内核完全初始化前检测物理内存硬件故障，防止坏内存被分配给关键数据结构。
- **嵌入式/服务器环境**：在高可靠性要求的系统中，通过启动参数 `memtest=N` 启用多轮内存测试，提升系统稳定性。
- **调试内存问题**：开发人员可利用此功能快速定位物理内存缺陷，尤其是在新硬件平台 bring-up 阶段。
- **用户空间监控**：通过 `/proc/meminfo` 中的 `EarlyMemtestBad` 字段，运维工具可监控系统是否存在物理内存故障。