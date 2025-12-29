# module\livepatch.c

> 自动生成时间: 2025-10-25 15:03:55
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `module\livepatch.c`

---

# module/livepatch.c 技术文档

## 1. 文件概述

`module/livepatch.c` 是 Linux 内核模块子系统中用于支持 **内核实时补丁（Livepatch）** 功能的关键文件。该文件主要负责在模块加载过程中持久化保存模块的 ELF（Executable and Linkable Format）元数据信息，以便后续 livepatch 机制能够正确解析和重定向函数符号。这些信息在普通模块初始化完成后通常会被释放，但 livepatch 模块需要长期保留以支持运行时的符号解析和函数替换。

## 2. 核心功能

### 主要函数

- **`copy_module_elf(struct module *mod, struct load_info *info)`**  
  将模块加载时的 ELF 相关信息（ELF 头、节头表、节名字符串表、符号表索引）从临时加载结构 `load_info` 复制到模块结构 `module` 的 `klp_info` 字段中，供 livepatch 使用。

- **`free_module_elf(struct module *mod)`**  
  释放由 `copy_module_elf()` 分配的 `klp_info` 及其包含的动态内存，用于模块卸载时的资源清理。

### 关键数据结构

- **`struct module::klp_info`**  
  指向一个动态分配的结构体，用于存储 livepatch 所需的 ELF 元数据，包括：
  - `hdr`：ELF 文件头
  - `sechdrs`：节头表（section header table）的副本
  - `secstrings`：节名称字符串表的副本
  - `symndx`：符号表节（.symtab）在节头表中的索引

## 3. 关键实现

- **ELF 信息持久化**：  
  在模块加载阶段，`load_info` 结构体包含临时的 ELF 解析数据。普通模块在初始化完成后会释放这些数据，但 livepatch 模块需长期保留。`copy_module_elf()` 使用 `kmalloc` 和 `kmemdup` 将关键 ELF 结构深拷贝到 `mod->klp_info` 中。

- **符号表地址重定向**：  
  一个关键实现细节是将符号表节头的 `sh_addr` 字段重定向到 `mod->core_kallsyms.symtab`。这是因为模块初始化完成后，原始位于 init 内存区域的符号表会被释放，而 `core_kallsyms.symtab` 是保留在 core 内存中的完整符号表副本，livepatch 必须使用这个持久地址进行符号解析。

- **错误处理与资源释放**：  
  函数采用分阶段内存分配，并在失败时通过标签（`free_sechdrs`, `free_info`）回滚已分配资源，避免内存泄漏。

- **内存管理**：  
  所有分配均使用 `GFP_KERNEL` 标志，适用于进程上下文中的常规内存分配。

## 4. 依赖关系

- **内部依赖**：
  - `#include "internal.h"`：依赖模块子系统的内部头文件，可能包含 `struct module` 的扩展定义。
  - 使用 `struct load_info`（定义于 `kernel/module/internal.h`），该结构在模块加载过程中由 `setup_load_info()` 等函数填充。

- **外部依赖**：
  - 依赖内核通用内存管理接口（`kmalloc`, `kmemdup`, `kfree`）。
  - 与 livepatch 核心机制（如 `kernel/livepatch/` 子系统）紧密协作，为其提供模块符号解析所需的基础数据。
  - 依赖 `module.c` 中定义的 `module` 结构体及其 `core_kallsyms` 字段。

## 5. 使用场景

- **内核实时补丁（Livepatch）模块加载**：  
  当使用 `klp_module_compose()` 或类似机制加载 livepatch 模块时，内核会调用 `copy_module_elf()` 保存 ELF 元数据，使得后续的符号查找（如通过 `kallsyms` 或 livepatch 的对象匹配逻辑）能够正确解析补丁目标函数的地址。

- **模块卸载清理**：  
  当 livepatch 模块被卸载时，`free_module_elf()` 被调用以释放之前分配的 ELF 信息内存，防止资源泄漏。

- **符号解析与函数重定向**：  
  在 livepatch 应用过程中，系统依赖 `klp_info` 中保存的节头表和符号表信息，将补丁中的新函数正确映射到被替换的旧函数地址，实现无缝热更新。