# page_owner.c

> 自动生成时间: 2025-12-07 17:04:18
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `page_owner.c`

---

# page_owner.c 技术文档

## 1. 文件概述

`page_owner.c` 是 Linux 内核中用于追踪物理内存页分配与释放信息的调试模块。它通过记录每个页面（或页块）的分配者、释放者、分配时间、调用栈、GFP 标志、进程上下文等元数据，帮助开发者诊断内存泄漏、非法释放、重复释放等内存管理问题。该功能可通过内核启动参数 `page_owner=on` 启用，并通过 debugfs 接口（如 `/sys/kernel/debug/page_owner`）导出详细信息。

## 2. 核心功能

### 主要数据结构

- **`struct page_owner`**：存储单个页面（或页块）的归属信息
  - `order`：分配时的页阶数（2^order 个连续页）
  - `last_migrate_reason`：最后一次迁移的原因（-1 表示未迁移）
  - `gfp_mask`：分配时使用的 GFP 标志
  - `handle` / `free_handle`：分配/释放时的调用栈句柄（由 stackdepot 管理）
  - `ts_nsec` / `free_ts_nsec`：分配/释放的时间戳（纳秒级）
  - `comm` / `pid` / `tgid`：分配进程的名称、PID 和线程组 ID
  - `free_pid` / `free_tgid`：释放进程的 PID 和线程组 ID

### 主要函数

- **`__set_page_owner()`**：在页面分配时记录归属信息
- **`__reset_page_owner()`**：在页面释放时记录释放信息
- **`__set_page_owner_migrate_reason()`**：记录页面迁移原因
- **`__split_page_owner()`**：在页面分裂时更新页阶信息
- **`__folio_copy_owner()`**：在 folio 迁移时复制归属信息
- **`pagetypeinfo_showmixedcount_print()`**：统计并打印混合迁移类型的页块信息（未完整实现）

### 全局变量与初始化

- `page_owner_enabled`：是否启用 page owner 功能（由启动参数控制）
- `page_owner_inited`：静态跳转键，标识 page owner 是否已初始化
- `dummy_handle` / `failure_handle` / `early_handle`：特殊调用栈句柄，用于避免递归或处理异常情况
- `page_owner_ops`：`page_ext` 框架的操作集，用于注册 page owner 扩展

## 3. 关键实现

### 调用栈捕获与去重

- 使用 `stack_trace_save()` 捕获深度为 `PAGE_OWNER_STACK_DEPTH`（16 层）的调用栈
- 通过 `stack_depot_save()` 将调用栈存入全局去重仓库（stack depot），返回紧凑句柄
- 为避免在分配 page owner 元数据时触发递归（如 stack depot 自身需要分配内存），使用 `current->in_page_owner` 标志临时禁用追踪，并返回 `dummy_handle`

### 页面扩展（page_ext）集成

- 利用内核的 `page_ext` 机制为每个 struct page 附加 `struct page_owner` 元数据
- 通过 `page_ext_get()` / `page_ext_put()` 安全访问扩展数据
- 在 `init_page_owner()` 中注册 `page_owner_ops`，使 page_ext 框架在初始化时为所有页面预留空间

### 特殊句柄处理

- **`dummy_handle`**：用于递归保护场景
- **`failure_handle`**：当 `stack_depot_save()` 失败时的备用句柄
- **`early_handle`**：用于早期分配页面（如 memblock 阶段）的归属标记

### 内存操作一致性

- 在页面分配（`__set_page_owner`）、释放（`__reset_page_owner`）、迁移（`__folio_copy_owner`）和分裂（`__split_page_owner`）等关键路径上同步更新元数据
- 使用 `PAGE_EXT_OWNER_ALLOCATED` 位标记页面当前是否处于已分配状态
- 时间戳使用 `local_clock()` 获取高精度单调时钟

## 4. 依赖关系

- **`<linux/page_ext.h>`**：提供页面扩展框架，用于附加元数据
- **`<linux/stackdepot.h>`**：提供调用栈去重存储服务
- **`<linux/stacktrace.h>`**：提供调用栈捕获接口
- **`<linux/debugfs.h>`**：用于创建 debugfs 接口（虽未在代码片段中体现，但通常配套实现）
- **`mm/internal.h`**：包含内部内存管理辅助函数
- **`<linux/memcontrol.h>`**、**`<linux/migrate.h>`**：支持内存控制组和页面迁移场景

## 5. 使用场景

- **内存泄漏检测**：通过分析未释放页面的分配栈和进程上下文定位泄漏源
- **Use-after-free 调试**：检查已释放页面的释放者信息，判断非法访问来源
- **内存碎片分析**：结合迁移类型和分配模式，识别导致碎片化的分配行为
- **性能调优**：通过分配/释放时间戳分析内存分配延迟
- **内核开发与测试**：在启用 `CONFIG_PAGE_OWNER` 配置选项后，作为内存子系统的重要调试工具

> 注：该功能会显著增加内存开销（每个页面约 64 字节元数据）和运行时开销，仅建议在调试环境中启用。