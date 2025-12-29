# swap_cgroup.c

> 自动生成时间: 2025-12-07 17:26:23
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `swap_cgroup.c`

---

# swap_cgroup.c 技术文档

## 1. 文件概述

`swap_cgroup.c` 实现了 Linux 内核中用于跟踪交换（swap）条目与内存控制组（mem_cgroup）之间关联关系的机制。该文件通过紧凑的数据结构将每个 swap 条目映射到对应的 mem_cgroup ID，从而支持基于 cgroup 的内存资源统计和限制功能（特别是 swap accounting）。当系统启用 `CONFIG_MEMCG_SWAP` 时，此机制用于在页面换出（swap out）时记录所属 cgroup，并在换入（swap in）或释放 swap 槽位时清除记录。

## 2. 核心功能

### 主要数据结构

- **`struct swap_cgroup`**  
  原子变量（`atomic_t`）封装结构，用于存储多个 swap 条目的 cgroup ID。每个 `swap_cgroup` 实例可容纳 `ID_PER_SC` 个 16 位的 cgroup ID。

- **`struct swap_cgroup_ctrl`**  
  每个 swap 设备（最多 `MAX_SWAPFILES` 个）对应一个控制器，包含指向 `swap_cgroup` 数组的指针 `map`。

- **全局数组 `swap_cgroup_ctrl[MAX_SWAPFILES]`**  
  管理所有已激活 swap 设备的 cgroup 映射表。

### 主要函数

- **`swap_cgroup_record()`**  
  为属于同一 folio 的连续多个 swap 条目记录指定的 mem_cgroup ID。

- **`swap_cgroup_clear()`**  
  清除一组连续 swap 条目所关联的 mem_cgroup ID，并返回原 ID。

- **`lookup_swap_cgroup_id()`**  
  查询指定 swap 条目当前关联的 mem_cgroup ID。

- **`swap_cgroup_swapon()`**  
  在启用 swap 设备时，为其分配并初始化 cgroup 映射表。

- **`swap_cgroup_swapoff()`**  
  在停用 swap 设备时，释放其对应的 cgroup 映射表。

## 3. 关键实现

### 紧凑存储设计

- 利用 `atomic_t`（通常为 32 位）同时存储两个 16 位的 cgroup ID（`ID_PER_SC = 2`），通过位操作实现高效存取。
- 定义宏：
  - `ID_SHIFT = 16`（`unsigned short` 的位宽）
  - `ID_MASK = 0xFFFF`
  - 每个 `swap_cgroup` 结构体大小等于 `atomic_t`，确保原子操作可行性。

### 原子读写操作

- **`__swap_cgroup_id_lookup()`**：通过位移和掩码从 `atomic_t` 中提取指定偏移的 ID。
- **`__swap_cgroup_id_xchg()`**：使用 `atomic_try_cmpxchg()` 循环实现无锁更新，确保并发安全地替换指定位置的 ID。

### 内存管理

- 使用 `vzalloc()` 分配大块非连续虚拟内存（因 swap 空间可能很大），并在 `swapoff` 时通过 `vfree()` 释放。
- 分配大小为 `DIV_ROUND_UP(max_pages, ID_PER_SC) * sizeof(struct swap_cgroup)`，即每两个 swap 条目共享一个 `swap_cgroup` 结构。

### 安全性保障

- 使用 `mutex`（`swap_cgroup_mutex`）保护 `swap_cgroup_ctrl[].map` 的赋值/清空操作，防止 swapon/swapoff 期间的竞态。
- 多处使用 `VM_BUG_ON()` 断言确保调用前提（如清除时所有条目 ID 一致、记录时原 ID 为 0）。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/swap_cgroup.h>`：声明对外接口
  - `<linux/vmalloc.h>`：提供 `vzalloc`/`vfree`
  - `<linux/mm.h>` 和 `<linux/swapops.h>`：提供 swap 条目操作（`swp_offset`, `swp_type`）及内存管理基础

- **配置依赖**：
  - 仅在 `CONFIG_MEMCG` 启用且未通过 `swapaccount=0` 禁用时生效（由 `mem_cgroup_disabled()` 控制）

- **与其他子系统交互**：
  - 与 **memory cgroup (memcg)** 子系统紧密集成，在页面换出/换入路径中被调用
  - 依赖 **swap subsystem** 提供的 `swp_entry_t` 抽象和 swap 设备管理

## 5. 使用场景

- **Swap Accounting（cgroup v1）**：  
  当进程属于特定 mem cgroup 且其匿名页被换出时，内核调用 `swap_cgroup_record()` 将 swap 条目与 cgroup ID 绑定；后续换入或释放 swap 槽位时调用 `swap_cgroup_clear()` 解绑。

- **资源统计与限制**：  
  通过 `lookup_swap_cgroup_id()` 查询 swap 条目所属 cgroup，用于统计各 cgroup 的 swap 使用量，并在达到 `memory.swappiness` 或 `memory.limit_in_bytes` 限制时触发回收。

- **Swap 设备生命周期管理**：  
  在 `sys_swapon()` 中调用 `swap_cgroup_swapon()` 初始化映射表，在 `sys_swapoff()` 中调用 `swap_cgroup_swapoff()` 释放资源。