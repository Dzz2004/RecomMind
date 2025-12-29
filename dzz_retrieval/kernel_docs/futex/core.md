# futex\core.c

> 自动生成时间: 2025-10-25 13:31:54
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `futex\core.c`

---

# futex/core.c 技术文档

## 文件概述

`futex/core.c` 是 Linux 内核中快速用户空间互斥锁（Futex, Fast Userspace muTEXes）子系统的核心实现文件。该文件提供了 Futex 机制的基础功能，包括全局哈希表管理、超时定时器设置、以及用于唯一标识用户空间 futex 变量的键（key）生成逻辑。Futex 是用户空间同步原语（如互斥锁、信号量等）在内核中的高效支撑机制，允许在无竞争情况下完全在用户空间完成操作，仅在需要阻塞或唤醒时才陷入内核。

## 核心功能

### 主要数据结构

- **`__futex_data`**：包含全局 futex 等待队列哈希桶数组（`futex_queues`）及其大小（`futex_hashsize`），使用 `__read_mostly` 和缓存行对齐优化访问性能。
- **`union futex_key`**：用于唯一标识一个 futex 的联合体结构，根据是否为共享映射（`FLAGS_SHARED`）采用不同字段组合：
  - **共享 futex**：`(inode->i_sequence, page->index, offset_within_page)`
  - **私有 futex**：`(current->mm, address, 0)`
- **`fail_futex`**（条件编译）：用于故障注入测试的配置结构，支持通过内核参数和 debugfs 控制 futex 操作失败行为。

### 主要函数

- **`futex_hash()`**：根据 `futex_key` 计算哈希值，并返回对应的全局哈希桶（`futex_hash_bucket`）。
- **`futex_setup_timer()`**：初始化高分辨率定时器（`hrtimer_sleeper`），用于支持带超时的 futex 等待操作。
- **`get_inode_sequence_number()`**：为 inode 生成全局唯一的 64 位序列号，确保即使 inode 被回收重建也不会产生键冲突。
- **`get_futex_key()`**：根据用户空间地址 `uaddr` 和标志 `flags`，生成用于标识 futex 的 `futex_key`。这是 futex 机制正确性和安全性的关键函数。

## 关键实现

### 全局哈希表设计

- 所有等待中的 futex 都通过 `futex_key` 映射到一个全局哈希表中的桶（`futex_hash_bucket`）。
- 哈希表大小为 2 的幂，使用位掩码 `futex_hashsize - 1` 进行取模运算，提升性能。
- `__futex_data` 结构体对齐到两个指针大小，确保 `queues` 和 `hashsize` 位于同一缓存行，减少 CPU 缓存未命中。

### Futex 键（Key）生成策略

- **私有 futex**（`!FLAGS_SHARED`）：直接使用当前进程的内存描述符 `mm` 和对齐后的虚拟地址作为键。在无 MMU 系统中，仅使用地址，因为整个系统只有一个地址空间。
- **共享 futex**（`FLAGS_SHARED`）：
  - 通过 `get_user_pages_fast()` 获取对应用户页的物理页结构。
  - 使用 inode 的唯一序列号（由 `get_inode_sequence_number()` 生成）、页在文件中的索引（`page->index`）以及页内偏移构成键。
  - inode 序列号通过全局原子计数器分配，确保即使 inode 被释放后重建，新 inode 也会获得不同的序列号，从而避免不同文件间的 futex 错误匹配（false-positive），这对 PI-futex（优先级继承 futex）至关重要。

### 故障注入支持

- 通过 `CONFIG_FAIL_FUTEX` 配置选项启用。
- 支持通过内核启动参数 `fail_futex=` 配置故障注入属性。
- 提供 `ignore-private` debugfs 接口，可选择性地忽略对私有 futex 的故障注入，便于针对性测试。

### 超时定时器设置

- `futex_setup_timer()` 封装了高分辨率定时器的初始化逻辑。
- 根据 `FLAGS_CLOCKRT` 标志选择使用 `CLOCK_REALTIME` 或 `CLOCK_MONOTONIC` 时钟源。
- 支持可选的超时范围（`range_ns`），用于优化定时器精度和功耗。

## 依赖关系

- **头文件依赖**：
  - `<linux/jhash.h>`：提供 Jenkins 哈希函数 `jhash2()`。
  - `<linux/pagemap.h>`、`<linux/mm.h>`：用于页管理和 `get_user_pages_fast()`。
  - `<linux/hrtimer.h>`：高分辨率定时器支持。
  - `"futex.h"`：Futex 子系统内部头文件，定义关键数据结构和常量。
  - `"../locking/rtmutex_common.h"`：为 PI-futex 提供实时互斥锁支持。
- **子系统依赖**：
  - **内存管理（MM）**：依赖页表遍历、页锁定和 VMA 管理。
  - **调度器**：futex 等待和唤醒最终会调用调度器进行任务阻塞和唤醒。
  - **时间子系统**：依赖高分辨率定时器实现超时功能。
  - **故障注入框架**：用于测试目的。

## 使用场景

- **用户空间同步原语实现**：glibc 的 `pthread_mutex_t`、`sem_t` 等在竞争激烈时会调用 `futex()` 系统调用，内核通过本文件提供的机制进行阻塞和唤醒。
- **跨进程同步**：当多个进程共享同一内存区域（如通过 `mmap` 映射同一文件）时，使用共享 futex 实现同步。
- **进程内同步**：线程间使用私有 futex 进行高效同步。
- **实时应用**：PI-futex 支持优先级继承，防止优先级反转，适用于实时任务。
- **内核测试**：通过故障注入机制验证 futex 相关代码路径的健壮性。