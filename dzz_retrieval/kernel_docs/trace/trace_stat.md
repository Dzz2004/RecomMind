# trace\trace_stat.c

> 自动生成时间: 2025-10-25 17:38:16
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_stat.c`

---

# `trace/trace_stat.c` 技术文档

## 1. 文件概述

`trace/trace_stat.c` 是 Linux 内核中用于实现**统计追踪（statistic tracing）**功能的核心基础设施模块。该文件提供了一套通用框架，允许不同的追踪器（tracer）将其内部统计信息以**排序后的直方图（histogram）形式**通过 tracefs 文件系统暴露给用户空间。每次用户打开对应的 tracefs 文件时，系统会动态地从追踪器获取最新统计数据、按指定规则排序（通常为降序），并以可读格式输出。

该机制主要用于性能分析、调试和监控，例如分支预测命中率统计、函数调用频次等场景。

## 2. 核心功能

### 主要数据结构

- **`struct stat_node`**  
  表示红黑树中的一个节点，封装了追踪器提供的原始统计条目（`void *stat`）。

- **`struct stat_session`**  
  表示一个统计会话，对应 tracefs 中的一个文件。包含：
  - 指向 `tracer_stat` 的指针（定义统计行为）
  - 红黑树根节点（`stat_root`），用于存储并排序当前会话的所有统计条目
  - 互斥锁（`stat_mutex`），保护红黑树的并发访问
  - 对应的 tracefs 文件 dentry

- **`struct tracer_stat`**（定义在 `trace_stat.h` 中）  
  由具体追踪器实现的回调接口结构体，包含：
  - `stat_start()` / `stat_next()`：迭代器，用于遍历所有统计条目
  - `stat_show()`：将单个统计条目格式化输出到 seq_file
  - `stat_cmp()`：比较函数，用于排序（可选）
  - `stat_release()`：释放统计条目资源（可选）
  - `stat_headers()`：输出表头（可选）

### 主要函数

- **`register_stat_tracer()`**  
  向系统注册一个新的统计追踪器，自动在 `trace_stat/` 目录下创建对应文件。

- **`unregister_stat_tracer()`**  
  注销已注册的统计追踪器，并移除其 tracefs 文件。

- **`tracing_stat_open()`**  
  文件打开回调：初始化会话，调用追踪器获取所有统计条目并构建排序红黑树。

- **`tracing_stat_release()`**  
  文件关闭回调：释放本次会话构建的红黑树，避免内存泄漏。

- **`stat_seq_*()` 系列函数**  
  实现 `seq_file` 接口，用于按顺序遍历红黑树并输出内容。

- **`insert_stat()`**  
  将统计条目插入红黑树，使用 `tracer_stat->stat_cmp` 进行比较（若未提供则使用 `dummy_cmp` 插入最右侧）。

- **`__reset_stat_session()` / `reset_stat_session()`**  
  清空并释放当前会话的红黑树中所有节点。

## 3. 关键实现

### 动态构建与排序
- 每次用户打开 tracefs 统计文件时，都会**重新调用追踪器的迭代器**（`stat_start`/`stat_next`）获取最新数据。
- 所有统计条目被插入到**红黑树**中，利用 `tracer_stat->stat_cmp` 回调进行**降序排序**（`cmp >= 0` 时插入左子树）。
- 若追踪器未提供 `stat_cmp`，则使用 `dummy_cmp` 强制将所有节点插入树的最右侧，保持原始顺序。

### 内存与并发安全
- 每个 `stat_session` 拥有独立的红黑树和互斥锁（`stat_mutex`），确保多线程/多进程并发读取同一文件时的安全性。
- 文件关闭时自动释放本次会话分配的所有 `stat_node` 内存，并调用 `stat_release` 释放追踪器分配的统计条目资源。
- 全局会话列表 `all_stat_sessions` 由 `all_stat_sessions_mutex` 保护，确保注册/注销操作的原子性。

### seq_file 集成
- 使用标准 `seq_file` 机制实现大文件的分页读取。
- `SEQ_START_TOKEN` 用于在文件开头输出表头（如果 `stat_headers` 存在）。
- 遍历时通过 `rb_first()` 和 `rb_next()` 按红黑树顺序（即排序后顺序）访问节点。

### tracefs 集成
- 所有统计文件统一存放在 `tracefs/trace_stat/` 目录下。
- 文件权限为 `TRACE_MODE_WRITE`（实际为 `0644`），允许用户读取。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/tracefs.h>`：tracefs 文件系统接口
  - `<linux/rbtree.h>`：红黑树数据结构
  - `"trace_stat.h"`：`struct tracer_stat` 定义
  - `"trace.h"`：追踪子系统通用接口（如 `tracing_init_dentry()`）

- **内核子系统依赖**：
  - **Tracefs**：提供用户可见的接口文件
  - **Security Framework**：通过 `security_locked_down(LOCKDOWN_TRACEFS)` 检查是否允许访问 tracefs
  - **SLAB Allocator**：动态分配 `stat_session` 和 `stat_node`

- **被依赖方**：
  - 具体的统计追踪器（如 `branch tracer`、`function profiler` 等）需实现 `tracer_stat` 接口并调用 `register_stat_tracer()`。

## 5. 使用场景

- **分支预测统计**：`trace_branch.c` 使用此框架输出分支预测命中/未命中次数的直方图。
- **函数性能分析**：函数追踪器可统计各函数的调用次数、执行时间等，并按频次排序输出。
- **中断/软中断统计**：统计各类中断的触发次数和延迟。
- **锁竞争分析**：统计不同锁的争用情况。
- **通用调试工具**：任何需要将内核内部计数器以排序表格形式暴露给用户空间的场景。

用户通过读取 `/sys/kernel/tracing/trace_stat/<tracer_name>` 即可获得实时、排序后的统计信息，无需重启或重新配置追踪器。