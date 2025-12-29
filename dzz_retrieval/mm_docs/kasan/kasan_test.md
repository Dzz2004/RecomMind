# kasan\kasan_test.c

> 自动生成时间: 2025-12-07 16:16:26
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\kasan_test.c`

---

# kasan/kasan_test.c 技术文档

## 1. 文件概述

`kasan_test.c` 是 Linux 内核中用于测试 **Kernel Address Sanitizer (KASAN)** 功能的 KUnit 测试套件。该文件通过一系列精心设计的内存访问违规操作（如越界读写、释放后使用、非法释放等），验证 KASAN 在不同配置（如 `CONFIG_KASAN_GENERIC` 和 `CONFIG_KASAN_HW_TAGS`）下是否能正确检测并报告内存错误。测试利用内核的 tracepoint 机制监听控制台输出，以判断 KASAN 是否成功触发了预期的错误报告。

## 2. 核心功能

### 主要函数
- `kasan_suite_init()` / `kasan_suite_exit()`：KUnit 测试套件的初始化与清理函数，负责启用多报告模式、注册/注销控制台探针。
- `probe_console()`：tracepoint 回调函数，用于从内核日志中识别 KASAN 错误报告和异步故障信息。
- `kmalloc_oob_right()` / `kmalloc_oob_left()`：测试 kmalloc 分配内存的右/左边界越界访问。
- `kmalloc_node_oob_right()`：测试指定 NUMA 节点上的 kmalloc 越界。
- `kmalloc_pagealloc_*` 系列函数：针对 SLUB 分配器中大块内存（绕过 slab cache，直接使用页分配器）的越界、UAF（Use-After-Free）、非法释放等场景进行测试。
- `pagealloc_oob_right()`：测试直接页分配（`alloc_pages`）的越界访问（仅在非 GENERIC 模式下有效）。

### 关键数据结构与变量
- `test_status`：全局状态结构体，记录是否检测到 KASAN 报告 (`report_found`) 或异步故障 (`async_fault`)。
- `kasan_ptr_result` / `kasan_int_result`：用于防止编译器优化掉“无用”表达式的全局占位变量。
- `multishot`：保存原始 KASAN 多报告模式状态，测试期间临时启用以允许多次错误报告。

### 核心宏定义
- `KUNIT_EXPECT_KASAN_FAIL(test, expression)`：核心测试宏，执行给定表达式并验证其是否触发 KASAN 报告。包含对硬件标签 KASAN 的特殊处理（禁用迁移、重新启用标签检查）。
- `KASAN_TEST_NEEDS_CONFIG_ON/OFF`：根据内核配置条件性跳过测试。
- `KASAN_TEST_NEEDS_CHECKED_MEMINTRINSICS`：判断是否需要编译器对内存操作函数（如 `memcpy`）进行 KASAN 插桩。

## 3. 关键实现

### KASAN 报告检测机制
- 通过 `register_trace_console(probe_console, NULL)` 注册控制台输出探针。
- `probe_console()` 函数扫描每条内核日志，若包含 `"BUG: KASAN: "` 则标记 `test_status.report_found = true`；若包含 `"Asynchronous fault: "` 则标记 `test_status.async_fault = true`。
- 使用 `READ_ONCE()` / `WRITE_ONCE()` 和 `barrier()` 防止编译器对 `test_status` 的访问进行重排序或优化。

### 多报告模式管理
- 测试开始前调用 `kasan_save_enable_multi_shot()` 启用多报告模式，避免因 `panic_on_warn` 导致内核在首个错误后崩溃。
- 测试结束后通过 `kasan_restore_multi_shot()` 恢复原始设置。

### 硬件标签 KASAN (HW_TAGS) 特殊处理
- 在 `KUNIT_EXPECT_KASAN_FAIL` 宏中，若可能触发同步标签故障，则调用 `migrate_disable()` 禁用 CPU 迁移（因 HW_TAGS 状态是 per-CPU 的）。
- 若检测到同步故障（`report_found && !async_fault`），则调用 `kasan_enable_hw_tags()` 重新启用标签检查。
- 测试结束后调用 `migrate_enable()` 恢复迁移。

### 编译器优化规避
- 使用 `OPTIMIZER_HIDE_VAR(ptr)` 宏（通常展开为 `asm volatile("" : "+r"(ptr))`）防止编译器优化掉指针操作。
- 所有对 `test_status` 的读写均使用原子访问原语，并在关键表达式前后插入内存屏障。

### 测试隔离与状态重置
- 每次 `KUNIT_EXPECT_KASAN_FAIL` 执行后，都会重置 `test_status.report_found` 和 `test_status.async_fault` 为 `false`。
- 每个测试用例结束时（`kasan_test_exit`）会断言 `test_status.report_found == false`，确保没有意外的 KASAN 报告发生。

## 4. 依赖关系

- **KASAN 子系统**：依赖 `<linux/kasan.h>` 提供的核心 API（如 `kasan_enabled()`, `kasan_save_enable_multi_shot()` 等）及内部头文件 `"kasan.h"`。
- **KUnit 测试框架**：使用 `<kunit/test.h>` 提供的测试断言、跳过机制和生命周期管理。
- **内存管理子系统**：依赖 SLAB/SLUB 分配器（`kmalloc`/`kfree`）、页分配器（`alloc_pages`）及相关配置（如 `CONFIG_SLUB`, `KMALLOC_MAX_CACHE_SIZE`）。
- **Tracepoint 机制**：通过 `<linux/tracepoint.h>` 和 `trace/events/printk.h` 注册控制台输出探针。
- **体系结构相关**：包含 `<asm/page.h>` 获取页大小等架构定义，并针对 HW_TAGS 模式处理 CPU 迁移。

## 5. 使用场景

- **内核开发与调试**：开发者在修改 KASAN 相关代码后，运行此测试套件验证功能正确性。
- **持续集成 (CI)**：作为内核 CI 系统的一部分，在不同配置（GENERIC/HW_TAGS, SLAB/SLUB 等）下自动执行，确保 KASAN 行为符合预期。
- **新平台适配**：在将 KASAN 移植到新硬件架构（尤其是支持 MTE 的 ARM64 平台）时，用于验证 HW_TAGS 模式的检测能力。
- **回归测试**：防止未来内核变更破坏 KASAN 的内存错误检测功能，特别是针对边界情况（如大块内存分配、跨 granule 访问等）。