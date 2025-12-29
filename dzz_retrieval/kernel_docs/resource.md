# resource.c

> 自动生成时间: 2025-10-25 15:53:12
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `resource.c`

---

# resource.c 技术文档

## 1. 文件概述

`resource.c` 是 Linux 内核中用于管理和分配系统资源（如 I/O 端口和内存区域）的核心实现文件。它提供了一套通用的资源树管理机制，支持资源的申请、释放、查找和冲突检测。该文件维护了两个全局根资源节点：`ioport_resource`（用于 I/O 端口空间）和 `iomem_resource`（用于内存映射 I/O 空间），并通过树形结构组织所有已分配的子资源，确保资源分配的唯一性和安全性。

## 2. 核心功能

### 主要全局数据结构
- `struct resource ioport_resource`：I/O 端口资源的根节点，范围为 `[0, IO_SPACE_LIMIT]`，标志为 `IORESOURCE_IO`。
- `struct resource iomem_resource`：内存映射 I/O 资源的根节点，范围为 `[0, -1]`（即全地址空间），标志为 `IORESOURCE_MEM`。
- `struct resource_constraint`：用于描述资源分配时的约束条件（最小/最大地址、对齐要求及自定义对齐函数）。

### 关键函数
- `request_resource(struct resource *root, struct resource *new)`：尝试在指定根资源下申请一段新资源，成功返回 0，冲突返回 `-EBUSY`。
- `request_resource_conflict(...)`：与 `request_resource` 类似，但冲突时直接返回冲突的资源指针。
- `release_resource(struct resource *old)`：释放已分配的资源。
- `release_child_resources(struct resource *r)`：递归释放指定资源的所有子资源。
- `find_next_iomem_res(...)`：在 `iomem_resource` 树中查找与指定区间 `[start, end]` 重叠且满足标志和描述符条件的下一个内存资源。
- `for_each_resource` 宏：遍历资源树的通用宏，支持是否跳过子树的选项。

### /proc 接口（条件编译）
- 通过 `CONFIG_PROC_FS` 启用时，注册 `/proc/ioports` 和 `/proc/iomem` 文件，以树形格式展示当前系统中已分配的 I/O 端口和内存资源（仅对 `CAP_SYS_ADMIN` 权限用户显示实际地址）。

## 3. 关键实现

### 资源树结构
- 资源以多叉树形式组织，每个 `struct resource` 包含 `child`（第一个子节点）、`sibling`（下一个兄弟节点）和 `parent` 指针。
- 树内节点按起始地址升序排列，便于快速查找和插入。

### 资源申请（`__request_resource`）
- 在持有写锁 `resource_lock` 的前提下，遍历根节点的子链表。
- 若新资源与现有节点无重叠，则按地址顺序插入；若存在重叠，则返回冲突节点。
- 插入操作维护树的有序性：新节点插入到第一个起始地址大于其结束地址的节点之前。

### 资源释放（`__release_resource`）
- 支持两种模式：完全释放（含子资源）或仅提升子资源（当 `release_child=false` 时，将子节点直接挂到父节点下）。
- 释放时调整兄弟链表指针，确保树结构完整性。

### 资源遍历
- `next_resource()`：深度优先遍历（先子节点，再兄弟节点）。
- `next_resource_skip_children()`：仅遍历同级兄弟节点，跳过子树。
- `/proc` 显示使用深度优先遍历，并限制最大显示层级（`MAX_IORES_LEVEL=5`）以避免过深嵌套。

### 内存管理
- 资源结构体通过 `alloc_resource()`（即 `kzalloc`）分配，通过 `free_resource()` 释放。
- 注释指出：若资源由早期 `memblock` 分配，则无法安全释放（因非页对齐），会轻微泄漏，这是有意为之的简化设计。

### 并发控制
- 使用读写锁 `resource_lock` 保护全局资源树：
  - 读操作（如 `/proc` 显示、`find_next_iomem_res`）使用 `read_lock`。
  - 写操作（申请/释放资源）使用 `write_lock`。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/ioport.h>`：定义 `struct resource` 及相关宏（如 `IORESOURCE_IO`）。
  - `<linux/proc_fs.h>`、`<linux/seq_file.h>`：实现 `/proc` 接口。
  - `<linux/slab.h>`：资源结构体的动态分配。
  - `<linux/spinlock.h>`：读写锁 `resource_lock` 的实现。
  - `<asm/io.h>`：架构相关的 I/O 定义（如 `IO_SPACE_LIMIT`）。
- **导出符号**：
  - `ioport_resource`、`iomem_resource`、`request_resource`、`release_resource` 通过 `EXPORT_SYMBOL` 导出，供其他内核模块（如 PCI、platform_device 驱动）使用。
- **配置依赖**：
  - `/proc` 接口依赖 `CONFIG_PROC_FS`。

## 5. 使用场景

- **设备驱动资源管理**：PCI、platform 等总线驱动在探测设备时，调用 `request_resource()` 申请 I/O 端口或内存区域，防止资源冲突。
- **固件/ACPI 资源解析**：内核解析 ACPI 表或 EFI 内存映射时，将保留区域注册到 `iomem_resource` 树中。
- **系统调试与监控**：用户空间通过 `/proc/ioports` 和 `/proc/iomem` 查看硬件资源分配情况（需 root 权限）。
- **内核子系统协作**：内存管理子系统（如 `devm_request_mem_region`）、DMA 引擎等依赖此机制确保物理地址资源的独占使用。
- **热插拔支持**：设备移除时调用 `release_resource()` 释放资源，供后续设备重用。