# kmemleak.c

> 自动生成时间: 2025-12-07 16:27:27
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kmemleak.c`

---

# kmemleak.c 技术文档

## 1. 文件概述

`kmemleak.c` 是 Linux 内核中用于检测内核内存泄漏（kernel memory leak）的调试工具实现文件。它通过跟踪内核动态分配的内存块，并周期性扫描内核地址空间，查找是否有指向这些内存块的有效指针。若某内存块在分配后经过一定时间仍未被任何指针引用，则被判定为潜在的内存泄漏。该机制类似于用户空间的垃圾回收中的“可达性分析”，但仅用于诊断目的，不会自动释放内存。

## 2. 核心功能

### 主要数据结构

- **`struct kmemleak_object`**  
  表示一个被跟踪的内存分配对象，包含以下关键字段：
  - `pointer` / `size`：分配的内存地址和大小
  - `flags`：对象状态标志（如 `OBJECT_ALLOCATED`, `OBJECT_PHYS` 等）
  - `count` / `min_count`：当前找到的引用指针数量及判定为泄漏所需的最小引用数
  - `use_count`：引用计数，用于 RCU 安全释放
  - `del_state`：删除状态，控制对象从全局列表中移除的时机
  - `area_list`：指定需扫描的子区域（可选）
  - `trace_handle`：分配时的栈回溯信息（通过 stackdepot 存储）
  - `jiffies` / `pid` / `comm`：分配时间、进程 ID 和命令名，用于报告上下文

- **全局数据结构**
  - `object_list`：所有已分配对象的链表
  - `gray_list`：待扫描的“灰色”对象列表（在当前扫描周期中需检查其内容）
  - `object_tree_root` / `object_phys_tree_root` / `object_percpu_tree_root`：基于红黑树的索引结构，用于根据指针地址快速查找对应的 `kmemleak_object`
  - `mem_pool`：预分配的对象池，避免在内存压力下因分配元数据失败而影响检测

### 主要函数（虽未完整列出，但可推断）

- **对象生命周期管理**：
  - `create_object()`：创建并注册新分配的内存块
  - `delete_object()` / `__remove_object()`：注销已释放的内存块
  - `get_object()` / `put_object()`：引用计数管理，配合 RCU 释放

- **内存扫描与分析**：
  - 扫描线程（`scan_mutex` 保护）遍历 `gray_list`，解析每个对象内存内容，查找可能指向其他对象的指针
  - 更新目标对象的 `count`，若引用不足且超时则标记为泄漏

- **接口与调试支持**：
  - 通过 `debugfs` 提供 `/sys/kernel/debug/kmemleak` 接口，支持手动触发扫描、清除报告、调整参数等
  - 支持 `kmemleak_alloc()` / `kmemleak_free()` 等钩子函数，由 SLAB、vmalloc、percpu 等分配器调用

## 3. 关键实现

### 锁定机制

采用多级锁策略以平衡并发性能与数据一致性：

- **`kmemleak_lock`（raw_spinlock_t）**  
  全局自旋锁，保护 `object_list` 和三棵红黑树的结构修改（插入/删除节点），以及 `del_state` 的变更。

- **`kmemleak_object.lock`（raw_spinlock_t）**  
  每对象自旋锁，保护对象内部元数据（如 `count`）的并发访问，并在扫描对象内存时持有，防止该内存被释放。

- **`scan_mutex`（mutex）**  
  互斥锁，确保同一时间仅有一个线程执行内存扫描。扫描期间操作 `gray_list`，并对其中每个对象调用 `get_object()` 增加引用计数，防止其被释放。

**锁顺序约定**：  
`scan_mutex` → `object->lock` → `kmemleak_lock` → `other_object->lock`（使用 `SINGLE_DEPTH_NESTING` 避免死锁）。禁止在未持有 `scan_mutex` 时嵌套 `kmemleak_lock` 与 `object->lock`。

### 对象生命周期与 RCU

- 所有 `kmemleak_object` 实例通过引用计数（`use_count`）管理生命周期。
- 当 `use_count` 降为 0 时，通过 RCU 回调异步释放对象，确保读取路径（如 `rcu_read_lock()` 保护下的查找）不会访问已释放内存。
- 删除对象时先标记 `DELSTATE_REMOVED`，延迟从 `object_list` 移除，直到无活跃引用。

### 扫描算法

- **灰色对象（Gray List）**：初始时所有新分配对象加入灰色列表。扫描时将其内存内容按指针大小解析，若发现值落在某已知对象地址范围内，则增加目标对象的 `count`。
- **泄漏判定**：对象需满足：
  1. `count < min_count`（默认 `min_count=1`）
  2. 分配时间超过 `MSECS_MIN_AGE`（5000ms）
  3. 未被标记为 `OBJECT_REPORTED`
- **扫描优化**：
  - 支持通过 `kmemleak_scan_area` 指定仅扫描对象内的特定区域
  - 若无法分配 `scan_area`，则回退到全对象扫描（`OBJECT_FULL_SCAN`）

### 内存池设计

- 使用静态数组 `mem_pool` 预分配固定数量的 `kmemleak_object`（数量由 `CONFIG_DEBUG_KMEMLEAK_MEM_POOL_SIZE` 配置）
- 避免在内存紧张或中断上下文中因动态分配元数据失败而导致跟踪丢失

## 4. 依赖关系

- **内存分配器**：依赖 SLAB、SLUB、SLOB、vmalloc、percpu 等子系统在分配/释放内存时调用 `kmemleak_alloc*()` / `kmemleak_free*()` 钩子。
- **调试基础设施**：
  - `debugfs`：提供用户交互接口
  - `stackdepot`：高效存储分配点的栈回溯
  - `RCU`：安全释放对象元数据
- **其他调试工具**：与 KASAN、KFENCE 互斥（通常不同时启用），因功能重叠且开销大。
- **架构相关代码**：通过 `<asm/sections.h>` 获取内核符号范围，用于排除静态数据区的误报。

## 5. 使用场景

- **内核开发与调试**：开发者在启用 `CONFIG_DEBUG_KMEMLEAK` 后，可通过 `debugfs` 接口检测驱动或子系统中的内存泄漏。
- **持续集成测试**：在自动化测试中定期触发 kmemleak 扫描，捕获回归引入的泄漏。
- **生产环境诊断（谨慎）**：在可控环境下临时启用以定位疑难内存问题，因其带来显著性能开销（内存与 CPU）。
- **与内存热插拔协同**：通过 `memory_hotplug` 通知机制，处理物理内存区域变化对扫描范围的影响。