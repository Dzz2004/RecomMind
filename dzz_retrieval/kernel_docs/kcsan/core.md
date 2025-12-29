# kcsan\core.c

> 自动生成时间: 2025-10-25 14:17:10
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kcsan\core.c`

---

# kcsan/core.c 技术文档

## 文件概述

`kcsan/core.c` 是内核竞争条件检测器（KCSAN, Kernel Concurrency Sanitizer）的核心运行时实现文件。该文件负责管理观察点（watchpoints）的设置、查找与清除，实现对并发内存访问冲突的动态检测。KCSAN 通过概率性地监视内存访问，无需对所有内存访问进行插桩，从而在较低性能开销下检测数据竞争。

## 核心功能

### 主要全局变量
- `kcsan_enabled`：控制 KCSAN 是否启用的全局开关。
- `watchpoints[]`：原子长整型数组，用于存储编码后的观察点信息。
- `kcsan_cpu_ctx`：每个 CPU 的上下文结构，用于中断上下文中的 KCSAN 状态管理。
- 模块参数（可通过 `/sys/module/kcsan/parameters/` 调整）：
  - `early_enable`：是否在早期启动阶段启用 KCSAN。
  - `udelay_task` / `udelay_interrupt`：任务/中断上下文中检测前的延迟微秒数。
  - `skip_watch`：跳过监视的指令计数器。
  - `interrupt_watcher`：是否监视中断上下文中的访问。
  - `weak_memory`（仅当 `CONFIG_KCSAN_WEAK_MEMORY` 启用）：是否启用弱内存序检测。

### 主要函数
- `find_watchpoint()`：在观察点表中查找与给定地址范围匹配的观察点。
- `insert_watchpoint()`：尝试将新的观察点插入观察点表。
- `try_consume_watchpoint()` / `consume_watchpoint()` / `remove_watchpoint()`：管理观察点的消费与移除。
- `get_ctx()`：获取当前执行上下文（任务或中断）的 KCSAN 上下文。
- `kcsan_check_scoped_accesses()`：检查当前上下文中注册的作用域访问（scoped accesses）。

### 核心数据结构
- `struct kcsan_ctx`：KCSAN 执行上下文，包含作用域访问链表、禁用标志等。
- `struct kcsan_scoped_access`：表示一个作用域内的内存访问，用于延迟检查。

## 关键实现

### 观察点管理
- **编码存储**：每个观察点通过 `encode_watchpoint()` 编码为单个 `atomic_long_t`，包含地址、大小和访问类型（读/写），避免使用锁。
- **槽位索引策略**：
  - 使用 `watchpoint_slot(addr)` 将地址映射到主槽位。
  - 通过 `SLOT_IDX` 和 `SLOT_IDX_FAST` 宏支持检查相邻槽位（由 `KCSAN_CHECK_ADJACENT` 控制），以处理跨槽访问和槽位冲突。
  - 数组大小为 `CONFIG_KCSAN_NUM_WATCHPOINTS + NUM_SLOTS - 1`，避免快速路径中的取模运算。
- **无锁操作**：使用 `atomic_long_try_cmpxchg_relaxed()` 实现观察点的原子插入和消费。

### 上下文管理
- **双上下文支持**：任务上下文使用 `current->kcsan_ctx`，中断上下文使用 per-CPU 变量 `kcsan_cpu_ctx`。
- **作用域访问**：通过链表管理延迟检查的访问（如 `kcsan_check_scoped_accesses()`），避免在禁用区域内重复检查。

### 检测逻辑
- **概率性检测**：通过 `kcsan_skip` 计数器和随机延迟（`kcsan_udelay_*`）控制检测频率，平衡开销与覆盖率。
- **原子访问识别**：根据访问类型标志（`KCSAN_ACCESS_ATOMIC`、`KCSAN_ACCESS_ASSERT`）和配置（`CONFIG_KCSAN_ASSUME_PLAIN_WRITES_ATOMIC`）判断访问是否为原子操作，避免误报。

## 依赖关系

- **内部依赖**：
  - `encoding.h`：提供观察点的编码/解码函数。
  - `kcsan.h`：定义核心数据结构和常量。
  - `permissive.h`：提供宽松模式下的行为控制。
- **内核子系统**：
  - 调度器（`linux/sched.h`）：用于获取当前任务上下文。
  - 原子操作（`linux/atomic.h`）：实现无锁观察点管理。
  - Per-CPU 变量（`linux/percpu.h`）：管理中断上下文状态。
  - 内存访问（`linux/uaccess.h`）：处理用户空间访问区域。

## 使用场景

- **数据竞争检测**：在 SMP 系统中检测未同步的并发内存访问（如未加锁的共享变量读写）。
- **开发与调试**：内核开发者启用 KCSAN 后，可在运行时捕获竞争条件，通过报告定位问题代码。
- **中断与任务交互**：通过 `kcsan_interrupt_watcher` 参数控制是否检测中断与任务之间的竞争。
- **弱内存序系统**：在启用 `CONFIG_KCSAN_WEAK_MEMORY` 的架构（如 ARM、RISC-V）上检测内存重排序导致的竞争。