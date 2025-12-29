# kcsan\kcsan.h

> 自动生成时间: 2025-10-25 14:19:29
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kcsan\kcsan.h`

---

# `kcsan/kcsan.h` 技术文档

## 1. 文件概述

`kcsan/kcsan.h` 是 Linux 内核中 **Kernel Concurrency Sanitizer (KCSAN)** 动态数据竞争检测器的核心头文件。该文件定义了 KCSAN 的全局控制变量、统计计数器、报告接口以及与中断上下文和任务上下文交互所需的辅助函数。KCSAN 用于在运行时检测内核中的数据竞争（data races），帮助开发者发现并发访问中的潜在问题。

## 2. 核心功能

### 全局变量
- `kcsan_enabled`：布尔值，用于全局启用或禁用 KCSAN 检测。
- `kcsan_udelay_task` / `kcsan_udelay_interrupt`：分别指定在任务上下文和中断上下文中检测时引入的延迟时间（微秒），用于增加竞争暴露概率。
- `kcsan_counters[KCSAN_COUNTER_COUNT]`：原子长整型数组，用于记录 KCSAN 运行时的各类统计信息。

### 枚举类型
- `enum kcsan_counter_id`：定义 KCSAN 统计计数器的种类，包括：
  - `KCSAN_COUNTER_USED_WATCHPOINTS`：当前使用的观察点数量
  - `KCSAN_COUNTER_SETUP_WATCHPOINTS`：设置的观察点总数
  - `KCSAN_COUNTER_DATA_RACES`：检测到的数据竞争总数
  - `KCSAN_COUNTER_ASSERT_FAILURES`：因竞争导致的 ASSERT 失败次数
  - `KCSAN_COUNTER_NO_CAPACITY`：因无可用观察点槽位而跳过的次数
  - `KCSAN_COUNTER_REPORT_RACES`：因多个线程同时检查同一观察点而仅报告一次的次数
  - `KCSAN_COUNTER_RACES_UNKNOWN_ORIGIN`：值变化但无法确定写入者来源的竞争
  - `KCSAN_COUNTER_UNENCODABLE_ACCESSES`：无法编码为有效观察点的访问
  - `KCSAN_COUNTER_ENCODING_FALSE_POSITIVES`：因编码导致误报的次数
- `enum kcsan_value_change`：描述观察到的值是否发生变化，用于决定是否报告竞争：
  - `KCSAN_VALUE_CHANGE_MAYBE`：未观察到变化，但可报告（取决于配置）
  - `KCSAN_VALUE_CHANGE_FALSE`：未变化，不应报告
  - `KCSAN_VALUE_CHANGE_TRUE`：值已变化，应报告

### 函数接口
- `kcsan_save_irqtrace(struct task_struct *task)`  
  保存当前任务的中断标志状态（IRQ trace），防止 KCSAN 自身操作污染原始状态。
- `kcsan_restore_irqtrace(struct task_struct *task)`  
  恢复之前保存的中断标志状态。
- `kcsan_skip_report_debugfs(unsigned long func_addr)`  
  根据 debugfs 配置判断是否应跳过对指定函数地址所在函数的数据竞争报告。
- `kcsan_report_set_info(...)`  
  当前线程命中并消费了一个观察点，设置报告所需的基本访问信息（由竞争线程调用）。
- `kcsan_report_known_origin(...)`  
  当前线程发现其设置的观察点被另一线程命中，基于对方设置的信息生成完整竞争报告。
- `kcsan_report_unknown_origin(...)`  
  在无明确竞争线程的情况下（如值在延迟后发生变化），报告“来源未知”的数据竞争。

### 宏定义
- `KCSAN_CHECK_ADJACENT`：定义在检查观察点时需同时检查的相邻内存地址数量（默认为 1）。
- `NUM_SLOTS`：计算观察点槽位总数，公式为 `1 + 2 * KCSAN_CHECK_ADJACENT`，用于支持对齐和邻近访问的检测。

## 3. 关键实现

- **观察点机制**：KCSAN 使用有限数量的“观察点”（watchpoints）来监控内存访问。每个观察点记录地址、大小、访问类型等信息。当另一线程访问该地址时，可能触发竞争检测。
- **邻近访问检查**：通过 `KCSAN_CHECK_ADJACENT` 支持检测与观察点地址相邻的访问，提升对非对齐或跨缓存行访问的覆盖能力。
- **双阶段报告**：
  1. 竞争线程调用 `kcsan_report_set_info()` 设置冲突信息；
  2. 原始设置观察点的线程调用 `kcsan_report_known_origin()` 生成完整报告。
- **未知来源竞争**：当启用延迟检测（通过 `udelay`）后，若值发生变化但未捕获到明确的竞争线程，则调用 `kcsan_report_unknown_origin()` 报告。
- **统计计数**：所有计数器通过 `atomic_long_t` 实现，确保在慢路径（如报告生成）中安全更新，供 debugfs 导出分析。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/atomic.h>`：用于原子操作（统计计数器）
  - `<linux/kcsan.h>`：用户态或架构无关的 KCSAN 接口定义
  - `<linux/sched.h>`：依赖 `struct task_struct`，用于保存/恢复任务的 IRQ 状态
- **模块依赖**：
  - 依赖 KCSAN 核心实现（如 `kcsan.c`）提供观察点管理、竞争检测逻辑
  - 与 debugfs 集成，用于动态控制报告过滤（`kcsan_skip_report_debugfs`）
  - 与内核调度器和中断子系统交互，确保在不同上下文（任务/中断）中正确运行

## 5. 使用场景

- **内核开发与调试**：在启用 `CONFIG_KCSAN` 的内核中，该头文件被 KCSAN 核心代码、内存访问插桩（instrumentation）逻辑以及报告模块包含，用于实现运行时数据竞争检测。
- **竞争报告生成**：当两个线程并发访问同一内存区域且至少一个是写操作时，KCSAN 通过本文件定义的接口收集信息并生成详细竞争报告。
- **性能调优与分析**：通过 `kcsan_counters` 提供的统计数据，开发者可评估 KCSAN 覆盖率、误报率及系统开销。
- **动态控制**：通过 `kcsan_enabled` 和 debugfs 接口，可在运行时开启/关闭检测或过滤特定函数的竞争报告，适用于生产环境调试或性能敏感场景。