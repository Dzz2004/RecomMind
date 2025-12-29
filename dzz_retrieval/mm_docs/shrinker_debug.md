# shrinker_debug.c

> 自动生成时间: 2025-12-07 17:20:41
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `shrinker_debug.c`

---

# shrinker_debug.c 技术文档

## 1. 文件概述

`shrinker_debug.c` 是 Linux 内核中用于调试内存回收（shrinker）机制的 debugfs 接口实现文件。它通过在 debugfs 文件系统下为每个注册的 shrinker 创建专属目录和控制文件，允许用户空间查看各 shrinker 在不同 NUMA 节点和 memcg（memory cgroup）上下文中的对象数量，并手动触发指定 shrinker 的扫描操作，从而辅助内核开发者诊断内存回收行为。

## 2. 核心功能

### 主要函数

- `shrinker_count_objects()`：调用 shrinker 的 `count_objects` 回调，统计指定 memcg 和所有 NUMA 节点上的可回收对象总数，并填充每节点计数。
- `shrinker_debugfs_count_show()`：实现 `/sys/kernel/debug/shrinker/<name>/count` 文件的读取逻辑，遍历所有在线 memcg（或全局上下文），输出各 shrinker 的 per-node 对象计数。
- `shrinker_debugfs_scan_write()`：实现 `/sys/kernel/debug/shrinker/<name>/scan` 文件的写入逻辑，解析用户输入参数（memcg ino、node id、扫描数量），调用 shrinker 的 `scan_objects` 回调执行实际回收。
- `shrinker_debugfs_add()`：为新注册的 shrinker 在 debugfs 中创建对应的目录和 `count`/`scan` 文件。
- `shrinker_debugfs_rename()`：在运行时重命名 shrinker 并更新其 debugfs 目录名（导出符号，供其他模块使用）。
- `shrinker_debugfs_detach()` / `shrinker_debugfs_remove()`：配合 shrinker 注销流程，安全移除 debugfs 条目并释放 IDA 分配的 ID。
- `shrinker_debugfs_init()`：late initcall 初始化函数，在 debugfs 根目录下创建 `shrinker` 目录，并为启动阶段已注册的 shrinker 创建 debugfs 条目。

### 主要数据结构与全局变量

- `shrinker_debugfs_ida`：IDA（Incremental Dynamic Allocator）实例，用于为每个 shrinker 分配唯一 ID，避免命名冲突。
- `shrinker_debugfs_root`：指向 debugfs 中 `shrinker` 根目录的 dentry。
- `shrinker_debugfs_count_fops`：`count` 文件的 file_operations，只读。
- `shrinker_debugfs_scan_fops`：`scan` 文件的 file_operations，只写。

## 3. 关键实现

- **NUMA 感知处理**：`shrinker_count_objects()` 函数根据 shrinker 是否设置 `SHRINKER_NUMA_AWARE` 标志决定是否对所有 NUMA 节点调用 `count_objects`。非 NUMA-aware shrinker 仅在 node 0 上计数。
- **Memcg 遍历与上下文切换**：`shrinker_debugfs_count_show()` 使用 `mem_cgroup_iter()` 遍历所有在线 memcg。若 shrinker 不支持 memcg（未设 `SHRINKER_MEMCG_AWARE`），则仅在全局 memcg（NULL）上下文中计数一次。
- **Scan 接口参数解析**：`shrinker_debugfs_scan_write()` 从用户输入解析三个参数：memcg inode number、目标 NUMA 节点 ID、要扫描的对象数量。对 memcg-aware shrinker，通过 inode 号查找对应 memcg 实例；非 memcg-aware shrinker 要求 inode 号必须为 0。
- **并发安全**：所有修改 shrinker debugfs 状态的操作（add/rename/remove）均在 `shrinker_mutex` 保护下进行，该互斥锁也用于保护全局 shrinker 列表。`lockdep_assert_held()` 用于验证锁持有状态。
- **延迟初始化**：使用 `late_initcall` 确保在大多数 shrinker 注册完成后再初始化 debugfs，同时 `shrinker_debugfs_add()` 支持在 debugfs 初始化前注册的 shrinker 延迟创建条目。

## 4. 依赖关系

- **内部头文件**：包含 `"internal.h"`，可能定义了 shrinker 子系统的内部接口。
- **外部内核模块**：
  - `vmscan.c`：依赖其导出的 `shrinker_mutex` 和 `shrinker_list` 全局变量。
  - Memory Control Group (`memcontrol.h`)：使用 memcg 迭代、在线状态检查、inode 查找等接口。
  - DebugFS (`debugfs.h`)：核心依赖，用于创建和管理调试文件。
  - IDR/IDA (`idr.h`)：用于分配唯一 shrinker ID。
  - Slab Allocator (`slab.h`)：用于动态分配 per-node 计数数组。
  - RCU (`rcu_read_lock/unlock`)：保护 memcg 遍历过程。

## 5. 使用场景

- **内核开发与调试**：开发者可通过读取 `count` 文件实时监控特定 shrinker（如 dentry、inode cache）在不同 memcg 和 NUMA 节点上的缓存大小，分析内存分布。
- **手动触发内存回收**：通过向 `scan` 文件写入参数，可在不等待内核自动回收的情况下，立即测试 shrinker 的 `scan_objects` 行为，验证回收逻辑正确性或强制释放内存。
- **性能分析**：结合其他工具（如 ftrace），观察 shrinker 调用频率和效果，优化内存子系统性能。
- **运行时重命名**：`shrinker_debugfs_rename()` 允许动态修改 shrinker 名称（例如基于设备名），使 debugfs 条目更具可读性。