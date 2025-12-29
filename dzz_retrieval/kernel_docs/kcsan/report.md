# kcsan\report.c

> 自动生成时间: 2025-10-25 14:21:39
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kcsan\report.c`

---

# kcsan/report.c 技术文档

## 文件概述

`kcsan/report.c` 是 Linux 内核 KCSAN（Kernel Concurrency Sanitizer）子系统中负责**数据竞争报告生成与管理**的核心模块。该文件实现了检测到潜在数据竞争后，如何收集、格式化、限频并安全输出诊断信息的完整逻辑，确保在高并发环境下仍能原子地生成清晰、可读的竞态报告，同时避免死锁和性能瓶颈。

## 核心功能

### 主要数据结构

- **`struct access_info`**  
  封装单次内存访问的关键信息：访问地址 (`ptr`)、大小 (`size`)、访问类型 (`access_type`)、任务 PID (`task_pid`)、CPU ID (`cpu_id`) 和指令指针 (`ip`)。

- **`struct other_info`**  
  用于在竞争双方线程间传递信息。包含对方线程的 `access_info`、调用栈 (`stack_entries`)、栈深度 (`num_stack_entries`)，以及指向对方 `task_struct` 的指针（用于详细锁信息打印）。

- **`struct report_time`**  
  用于实现报告限频机制，记录特定竞争模式（由两个调用栈帧标识）的最后报告时间。

- **全局静态数组**  
  - `other_infos[]`：预分配的 `other_info` 缓冲池，大小为 `CONFIG_KCSAN_NUM_WATCHPOINTS + NUM_SLOTS - 1`，避免动态分配。
  - `report_times[]`：固定大小的限频记录表，最大占用一个内存页。

- **`report_lock`**  
  原始自旋锁 (`raw_spinlock_t`)，用于序列化报告生成过程及对 `other_infos` 的访问。

### 主要函数

- **`rate_limit_report()`**  
  实现基于时间窗口的报告限频逻辑。若相同竞争模式在 `CONFIG_KCSAN_REPORT_ONCE_IN_MS` 毫秒内已报告过，则跳过本次报告。

- **`skip_report()`**  
  根据配置（如 `CONFIG_KCSAN_REPORT_VALUE_CHANGE_ONLY`）和访问特性（如值是否改变、是否涉及 RCU 函数）决定是否跳过报告。

- **`get_access_type()`**  
  将内部访问类型标志（如 `KCSAN_ACCESS_WRITE`, `KCSAN_ACCESS_ATOMIC` 等）转换为人类可读的字符串描述。

## 关键实现

### 无阻塞信息传递机制
- 使用预分配的 `other_infos[]` 数组作为生产者-消费者缓冲区，避免在报告路径上进行内存分配（这对调试内存分配器本身至关重要）。
- 通过**暂停填充 `other_info` 的线程**（而非引用计数）来安全传递 `task_struct*`，规避了在 `release_report()` 中释放任务结构可能导致的死锁。

### 安全的限频策略
- `report_times[]` 采用**固定大小数组**（最大一页），避免使用 `krealloc` 导致在调试分配器时死锁。
- 限频逻辑采用**滑动时间窗口**：遍历记录表，若找到匹配的竞争模式且其时间戳在有效窗口内，则限频；否则复用最旧的记录项。

### 报告内容过滤
- 在 `CONFIG_KCSAN_REPORT_VALUE_CHANGE_ONLY` 模式下，若检测到写操作但值未改变（`KCSAN_VALUE_CHANGE_MAYBE`），默认跳过报告。
- **例外处理**：对包含 `rcu_`、`_rcu`、`_srcu` 的函数名豁免此过滤，因 RCU 机制常涉及无副作用的写操作。

### 原子报告生成
- 全局 `report_lock` 确保整个报告生成过程（包括收集双方线程信息、打印栈回溯、锁持有状态等）的原子性，防止多竞争报告交错输出。

## 依赖关系

- **内核基础组件**：  
  依赖 `printk`（日志输出）、`jiffies`（时间戳）、`kallsyms`（符号解析）、`stacktrace`（栈回溯）、`sched`（任务信息）等核心子系统。
- **KCSAN 内部模块**：  
  与 `kcsan.c`（主检测逻辑）、`encoding.h`（访问类型编码）紧密协作；调用 `kcsan_skip_report_debugfs()` 实现运行时动态过滤。
- **锁调试设施**：  
  集成 `lockdep` 和 `debug_locks` 以在详细模式（`CONFIG_KCSAN_VERBOSE`）下打印线程持有的锁信息。

## 使用场景

- **数据竞争检测报告**：当 KCSAN 检测到两个非原子内存访问存在潜在竞争时，由触发 watchpoint 的线程调用此模块生成完整报告。
- **内核调试与验证**：在启用 KCSAN 的内核构建中，用于定位并发 bug，尤其适用于调试内存分配器、RCU、调度器等底层并发敏感代码。
- **性能与噪音控制**：通过限频机制和值变更过滤，在保证检出率的同时减少重复报告对系统性能的影响，适用于长时间运行的测试场景。