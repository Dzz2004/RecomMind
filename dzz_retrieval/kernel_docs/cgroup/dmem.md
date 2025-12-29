# cgroup\dmem.c

> 自动生成时间: 2025-10-25 12:45:21
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cgroup\dmem.c`

---

# cgroup/dmem.c 技术文档

## 文件概述

`cgroup/dmem.c` 实现了一个名为 **dmem（device memory）** 的 cgroup 子系统，用于对设备内存（如 GPU、NPU 或其他专用硬件内存）的使用进行资源控制和配额管理。该子系统通过 `page_counter` 机制跟踪每个 cgroup 在特定设备内存区域（region）上的用量，并支持设置 `min`、`low` 和 `max` 三种资源限制级别，以实现分级内存保护和回收策略。文件还提供了内存回收时的“是否可驱逐”判断逻辑，用于指导设备驱动在内存压力下选择合适的 cgroup 进行释放。

## 核心功能

### 主要数据结构

- **`struct dmem_cgroup_region`**  
  表示一个设备内存区域（如某块 GPU 显存），包含：
  - `ref`：引用计数，配合 RCU 管理生命周期
  - `region_node`：全局区域链表节点（`dmem_cgroup_regions`）
  - `pools`：关联到该区域的所有 cgroup 内存池列表
  - `size`：区域总大小（字节）
  - `name`：区域名称
  - `unregistered`：标记区域是否已注销，防止新池加入

- **`struct dmemcg_state`**  
  cgroup 子系统状态（CSS），每个 cgroup 实例对应一个，包含：
  - `css`：标准 cgroup_subsys_state 基类
  - `pools`：该 cgroup 下所有设备内存池的链表

- **`struct dmem_cgroup_pool_state`**  
  表示某个 cgroup 在特定设备内存区域上的使用状态，包含：
  - `region`：指向所属的 `dmem_cgroup_region`
  - `cs`：指向所属的 `dmemcg_state`
  - `css_node`：挂载到 cgroup 的 `pools` 链表（RCU 保护）
  - `region_node`：挂载到 region 的 `pools` 链表（自旋锁保护）
  - `cnt`：`page_counter` 实例，记录当前用量及限制
  - `inited`：初始化标志

### 主要函数

- **资源限制操作函数**  
  - `set_resource_min/low/max()`：设置 min/low/max 限制
  - `get_resource_current/min/low/max()`：获取当前用量或限制值
  - `reset_all_resource_limits()`：重置所有限制为默认值

- **cgroup 生命周期回调**  
  - `dmemcs_alloc()`：分配 cgroup 状态
  - `dmemcs_offline()`：cgroup 下线时重置所有池的限制
  - `dmemcs_free()`：释放 cgroup 状态及关联的池

- **内存回收辅助函数**  
  - `dmem_cgroup_state_evict_valuable()`：判断某内存池是否可被驱逐（核心回收逻辑）
  - `dmem_cgroup_calculate_protection()`：计算子树中各池的有效保护值（emin/elow）

- **辅助函数**  
  - `find_cg_pool_locked()`：在指定 cgroup 中查找特定 region 的池（需持锁）
  - `pool_parent()`：获取池的父池（基于 page_counter 层级）

## 关键实现

### 并发控制策略

- **全局自旋锁 `dmemcg_lock`**：保护以下操作：
  - 全局区域列表 `dmem_cgroup_regions` 的增删
  - cgroup 的 `pools` 链表与 region 的 `pools` 链表的修改
- **RCU 机制**：用于无锁读取 cgroup 的 `pools` 链表（如 `dmemcs_offline()` 和 `find_cg_pool_locked()`）
- **`page_counter`**：本身是无锁的原子计数器，用于高效跟踪内存用量

### 内存保护与回收逻辑

- **三级保护机制**：
  - `min`：硬性保证，用量 ≤ min 时不可驱逐
  - `low`：软性保护，用量 > low 时可驱逐；用量 ≤ low 时需特殊处理（如设置 `ret_hit_low`）
  - `max`：硬性上限，用量不可超过
- **`dmem_cgroup_state_evict_valuable()` 工作流程**：
  1. 若 `limit_pool == test_pool`，直接允许驱逐（自身超限）
  2. 若 `limit_pool` 无父 cgroup（即根 cgroup），允许驱逐
  3. 检查 `test_pool` 是否在 `limit_pool` 的子树中（通过 `pool_parent` 遍历）
  4. 调用 `dmem_cgroup_calculate_protection()` 计算子树中各池的有效保护值
  5. 比较 `test_pool` 的当前用量与 `emin`/`elow`：
     - 用量 ≤ `emin` → 不可驱逐
     - 用量 > `elow` → 可驱逐
     - 用量 ≤ `elow` 且 `ignore_low=false` → 不可驱逐，但设置 `ret_hit_low=true` 建议重试

### 层级关系维护

- **池的父子关系**：通过 `page_counter` 的 `parent` 字段隐式建立，`pool_parent()` 用于向上遍历
- **保护值传播**：`dmem_cgroup_calculate_protection()` 遍历 `limit_pool` 的整个子树，调用 `page_counter_calculate_protection()` 更新各子池的 `emin`/`elow`

## 依赖关系

- **核心依赖**：
  - `<linux/cgroup.h>`：cgroup 子系统框架
  - `<linux/page_counter.h>`：内存用量计数与保护机制
  - `<linux/rcupdate.h>`（隐式）：RCU 读写锁
  - `<linux/spinlock.h>`：自旋锁实现
- **头文件依赖**：
  - `<linux/cgroup_dmem.h>`：dmem cgroup 的公共接口定义（如 `dmem_cgrp_id`）
- **与其他子系统关系**：
  - 类似 `rdma` 和 `misc` cgroup 控制器的设计模式
  - 为设备驱动（如 GPU/NPU 驱动）提供内存配额管理接口

## 使用场景

- **设备内存资源隔离**：在多租户或容器化环境中，限制不同 cgroup 对专用设备内存（如 GPU 显存）的使用量。
- **分级内存回收**：当设备内存不足时，驱动调用 `dmem_cgroup_state_evict_valuable()` 判断哪些 cgroup 的内存可安全释放，优先驱逐超出 `low` 限制的 cgroup，保护 `min` 限制内的关键任务。
- **动态配额调整**：管理员可通过 cgroup 接口（如 `memory.dmem.*` 文件）动态调整各 cgroup 的 `min`/`low`/`max` 限制，实现灵活的资源调度。
- **根 cgroup 默认行为**：未显式设置限制的 cgroup 继承根 cgroup 的默认策略（`max=PAGE_COUNTER_MAX`，无硬限制）。