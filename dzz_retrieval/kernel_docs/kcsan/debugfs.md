# kcsan\debugfs.c

> 自动生成时间: 2025-10-25 14:18:03
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kcsan\debugfs.c`

---

# kcsan/debugfs.c 技术文档

## 1. 文件概述

`kcsan/debugfs.c` 是 Linux 内核 KCSAN（Kernel Concurrency Sanitizer）动态数据竞争检测器的 debugfs 接口实现文件。该文件提供了通过 debugfs 文件系统与 KCSAN 运行时交互的能力，包括启用/禁用检测、查看内部统计计数器、配置函数报告过滤列表（白名单/黑名单）、以及执行微基准测试等功能。用户空间可通过读写 `/sys/kernel/debug/kcsan` 文件来控制和监控 KCSAN 的行为。

## 2. 核心功能

### 主要数据结构

- **`kcsan_counters[KCSAN_COUNTER_COUNT]`**  
  全局原子计数器数组，用于统计 KCSAN 各类内部事件（如设置观察点次数、检测到的数据竞争数等）。

- **`counter_names[]`**  
  与 `kcsan_counters` 对应的可读名称字符串数组，用于 debugfs 输出。

- **`report_filterlist`**  
  用于过滤报告的函数地址列表结构体，包含：
  - `addrs`: 函数地址数组
  - `size`: 数组容量
  - `used`: 已使用元素数量
  - `sorted`: 是否已排序（用于二分查找）
  - `whitelist`: 布尔值，指示列表是白名单（true）还是黑名单（false）

- **`report_filterlist_lock`**  
  保护 `report_filterlist` 的原始自旋锁（raw spinlock），支持在原子上下文中安全访问。

### 主要函数

- **`microbenchmark(unsigned long iters)`**  
  执行 KCSAN 核心路径的微基准测试，临时禁用 KCSAN 并反复调用 `__kcsan_check_access` 以测量性能开销。

- **`kcsan_skip_report_debugfs(unsigned long func_addr)`**  
  根据 `report_filterlist` 判断是否应跳过对指定函数地址的数据竞争报告。

- **`insert_report_filterlist(const char *func)`**  
  将指定函数名解析为地址并插入到过滤列表中，支持动态扩容。

- **`set_report_filterlist_whitelist(bool whitelist)`**  
  设置过滤列表模式为白名单或黑名单。

- **`show_info(struct seq_file *file, void *v)`**  
  向 debugfs 文件输出 KCSAN 当前状态，包括启用状态、所有计数器值和过滤列表内容。

- **`debugfs_write(...)`**  
  处理用户写入 debugfs 文件的命令，支持 `on`/`off`、`microbench=`、`whitelist`/`blacklist`、`!function_name` 等指令。

- **`kcsan_debugfs_init(void)`**  
  初始化函数，在内核启动时创建 debugfs 文件 `/sys/kernel/debug/kcsan`。

## 3. 关键实现

### 过滤列表的动态管理
- 过滤列表采用动态数组实现，初始容量为 4，按需倍增扩容。
- 插入新地址时，若容量不足，先在锁外预分配新数组，再在锁内验证并切换指针，避免在原子上下文中分配内存。
- 使用 `kallsyms_lookup_name()` 将函数名解析为内核符号地址，并通过 `kallsyms_lookup_size_offset()` 获取函数起始地址以确保精确匹配。
- 列表在首次查询时懒排序（`sorted = false` 触发 `sort()`），后续查询使用 `bsearch()` 进行高效二分查找。

### 白名单/黑名单逻辑
- 若为**白名单模式**（`whitelist = true`），仅当函数**不在**列表中时才跳过报告（即只报告列表中的函数）。
- 若为**黑名单模式**（`whitelist = false`），当函数**在**列表中时跳过报告（即屏蔽列表中的函数）。
- 默认行为等效于空黑名单（报告所有函数）。

### 微基准测试设计
- 临时保存并重置当前任务的 `kcsan_ctx` 上下文，避免干扰。
- 强制设置 `kcsan_enabled = false`，确保只测试快速路径（fast-path）开销，不触发观察点设置等慢速路径。
- 使用 `get_cycles()` 精确测量循环执行的 CPU 周期数。

### 并发安全
- 所有对 `report_filterlist` 的修改和查询均通过 `raw_spin_lock_irqsave()` 保护，确保在中断和原子上下文中的安全性。
- 计数器使用 `atomic_long_t` 类型，保证多核并发更新的原子性。

## 4. 依赖关系

- **KCSAN 核心模块** (`kcsan.h`, `kcsan.c`)：依赖 `kcsan_enabled` 全局开关、`kcsan_counters` 计数器、`__kcsan_check_access()` 接口及 `KCSAN_ACCESS_*` 访问类型定义。
- **内核符号解析** (`kallsyms.h`)：使用 `kallsyms_lookup_name()` 和 `kallsyms_lookup_size_offset()` 解析函数地址。
- **Debugfs 子系统** (`debugfs.h`)：通过 `debugfs_create_file()` 创建调试接口文件。
- **内存管理** (`slab.h`)：使用 `kmalloc_array()` 动态分配过滤列表内存。
- **排序与查找** (`sort.h`, `bsearch.h`)：对过滤列表进行排序和二分查找。
- **任务上下文** (`sched.h`)：访问 `current->kcsan_ctx` 任务特定的 KCSAN 上下文。

## 5. 使用场景

- **动态启停 KCSAN**：通过向 debugfs 文件写入 `on`/`off`，在运行时启用或禁用数据竞争检测，便于针对性测试。
- **性能分析**：使用 `microbench=<iters>` 命令评估 KCSAN 快速路径的性能开销，辅助优化核心检测逻辑。
- **报告过滤**：
  - 添加函数到黑名单（`!function_name`）以屏蔽已知安全或无关紧要的竞争报告。
  - 切换至白名单模式（`whitelist`）后，仅报告指定函数内的竞争，缩小问题排查范围。
- **运行时监控**：读取 debugfs 文件获取 KCSAN 内部计数器（如 `data_races`、`no_capacity` 等），分析检测覆盖率和资源使用情况。
- **调试辅助**：结合 `kallsyms` 符号信息，精确控制报告粒度，提升数据竞争调试效率。