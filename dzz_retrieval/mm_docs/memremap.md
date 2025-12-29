# memremap.c

> 自动生成时间: 2025-12-07 16:45:41
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `memremap.c`

---

# memremap.c 技术文档

## 1. 文件概述

`memremap.c` 是 Linux 内核中用于管理设备持久内存（Persistent Memory）映射的核心实现文件。它提供了将物理设备内存（如 NVDIMM、CXL 等）映射到内核虚拟地址空间并将其纳入内存管理子系统（特别是 ZONE_DEVICE）的机制。该文件主要实现了 `memremap_pages()` 和 `memunmap_pages()` 接口，用于注册和注销设备页映射（`dev_pagemap`），支持多种设备内存类型（如 FS_DAX、PRIVATE、COHERENT 等），并确保与内存热插拔、KASAN、NUMA 等子系统的正确集成。

## 2. 核心功能

### 主要数据结构
- **`struct dev_pagemap`**：描述设备内存区域的元数据结构，包含内存范围、类型、引用计数、完成量等。
- **`pgmap_array`**：全局 XArray 结构，用于按 PFN 范围快速查找对应的 `dev_pagemap` 实例。

### 主要函数
- **`memremap_compat_align()`**：返回设备内存映射的最小兼容对齐粒度（默认为 `SUBSECTION_SIZE`），确保在不同映射模式间切换时满足架构约束。
- **`pgmap_pfn_valid()`**：判断给定 PFN 是否属于指定 `dev_pagemap` 的有效范围。
- **`memunmap_pages()`**：释放通过 `memremap_pages()` 映射的设备内存区域，包括从内存管理子系统移除、清理 KASAN 影子内存、更新 XArray 等。
- **`pagemap_range()`**：内部辅助函数，负责将单个内存范围添加到内核内存管理中（调用 `arch_add_memory()` 或 `add_pages()`）。
- **`devm_memremap_pages_release()`**：资源管理释放回调，用于自动清理通过 `devm_` 接口分配的映射。
- **`dev_pagemap_percpu_release()`**：percpu 引用计数释放回调，用于同步等待所有用户完成后再执行实际卸载。

### 静态键（Static Keys）
- **`devmap_managed_key`**：仅在 `CONFIG_FS_DAX` 启用时定义，用于优化 FS_DAX 设备内存路径的运行时分支预测。

## 3. 关键实现

### 设备内存映射流程 (`pagemap_range`)
1. **冲突检测**：通过 `get_dev_pagemap()` 检查目标 PFN 范围是否已存在映射，避免重叠。
2. **RAM 区域检查**：使用 `region_intersects()` 确保映射区域不与系统 RAM 重叠。
3. **XArray 注册**：将 `dev_pagemap` 指针存入全局 `pgmap_array`，以 PFN 为键。
4. **PFN 跟踪**：调用 `track_pfn_remap()` 建立页表映射。
5. **内存热插拔**：
   - 对于 `MEMORY_DEVICE_PRIVATE` 类型，调用 `add_pages()` 仅初始化 `struct page`，不建立线性映射。
   - 对于其他类型（如 FS_DAX），调用 `kasan_add_zero_shadow()` 添加 KASAN 影子内存，再调用 `arch_add_memory()` 建立完整线性映射。
6. **ZONE_DEVICE 集成**：调用 `move_pfn_range_to_zone()` 将 PFN 范围移动到 `ZONE_DEVICE`。
7. **延迟初始化**：调用 `memmap_init_zone_device()` 初始化 `struct page` 的设备特定字段。
8. **引用计数**：对非 PRIVATE/COHERENT 类型，增加 percpu 引用计数。

### 设备内存卸载流程 (`memunmap_pages`)
1. **引用计数终止**：调用 `percpu_ref_kill()` 标记引用不可再增加。
2. **引用释放**：对非 PRIVATE/COHERENT 类型，批量减少 percpu 引用。
3. **同步等待**：通过 `wait_for_completion()` 等待所有现有引用释放完毕。
4. **逐范围卸载**：对每个范围调用 `pageunmap_range()`：
   - 从对应 zone 移除 PFN 范围。
   - 调用 `__remove_pages()`（PRIVATE）或 `arch_remove_memory()` + `kasan_remove_zero_shadow()`（其他类型）。
   - 调用 `untrack_pfn()` 清理页表跟踪。
   - 从 `pgmap_array` 中删除映射。
5. **清理引用**：调用 `percpu_ref_exit()` 销毁 percpu 引用。
6. **静态键更新**：若为 FS_DAX 类型，减少 `devmap_managed_key` 计数。

### PFN 范围处理
- **起始 PFN**：`pfn_first()` 考虑 `vmem_altmap` 的偏移（用于预留 struct page 存储空间）。
- **结束 PFN**：`pfn_end()` 基于物理范围计算。
- **有效长度**：`pfn_len()` 计算实际可使用的页数，并考虑 `vmemmap_shift`（用于大页优化）。

## 4. 依赖关系

- **内存管理子系统**：依赖 `memory_hotplug.h`、`mmzone.h`、`swap.h` 等，与 `ZONE_DEVICE`、内存热插拔机制紧密集成。
- **体系结构相关代码**：调用 `arch_add_memory()`、`arch_remove_memory()`，依赖各架构的具体实现。
- **KASAN**：通过 `kasan_add/remove_zero_shadow()` 管理影子内存。
- **DAX 子系统**：当 `CONFIG_FS_DAX` 启用时，与 DAX 设备管理交互，使用 `devmap_managed_key` 优化路径。
- **XArray**：使用 XArray 数据结构高效管理 PFN 到 `dev_pagemap` 的映射。
- **Per-CPU 引用计数**：使用 `percpu_ref` 机制安全地管理设备内存的生命周期。
- **内部头文件**：包含 `"internal.h"`，访问内核内存管理内部接口。

## 5. 使用场景

- **持久内存 (PMEM) 设备驱动**：如 `libnvdimm` 子系统中的 `nd_pmem` 驱动，使用 `memremap_pages()` 将 NVDIMM 映射为可直接访问的内存。
- **CXL 内存设备**：CXL.mem 设备通过此接口将设备附加内存纳入内核管理。
- **DAX 文件系统**：当挂载支持 DAX 的文件系统（如 ext4、xfs）到 PMEM 设备时，底层使用此机制建立直接映射。
- **GPU/CXL 设备私有内存**：`MEMORY_DEVICE_PRIVATE` 类型用于管理 CPU 不可直接访问但可通过特殊指令（如迁移 API）操作的设备内存。
- **异构内存管理**：作为统一内存架构（UMA/NUMA 扩展）的一部分，将设备内存作为特殊内存节点纳入调度和分配策略。