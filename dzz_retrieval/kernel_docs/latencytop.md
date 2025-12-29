# latencytop.c

> 自动生成时间: 2025-10-25 14:31:05
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `latencytop.c`

---

# latencytop.c 技术文档

## 1. 文件概述

`latencytop.c` 实现了 Linux 内核中的延迟追踪基础设施，用于支持用户空间工具 `latencytop`。该机制并非追踪传统意义上的中断延迟（如 CPU 被其他任务占用），而是追踪应用程序因内核代表其睡眠（如等待 I/O、锁、资源等）而产生的延迟。延迟信息通过 `/proc/latency_stats`（系统级）和 `/proc/<pid>/latency`（进程级）导出，帮助开发者识别导致应用响应延迟的内核路径。

## 2. 核心功能

### 主要数据结构
- `struct latency_record`：存储延迟记录，包含：
  - `count`：该延迟原因发生的次数
  - `time`：累计延迟时间（微秒）
  - `max`：单次最大延迟时间（微秒）
  - `backtrace[LT_BACKTRACEDEPTH]`：字符串化的调用栈（函数地址）
- `latency_record[MAXLR]`：全局系统级延迟记录数组（`MAXLR = 128`）
- `latencytop_enabled`：全局开关，控制是否启用延迟追踪

### 主要函数
- `__account_scheduler_latency()`：核心入口函数，由调度器调用，记录一次延迟事件
- `account_global_scheduler_latency()`：将延迟记录合并到全局统计中
- `clear_tsk_latency_tracing()`：清除指定任务的延迟记录
- `clear_global_latency_tracing()`：清除全局延迟记录
- `lstats_show()`：生成 `/proc/latency_stats` 的输出内容
- `lstats_write()`：清空全局延迟记录（通过写 `/proc/latency_stats` 触发）
- `init_lstats_procfs()`：初始化 `/proc/latency_stats` 和 sysctl 接口

### Sysctl 接口
- `/proc/sys/kernel/latencytop`：控制 `latencytop_enabled` 开关，启用时自动开启调度统计（`force_schedstat_enabled()`）

## 3. 关键实现

### 延迟记录机制
- **调用栈捕获**：使用 `stack_trace_save_tsk()` 获取当前任务在调度点的调用栈（深度为 `LT_BACKTRACEDEPTH`）。
- **去重合并**：通过比较调用栈内容，将相同原因的延迟事件合并为一条记录，更新 `count`、`time` 和 `max`。
- **存储限制**：
  - 全局记录最多 `MAXLR`（128）条，满后不再记录新原因。
  - 每个任务最多记录 `LT_SAVECOUNT` 条（代码中硬编码为 32，注释称未来会优化为循环覆盖）。

### 过滤策略
- **跳过长可中断睡眠**：若睡眠可中断（`inter == 1`）且超过 5 毫秒（5000 微秒），视为用户主动等待（如 `select()`），不记录。
- **忽略无效延迟**：负值或零延迟（可能由时间回退引起）被直接丢弃。
- **跳过内核线程**：仅追踪用户进程（`tsk->mm != NULL`）。

### 并发控制
- 使用 `raw_spinlock_t latency_lock` 保护全局和进程级延迟记录的读写，确保多 CPU 环境下的数据一致性。

### 输出格式
`/proc/latency_stats` 每行格式为：
```
<count> <accumulated_time> <max_time> <func1> <func2> ... <funcN>
```
其中：
- `count`：延迟原因发生次数
- `accumulated_time`：累计延迟时间（微秒）
- `max_time`：单次最大延迟时间（微秒）
- 后续字段为调用栈函数符号（通过 `%ps` 格式化解析）

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/latencytop.h>`：定义 `struct latency_record` 和 `LT_BACKTRACEDEPTH`、`LT_SAVECOUNT` 等常量。
  - `<linux/stacktrace.h>`：提供 `stack_trace_save_tsk()` 用于捕获调用栈。
  - `<linux/sched/stat.h>`：提供 `force_schedstat_enabled()`，确保调度统计开启。
  - `<linux/proc_fs.h>`、`<linux/sysctl.h>`：实现 `/proc` 和 sysctl 接口。
- **内核配置依赖**：
  - `CONFIG_LATENCYTOP`：启用该功能。
  - `CONFIG_SCHEDSTATS`：延迟追踪依赖调度统计信息。
- **用户空间工具**：需配合 `latencytop` 工具解析 `/proc` 输出并可视化延迟原因。

## 5. 使用场景

- **性能调优**：开发者使用 `latencytop` 工具实时监控系统或特定进程的延迟热点，定位内核中导致应用卡顿的代码路径（如锁竞争、I/O 等待）。
- **系统诊断**：在实时性要求高的场景（如音视频处理、工业控制）中，分析不可接受的延迟来源。
- **内核开发**：验证新代码是否引入了意外的延迟，或评估调度器/子系统优化效果。
- **动态启用**：通过写 `/proc/sys/kernel/latencytop` 动态开启/关闭追踪，避免常驻开销。用户工具定期读取并清空 `/proc/latency_stats` 以持续收集新数据。