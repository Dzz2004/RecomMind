# kasan\report.c

> 自动生成时间: 2025-12-07 16:18:13
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\report.c`

---

# kasan/report.c 技术文档

## 1. 文件概述

`kasan/report.c` 是 Linux 内核中 **Kernel Address Sanitizer (KASAN)** 子系统的核心错误报告模块。该文件负责在检测到内存安全违规（如越界访问、释放后使用等）时，生成结构化、可读性强的错误报告，并根据配置决定是否触发内核 panic。它统一处理软件 KASAN（Generic 和 SW_TAGS）与硬件 KASAN（HW_TAGS）模式下的报告抑制、格式化输出、多报控制及测试集成逻辑。

## 2. 核心功能

### 主要全局变量
- `kasan_flags`：位图标志，用于控制报告行为（如 `KASAN_BIT_REPORTED`、`KASAN_BIT_MULTI_SHOT`）。
- `kasan_arg_fault`：通过内核启动参数 `kasan.fault=` 配置的故障响应策略（report/panic/panic_on_write）。

### 主要函数
- `report_suppressed_sw()`：判断当前是否处于软件 KASAN 的报告抑制状态（通过 `current->kasan_depth`）。
- `report_suppress_start()/report_suppress_stop()`：在生成报告期间临时禁用 KASAN 检查，防止死锁或误报。
- `report_enabled()`：检查是否允许生成新报告（受 `kasan_multi_shot` 控制）。
- `start_report()/end_report()`：报告生成的入口/出口，负责加锁、关闭 trace/lockdep、打印分隔线、处理 panic 策略。
- `print_error_description()`：打印错误类型、指令指针、访问地址、大小及任务信息。
- `print_track()`：打印分配/释放堆栈轨迹。
- `describe_object_addr()`：描述违规地址相对于合法对象的位置（左侧/内部/右侧）及所属 slab 缓存。

### 测试支持函数（条件编译）
- `kasan_save_enable_multi_shot()/kasan_restore_multi_shot()`：KUnit 测试中临时启用多报告模式。
- `kasan_kunit_test_suite_start()/end()`：标记 KASAN KUnit 测试执行状态。
- `fail_non_kasan_kunit_test()`：若非 KASAN 测试中触发 KASAN 错误，则标记测试失败。

### 初始化函数
- `early_kasan_fault()`：解析 `kasan.fault=` 启动参数。
- `kasan_set_multi_shot()`：解析 `kasan_multi_shot` 启动参数。

## 3. 关键实现

### 报告抑制机制
- **软件 KASAN**：通过 `current->kasan_depth` 计数器实现临界区抑制（`kasan_disable/enable_current()`），避免在 slab 元数据访问或报告自身代码中触发误报。
- **硬件 KASAN**：通过 CPU 特定指令（`hw_suppress_tag_checks_start/stop()`）动态关闭地址标签检查，并配合 `preempt_disable()` 确保抑制作用于当前 CPU。

### 多报告控制
- 默认仅报告首个错误（通过 `KASAN_BIT_REPORTED` 原子位标记）。
- 启用 `kasan_multi_shot` 后允许多次报告，便于测试和调试。
- KUnit 测试自动启用多报告模式，并提供保存/恢复原状态的接口。

### Panic 策略
- 支持三种策略：
  - `report`：仅打印错误（默认）。
  - `panic`：任何错误均触发 panic。
  - `panic_on_write`：仅写操作触发 panic。
- 通过 `check_panic_on_warn()` 与全局 `panic_on_warn` 设置联动。

### 错误描述生成
- 自动推断违规地址与合法对象的相对位置（左/右/内部）及偏移字节数。
- 区分访问类型（Read/Write）和释放操作（Free）。
- 打印 slab 缓存名、对象大小及分配/释放堆栈（通过 `stack_depot`）。

### 并发与可靠性保障
- 使用 `raw_spinlock_t report_lock` 保证报告输出的原子性。
- 调用 `lockdep_off()` 防止 LOCKDEP 干扰报告内容。
- 调用 `disable_trace_on_warning()` 遵循 traceoff_on_warning 接口。
- 报告后添加 `TAINT_BAD_PAGE` 污点标记。

## 4. 依赖关系

### 内核头文件依赖
- **KASAN 核心**：`<linux/kasan.h>`, `"kasan.h"`
- **内存管理**：`<linux/mm.h>`, `<linux/slab.h>`, `"../slab.h"`, `<linux/vmalloc.h>`
- **调度与任务**：`<linux/sched.h>`, `<linux/sched/task_stack.h>`
- **调试与追踪**：`<linux/stacktrace.h>`, `<linux/stackdepot.h>`, `<linux/ftrace.h>`, `<trace/events/error_report.h>`
- **底层架构**：`<asm/sections.h>`（用于地址有效性判断）

### 配置选项依赖
- `CONFIG_KASAN_GENERIC` / `CONFIG_KASAN_SW_TAGS` / `CONFIG_KASAN_HW_TAGS`：决定抑制机制实现。
- `CONFIG_KASAN_KUNIT_TEST` / `CONFIG_KASAN_MODULE_TEST`：启用测试专用接口。
- `CONFIG_KUNIT`：集成 KUnit 测试失败标记逻辑。

## 5. 使用场景

1. **运行时内存错误检测**：当 KASAN 检测到非法内存访问（如越界、UAF）时，调用本模块生成详细报告。
2. **内核调试与崩溃分析**：开发者通过报告中的堆栈、对象信息定位内存错误根源。
3. **自动化测试**：
   - KASAN 自带的 KUnit 测试套件利用 `kasan_multi_shot` 进行多错误验证。
   - 非 KASAN 的 KUnit 测试若意外触发 KASAN 错误，会被自动标记为失败。
4. **生产环境策略控制**：
   - 通过 `kasan.fault=panic` 在关键系统中强制宕机以防止数据损坏。
   - 通过 `kasan_multi_shot` 在压力测试中收集多个错误实例。
5. **硬件辅助 KASAN 支持**：在 ARM64 MTE 等硬件平台上，协调 CPU 标签检查抑制与报告生成。