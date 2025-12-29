# static_call_inline.c

> 自动生成时间: 2025-10-25 16:29:06
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `static_call_inline.c`

---

# static_call_inline.c 技术文档

## 1. 文件概述

`static_call_inline.c` 是 Linux 内核中实现 **静态调用（Static Call）** 机制的核心文件之一。静态调用是一种运行时可动态更新的函数调用优化技术，它在编译时将函数调用点内联为对跳板（trampoline）的直接跳转，而在运行时可通过 `__static_call_update()` 动态修改所有调用点，使其跳转到新的目标函数，从而避免传统函数指针调用的间接开销。该机制常用于性能敏感路径（如调度、RCU、tracepoint 等），同时支持模块热插拔和初始化阶段的特殊处理。

## 2. 核心功能

### 主要函数

- `static_call_force_reinit(void)`  
  强制重新初始化静态调用机制，用于调试或特殊场景，必须在 `early_initcall()` 之前调用。

- `__static_call_update(struct static_call_key *key, void *tramp, void *func)`  
  核心更新函数：将指定 `key` 对应的所有静态调用点更新为调用 `func`，并更新跳板 `tramp`。支持内核和模块中的调用点。

- `__static_call_init(struct module *mod, struct static_call_site *start, struct static_call_site *stop)`  
  初始化静态调用站点，对站点按 `key` 排序，并建立 `key` 到站点的映射关系，同时执行首次 `arch_static_call_transform`。

- `__static_call_text_reserved(...)`  
  检查指定代码区间是否与活跃的静态调用站点冲突，用于内存热插拔或代码修改前的安全校验。

### 主要数据结构

- `struct static_call_site`  
  描述一个静态调用点的位置（`addr`）和关联的 `key`（带标志位）。

- `struct static_call_key`  
  静态调用的“键”，用于将多个调用点分组。包含当前函数指针 `func` 和类型/模块信息。

- `struct static_call_mod`  
  用于模块场景下，将模块与该模块中属于某 `key` 的调用点列表关联。

- 全局符号：
  - `__start_static_call_sites[]` / `__stop_static_call_sites[]`：内核镜像中所有静态调用点的链接器生成数组。
  - `__start_static_call_tramp_key[]` / `__stop_static_call_tramp_key[]`：跳板与 key 的映射。

### 辅助函数与宏

- `static_call_addr(site)`：计算调用点的实际地址（处理重定位）。
- `static_call_key(site)`：从站点中提取 `static_call_key*`（忽略标志位）。
- `static_call_is_init(site)` / `static_call_is_tail(site)`：检查站点是否位于 `__init` 段或是否为尾调用。
- `static_call_sort_entries()`：对站点按 `key` 排序，便于批量处理。
- `static_call_key_has_mods()` / `static_call_key_sites()`：判断 key 是否关联模块或直接站点。

## 3. 关键实现

### 地址重定位处理
由于静态调用站点在编译时使用相对地址存储，`static_call_addr()` 和 `__static_call_key()` 通过 `(long)field + (long)&field` 的方式计算出运行时绝对地址，这是处理位置无关代码（PIC）和内核重定位的关键技巧。

### 站点组织与模块支持
- **内核（vmlinux）场景**：为节省内存和避免早期内存分配，将首个站点指针直接编码到 `key->type` 的低有效位中（通过 `| 1` 标记）。
- **模块场景**：使用 `static_call_mod` 链表管理不同模块中属于同一 `key` 的站点，支持模块加载/卸载时的动态注册。

### 初始化与更新流程
1. **初始化**（`__static_call_init`）：
   - 对站点按 `key` 排序。
   - 标记位于 `__init` 段的站点（后续更新可跳过）。
   - 建立 `key` 到站点的映射。
   - 调用架构相关 `arch_static_call_transform` 执行首次转换（通常设为跳板）。

2. **更新**（`__static_call_update`）：
   - 更新 `key->func`。
   - 更新跳板 `tramp` 指向新函数。
   - 遍历所有关联站点（包括模块），调用 `arch_static_call_transform` 修改调用点指令（如 x86 的 `jmp` 目标）。
   - 跳过 `__init` 段中已初始化的站点（因不会被执行）。

### 安全与并发控制
- 使用 `cpus_read_lock()` 防止 CPU 热插拔期间的并发问题。
- 使用 `static_call_mutex` 保护 `key` 和站点数据结构的修改。
- 通过 `kernel_text_address()` 验证调用点是否在可执行内核文本段，避免修改无效地址。

## 4. 依赖关系

- **架构依赖**：依赖 `asm/sections.h` 和 `arch_static_call_transform()`（由各架构实现，如 x86、ARM64）。
- **内核子系统**：
  - `linux/module.h`：模块加载/卸载时的静态调用站点管理。
  - `linux/cpu.h` / `linux/smp.h`：CPU 热插拔和并发控制。
  - `linux/sort.h`：站点排序。
  - `linux/slab.h`：模块场景下的动态内存分配。
- **链接器脚本**：依赖链接器生成的 `__start/stop_static_call_sites` 等符号，这些在 `vmlinux.lds` 中定义。

## 5. 使用场景

- **内核核心优化**：在调度器、RCU、中断处理等高频路径中替代函数指针，减少间接调用开销。
- **动态追踪（ftrace）**：作为 tracepoint 或 kprobe 的底层机制，实现零开销探针。
- **模块热插拔**：模块加载时注册其静态调用站点，卸载时自动清理，确保调用点始终有效。
- **初始化优化**：`__init` 段的调用点在初始化完成后可被安全忽略，减少运行时开销。
- **安全代码修改**：在 livepatch 或内核热补丁中，安全地替换函数实现而不影响运行中的调用。