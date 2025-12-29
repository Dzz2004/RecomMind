# page_poison.c

> 自动生成时间: 2025-12-07 17:04:51
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `page_poison.c`

---

# page_poison.c 技术文档

## 1. 文件概述

`page_poison.c` 实现了 Linux 内核中的**页面毒化（Page Poisoning）**机制，用于在内存页被释放到伙伴系统（buddy allocator）时填充特定的毒化值（`PAGE_POISON`），并在后续分配时检测该值是否被意外修改。此机制主要用于**检测内存越界写、Use-After-Free 等内存错误**，是内核调试和内存安全的重要工具。该功能可通过内核启动参数 `page_poison=1` 启用。

## 2. 核心功能

### 全局变量
- `_page_poisoning_enabled_early`：布尔变量，记录早期启动阶段是否通过命令行启用了页面毒化。
- `_page_poisoning_enabled`：静态键（static key），用于运行时高效判断页面毒化是否启用。

### 主要函数
- `early_page_poison_param()`：解析内核启动参数 `page_poison`，设置 `_page_poisoning_enabled_early`。
- `poison_page()`：对单个页面进行毒化（填充 `PAGE_POISON` 字节）。
- `__kernel_poison_pages()`：批量毒化连续的多个页面。
- `unpoison_page()`：在页面重新分配前检查其内容是否仍为毒化值，并报告异常。
- `__kernel_unpoison_pages()`：批量检查并“解毒”多个页面。
- `check_poison_mem()`：检测内存区域是否被非法修改，区分单比特翻转与严重内存破坏。
- `__kernel_map_pages()`（仅当 `CONFIG_ARCH_SUPPORTS_DEBUG_PAGEALLOC` 未定义时）：空实现，表示架构不支持基于映射的调试页分配。

### 辅助函数
- `single_bit_flip()`：判断两个字节是否仅有一位不同（用于识别可能的硬件单比特错误）。

## 3. 关键实现

### 页面毒化流程
- 当页面被释放到 buddy allocator 时，若页面毒化启用，则调用 `__kernel_poison_pages()`。
- `poison_page()` 使用 `kmap_atomic()` 临时映射高内存页，绕过 KASAN 的检测（通过 `kasan_disable_current()`/`kasan_enable_current()`），然后用 `PAGE_POISON`（通常为 `0xaa`）填充整个页面。

### 毒化检查机制
- 在页面重新分配前，调用 `__kernel_unpoison_pages()` 触发 `unpoison_page()`。
- `unpoison_page()` 映射页面后调用 `check_poison_mem()` 验证内容：
  - 使用 `memchr_inv()` 快速查找首个非毒化字节。
  - 若发现异常，使用速率限制（ratelimit）避免日志泛洪。
  - 区分两种错误：
    - **单比特翻转**：可能由硬件 ECC 错误引起，打印 `"single bit error"`。
    - **其他修改**：视为内存破坏，打印 `"memory corruption"`。
  - 输出十六进制内存转储、调用栈及页面详细信息（通过 `dump_page()`）。

### 性能优化
- 使用 `static_key`（`_page_poisoning_enabled`）实现零开销分支：当功能关闭时，相关代码路径可被编译器完全跳过。
- 速率限制（`DEFINE_RATELIMIT_STATE`）防止频繁错误导致系统卡死。

### KASAN 兼容性
- 在毒化/检查过程中显式禁用 KASAN 检测（`kasan_disable_current()`），因为 KASAN 仍认为页面处于“已分配”状态，直接访问会触发误报。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/poison.h>`：提供 `PAGE_POISON` 宏定义。
  - `<linux/kasan.h>`：提供 KASAN 相关接口（`kasan_disable_current` 等）。
  - `<linux/mm.h>`、`<linux/highmem.h>`：提供页面管理及高内存映射函数（`kmap_atomic`）。
  - `<linux/ratelimit.h>`：提供日志速率限制功能。
- **配置依赖**：
  - 依赖 `CONFIG_PAGE_POISONING` 内核配置选项。
  - 若架构支持 `CONFIG_ARCH_SUPPORTS_DEBUG_PAGEALLOC`，则 `__kernel_map_pages` 由架构层实现；否则本文件提供空实现。
- **与其他子系统交互**：
  - 与 **伙伴分配器（buddy allocator）** 紧密集成，在 `free_pages_prepare()` 和 `prep_new_page()` 中调用毒化/解毒函数。
  - 与 **KASAN（Kernel Address Sanitizer）** 协同工作，避免检测冲突。

## 5. 使用场景

- **内核调试**：开发人员启用 `page_poison=1` 后，可捕获 Use-After-Free、缓冲区溢出等内存错误。
- **生产环境监控**：在稳定性要求高的系统中，可长期启用以检测潜在的硬件内存故障（如单比特错误）或驱动 bug。
- **安全加固**：通过填充不可预测的毒化值（结合 `CONFIG_PAGE_POISONING_ZERO` 可设为 0），增加攻击者利用 UAF 漏洞的难度。
- **错误诊断**：当检测到内存破坏时，自动输出详细的内存转储和调用栈，加速问题定位。