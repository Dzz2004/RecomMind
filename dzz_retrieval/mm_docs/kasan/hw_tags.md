# kasan\hw_tags.c

> 自动生成时间: 2025-12-07 16:14:10
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\hw_tags.c`

---

# `kasan/hw_tags.c` 技术文档

## 1. 文件概述

`kasan/hw_tags.c` 是 Linux 内核中硬件标签（Hardware Tag-Based）KASAN（Kernel Address Sanitizer）的核心实现文件。该文件负责初始化和管理基于硬件内存标签（如 ARM64 的 MTE，Memory Tagging Extension）的 KASAN 功能，包括命令行参数解析、运行模式配置、vmalloc 区域支持以及每 CPU 初始化逻辑。其目标是利用硬件特性高效检测内核中的内存安全问题（如越界访问、释放后使用等），同时提供同步（sync）、异步（async）和非对称（asymm）等多种检测模式。

## 2. 核心功能

### 主要全局变量
- `kasan_arg`：控制 KASAN 是否启用（`off`/`on`）。
- `kasan_arg_mode`：指定 KASAN 运行模式（`sync`/`async`/`asymm`）。
- `kasan_arg_vmalloc`：控制是否对 vmalloc 分配的内存启用标签。
- `kasan_flag_enabled`：静态键（static key），表示 KASAN 是否已启用。
- `kasan_mode`：当前生效的 KASAN 模式（`KASAN_MODE_SYNC` 等）。
- `kasan_flag_vmalloc`：静态键，表示是否启用 vmalloc 标签。
- `kasan_page_alloc_sample` 和 `kasan_page_alloc_sample_order`：用于对 page allocator 的分配进行采样（减少性能开销）。
- `kasan_page_alloc_skip`（per-CPU）：记录跳过的 page allocator 分配次数。

### 主要函数
- `early_kasan_flag()` / `early_kasan_mode()` / `early_kasan_flag_vmalloc()` / `early_kasan_flag_page_alloc_sample()` / `early_kasan_flag_page_alloc_sample_order()`：解析内核启动参数（`kasan=`, `kasan.mode=`, `kasan.vmalloc=`, `kasan.page_alloc.sample=`, `kasan.page_alloc.sample.order=`）。
- `kasan_init_hw_tags_cpu()`：为每个 CPU 初始化硬件标签功能（支持 CPU 热插拔）。
- `kasan_init_hw_tags()`：在启动 CPU 上执行一次性的 KASAN 硬件标签初始化。
- `__kasan_unpoison_vmalloc()`：对 vmalloc 分配的内存进行“解毒”（unpoison），即设置有效的内存标签（仅限 `VM_ALLOC` 类型）。
- `unpoison_vmalloc_pages()`：为 vmalloc 区域中的每个物理页设置指定的标签。
- `init_vmalloc_pages()`：清除 vmalloc 页面的高字节（用于未启用 KASAN 时的初始化）。

## 3. 关键实现

### 命令行参数处理
通过 `early_param()` 宏注册多个启动参数：
- `kasan=off/on`：全局开关。
- `kasan.mode=sync/async/asymm`：选择检测模式。
- `kasan.vmalloc=off/on`：控制 vmalloc 标签。
- `kasan.page_alloc.sample=N` 和 `kasan.page_alloc.sample.order=M`：对大块页面分配启用采样机制，以降低性能开销。

### 初始化流程
1. **硬件能力检查**：`kasan_init_hw_tags()` 首先调用 `system_supports_mte()` 确认 CPU 支持 MTE。
2. **参数应用**：根据命令行参数设置 `kasan_mode` 和 `kasan_flag_vmalloc` 静态键。
3. **标签子系统初始化**：调用 `kasan_init_tags()` 完成底层标签管理结构的初始化。
4. **启用 KASAN**：通过 `static_branch_enable(&kasan_flag_enabled)` 激活 KASAN 功能。
5. **CPU 级初始化**：`kasan_init_hw_tags_cpu()` 在每个 CPU 上调用 `kasan_enable_hw_tags()` 启用硬件标签功能（如设置 TCR_EL1.TBI 等寄存器位）。

### vmalloc 支持
- **限制**：硬件标签 KASAN 仅支持 `VM_ALLOC` 类型的 vmalloc 分配（即通过 `vmalloc()`/`vzalloc()` 等分配的内存）。
- **原因**：
  - 硬件标签只能应用于物理内存，且一个物理页只能有一个有效标签。
  - 非 `VM_ALLOC` 映射可能由其他子系统创建，难以统一管理标签。
- **实现**：`__kasan_unpoison_vmalloc()` 为 `VM_ALLOC` 区域分配随机标签，并通过 `unpoison_vmalloc_pages()` 将标签写入每个物理页的 `page->flags` 中（通过 `page_kasan_tag_set()`）。

### 采样机制
- 对 `order >= kasan_page_alloc_sample_order` 的页面分配，以 `1/kasan_page_alloc_sample` 的概率跳过 KASAN 检查。
- 使用 per-CPU 变量 `kasan_page_alloc_skip` 跟踪跳过次数，避免频繁调用随机数生成器。

## 4. 依赖关系

- **架构依赖**：依赖 ARM64 架构的 MTE（Memory Tagging Extension）支持，通过 `system_supports_mte()` 和 `kasan_enable_hw_tags()` 等架构相关函数交互。
- **内存管理子系统**：
  - 依赖 `mm/vmalloc.c` 提供 `find_vm_area()`、`vmalloc_to_page()` 等接口。
  - 与页面分配器（`mm/page_alloc.c`）集成，通过 `___GFP_SKIP_KASAN` 标志跳过某些分配的标签处理。
- **KASAN 通用框架**：包含 `"kasan.h"`，与软件 KASAN（shadow-based）共享部分基础设施，但实现独立。
- **静态键（Static Keys）**：使用 `DEFINE_STATIC_KEY_FALSE/TRUE` 实现运行时零开销的条件判断。

## 5. 使用场景

- **内核开发与调试**：在支持 MTE 的 ARM64 平台上启用 KASAN，用于检测内核内存错误。
- **性能敏感场景**：通过 `async` 或 `asymm` 模式降低运行时开销，或通过 `kasan.page_alloc.sample` 对大内存分配进行采样。
- **虚拟内存调试**：当需要检测 vmalloc 区域的内存错误时，启用 `kasan.vmalloc=on`。
- **生产环境部署**：在支持 MTE 的服务器或移动设备上，使用异步模式进行轻量级内存安全监控。
- **CPU 热插拔**：通过 `kasan_init_hw_tags_cpu()` 确保新上线的 CPU 正确初始化硬件标签功能。