# slab_common.c

> 自动生成时间: 2025-12-07 17:22:45
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `slab_common.c`

---

# slab_common.c 技术文档

## 1. 文件概述

`slab_common.c` 是 Linux 内核中 Slab 分配器的通用实现文件，包含与具体分配策略（如 SLAB、SLUB、SLOB）无关的公共函数和基础设施。该文件负责管理 Slab 缓存的创建、合并、销毁等核心逻辑，并提供统一的接口供上层使用。它实现了缓存注册、命名、对齐计算、调试支持以及与内存子系统交互的基础功能。

## 2. 核心功能

### 主要全局变量
- `slab_state`：表示 Slab 子系统的初始化状态（如 DOWN、PARTIAL、UP 等）
- `slab_caches`：全局链表，维护所有已注册的 `kmem_cache` 实例
- `slab_mutex`：保护 `slab_caches` 链表的互斥锁
- `kmem_cache`：指向用于分配 `kmem_cache` 结构本身的缓存对象
- `slab_caches_to_rcu_destroy`：待通过 RCU 安全方式销毁的缓存链表
- `slab_nomerge`：控制是否禁止 Slab 缓存合并的布尔标志

### 主要函数
- `kmem_cache_size()`：返回指定缓存中对象的实际大小
- `calculate_alignment()`：根据标志、用户对齐要求和对象大小计算最终对齐值
- `slab_unmergeable()`：判断给定缓存是否可被合并
- `find_mergeable()`：在现有缓存中查找可合并的目标缓存
- `create_cache()`：创建新的 `kmem_cache` 实例
- `__kmem_cache_create_args()`：带参数的缓存创建主入口函数

### 关键宏定义
- `SLAB_NEVER_MERGE`：包含禁止缓存合并的标志集合（如 RED_ZONE、POISON 等）
- `SLAB_MERGE_SAME`：合并时必须相同的标志集合（如 DMA 相关、ACCOUNT 等）

## 3. 关键实现

### 缓存合并机制
文件实现了智能的缓存合并策略：
1. 通过 `slab_nomerge` 全局开关或内核启动参数（`slab_nomerge`/`slab_merge`）控制是否启用合并
2. 使用 `SLAB_NEVER_MERGE` 排除带有调试或特殊语义标志的缓存
3. 在 `find_mergeable()` 中遍历 `slab_caches` 链表，检查：
   - 对象大小兼容性（新缓存 ≤ 现有缓存）
   - 必须相同的标志位一致
   - 对齐兼容性（现有缓存大小是新对齐的整数倍）
   - 内存浪费不超过一个指针大小

### 对齐计算
`calculate_alignment()` 实现了分层对齐策略：
- 若设置 `SLAB_HWCACHE_ALIGN`，则基于缓存行大小动态调整（对象越小，对齐粒度越细）
- 始终满足架构最小对齐要求（`arch_slab_minalign()`）
- 最终对齐值向上对齐到指针大小的倍数

### 安全与调试支持
- **完整性检查**：`kmem_cache_sanity_check()` 在 `CONFIG_DEBUG_VM` 下验证缓存名和大小合法性
- **用户复制硬化**：集成 `CONFIG_HARDENED_USERCOPY` 检查用户区域偏移/大小有效性
- **调试标志处理**：自动启用 `slub_debug_enabled` 静态分支和 `stack_depot` 初始化
- **KFENCE/KASAN 集成**：通过头文件包含支持内存错误检测框架

### RCU 安全销毁
通过工作队列 `slab_caches_to_rcu_destroy_work` 延迟销毁缓存，确保在 RCU 宽限期结束后释放内存，避免并发访问已释放结构。

## 4. 依赖关系

### 头文件依赖
- **核心子系统**：`<linux/slab.h>`, `<linux/mm.h>`, `<linux/memory.h>`
- **调试设施**：`<linux/kasan.h>`, `<linux/kfence.h>`, `<linux/kmemleak.h>`
- **架构相关**：`<asm/cacheflush.h>`, `<asm/page.h>`
- **内部实现**：`"internal.h"`, `"slab.h"`（包含分配器特定接口）

### 功能依赖
- **内存管理**：依赖页分配器（`alloc_pages`）和内存控制组（`memcontrol`）
- **同步机制**：使用 mutex、RCU 和 workqueue 实现并发控制
- **调试框架**：与 KASAN、KFENCE、SLUB_DEBUG 等调试子系统深度集成
- **DMA 支持**：通过 `SLAB_CACHE_DMA`/`SLAB_CACHE_DMA32` 标志与 DMA 映射子系统交互

## 5. 使用场景

### 内核初始化
- 在 `start_kernel()` 早期阶段初始化 `kmem_cache` 自身（bootstrap 过程）
- 通过 `__setup_param` 处理内核命令行参数（如 `slab_nomerge`）

### 动态缓存创建
- 当驱动或子系统调用 `kmem_cache_create()` 时，经由此文件的 `__kmem_cache_create_args()` 创建新缓存
- 自动尝试合并相似缓存以减少内存碎片（除非显式禁用）

### 调试与监控
- `/proc/slabinfo` 和 debugfs 接口通过此文件获取缓存列表信息
- 内存错误检测工具（KASAN/KFENCE）利用此文件的钩子注入检测逻辑

### 特殊内存分配
- 支持 DMA 缓存（`SLAB_CACHE_DMA`）、RCU 安全释放（`SLAB_TYPESAFE_BY_RCU`）等特殊场景
- 为 hardened usercopy 提供对象边界验证所需元数据（`useroffset`/`usersize`）