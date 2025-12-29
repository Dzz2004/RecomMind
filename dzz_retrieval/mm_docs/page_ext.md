# page_ext.c

> 自动生成时间: 2025-12-07 17:01:26
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `page_ext.c`

---

# page_ext.c 技术文档

## 1. 文件概述

`page_ext.c` 实现了 Linux 内核中的 **页面扩展（page extension）** 机制，用于在不修改 `struct page` 结构体的前提下，为每个物理页附加额外的元数据。该机制解决了传统方式中因直接扩增 `struct page` 而导致的内核重建成本高、第三方模块兼容性差以及潜在系统行为变更等问题。

页面扩展内存按需分配：仅当至少一个功能模块声明需要扩展数据时，才在启动阶段分配大块连续内存；否则完全跳过分配，避免内存浪费。该机制支持平坦内存（FLATMEM）和稀疏内存（SPARSEMEM）两种内存模型，并提供统一的访问接口。

## 2. 核心功能

### 主要数据结构
- `struct page_ext_operations`：客户端模块注册的回调操作集，包含：
  - `need()`：判断是否需要为本模块分配扩展内存（必选）
  - `init()`：扩展内存分配完成后执行的初始化函数（可选）
  - `size`：所需额外内存大小（字节）
  - `offset`：分配后返回的偏移量（由核心填充）
  - `need_shared_flags`：是否需要共享基础 `struct page_ext` 结构

### 主要全局变量
- `page_ext_size`：每个页面对应的扩展数据总大小（含基础结构和各模块私有数据）
- `total_usage`：已分配的页面扩展内存总量（字节）
- `early_page_ext`：是否强制在早期（早于常规内存初始化）启用 page_ext（通过内核参数控制）

### 主要函数
- `invoke_need_callbacks()`：遍历所有注册的 `page_ext_ops`，调用其 `need()` 回调，决定是否分配内存并计算总大小
- `invoke_init_callbacks()`：在 page_ext 内存分配完成后，调用各模块的 `init()` 回调进行初始化
- `lookup_page_ext(const struct page *page)`：根据 `page` 指针查找对应的 `page_ext` 扩展数据结构（区分 FLATMEM/SPARSEMEM 实现）
- `alloc_node_page_ext(int nid)`（FLATMEM）：为指定 NUMA 节点分配 page_ext 内存表
- `page_ext_init_flatmem()` / `page_ext_init_flatmem_late()`（FLATMEM）：平坦内存模型下的初始化入口
- `setup_early_page_ext()`：解析内核启动参数 `early_page_ext`

## 3. 关键实现

### 按需内存分配机制
- 启动时调用 `invoke_need_callbacks()` 遍历所有注册的扩展模块。
- 若任一模块的 `need()` 返回 `true`，则触发内存分配；否则完全跳过，零开销。
- 对于声明 `need_shared_flags = true` 的模块（如 32 位下的 `PAGE_IDLE`），强制使用基础 `struct page_ext` 结构，确保标志位共享。

### 内存布局与索引
- 每个物理页对应一个 `page_ext` 条目，大小为 `page_ext_size`。
- 条目按 PFN（Page Frame Number）顺序线性排列。
- 在 FLATMEM 模型中，以节点起始 PFN 对齐到 `MAX_ORDER_NR_PAGES` 为基址，支持 buddy allocator 跨边界访问。
- 在 SPARSEMEM 模型中，每个内存 section 独立维护 `page_ext` 数组，通过 `__pfn_to_section(pfn)` 定位。

### 稀疏内存特殊处理
- 定义 `PAGE_EXT_INVALID = 0x1` 标志位，用于标记未初始化的 section。
- `lookup_page_ext()` 中通过低位掩码检查有效性，避免访问未分配内存。
- 支持内存热插拔场景下动态分配 section 的 page_ext。

### 早期初始化支持
- 通过 `early_param("early_page_ext", ...)` 支持内核参数强制提前初始化。
- `CONFIG_MEM_ALLOC_PROFILING_DEBUG` 下默认启用，确保分配标签（如 task stack）不丢失。

### 安全访问保障
- `lookup_page_ext()` 中包含 `WARN_ON_ONCE(!rcu_read_lock_held())`，要求调用者持有 RCU 读锁，防止并发释放期间访问悬空指针。
- 处理内存子系统早期初始化阶段（如 boot-time page free）可能触发的空指针访问，安全返回 `NULL`。

## 4. 依赖关系

### 编译依赖（Kconfig）
- `CONFIG_PAGE_OWNER`：页面归属跟踪
- `CONFIG_PAGE_IDLE_FLAG`：页面空闲标记（32 位架构）
- `CONFIG_MEM_ALLOC_PROFILING`：内存分配打标（PGALLOC_TAG）
- `CONFIG_PAGE_TABLE_CHECK`：页表一致性检查
- `CONFIG_SPARSEMEM`：稀疏内存模型支持

### 头文件依赖
- `<linux/mm.h>` / `<linux/mmzone.h>`：内存管理核心结构
- `<linux/memblock.h>`：启动阶段内存分配
- `<linux/vmalloc.h>`：备用分配路径（未在当前片段体现）
- `<linux/rcupdate.h>`：RCU 锁定语义
- 各功能模块头文件（如 `page_owner.h`, `page_idle.h` 等）

### 运行时依赖
- 内存初始化流程（`memmap` 建立之后）
- NUMA 节点信息（`NODE_DATA(nid)`）
- 稀疏内存 section 管理（`__pfn_to_section`）

## 5. 使用场景

1. **调试与追踪**：
   - `PAGE_OWNER`：记录每页的分配/释放调用栈，用于内存泄漏检测
   - `PAGE_TABLE_CHECK`：验证页表映射一致性

2. **性能分析**：
   - `PAGE_IDLE`：标记长时间未访问的页面，供内存回收或迁移策略使用（32 位架构因地址空间限制需外部存储）

3. **内存分配剖析**：
   - `MEM_ALLOC_PROFILING`（PGALLOC_TAG）：为页面打上分配上下文标签，用于内存使用归因分析

4. **内核自检**：
   - 在 buddy allocator 释放路径中校验页面状态，需访问扩展数据

5. **早期内存分配保障**：
   - 当需要在常规内存子系统完全初始化前（如 early initcall 阶段）使用带标签的页面时，通过 `early_page_ext` 参数确保 page_ext 提前就绪