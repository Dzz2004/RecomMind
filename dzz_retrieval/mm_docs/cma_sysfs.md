# cma_sysfs.c

> 自动生成时间: 2025-12-07 15:43:57
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cma_sysfs.c`

---

# cma_sysfs.c 技术文档

## 1. 文件概述

`cma_sysfs.c` 实现了连续内存分配器（Contiguous Memory Allocator, CMA）的 sysfs 接口，用于向用户空间暴露 CMA 区域的运行时统计信息。通过该接口，用户可以在 `/sys/kernel/mm/cma/` 目录下查看每个 CMA 区域成功和失败分配的页面数量，便于系统调试与性能分析。

## 2. 核心功能

### 主要函数
- `cma_sysfs_account_success_pages(struct cma *cma, unsigned long nr_pages)`  
  原子累加成功分配的页面数到指定 CMA 区域的统计计数器。
  
- `cma_sysfs_account_fail_pages(struct cma *cma, unsigned long nr_pages)`  
  原子累加分配失败的页面数到指定 CMA 区域的统计计数器。

- `alloc_pages_success_show()`  
  sysfs 属性读取回调，返回 `nr_pages_succeeded` 的当前值。

- `alloc_pages_fail_show()`  
  sysfs 属性读取回调，返回 `nr_pages_failed` 的当前值。

- `cma_kobj_release()`  
  CMA kobject 的释放回调，负责清理关联的 `cma_kobject` 结构。

- `cma_sysfs_init()`  
  模块初始化函数，创建 sysfs 目录结构并为每个 CMA 区域注册对应的 sysfs 条目。

### 主要数据结构
- `struct cma_kobject`（定义在 `cma.h` 中）  
  封装 `kobject` 与指向 `struct cma` 的指针，用于 sysfs 表示。

- `cma_ktype`  
  定义 CMA kobject 的类型，包含 release 回调、sysfs 操作集和默认属性组。

- `cma_attrs[]` 和 `cma_groups`  
  定义 sysfs 中可读的属性列表（`alloc_pages_success` 和 `alloc_pages_fail`）。

## 3. 关键实现

- **原子计数**：使用 `atomic64_t` 类型（`nr_pages_succeeded` 和 `nr_pages_failed`）确保多线程环境下统计信息的准确性。
  
- **kobject 封装**：通过 `container_of` 宏从 `kobject` 反向获取所属的 `struct cma`，实现 sysfs 对象与内核 CMA 区域的绑定。

- **sysfs 属性生成**：利用 `CMA_ATTR_RO` 宏简化只读属性的定义，自动创建符合 sysfs 规范的 `kobj_attribute`。

- **动态目录创建**：在 `mm_kobj`（即 `/sys/kernel/mm/`）下创建 `cma` 子目录，并为每个已注册的 CMA 区域（`cma_areas[]`）创建以区域名为名的子目录。

- **错误处理与资源回收**：初始化过程中若任一 CMA 区域的 kobject 创建失败，会回滚已创建的 kobject 并释放资源，避免内存泄漏。

- **初始化时机**：通过 `subsys_initcall` 注册，确保在内核子系统初始化阶段（早于普通模块）完成 sysfs 结构的建立。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/cma.h>`：提供 CMA 核心 API 和 `struct cma` 定义。
  - `"cma.h"`（本地头文件）：定义 `struct cma_kobject` 等内部结构。
  - `<linux/kernel.h>`、`<linux/slab.h>`：提供基础内核工具函数和内存分配接口。

- **内核子系统依赖**：
  - **sysfs 子系统**：依赖 `kobject`、`kobj_attribute` 等机制暴露用户接口。
  - **内存管理子系统**：依赖 `mm_kobj` 作为 sysfs 挂载点，以及 CMA 核心逻辑提供的 `cma_areas` 和 `cma_area_count`。

## 5. 使用场景

- **系统调试**：开发人员可通过读取 `/sys/kernel/mm/cma/<area>/alloc_pages_success` 和 `alloc_pages_fail` 快速判断 CMA 分配器的工作状态，识别内存碎片或配置问题。

- **性能监控**：运维工具可定期采集 CMA 分配成功率，用于评估系统实时性或大块连续内存需求的满足情况。

- **内核测试**：在 CMA 相关功能验证中，该接口提供可量化的分配行为指标，辅助回归测试和压力测试。

- **驱动开发参考**：设备驱动在使用 `dma_alloc_coherent()` 等 CMA 接口时，可通过此 sysfs 路径确认底层分配是否按预期工作。