# cgroup\rdma.c

> 自动生成时间: 2025-10-25 12:50:50
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cgroup\rdma.c`

---

# cgroup/rdma.c 技术文档

## 文件概述

`cgroup/rdma.c` 实现了 RDMA（Remote Direct Memory Access）资源限制控制器，作为 cgroup 子系统的一部分。该模块用于限制 cgroup 层级结构中的进程在达到指定资源上限后无法继续消耗额外的 RDMA 资源。通过为每个 cgroup 和每个 RDMA 设备维护资源池，实现对 RDMA 资源（如 HCA 句柄和对象）的精细化配额管理与层级化计费（charge/uncharge）。

## 核心功能

### 主要数据结构

- **`rdmacg_resource`**  
  表示单个 RDMA 资源类型的使用情况，包含 `max`（最大限额）和 `usage`（当前使用量）。

- **`rdmacg_resource_pool`**  
  表示一个 cgroup 在特定 RDMA 设备上的资源池，包含：
  - 指向 `rdmacg_device` 的指针
  - 各类资源的 `rdmacg_resource` 数组
  - 双向链表节点（分别链接到 cgroup 和设备的资源池列表）
  - `usage_sum`：该池中所有资源的总使用计数
  - `num_max_cnt`：设置为 `S32_MAX`（即无限制）的资源项数量

- **`rdmacg_resource_names`**  
  用户可见的资源名称映射表，当前支持：
  - `"hca_handle"` → `RDMACG_RESOURCE_HCA_HANDLE`
  - `"hca_object"` → `RDMACG_RESOURCE_HCA_OBJECT`

### 主要函数

- **`rdmacg_try_charge()`**  
  尝试在 cgroup 层级中为指定 RDMA 设备和资源类型进行资源计费。从当前 cgroup 向上遍历至根，逐级检查并增加使用量。若任一层级超出限额，则回滚并返回 `-EAGAIN`。

- **`rdmacg_uncharge()`**  
  在 cgroup 层级中释放指定资源的使用量，从当前 cgroup 向上遍历至根，逐级减少使用量。

- **`rdmacg_uncharge_hierarchy()`**  
  支持在指定停止点（`stop_cg`）前的层级范围内执行资源释放，用于更灵活的资源回收场景。

- **`get_cg_rpool_locked()` / `find_cg_rpool_locked()`**  
  在加锁状态下查找或创建指定 cgroup 与设备对应的资源池。

- **`free_cg_rpool_locked()`**  
  当资源池的 `usage_sum` 为 0 且所有资源均设为 `max`（即未显式限制）时，安全释放该资源池。

## 关键实现

### 层级化资源计费机制

RDMA cgroup 采用**自底向上计费、自顶向下限制**的策略：
- **计费（charge）**：从当前任务所属 cgroup 开始，逐级向上（至根 cgroup）尝试增加资源使用量。任一祖先 cgroup 超限即失败。
- **释放（uncharge）**：同样沿层级向上释放，确保资源使用量始终反映实际占用。

### 资源池生命周期管理

- 每个 `(cgroup, device)` 对应一个 `rdmacg_resource_pool`。
- 资源池在首次计费时按需创建（`get_cg_rpool_locked`）。
- 当 `usage_sum == 0` 且所有资源项均为 `max`（即无显式限制）时，自动释放资源池以节省内存。

### 限额表示

- 使用 `S32_MAX` 表示“无限制”（即 `max` 值）。
- `num_max_cnt` 用于快速判断是否所有资源均为无限制状态，从而决定是否可安全释放资源池。

### 并发控制

- 全局互斥锁 `rdmacg_mutex` 保护：
  - 所有 cgroup 的资源池链表（`cg->rpools`）
  - 所有 RDMA 设备的资源池链表（`device->rpools`）
  - 全局设备列表 `rdmacg_devices`
- 所有资源池操作（创建、查找、释放）均在锁保护下进行。

## 依赖关系

- **内核头文件依赖**：
  - `<linux/cgroup.h>`：cgroup 核心框架
  - `<linux/cgroup_rdma.h>`：RDMA cgroup 接口定义（如 `rdma_cgroup`、`rdmacg_device` 等）
  - `<linux/ib_verbs.h>`（隐含）：RDMA 资源类型定义（如 `RDMACG_RESOURCE_HCA_HANDLE`）
- **导出符号**：
  - `rdmacg_uncharge()`：供 RDMA 驱动（如 InfiniBand、RoCE 驱动）在释放资源时调用
- **cgroup 子系统集成**：
  - 通过 `rdma_cgrp_id` 获取当前任务的 cgroup 上下文
  - 依赖 cgroup 的层级遍历机制（`css.parent`）

## 使用场景

1. **RDMA 驱动资源分配**  
   当用户空间应用通过 verbs API 创建 QP、CQ、MR 等对象时，底层驱动调用 `rdmacg_try_charge()` 检查是否允许分配。若成功，则在对象销毁时调用 `rdmacg_uncharge()` 释放配额。

2. **多租户 RDMA 资源隔离**  
   在容器化或虚拟化环境中，管理员可通过 cgroup v1/v2 接口为不同租户设置 RDMA 资源上限（如最大 HCA 对象数），防止资源耗尽攻击。

3. **动态资源回收**  
   当 cgroup 中所有任务退出且无 RDMA 资源占用时，自动清理对应的资源池，避免内存泄漏。

4. **层级配额继承**  
   子 cgroup 的资源使用量计入所有祖先 cgroup，确保父级配额对整个子树生效，实现严格的资源隔离。