# vmcore_info.c

> 自动生成时间: 2025-10-25 17:49:46
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `vmcore_info.c`

---

# vmcore_info.c 技术文档

## 1. 文件概述

`vmcore_info.c` 是 Linux 内核中用于支持内核崩溃转储（crash dump）机制的核心文件之一。该文件负责在系统崩溃前收集并保存关键的内核元数据（称为 **vmcoreinfo**），这些信息在后续使用 `crash` 或 `gdb` 等工具分析 vmcore 文件时至关重要。vmcoreinfo 包含了内核符号地址、数据结构布局、编译时配置、页表信息等，使得用户空间工具能够正确解析崩溃内存镜像。

## 2. 核心功能

### 全局变量
- `vmcoreinfo_data`：指向动态分配的缓冲区，用于存储 vmcoreinfo 的文本内容。
- `vmcoreinfo_size`：当前 `vmcoreinfo_data` 中已写入的数据长度。
- `vmcoreinfo_note`：指向 ELF note 结构的内存区域，用于将 vmcoreinfo 嵌入到 ELF 格式的 crash dump 中。
- `vmcoreinfo_data_safecopy`：指向位于“崩溃安全内存”中的 vmcoreinfo 数据副本，确保在系统崩溃后仍可访问。

### 主要函数
- `append_elf_note()`：将指定名称、类型和数据追加为一个 ELF note 条目。
- `final_note()`：在 ELF note 缓冲区末尾写入终止符（空 note）。
- `update_vmcoreinfo_note()`：使用当前 `vmcoreinfo_data` 重新构建 `vmcoreinfo_note`。
- `crash_update_vmcoreinfo_safecopy()`：将 vmcoreinfo 数据复制到安全内存区域，并更新 `vmcoreinfo_data_safecopy` 指针。
- `crash_save_vmcoreinfo()`：在系统即将崩溃前调用，更新崩溃时间戳并刷新 vmcoreinfo note。
- `vmcoreinfo_append_str()`：格式化字符串并追加到 `vmcoreinfo_data` 缓冲区，防止溢出。
- `arch_crash_save_vmcoreinfo()`（弱符号）：架构特定的 vmcoreinfo 扩展点，可由各架构实现。
- `paddr_vmcoreinfo_note()`（弱符号）：返回 `vmcoreinfo_note` 的物理地址，供 kexec 使用。
- `crash_save_vmcoreinfo_init()`：模块初始化函数，分配内存并填充初始 vmcoreinfo 内容。

### 宏辅助
文件大量使用 `VMCOREINFO_*` 宏（定义在其他头文件中），用于便捷地向 `vmcoreinfo_data` 添加：
- 符号地址（`VMCOREINFO_SYMBOL`）
- 结构体偏移量（`VMCOREINFO_OFFSET`）
- 结构体/类型大小（`VMCOREINFO_STRUCT_SIZE`, `VMCOREINFO_SIZE`）
- 数组长度（`VMCOREINFO_LENGTH`）
- 常量数值（`VMCOREINFO_NUMBER`）
- 字符串值（如 `VMCOREINFO_OSRELEASE`）

## 3. 关键实现

### ELF Note 构建
- `vmcoreinfo_note` 被格式化为标准的 **ELF note**（`PT_NOTE` 类型），名称为 `"VMCOREINFO"`。
- `append_elf_note()` 按照 ELF 规范对齐 name 和 desc 字段（以 `Elf_Word` 为单位向上取整）。
- `final_note()` 写入一个空 note 作为终止标记，符合 ELF note 列表惯例。

### 安全副本机制
- 为防止系统崩溃时常规内存损坏，`crash_update_vmcoreinfo_safecopy()` 允许将 vmcoreinfo 复制到预先保留的“崩溃安全内存”中。
- 在 `crash_save_vmcoreinfo()` 中，若存在安全副本，则临时切换 `vmcoreinfo_data` 指针指向该副本，确保生成的 note 基于可靠数据。

### 初始化内容
- `crash_save_vmcoreinfo_init()` 在内核初始化早期（`subsys_initcall` 阶段）执行：
  - 分配一页内存（`get_zeroed_page`）作为 `vmcoreinfo_data`。
  - 分配精确大小的内存（`alloc_pages_exact`）作为 `vmcoreinfo_note`。
  - 填充大量内核元数据，包括：
    - 内核版本（`init_uts_ns.name.release`）
    - Build ID（用于匹配调试符号）
    - 页大小（`PAGE_SIZE`）
    - 关键符号地址（如 `_stext`, `mem_map`, `swapper_pg_dir` 等）
    - 内存管理结构布局（`page`, `pglist_data`, `zone` 等的偏移和大小）
    - 位图和标志常量（如 `PG_lru`, `PG_head_mask` 等）
    - KASLR 相关符号（若启用 `CONFIG_KALLSYMS`）
    - 架构特定信息（通过 `arch_crash_save_vmcoreinfo()`）

### 溢出保护
- `vmcoreinfo_append_str()` 使用 `vscnprintf` 格式化字符串，并通过 `min()` 限制写入长度，确保不超过 `VMCOREINFO_BYTES`（通常为一页）。
- 若缓冲区满，会触发 `WARN_ONCE` 提示截断。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/kexec.h>`：kexec 和 crash dump 核心接口。
  - `<linux/buildid.h>`：获取内核 Build ID。
  - `<linux/utsname.h>`：获取内核版本信息。
  - `<asm/sections.h>`：访问内核链接段符号（如 `_stext`）。
  - `"kallsyms_internal.h"`：访问 kallsyms 内部符号表。
  - `"kexec_internal.h"`：kexec 内部辅助函数和宏定义（如 `VMCOREINFO_*`）。
- **架构依赖**：
  - 通过弱符号 `arch_crash_save_vmcoreinfo()` 和 `paddr_vmcoreinfo_note()` 允许架构代码覆盖默认行为。
  - 条件编译依赖多个内核配置选项（如 `CONFIG_NUMA`, `CONFIG_SPARSEMEM`, `CONFIG_KALLSYMS` 等）。
- **内存管理**：
  - 依赖 `memblock` 和 `vmalloc` 相关接口进行内存分配。
  - 与 `log_buf_vmcoreinfo_setup()`（来自 printk 子系统）集成以导出日志缓冲区信息。

## 5. 使用场景

- **内核崩溃转储（kdump/kexec）**：
  - 当系统发生严重错误（如 panic）并配置了 kdump 时，`crash_save_vmcoreinfo()` 被调用，更新崩溃时间并确保 vmcoreinfo note 最新。
  - 第二内核（capture kernel）通过 `paddr_vmcoreinfo_note()` 获取第一内核的 vmcoreinfo 物理地址，并将其嵌入到生成的 vmcore 文件中。
- **离线内存分析**：
  - 用户空间工具（如 `crash` utility）加载 vmcore 文件时，解析其中的 VMCOREINFO note，利用其中的元数据正确解读内存布局、符号地址和数据结构，从而进行有效的故障诊断。
- **热补丁与调试**：
  - vmcoreinfo 提供的结构体偏移和符号信息也可用于内核热补丁（livepatch）或高级调试场景，确保运行时与编译时视图一致。