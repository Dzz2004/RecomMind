# bpf\devmap.c

> 自动生成时间: 2025-10-25 12:08:49
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\devmap.c`

---

# `bpf/devmap.c` 技术文档

## 1. 文件概述

`bpf/devmap.c` 实现了 BPF **设备映射（devmap）** 功能，主要用于支持 XDP（eXpress Data Path）程序中的 `bpf_redirect_map()` 辅助函数，实现高性能的网络数据包重定向到指定网络设备。该文件提供了两种类型的 BPF 映射：

- `BPF_MAP_TYPE_DEVMAP`：基于数组索引的设备映射
- `BPF_MAP_TYPE_DEVMAP_HASH`：基于哈希表的设备映射（以 ifindex 为键）

核心设计目标是在数据路径（datapath）中**避免使用锁**，通过 RCU（Read-Copy-Update）机制和原子操作保证并发安全，同时支持设备注销时的安全清理。

## 2. 核心功能

### 主要数据结构

- **`struct xdp_dev_bulk_queue`**  
  每 CPU 的批量发送队列，用于暂存待重定向的数据包，包含：
  - 最多 `DEV_MAP_BULK_SIZE` 个 `xdp_frame`
  - 关联的目标设备 `dev` 和接收设备 `dev_rx`
  - 可选的 XDP 程序 `xdp_prog`
  - 队列计数器 `count`

- **`struct bpf_dtab_netdev`**  
  表示映射中一个设备条目，包含：
  - 指向 `net_device` 的指针（必须为第一个成员，供 tracepoint 使用）
  - 哈希链表节点 `index_hlist`（仅用于 `DEVMAP_HASH`）
  - 关联的 XDP 程序 `xdp_prog`
  - RCU 回调头 `rcu`
  - 在数组中的索引 `idx`
  - 设备值结构 `bpf_devmap_val`

- **`struct bpf_dtab`**  
  devmap 的主控制结构，继承自 `bpf_map`，包含：
  - `netdev_map`：指向 `bpf_dtab_netdev*` 数组（仅用于 `DEVMAP`）
  - `dev_index_head`：哈希桶数组（仅用于 `DEVMAP_HASH`）
  - `index_lock`：保护哈希表的自旋锁
  - `items` 和 `n_buckets`：哈希表项数和桶数
  - 全局链表节点 `list`

### 主要函数

- **`dev_map_alloc()`**  
  分配并初始化 devmap 实例，根据 `attr->map_type` 选择数组或哈希实现。

- **`dev_map_free()`**  
  安全释放 devmap，确保所有 RCU 读取和 flush 操作完成后再释放资源。

- **`dev_map_init_map()`**  
  验证 BPF 属性并初始化映射结构，强制设置 `BPF_F_RDONLY_PROG` 保证只读。

- **`dev_map_create_hash()`**  
  为 `DEVMAP_HASH` 类型分配并初始化哈希桶数组。

- **`dev_map_index_hash()`**  
  计算 ifindex 在哈希表中的桶位置（使用位掩码取模）。

- **`dev_map_get_next_key()`**（未完整展示）  
  支持 BPF 迭代器遍历映射键。

## 3. 关键实现

### 无锁数据路径设计
- **读操作（lookup）**：在 RCU 临界区内直接读取 `netdev_map[idx]`，无锁。
- **写操作（update/delete）**：使用 `xchg()` 原子替换指针，确保读侧看到一致状态。
- **内存回收**：通过 `call_rcu()` 延迟释放旧条目，等待 RCU 宽限期结束。

### Flush 机制
- 每 CPU 维护 `dev_flush_list`，暂存待发送的数据包。
- `bpf_dtab_netdev` 对象在 flush 列表清空前不会被销毁，确保 NAPI 上下文安全。

### 设备注销处理
- 通过 `netdev_unregister` 通知链扫描所有 devmap。
- 使用 `cmpxchg()` 安全移除匹配的设备条目，防止并发更新导致误删。
- 内核保证注销期间 `dev_get_by_index()` 失败，阻止新条目添加。

### 两种映射类型
- **`DEVMAP`**：简单数组，索引即键，适合密集 ifindex。
- **`DEVMAP_HASH`**：哈希表实现，键为 ifindex，适合稀疏场景，避免内存浪费。
- 两者共享数据包入队和发送逻辑，仅 lookup/insert 实现不同。

### 安全与验证
- 强制设置 `BPF_F_RDONLY_PROG`，防止 BPF 程序修改映射值。
- 严格校验 `value_size`（仅允许 4 字节 ifindex 或 8 字节 ifindex+prog_fd）。

## 4. 依赖关系

- **BPF 子系统**：`<linux/bpf.h>`，提供基础映射框架和程序管理。
- **XDP 框架**：`<net/xdp.h>`，定义 `xdp_frame` 和重定向接口。
- **网络设备层**：依赖 `net_device` 结构和 `dev_put()`/`dev_hold()` 引用管理。
- **RCU 机制**：用于无锁并发控制和安全内存回收。
- **Tracepoint**：`<trace/events/xdp.h>`，支持 XDP 事件跟踪。
- **BTF**：`<linux/btf_ids.h>`，用于类型信息导出。

## 5. 使用场景

- **XDP 重定向**：在 XDP 程序中调用 `bpf_redirect_map(map, key, flags)` 将数据包重定向到指定网络设备。
- **高性能负载均衡**：结合 `DEVMAP_HASH` 实现基于 ifindex 的动态后端选择。
- **服务网格/防火墙**：在数据路径中动态更新出口设备，无需内核协议栈介入。
- **设备热插拔**：安全处理网络设备注销，自动清理映射中的无效条目。
- **批量发送优化**：通过 per-CPU flush 队列聚合数据包，减少驱动调用次数。