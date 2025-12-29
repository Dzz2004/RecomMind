# crash_core.c

> 自动生成时间: 2025-10-25 12:56:44
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `crash_core.c`

---

# crash_core.c 技术文档

## 1. 文件概述

`crash_core.c` 是 Linux 内核中实现崩溃转储（crash dump）核心功能的关键文件，主要负责在系统发生严重错误（如 panic）时，保存系统状态并引导至 crash kernel（即 kdump 内核），以便后续进行故障分析。该文件实现了与 kexec 机制集成的崩溃处理逻辑，包括 CPU 状态保存、vmcoreinfo 构建、ELF 头准备以及崩溃内核的加载与跳转。

## 2. 核心功能

### 主要全局变量
- `crash_notes`：每 CPU 变量，用于在系统崩溃时存储各 CPU 的寄存器状态（`note_buf_t` 类型）。

### 主要函数
- `kimage_crash_copy_vmcoreinfo(struct kimage *image)`  
  为 crash dump 分配并映射 vmcoreinfo 的安全副本，确保在崩溃时可安全访问。
  
- `kexec_should_crash(struct task_struct *p)`  
  判断当前任务是否应触发崩溃转储，依据是否处于中断上下文、是否为 init 进程、是否启用 `panic_on_oops` 等条件。

- `kexec_crash_loaded(void)`  
  检查是否已加载 crash kernel（通过 `kexec_crash_image` 是否非空），供外部模块调用。

- `__crash_kexec(struct pt_regs *regs)`  
  实际执行崩溃转储的核心函数，负责保存寄存器、更新 vmcoreinfo、关闭硬件并跳转至 crash kernel。

- `crash_kexec(struct pt_regs *regs)`  
  崩溃转储的入口函数，确保仅一个 CPU 执行（通过 `panic_cpu` 原子变量互斥），防止并发调用。

- `crash_prepare_elf64_headers(...)`  
  为 crash dump 生成符合 ELF64 格式的内存布局描述头，包含 CPU notes、vmcoreinfo note、内核文本段及物理内存区域的 PT_LOAD 段。

- `crash_exclude_mem_range(...)`  
  从 crash 内存范围列表中排除指定的内存区间（函数未完整，但意图明确）。

## 3. 关键实现

### 崩溃转储互斥机制
通过 `panic_cpu` 原子变量确保仅一个 CPU 能执行 `crash_kexec()`，避免多个 CPU 同时尝试加载 crash kernel 导致竞争。该机制复用 panic 的 CPU 锁定逻辑。

### vmcoreinfo 安全副本
在 `kimage_crash_copy_vmcoreinfo()` 中，使用 `kimage_alloc_control_pages()` 从保留的 crash 内存中分配页面，并通过 `vmap()` 创建内核虚拟映射。这样即使 crash kernel 区域被 `arch_kexec_protect_crashkres()` 保护（禁止直接访问），仍可通过 vmalloc 区域安全读写 vmcoreinfo。

### ELF64 头构建
`crash_prepare_elf64_headers()` 动态构造 ELF64 程序头：
- 为每个可能的 CPU 添加 `PT_NOTE` 段，指向 `crash_notes` 的物理地址；
- 添加一个 `PT_NOTE` 段用于 `vmcoreinfo`；
- 可选添加内核文本段的 `PT_LOAD`（用于调试工具如 GDB）；
- 为每个物理内存范围添加 `PT_LOAD` 段，描述可转储的物理内存区域。

### 内存范围管理
`crash_exclude_mem_range()` 用于从 crash dump 的内存范围列表中剔除不应包含的区域（如保留内存、设备内存等），采用区间裁剪与移动策略，保持范围列表有序。

## 4. 依赖关系

- **kexec 子系统**：依赖 `kexec.h` 和 `kexec_internal.h`，使用 `kimage` 结构、`kexec_crash_image` 全局变量及 `machine_kexec()` 等接口。
- **内存管理**：使用 `vmalloc`、`memblock`、`page` 相关 API 进行内存分配与映射。
- **CPU 热插拔与 SMP**：依赖 `cpuhotplug.h` 和 `raw_smp_processor_id()` 实现每 CPU 状态保存与 CPU 互斥。
- **调试信息**：集成 `buildid.h`、`btf.h`、`kallsyms_internal.h` 提供符号与类型信息。
- **架构相关代码**：通过 `asm/page.h`、`asm/sections.h` 获取 `_text`、`_end` 等符号地址及物理地址转换。
- **安全与加密**：包含 `crypto/sha1.h`（虽未在片段中使用，但可能用于完整性校验）。

## 5. 使用场景

- **系统崩溃转储（kdump）**：当内核发生不可恢复错误（如 Oops、panic）时，若已通过 `kexec_load` 加载 crash kernel，则调用 `crash_kexec()` 触发转储流程。
- **崩溃信息收集**：通过 `crash_notes` 保存各 CPU 寄存器状态，通过 `vmcoreinfo` 提供内核符号、数据结构布局等元数据，供 `crash` 或 `gdb` 工具分析 vmcore 文件。
- **内存快照生成**：`crash_prepare_elf64_headers()` 为 `/proc/vmcore` 提供 ELF 头信息，使用户空间工具能正确解析物理内存镜像。
- **安全隔离**：在启用 `crash_kexec_post_notifiers` 时，延迟执行 crash_kexec 至 panic 通知链之后，确保日志等关键信息被记录。