# memory_hotplug.c

> 自动生成时间: 2025-12-07 16:43:14
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `memory_hotplug.c`

---

# memory_hotplug.c 技术文档

## 1. 文件概述

`memory_hotplug.c` 是 Linux 内核中实现内存热插拔（Memory Hotplug）功能的核心源文件，位于 `mm/` 子系统目录下。该文件提供了在系统运行时动态添加或移除物理内存区域的能力，包括内存资源注册、页表映射管理、内存上线策略控制、以及与 NUMA 架构的协同支持。它主要处理热添加内存时的初始化、内存块（memory block）管理、vmemmap 映射优化、以及在线策略配置等关键逻辑。

## 2. 核心功能

### 主要全局变量与参数
- `memmap_mode`：控制是否启用“内存上的 memmap”（memmap on memory）特性，支持 `disable`、`enable` 和 `force` 三种模式。
- `online_policy`：定义内存上线时的默认区域分配策略，可选 `contig-zones`（保持区域连续）或 `auto-movable`（自动分配到 ZONE_MOVABLE）。
- `auto_movable_ratio`：在 `auto-movable` 策略下，系统允许的 MOVABLE 与 KERNEL 内存的最大百分比比例（默认 301%，即约 3:1）。
- `auto_movable_numa_aware`（仅 CONFIG_NUMA）：是否在 `auto-movable` 策略中考虑 NUMA 节点级别的内存统计。
- `mhp_default_online_type`：内存热插拔时的默认上线类型（如 `MMOP_ONLINE_KERNEL`、`MMOP_ONLINE_MOVABLE` 等）。
- `movable_node_enabled`：标志是否启用了可移动节点（movable node）功能。
- `max_mem_size`：系统允许的最大内存大小上限（默认为 `U64_MAX`）。

### 主要函数与接口
- `get_online_mems()` / `put_online_mems()`：获取/释放内存热插拔读锁，用于保护内存上线/下线操作。
- `mem_hotplug_begin()` / `mem_hotplug_done()`：执行内存热插拔写操作前后的同步原语，同时持有 CPU 热插拔读锁和内存热插拔写锁。
- `mhp_get_default_online_type()` / `mhp_set_default_online_type()`：获取或设置内存热插拔的默认上线类型。
- `register_memory_resource()`：将新添加的内存区域注册为 I/O 资源（`System RAM` 类型），并检查是否超出 `max_mem_size` 限制。
- `mhp_memmap_on_memory()`：判断当前是否启用了 memmap on memory 特性。
- `memory_block_memmap_on_memory_pages()`：计算在 memmap on memory 模式下，每个内存块所需的额外页数（可能因对齐而浪费内存）。

### 回调机制
- `online_page_callback`：指向当前用于上线单个页面的回调函数，默认为 `generic_online_page`。
- `set_online_page_callback()` / `restore_online_page_callback()`（声明未在片段中，但有注释说明）：用于动态替换或恢复页面上线回调。

### 内核参数（module_param）
- `memmap_on_memory`：启用 memmap on memory 功能（Y/N/force）。
- `online_policy`：设置默认上线策略。
- `auto_movable_ratio`：设置 MOVABLE/KERNEL 内存比例上限。
- `auto_movable_numa_aware`：是否在 NUMA 感知下应用 auto-movable 策略。
- 启动参数 `memhp_default_state=`：通过内核命令行设置默认上线状态。

## 3. 关键实现

### Memmap on Memory 机制
当启用 `CONFIG_MHP_MEMMAP_ON_MEMORY` 时，内核尝试将描述物理页的 `struct page` 数组（即 vmemmap）直接放置在待热插拔的内存区域内，而非依赖预先保留的虚拟地址空间。这减少了对固定 vmemmap 区域的依赖，提升灵活性：
- **ENABLE 模式**：仅当 vmemmap 大小能被页块（pageblock）整除时才启用。
- **FORCE 模式**：强制对齐到页块边界，即使造成内存浪费（通过 `pageblock_align()` 实现），确保总能使用该内存区域存放 memmap。

### 内存上线策略
- **contig-zones（默认）**：将新内存添加到现有内存区域末尾，保持 ZONE_NORMAL 等区域的物理连续性。
- **auto-movable**：根据全局（及 NUMA 节点）的 KERNEL 与 MOVABLE 内存比例，智能决定是否将新内存加入 ZONE_MOVABLE，以提高内存可迁移性和碎片整理效率。比例由 `auto_movable_ratio` 控制。

### 并发控制
使用 `percpu_rwsem mem_hotplug_lock` 作为内存热插拔操作的主同步机制：
- 读操作（如内存访问路径）调用 `get/put_online_mems()` 获取读锁。
- 写操作（如 add_memory）调用 `mem_hotplug_begin/done()` 获取写锁，并同时持有 `cpus_read_lock()` 防止 CPU 热插拔干扰。

### 资源与大小限制
- 通过 `mhp_range_allowed()` 检查待添加内存是否超出 `max_mem_size`。
- 使用 `register_memory_resource()` 将内存注册为 `IORESOURCE_SYSTEM_RAM` 资源，若资源名非 "System RAM" 则标记为驱动管理（`IORESOURCE_SYSRAM_DRIVER_MANAGED`）。

## 4. 依赖关系

- **内存管理子系统**：依赖 `mm.h`、`page-isolation.h`、`migrate.h`、`compaction.h` 等，用于页面分配、隔离、迁移和压缩。
- **体系结构相关**：包含 `asm/tlbflush.h` 用于 TLB 刷新；依赖 `pfn.h`、`memblock.h` 处理物理页帧和启动内存布局。
- **设备模型与 sysfs**：通过 `memory.h` 与用户空间交互（如 `/sys/devices/system/memory/`）。
- **NUMA 支持**：在 `CONFIG_NUMA` 下使用节点感知策略。
- **虚拟内存**：依赖 `vmalloc.h` 和 `memremap.h` 管理 vmemmap 映射。
- **电源管理**：包含 `suspend.h`，可能与休眠/唤醒流程协调。
- **固件接口**：使用 `firmware-map.h` 与平台固件交互内存布局信息。

## 5. 使用场景

- **物理内存热添加**：在支持内存热插拔的服务器（如 IBM Power、x86 ACPI 系统）上，动态增加 DIMM 或内存模块后，内核通过此文件完成内存初始化和上线。
- **虚拟化环境**：KVM、Xen 等 hypervisor 向客户机热添加内存时，客户机内核调用此模块处理新增内存。
- **内存故障恢复**：在某些 RAS（Reliability, Availability, Serviceability）场景中，隔离坏页后重新上线备用内存。
- **测试与开发**：通过 sysfs 接口（如 `echo online > /sys/devices/system/memory/memoryX/state`）手动上线内存块，配合 `online_policy` 和 `memmap_on_memory` 参数进行功能验证。
- **容器与云平台**：支持弹性内存扩展，按需分配物理内存资源。