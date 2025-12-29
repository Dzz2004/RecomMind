# kexec_core.c

> 自动生成时间: 2025-10-25 14:23:56
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kexec_core.c`

---

# kexec_core.c 技术文档

## 1. 文件概述

`kexec_core.c` 是 Linux 内核中 `kexec` 系统调用的核心实现文件，负责管理内核热替换（kexec）过程中的内存布局、段验证、控制结构初始化等关键逻辑。该文件为用户空间通过 `kexec_load` 或 `kexec_file_load` 系统调用加载新内核镜像提供底层支持，并确保加载过程的安全性和正确性。kexec 允许在不经过固件（如 BIOS/UEFI）重启的情况下直接跳转到新内核，常用于快速重启、崩溃转储（crash dump）等场景。

## 2. 核心功能

### 主要全局变量
- `atomic_t __kexec_lock`：原子锁，用于防止多个 kexec 操作并发执行。
- `bool kexec_in_progress`：标志位，指示当前是否正在进行 kexec 操作。
- `bool kexec_file_dbg_print`：调试开关，控制是否打印 kexec 文件加载的调试信息。

### 主要宏定义
- `KIMAGE_NO_DEST`：表示无需指定目标地址的特殊值（`-1UL`）。
- `PAGE_COUNT(x)`：计算给定字节数所需的页数。

### 主要函数
- `sanity_check_segment_list(struct kimage *image)`：验证用户提供的内核镜像段列表的合法性，包括地址对齐、范围限制、重叠检测、内存用量限制等。
- `do_kimage_alloc_init(void)`：分配并初始化 `kimage` 控制结构，用于描述待加载的新内核镜像。
- `kimage_is_destination_range(struct kimage *image, unsigned long start, unsigned long end)`：检查指定物理地址范围是否与镜像的目标加载段重叠（函数未完整，但用途明确）。

### 核心数据结构
- `struct kimage`：kexec 镜像的核心控制结构，包含段信息、控制页、目标页、不可用页等列表，以及镜像类型（普通或崩溃转储）等元数据。

## 3. 关键实现

### 段合法性验证（`sanity_check_segment_list`）
该函数执行多层验证：
1. **地址对齐与范围检查**：所有段的起始/结束地址必须页对齐，且不能超过架构定义的 `KEXEC_DESTINATION_MEMORY_LIMIT`。
2. **段间重叠检测**：遍历所有段对，确保任意两个段的目标内存区域不重叠。
3. **缓冲区大小约束**：每个段的源数据大小（`bufsz`）不得超过目标内存大小（`memsz`）。
4. **内存用量限制**：单个段或所有段总页数不得超过系统总 RAM 页数的一半，防止因过度分配导致软锁定（soft lockup）。
5. **崩溃内核特殊处理**（`CONFIG_CRASH_DUMP`）：若为崩溃转储类型（`KEXEC_TYPE_CRASH`），所有段必须严格位于预留的崩溃内核内存区域（`crashk_res`）内。

### kimage 结构初始化（`do_kimage_alloc_init`）
- 分配零初始化的 `kimage` 结构。
- 初始化段链表头（`head`, `entry`, `last_entry`）。
- 初始化三个关键页列表：
  - `control_pages`：存放跳转到新内核所需的汇编 stub 代码页。
  - `dest_pages`：存放新内核的目标加载页。
  - `unusable_pages`：存放因冲突等原因无法使用的页。
- 若启用 `CONFIG_CRASH_HOTPLUG`，初始化热插拔相关字段。

### 内存模型约束
- kexec 跳转阶段要求物理地址与虚拟地址一一映射（identity mapping），因此控制代码必须位于 `0 - TASK_SIZE` 范围内。
- 仅支持物理地址可表示为 `unsigned long` 的内存（即 `(pfn << PAGE_SHIFT) <= ULONG_MAX`）。
- 架构可通过 `KEXEC_SOURCE_MEMORY_LIMIT` 和 `KEXEC_DEST_MEMORY_LIMIT` 进一步限制内存使用范围。

## 4. 依赖关系

### 头文件依赖
- **内核核心子系统**：`mm.h`（内存管理）、`fs.h`（文件系统）、`slab.h`（内存分配）、`reboot.h`（重启逻辑）、`cpu.h`（CPU 热插拔）。
- **架构相关**：`asm/page.h`、`asm/sections.h`、`asm/kexec.h`（提供 `KEXEC_*_MEMORY_LIMIT` 等宏）。
- **安全与能力**：`capability.h`（权限检查）、`crypto/hash.h`（镜像校验）。
- **调试与日志**：`kmsg_dump.h`（崩溃日志转储）、`console.h`（控制台管理）。
- **内部头文件**：`kexec_internal.h`（kexec 内部接口）。

### 配置选项依赖
- `CONFIG_KEXEC`：kexec 基础功能。
- `CONFIG_CRASH_DUMP`：崩溃转储支持，影响段验证逻辑。
- `CONFIG_CRASH_HOTPLUG`：崩溃内核热插拔支持，扩展 `kimage` 结构。

## 5. 使用场景

1. **常规内核热替换**：通过 `kexec_load` 系统调用加载新内核，执行快速重启（绕过固件初始化）。
2. **崩溃转储（kdump）**：系统崩溃时，通过预加载的 `KEXEC_TYPE_CRASH` 类型镜像捕获内存转储（vmcore），用于事后分析。
3. **内核更新与测试**：开发或运维中快速切换内核版本，无需硬件重启。
4. **高可用系统**：在关键服务中实现内核级故障恢复，减少停机时间。

该文件作为 kexec 机制的核心，为上述场景提供安全、可靠的内存管理和镜像加载基础，确保新内核能正确接管系统控制权。