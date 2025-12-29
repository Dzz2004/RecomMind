# damon\sysfs-schemes.c

> 自动生成时间: 2025-12-07 15:51:36
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `damon\sysfs-schemes.c`

---

# `damon/sysfs-schemes.c` 技术文档

## 1. 文件概述

`damon/sysfs-schemes.c` 是 Linux 内核中 DAMON（Data Access MONitor）子系统的一部分，负责通过 sysfs 接口暴露 DAMON 策略（schemes）相关的运行时监控数据和统计信息。该文件实现了多个 sysfs 目录和只读属性，用于展示：

- 符合策略条件的内存区域（regions）
- 策略执行的统计数据（stats）
- 策略过滤器（filter）的配置信息（部分实现）

所有属性均为只读（权限 0400），供用户空间监控和调试 DAMON 行为。

## 2. 核心功能

### 主要数据结构

| 结构体 | 说明 |
|--------|------|
| `struct damon_sysfs_scheme_region` | 表示一个被 DAMON 策略匹配到的内存区域，包含地址范围、访问次数和年龄 |
| `struct damon_sysfs_scheme_regions` | 包含多个 `scheme_region` 的容器，提供总字节数统计 |
| `struct damon_sysfs_stats` | 存储策略尝试应用和实际应用的统计信息 |
| `struct damon_sysfs_scheme_filter` | 表示策略过滤器的配置（当前仅分配结构，未完整实现 sysfs 属性） |

### 主要函数

| 函数 | 功能 |
|------|------|
| `damon_sysfs_scheme_region_alloc()` | 从内核 `damon_region` 分配并初始化 sysfs region 对象 |
| `damon_sysfs_scheme_regions_alloc()` | 分配并初始化 regions 容器 |
| `damon_sysfs_stats_alloc()` | 分配并清零 stats 结构 |
| `damon_sysfs_scheme_filter_alloc()` | 分配 filter 结构 |
| 各 `*_show()` 函数 | 实现 sysfs 属性的只读显示逻辑 |
| `damon_sysfs_scheme_regions_rm_dirs()` | 批量释放所有 region 的 kobject |
| 各 `*_release()` 函数 | kobject 引用计数归零时的清理回调 |

### sysfs 属性组

- **Region 属性**：`start`, `end`, `nr_accesses`, `age`
- **Regions 容器属性**：`total_bytes`
- **Stats 属性**：`nr_tried`, `sz_tried`, `nr_applied`, `sz_applied`, `qt_exceeds`

## 3. 关键实现

### 内存区域表示
- 每个 `damon_sysfs_scheme_region` 封装了内核 `damon_region` 的关键字段（地址范围、访问频次、年龄）
- 使用 `list_head` 维护在 `damon_sysfs_scheme_regions` 中的链表关系
- kobject 生命周期由引用计数管理，`release` 回调中自动从链表移除并释放内存

### 只读属性设计
- 所有属性使用 `__ATTR_RO_MODE(..., 0400)` 定义，确保用户空间只能读取
- 使用 `sysfs_emit()` 安全地格式化输出到缓冲区
- 属性值直接映射内核结构体字段，无额外计算开销

### 统计信息语义
- `nr_tried` / `sz_tried`：策略尝试处理的区域数量/总字节数
- `nr_applied` / `sz_applied`：策略实际成功应用的数量/字节数
- `qt_exceeds`：因超过配额（quota）而跳过处理的次数

### 过滤器类型映射
- `damon_sysfs_scheme_filter_type_strs` 数组与 `enum damos_filter_type` 严格对应
- 支持四种过滤器类型：匿名内存（anon）、memcg、地址范围（addr）、目标索引（target）

## 4. 依赖关系

- **内部依赖**：
  - `sysfs-common.h`：提供通用 sysfs 操作辅助（如 `kobj_sysfs_ops`）
  - DAMON 核心结构体（`damon_region`, `damon_addr_range`, `damos_filter_type`）
- **内核子系统**：
  - sysfs：通过 kobject/kobj_type 机制注册目录和属性
  - SLAB 内存分配器：使用 `kmalloc`/`kzalloc` 分配对象
- **头文件**：
  - `<linux/slab.h>`：内存分配接口

## 5. 使用场景

- **运行时监控**：用户通过 `/sys/kernel/mm/damon/.../schemes/*/regions/` 查看当前被策略匹配的内存区域详情
- **性能分析**：通过 `stats` 目录评估策略效率（如尝试 vs 实际应用比例）
- **调试过滤器**：检查策略过滤条件是否按预期工作（需配合完整 filter sysfs 实现）
- **资源审计**：`total_bytes` 和 `sz_*` 字段帮助量化 DAMON 操作的数据规模
- **配额调优**：`qt_exceeds` 计数指导用户调整策略配额参数避免过度操作