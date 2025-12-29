# memory-tiers.c

> 自动生成时间: 2025-12-07 16:41:40
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `memory-tiers.c`

---

# memory-tiers.c 技术文档

## 1. 文件概述

`memory-tiers.c` 是 Linux 内核中实现 **内存层级（Memory Tiering）** 功能的核心模块。该文件负责根据抽象距离（abstract distance, adistance）对 NUMA 节点进行分层管理，支持将不同性能特性的内存（如 DRAM、PMEM、HBM 等）组织成层级结构，并为页面迁移（demotion/promotion）和 NUMA 平衡提供基础支持。通过 sysfs 暴露内存层级信息，便于用户空间监控和策略配置。

## 2. 核心功能

### 主要数据结构

- `struct memory_tier`  
  表示一个内存层级，包含：
  - `adistance_start`：该层级的起始抽象距离（按 `MEMTIER_CHUNK_SIZE` 对齐）
  - `memory_types`：属于该层级的所有内存设备类型（`memory_dev_type`）链表
  - `lower_tier_mask`：所有更低层级（更高延迟/更低性能）节点的位掩码
  - `dev`：对应的 sysfs 设备对象

- `struct demotion_nodes`  
  用于记录每个节点在页面降级（demotion）时的首选目标节点集合。

- `struct node_memory_type_map`  
  每个 NUMA 节点到其内存设备类型的映射及引用计数。

- `node_demotion[]`（仅 `CONFIG_MIGRATION`）  
  全局数组，存储每个节点的降级目标偏好。

### 主要函数与接口

- `find_create_memory_tier()`  
  根据给定内存设备类型的抽象距离，查找或创建对应的 `memory_tier` 实例，并将其加入全局层级链表（按 `adistance_start` 升序排列）。

- `__node_get_memory_tier()` / `node_is_toptier()`  
  查询指定 NUMA 节点所属的内存层级；`node_is_toptier()` 判断节点是否属于顶层（最高性能）内存层级。

- `node_get_allowed_targets()`  
  获取指定节点在页面迁移时允许的目标节点集合（即其所在层级之下的所有节点）。

- `next_demotion_node()`（未完整展示）  
  返回从给定节点出发，在降级路径中的下一个目标节点 ID。

- `folio_use_access_time()`（仅 `CONFIG_NUMA_BALANCING`）  
  在启用内存层级模式的 NUMA 平衡中，判断是否将 folio 的 `_last_cpupid` 字段复用为访问时间戳（仅适用于非顶层内存节点）。

- `nodelist_show()`  
  sysfs 属性回调，输出当前内存层级包含的所有 NUMA 节点列表。

## 3. 关键实现

### 内存层级构建逻辑
- 所有内存设备类型（`memory_dev_type`）通过其 `adistance` 值被归入特定层级。
- 层级按 `adistance_start = round_down(adistance, MEMTIER_CHUNK_SIZE)` 分组，确保同一层级内设备具有相近的性能特征。
- 全局链表 `memory_tiers` 维护层级顺序（从低 `adistance` 到高），反映从高性能到低性能的层级结构。

### 层级间依赖关系
- 每个 `memory_tier` 的 `lower_tier_mask` 记录了所有比它性能更低（`adistance` 更高）的层级所包含的节点集合，用于快速确定迁移目标范围。
- 顶层层级由全局变量 `top_tier_adistance` 定义，通常对应最低 `adistance` 值的层级（如 CPU 本地 DRAM）。

### RCU 与锁机制
- 使用 `memory_tier_lock`（互斥锁）保护全局层级结构和设备注册。
- 节点到层级的映射（`pgdat->memtier`）通过 RCU 机制更新和读取，确保在无锁路径（如页面访问）中的高效性。
- `synchronize_rcu()` 用于在释放 `memory_tier` 前确保无并发 RCU 读者。

### sysfs 集成
- 每个 `memory_tier` 注册为 `memory_tiering` 子系统下的设备（`memory_tierX`）。
- 通过 `nodelist` 属性暴露该层级包含的 NUMA 节点，格式为位图字符串（如 `"0-3,8-11"`）。

## 4. 依赖关系

- **核心依赖**：
  - `<linux/memory.h>`：NUMA 节点和内存管理基础
  - `<linux/memory-tiers.h>`：内存层级公共接口定义
  - `"internal.h"`：内部辅助函数
- **可选依赖**：
  - `CONFIG_NUMA_BALANCING`：提供 `folio_use_access_time()`，支持基于访问时间的页面迁移
  - `CONFIG_MIGRATION`：提供 `node_demotion` 结构和 `next_demotion_node()` 等迁移相关功能
- **子系统交互**：
  - 与内存热插拔（`memory_hotplug`）协同，动态更新层级结构
  - 为自动 NUMA 平衡（AutoNUMA）和页面迁移框架提供层级拓扑信息

## 5. 使用场景

- **异构内存系统管理**：在包含 DRAM、PMEM、CXL 内存等多类型内存的系统中，自动构建性能层级视图。
- **智能页面迁移**：作为 `migrate_pages()` 和后台 demotion daemon 的决策依据，将冷页从高性能内存迁移到大容量低速内存。
- **NUMA 负载均衡优化**：在 `CONFIG_NUMA_BALANCING` 启用时，结合访问时间戳和层级信息，优先将热页保留在顶层内存。
- **用户空间监控与调优**：通过 `/sys/devices/memory_tiering/memory_tier*/nodelist` 查看各层级节点分布，辅助制定应用部署策略。