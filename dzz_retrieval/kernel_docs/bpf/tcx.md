# bpf\tcx.c

> 自动生成时间: 2025-10-25 12:34:01
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\tcx.c`

---

# `bpf/tcx.c` 技术文档

## 1. 文件概述

`bpf/tcx.c` 是 Linux 内核中实现 **TCX（Traffic Control eXpress）** BPF 程序挂载机制的核心文件。TCX 是一种新型的、轻量级的 BPF 程序挂载点，用于在网络设备的 **ingress（入站）** 或 **egress（出站）** 路径上高效执行 BPF 程序，替代或补充传统的 `tc`（traffic control）分类器。该文件负责管理 TCX BPF 程序的 **attach（挂载）**、**detach（卸载）**、**query（查询）** 以及通过 **BPF link** 对象进行生命周期管理。

## 2. 核心功能

### 主要函数

- **`tcx_prog_attach()`**  
  将指定的 BPF 程序挂载到指定网络设备的 ingress/egress 路径上，支持替换（`BPF_F_REPLACE`）和相对位置挂载。

- **`tcx_prog_detach()`**  
  从指定网络设备的 ingress/egress 路径上卸载指定的 BPF 程序。

- **`tcx_uninstall()`**  
  在网络设备注销时，清理并卸载所有挂载在该设备上的 TCX BPF 程序（包括通过 link 和直接 attach 的程序）。

- **`tcx_prog_query()`**  
  查询指定网络设备上挂载的 TCX BPF 程序列表及其元数据。

- **`tcx_link_attach()`**  
  创建一个 `BPF_LINK_TYPE_TCX` 类型的 BPF link 对象，并将 BPF 程序通过该 link 挂载到指定网络设备。

- **`tcx_link_release()` / `tcx_link_detach()`**  
  释放或显式分离 TCX BPF link，触发程序卸载。

- **`tcx_link_update()`**  
  更新 TCX BPF link 所关联的 BPF 程序（原子替换）。

- **`tcx_link_fdinfo()` / `tcx_link_fill_info()`**  
  提供 link 的调试信息（`/proc/self/fdinfo/`）和用户空间查询接口（`bpf_obj_get_info_by_fd`）。

### 关键数据结构

- **`struct tcx_link`**  
  表示一个 TCX BPF link 实例，包含：
  - `struct bpf_link link`：通用 BPF link 基类
  - `enum bpf_attach_type location`：挂载位置（`BPF_TCX_INGRESS` 或 `BPF_TCX_EGRESS`）
  - `struct net_device *dev`：关联的网络设备

- **`tcx_link_lops`**  
  `struct bpf_link_ops` 实例，定义 TCX link 的操作回调函数集。

## 3. 关键实现

### 多程序管理（`bpf_mprog` 框架）
- TCX 使用内核通用的 **`bpf_mprog`（multi-program）** 框架管理同一挂载点上的多个 BPF 程序。
- 每个网络设备的 ingress/egress 方向维护一个独立的 `bpf_mprog_entry`。
- `tcx_entry_fetch_or_create()` / `tcx_entry_fetch()` 用于获取或创建该 entry。
- `bpf_mprog_attach()` / `bpf_mprog_detach()` 执行实际的程序插入/删除逻辑，支持按 ID/FD 替换、相对位置挂载等高级功能。

### 原子更新与同步
- 所有 attach/detach 操作均在 **`rtnl_lock()`** 保护下执行，确保与网络设备状态变更同步。
- 修改 `bpf_mprog_entry` 后，通过 `tcx_entry_update()` 更新设备上的引用，并调用 `tcx_entry_sync()` 触发数据路径同步（如更新跳转表）。
- 使用 **copy-on-write** 语义：修改时创建新 entry（`entry_new`），成功后再原子替换。

### 引用计数与资源回收
- 通过 `tcx_skeys_inc()` / `tcx_skeys_dec()` 管理全局 TCX 程序计数（用于优化数据路径）。
- 当 entry 不再活跃（`tcx_entry_is_active()` 为假）时，调用 `tcx_entry_free()` 释放内存。
- `tcx_uninstall()` 在设备销毁时遍历所有程序，对 link 类型置空 `dev` 指针，对普通程序调用 `bpf_prog_put()`。

### BPF Link 集成
- TCX 程序可通过两种方式挂载：
  1. 直接 attach（`BPF_PROG_ATTACH` 命令）
  2. 通过 BPF link（`BPF_LINK_CREATE` 命令）
- Link 方式提供更灵活的生命周期管理（如自动 detach、程序更新）。
- `tcx_link_update()` 实现原子程序替换，确保数据路径无中断。

## 4. 依赖关系

- **`<linux/bpf.h>`**：BPF 核心 API 和数据结构定义。
- **`<linux/bpf_mprog.h>`**：多程序管理框架（`bpf_mprog_entry`、attach/detach/query 接口）。
- **`<linux/netdevice.h>`**：网络设备管理（`net_device`、`rtnl_lock`）。
- **`<net/tcx.h>`**：TCX 子系统头文件，定义 `tcx_entry_*`、`tcx_skeys_*` 等 TCX 专用接口。
- **BPF 子系统**：依赖 BPF 程序验证、JIT、map 等核心功能。
- **网络设备子系统**：与 `netdev` 通知链、设备注册/注销流程紧密集成。

## 5. 使用场景

- **高性能网络策略实施**：在网卡 ingress/egress 路径执行 XDP-like 的 BPF 程序，但位于更晚的网络栈阶段（可访问完整 skb）。
- **服务网格/微隔离**：替代 iptables/nftables 实现细粒度流量控制。
- **可观测性**：挂载监控程序收集流量统计信息。
- **动态程序更新**：通过 BPF link 实现零停机策略更新。
- **容器/虚拟化网络**：为每个 veth 接口挂载独立策略。
- **内核模块卸载**：当驱动模块卸载时，`tcx_uninstall()` 自动清理关联程序。