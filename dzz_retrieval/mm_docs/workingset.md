# workingset.c

> 自动生成时间: 2025-12-07 17:34:58
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `workingset.c`

---

# workingset.c 技术文档

## 1. 文件概述

`workingset.c` 实现了 Linux 内核中的 **工作集检测（Workingset Detection）** 机制，用于优化页面回收（page reclaim）策略。该机制通过跟踪页面的访问模式和重故障距离（refault distance），智能判断哪些页面应保留在内存中，从而减少系统颠簸（thrashing）并提升缓存效率。核心思想是：若一个被换出的页面在短时间内再次被访问（即重故障），且其重故障距离小于当前活跃页面数量，则应将其重新激活，以取代可能已不再活跃的现有活跃页面。

## 2. 核心功能

### 主要数据结构
- **Shadow Entry（影子条目）**：存储在页缓存槽位中的元数据，包含页面被驱逐时的时间戳（eviction counter 快照）、内存控制组 ID、节点 ID 和工作集标志。
- **node->nonresident_age**：每个 NUMA 节点维护的计数器，记录非驻留页面的“年龄”，用于计算重故障距离。

### 关键宏定义
- `WORKINGSET_SHIFT`：工作集标识位偏移。
- `EVICTION_SHIFT` / `EVICTION_MASK`：用于在 xarray 条目中紧凑编码驱逐时间戳的位操作参数。
- `bucket_order`：当时间戳位数不足时，用于对驱逐事件进行分桶聚合的粒度。

### 核心函数（部分实现）
- `pack_shadow()`：将内存控制组 ID、节点指针、驱逐计数器值和工作集标志打包成一个 shadow entry。
- （注：代码片段未完整展示其他关键函数如 `workingset_refault()`、`workingset_activation()` 等，但文档基于完整机制描述）

## 3. 关键实现

### 双 CLOCK 列表模型
- 每个 NUMA 节点为文件页维护两个 LRU 列表：**inactive list**（不活跃）和 **active list**（活跃）。
- 新缺页页面加入 inactive list 头部；回收从 inactive list 尾部扫描。
- 在 inactive list 上被二次访问的页面晋升至 active list；active list 过长时，尾部页面降级到 inactive list。

### 重故障距离（Refault Distance）算法
1. **驱逐时记录**：页面被驱逐时，将其所在节点的 `nonresident_age` 计数器值（代表累计的驱逐+激活次数）作为时间戳存入 shadow entry。
2. **重故障时计算**：
   - 当缺页发生且存在对应 shadow entry 时，读取当前 `nonresident_age` 值（R）与 shadow 中存储的值（E）。
   - 重故障距离 = `R - E`，表示页面不在内存期间发生的最小页面访问次数。
3. **激活决策**：
   - 若 `重故障距离 <= 当前活跃页面总数（file + anon）`，则认为若当时有足够 inactive 空间，该页面本可被激活而避免驱逐。
   - 因此**乐观地激活**该重故障页面，使其与现有活跃页面竞争内存空间。

### 影子条目压缩存储
- 利用 xarray 条目的有限位宽（`BITS_PER_XA_VALUE`），通过位域拼接存储：
  - 节点 ID（`NODES_SHIFT` 位）
  - 内存控制组 ID（`MEM_CGROUP_ID_SHIFT` 位）
  - 工作集标志（`WORKINGSET_SHIFT` 位）
  - 驱逐时间戳（剩余位，必要时通过 `bucket_order` 降低精度）

## 4. 依赖关系

- **内存管理核心**：`<linux/mm.h>`, `<linux/mm_inline.h>` — 提供页框、LRU 列表、页表操作等基础支持。
- **内存控制组**：`<linux/memcontrol.h>` — 支持按 cgroup 隔离工作集统计。
- **页缓存与交换**：`<linux/pagemap.h>`, `<linux/swap.h>`, `<linux/shmem_fs.h>` — 处理文件页、匿名页、tmpfs 页的回收逻辑。
- **xarray 数据结构**：用于高效存储和检索 shadow entries（隐含在 `pack_shadow` 的位操作中）。
- **DAX 支持**：`<linux/dax.h>` — 确保直接访问持久内存设备的页面也能参与工作集检测。

## 5. 使用场景

- **内存压力下的页面回收**：当系统内存紧张触发 kswapd 或直接回收时，工作集检测机制指导选择最优的牺牲页面。
- **工作集切换检测**：识别应用程序工作集的动态变化（如新任务启动、旧任务结束），快速淘汰过时缓存。
- **防止颠簸（Thrashing）**：在活跃工作集大小接近或超过可用内存时，通过重故障距离预测避免频繁换入换出。
- **混合工作负载优化**：同时处理文件缓存（page cache）和匿名内存（anonymous pages）的工作集，平衡二者内存分配。
- **容器化环境**：结合 memcg，在多租户系统中为每个容器独立维护工作集状态，避免相互干扰。