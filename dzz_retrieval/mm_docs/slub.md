# slub.c

> 自动生成时间: 2025-12-07 17:23:28
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `slub.c`

---

# slub.c 技术文档

## 1. 文件概述

`slub.c` 是 Linux 内核中 SLUB（Simple Low-overhead Unqueued Allocator）内存分配器的核心实现文件。SLUB 是一种高效的 slab 分配器，旨在减少缓存行使用并避免在每个 CPU 和节点上维护复杂的对象队列。它通过 per-slab 锁或原子操作进行同步，仅在管理部分填充的 slab 池时使用集中式锁。该分配器优化了常见路径的性能，同时支持调试、内存检测和热插拔等高级功能。

## 2. 核心功能

### 主要数据结构
- `kmem_cache`: slab 缓存描述符，包含对象大小、对齐方式、构造函数等元数据
- `kmem_cache_cpu`: 每 CPU 的 slab 管理结构，包含当前 CPU 的活跃 slab 和局部 freelist
- `slab`: slab 描述符（通常嵌入在 page 结构中），包含 freelist、inuse 计数、objects 总数和 frozen 状态

### 关键机制
- **CPU slab**: 每个 CPU 分配专用的 slab 进行快速分配
- **Partial slab 列表**: 节点级别的部分填充 slab 列表
- **CPU partial slab**: CPU 本地的部分填充 slab 缓存，用于加速释放操作
- **Frozen slab**: 冻结状态的 slab，免于全局列表管理

### 锁机制层次
1. `slab_mutex` - 全局互斥锁，保护所有 slab 列表和元数据变更
2. `node->list_lock` - 自旋锁，保护节点的 partial/full 列表
3. `kmem_cache->cpu_slab->lock` - 本地锁，保护慢路径的 per-CPU 字段
4. `slab_lock(slab)` - slab 锁（仅在不支持 `cmpxchg_double` 的架构上使用）
5. `object_map_lock` - 调试用途的对象映射锁

## 3. 关键实现

### 锁无关快速路径
- 分配 (`slab_alloc_node()`) 和释放 (`do_slab_free()`) 操作在满足条件时完全无锁
- 使用事务 ID (tid) 字段检测抢占或 CPU 迁移
- 在支持 `cmpxchg_double` 的架构上避免使用 slab_lock

### Slab 状态管理
- **Node partial slab**: `PG_Workingset && !frozen`
- **CPU partial slab**: `!PG_Workingset && !frozen`
- **CPU slab**: `!PG_Workingset && frozen`
- **Full slab**: `!PG_Workingset && !frozen`

### PREEMPT_RT 支持
- 在 RT 内核中禁用锁无关快速路径
- 使用 `migrate_disable()/enable()` 替代 `preempt_disable()/enable()`
- 本地锁始终被获取以确保 RT 安全性

### 内存管理优化
- 最小化 slab 设置/拆卸开销，依赖页分配器的 per-CPU 缓存
- 空 slab 直接释放回页分配器
- CPU partial slab 机制加速批量释放操作

## 4. 依赖关系

### 头文件依赖
- **内存管理**: `<linux/mm.h>`, `<linux/swap.h>`, `<linux/memory.h>`
- **同步原语**: `<linux/bit_spinlock.h>`, `<linux/interrupt.h>`
- **调试支持**: `<linux/kasan.h>`, `<linux/kmsan.h>`, `<linux/kfence.h>`, `<linux/debugobjects.h>`
- **系统设施**: `<linux/module.h>`, `<linux/proc_fs.h>`, `<linux/debugfs.h>`
- **内存控制**: `<linux/memcontrol.h>`, `<linux/cpuset.h>`, `<linux/mempolicy.h>`
- **测试框架**: `<kunit/test.h>`

### 内部依赖
- `"slab.h"` - slab 分配器通用接口
- `"internal.h"` - 内存管理内部实现

### 子系统交互
- **页分配器**: 作为底层内存来源
- **内存热插拔**: 通过 `slab_mutex` 同步回调
- **内存控制器**: 集成 memcg 功能
- **跟踪系统**: 通过 `trace/events/kmem.h` 提供分配事件跟踪

## 5. 使用场景

### 内核内存分配
- 为内核对象（如 task_struct、inode、dentry 等）提供高效的小内存分配
- 作为 `kmalloc()` 系列函数的底层实现
- 支持不同大小类别的内存请求（8 字节到几 KB）

### 性能关键路径
- 中断上下文中的内存分配（通过适当的锁机制保证安全）
- 高频分配/释放场景（利用 per-CPU slab 和 lockless 快速路径）
- 批量分配操作（通过 CPU partial slab 优化）

### 调试和监控
- 内存错误检测（KASAN、KMSAN、KFENCE 集成）
- 内存泄漏检测（kmemleak 集成）
- 性能分析（通过 `/proc/slabinfo` 和 debugfs 接口）
- 故障注入测试（fault-inject 支持）

### 特殊环境支持
- 实时系统（PREEMPT_RT 配置）
- 内存受限系统（CONFIG_SLUB_TINY 优化）
- NUMA 系统（节点感知分配）
- 内存热插拔环境