# sched\wait_bit.c

> 自动生成时间: 2025-10-25 16:21:40
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\wait_bit.c`

---

# `sched/wait_bit.c` 技术文档

## 1. 文件概述

`sched/wait_bit.c` 实现了 Linux 内核中基于**位（bit）等待机制**的通用等待/唤醒接口。该机制允许任务在某个内存地址的特定位被清除（或满足特定条件）之前进入睡眠状态，并在该位状态改变时被唤醒。这种机制广泛用于页缓存、inode 状态、设备状态等需要基于位标志进行同步的场景。

该文件提供了一套标准化的等待队列哈希表、等待入口结构、唤醒函数以及通用等待循环逻辑，支持可中断、不可中断、带超时、I/O 调度等多种等待模式。

## 2. 核心功能

### 主要数据结构

- **`bit_wait_table[WAIT_TABLE_SIZE]`**  
  全局静态哈希等待队列数组，大小为 256（`WAIT_TABLE_BITS = 8`），用于将不同 `(word, bit)` 对映射到不同的等待队列，减少竞争。

- **`struct wait_bit_key`**  
  表示等待目标的键结构，包含：
  - `void *flags`：指向被监视的位图（word）
  - `int bit_nr`：被监视的位编号（-1 表示变量级等待）
  - `unsigned long timeout`：超时时间（仅用于带超时的等待）

- **`struct wait_bit_queue_entry`**  
  等待队列项，内嵌 `wait_queue_entry`，包含一个 `wait_bit_key`，用于在唤醒时匹配目标。

### 主要函数

| 函数 | 功能 |
|------|------|
| `bit_waitqueue(void *word, int bit)` | 根据 `(word, bit)` 计算并返回对应的哈希等待队列头 |
| `__wait_on_bit()` | 通用位等待循环：测试位状态，调用用户动作函数，直到位清除或动作返回非零 |
| `__wait_on_bit_lock()` | 带“锁语义”的位等待：在位清除后尝试原子置位，实现类似自旋锁的获取逻辑 |
| `out_of_line_wait_on_bit*()` | 封装函数，用于避免内联膨胀，供外部模块调用 |
| `wake_up_bit(void *word, int bit)` | 唤醒所有在 `(word, bit)` 上等待的任务 |
| `__wake_up_bit()` | `wake_up_bit` 的底层实现 |
| `bit_wait*()` 系列函数 | 预定义的等待动作函数：<br> - `bit_wait`：普通调度<br> - `bit_wait_io`：I/O 调度<br> - `bit_wait_timeout`：带超时普通调度<br> - `bit_wait_io_timeout`：带超时 I/O 调度 |
| `init_wait_var_entry()` / `wake_up_var()` | 支持对整个变量（而非特定位）的等待/唤醒（`bit_nr = -1`） |
| `wait_bit_init()` | 初始化 `bit_wait_table` 中的所有等待队列头 |

## 3. 关键实现

### 哈希映射机制
- 使用 `hash_long(val, WAIT_TABLE_BITS)` 对 `(word << shift | bit)` 进行哈希，其中 `shift` 为 5（32 位）或 6（64 位），确保地址对齐不影响哈希分布。
- `__cacheline_aligned` 保证 `bit_wait_table` 按缓存行对齐，减少 false sharing。

### 等待循环逻辑
- `__wait_on_bit()`：  
  循环中先 `prepare_to_wait()` 加入队列，然后测试位是否仍置位。若是，则调用用户提供的 `action` 函数（如 `bit_wait`）。循环继续直到位被清除或 `action` 返回非零（如收到信号）。
- `__wait_on_bit_lock()`：  
  使用 `prepare_to_wait_exclusive()` 加入**独占等待队列**，避免惊群效应。在位清除后，尝试 `test_and_set_bit()` 原子置位，成功则获得“锁”；失败则继续等待。

### 唤醒匹配机制
- `wake_bit_function()` 作为默认唤醒回调，仅当 `wait_bit_key` 的 `flags` 和 `bit_nr` 与唤醒参数完全匹配 **且** 目标位**仍为置位状态**时，才调用 `autoremove_wake_function` 唤醒任务。
- 注意：**唤醒前必须确保内存屏障**（如 `smp_mb__after_atomic()`），以保证位清除操作对等待者可见。

### 变量级等待支持
- 通过 `bit_nr = -1` 实现对整个指针变量的等待（如 `wait_var_event()` 宏），由 `var_wake_function()` 处理匹配逻辑（忽略 `bit_nr`）。

### 超时处理
- 超时版本（如 `out_of_line_wait_on_bit_timeout`）在 `wait_bit_key` 中设置 `timeout = jiffies + timeout`，由 `bit_wait_timeout` 等函数检查是否超时。

## 4. 依赖关系

- **头文件依赖**：  
  依赖 `<linux/wait.h>`、`<linux/sched.h>`、`<linux/hash.h>` 等，使用 `wait_queue_head_t`、`prepare_to_wait`、`schedule` 等核心调度原语。
- **内联宏依赖**：  
  依赖 `DEFINE_WAIT_BIT`、`__WAIT_BIT_KEY_INITIALIZER` 等宏（定义在 `wait.h` 中）。
- **导出符号**：  
  多个函数通过 `EXPORT_SYMBOL` 或 `EXPORT_SYMBOL_GPL` 导出，供其他内核模块（如 `mm/`、`fs/`、`block/`）使用。
- **初始化依赖**：  
  `wait_bit_init()` 由内核启动时调用（通过 `core_initcall` 或类似机制），确保 `bit_wait_table` 在使用前初始化。

## 5. 使用场景

- **页缓存状态同步**：  
  在 `mm/filemap.c` 中，等待页面 `PG_locked`、`PG_writeback` 等标志位清除。
- **Inode 状态等待**：  
  在 `fs/inode.c` 中，等待 `I_SYNC`、`I_FREEING` 等 inode 标志。
- **块设备 I/O 等待**：  
  等待请求完成标志位。
- **通用位标志同步**：  
  任何需要基于单个位进行任务阻塞/唤醒的场景，如设备状态机、资源锁等。
- **变量值等待**：  
  通过 `wait_var_event()` 等宏，等待某个变量变为特定值（底层使用 `bit_nr = -1` 机制）。

该机制提供了一种轻量、高效、可扩展的基于位的同步原语，是 Linux 内核中重要的底层同步基础设施之一。