# kasan\quarantine.c

> 自动生成时间: 2025-12-07 16:17:26
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\quarantine.c`

---

# kasan/quarantine.c 技术文档

## 1. 文件概述

`kasan/quarantine.c` 实现了 KASAN（Kernel Address Sanitizer）的隔离区（Quarantine）机制。该机制用于延迟释放已释放但可能仍被非法访问的内存对象，从而提高检测 Use-After-Free（UAF）错误的能力。通过将释放的对象暂时放入隔离队列而非立即归还给内存分配器，KASAN 能在后续访问这些“已释放”内存时捕获违规行为。

隔离区由每个 CPU 的本地队列和一个全局循环批次队列组成，并支持动态调整大小以适应系统内存压力，防止因隔离区过大导致 OOM（Out-Of-Memory）。

## 2. 核心功能

### 主要数据结构

- **`struct qlist_head`**  
  表示一个单向链表队列，包含头指针、尾指针、总字节数和离线标志。
  
- **`cpu_quarantine`**（per-CPU）  
  每个 CPU 的本地隔离队列，用于暂存刚释放的对象。

- **`global_quarantine[QUARANTINE_BATCHES]`**  
  全局隔离批次数组，采用循环 FIFO 结构，存储从各 CPU 队列转移过来的批量对象。

- **`shrink_qlist`**（per-CPU）  
  用于内存回收路径的辅助队列，带自旋锁保护。

- **`remove_cache_srcu`**  
  SRCU（Sleepable RCU）同步机制，用于安全地移除特定 slab 缓存的所有隔离对象。

### 主要函数

- **`kasan_quarantine_put()`**  
  将指定对象放入当前 CPU 的隔离队列；若队列超过阈值，则批量转移到全局隔离区。

- **`kasan_quarantine_reduce()`**  
  当全局隔离区总大小超过限制时，释放最早一批对象以回收内存。

- **`qlist_free_all()`**  
  遍历并实际释放队列中所有对象回 slab 分配器。

- **`qlink_free()`**  
  执行单个隔离对象的实际释放操作，包括清除 KASAN 元数据和 shadow 内存标记。

- **`qlist_move_cache()`**（未完成）  
  （代码截断）预期用于将特定缓存类型的所有对象从一个队列迁移到另一个队列，通常用于缓存销毁时清理隔离对象。

## 3. 关键实现

### 隔离队列结构
- 使用轻量级单向链表 `qlist_head` 管理对象，每个节点为 `struct qlist_node`（嵌入在 `kasan_free_meta` 中）。
- 每个 CPU 维护一个本地队列（`cpu_quarantine`），避免锁竞争，提升性能。
- 全局隔离区由 `QUARANTINE_BATCHES` 个批次组成环形缓冲区，通过 `quarantine_head` 和 `quarantine_tail` 实现 FIFO。

### 内存管理策略
- 单个 CPU 队列最大为 `QUARANTINE_PERCPU_SIZE`（1MB）。
- 全局隔离区最大容量为系统物理内存的 `1/QUARANTINE_FRACTION`（即 1/32），再减去所有 CPU 队列的上限总和。
- 批次大小 `quarantine_batch_size` 动态计算，至少为 `QUARANTINE_PERCPU_SIZE`，确保高效批量处理。

### 并发与同步
- CPU 本地操作使用 `local_irq_save/restore` 禁用中断，保证原子性。
- 全局队列操作受 `quarantine_lock`（raw spinlock）保护。
- 使用 `SRCU`（`remove_cache_srcu`）协调 `kasan_quarantine_remove_cache()` 与隔离对象释放之间的同步，确保在缓存销毁时不会遗漏隔离中的对象。

### 安全释放机制
- 对象释放前会将对应的 KASAN shadow 字节设为 `KASAN_SLAB_FREE`，使后续访问触发 KASAN 报告。
- 若启用了 `init_on_free` 且 free metadata 存储在对象内部，则在释放前显式清零元数据，避免残留敏感信息。

## 4. 依赖关系

- **KASAN 核心模块**：依赖 `kasan.h` 中定义的元数据结构（如 `kasan_free_meta`）、shadow 内存操作和 `kasan_get_free_meta()` 等接口。
- **Slab 分配器**：通过 `___cache_free()` 将对象归还给底层 slab（SLAB/SLUB）；使用 `virt_to_slab()` 和 `slab_want_init_on_free()` 等 slab 内部接口。
- **内存管理子系统**：调用 `totalram_pages()` 获取系统内存总量，用于动态调整隔离区大小。
- **CPU 热插拔**：通过 `num_online_cpus()` 适配 CPU 数量变化。
- **同步原语**：使用 `percpu`、`raw_spinlock`、`SRCU` 和 `local_irq_*` 实现并发控制。
- **内存回收**：虽未直接注册 shrinker（注释提及 SLAB 不支持），但 `kasan_quarantine_reduce()` 可被外部调用以响应内存压力。

## 5. 使用场景

- **Use-After-Free 检测增强**：当内核启用 KASAN（特别是 `CONFIG_KASAN_GENERIC` 或 `CONFIG_KASAN_SW_TAGS`）时，`kfree()` 或 `kmem_cache_free()` 调用会先将对象放入隔离区而非立即释放，延长 UAF 检测窗口。
- **内存压力下的自动回收**：当系统内存紧张或隔离区超过阈值时，调用 `kasan_quarantine_reduce()` 释放最早隔离的一批对象，防止内存耗尽。
- **Slab 缓存销毁**：当某个 `kmem_cache` 被销毁时，需调用未在本文件中完整实现的 `kasan_quarantine_remove_cache()`（依赖 `qlist_move_cache`），将该缓存的所有隔离对象立即释放，避免悬空引用。
- **调试与测试**：在内核开发和测试阶段，隔离机制显著提升内存错误的可复现性和诊断能力。