# module\debug_kmemleak.c

> 自动生成时间: 2025-10-25 14:58:25
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `module\debug_kmemleak.c`

---

# module/debug_kmemleak.c 技术文档

## 1. 文件概述

该文件为 Linux 内核模块系统提供对 **kmemleak**（内核内存泄漏检测器）的支持。其主要作用是在模块加载过程中，将模块相关的可写、非可执行内存区域注册到 kmemleak 扫描机制中，以便 kmemleak 能够追踪这些区域中的指针引用，从而避免将仍在使用的动态分配内存误判为泄漏。

## 2. 核心功能

- **函数**：
  - `void kmemleak_load_module(const struct module *mod, const struct load_info *info)`  
    在模块加载时，向 kmemleak 注册模块结构体本身以及模块中所有可写且非可执行的已分配节（section）作为扫描区域。

- **数据结构（引用）**：
  - `struct module`：内核模块的核心描述结构。
  - `struct load_info`：模块加载过程中的临时信息结构，包含 ELF 头、节头表等。
  - `Elf_Shdr`（通过 `info->sechdrs` 访问）：ELF 节头描述符，用于判断节的属性。

## 3. 关键实现

- **模块结构体扫描**：  
  首先调用 `kmemleak_scan_area(mod, sizeof(struct module), GFP_KERNEL)`，将整个 `struct module` 实例标记为 kmemleak 的扫描区域，确保模块元数据中的指针不会被误判为泄漏。

- **节（Section）筛选逻辑**：  
  遍历 ELF 文件的所有节（从索引 1 开始，跳过空节），仅对同时满足以下条件的节进行扫描注册：
  - `SHF_ALLOC`：该节在运行时需要被加载到内存中。
  - `SHF_WRITE`：该节是可写的（通常包含数据段，如 `.data`、`.bss` 等）。
  - **非** `SHF_EXECINSTR`：该节**不是**可执行的（排除代码段如 `.text`）。

- **内存区域注册**：  
  对符合条件的节，调用 `kmemleak_scan_area()`，传入节在内核空间的虚拟地址（`sh_addr`）和大小（`sh_size`），通知 kmemleak 在后续的内存泄漏扫描中将该区域视为“根指针”来源，用于追踪潜在的内存引用。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/module.h>`：提供模块系统相关定义。
  - `<linux/kmemleak.h>`：提供 `kmemleak_scan_area()` 等 kmemleak 接口。
  - `"internal.h"`：模块子系统内部头文件，定义 `struct load_info` 等内部结构。

- **功能依赖**：
  - 依赖 **kmemleak 子系统**（需在内核配置中启用 `CONFIG_DEBUG_KMEMLEAK`）。
  - 与 **模块加载器**（`load_module()` 流程）紧密集成，在模块布局完成后、正式启用前调用此函数。

## 5. 使用场景

- 当内核启用 **kmemleak 内存泄漏检测功能** 且动态加载模块（通过 `insmod` 或 `modprobe`）时，此函数会被模块加载流程自动调用。
- 用于确保模块自身的数据段（如全局变量、静态变量等）中的指针能被 kmemleak 正确识别为有效引用，防止将模块仍在使用的动态分配内存（如通过 `kmalloc()` 分配）错误报告为内存泄漏。
- 仅在 `CONFIG_DEBUG_KMEMLEAK` 配置选项启用时编译进内核，对正常系统运行无影响。