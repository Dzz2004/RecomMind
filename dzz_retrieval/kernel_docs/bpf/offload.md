# bpf\offload.c

> 自动生成时间: 2025-10-25 12:22:34
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\offload.c`

---

# bpf/offload.c 技术文档

## 1. 文件概述

`bpf/offload.c` 是 Linux 内核中用于支持 BPF（Berkeley Packet Filter）程序和映射（map）硬件卸载（offload）功能的核心实现文件。该文件提供了将 BPF 程序绑定到特定网络设备（netdev）的能力，并支持将 BPF 逻辑卸载到支持该功能的智能网卡（如 Netronome NFP）上执行，从而提升数据包处理性能。同时，它也支持仅将 BPF 程序“绑定”到设备而不实际卸载（dev-bound-only 模式），用于限制程序作用域。

## 2. 核心功能

### 主要数据结构

- **`struct bpf_offload_dev`**  
  表示一个 BPF 卸载设备实例，包含卸载操作回调（`ops`）、关联的网络设备列表（`netdevs`）和私有数据（`priv`）。

- **`struct bpf_offload_netdev`**  
  表示一个支持 BPF 卸载的网络设备上下文，包含：
  - 指向底层 `net_device` 的指针
  - 所属的 `bpf_offload_dev`（若为纯绑定模式则为 NULL）
  - 已绑定/卸载的 BPF 程序列表（`progs`）
  - 已卸载的 BPF 映射列表（`maps`）
  - 在 `offdev->netdevs` 中的链表节点

- **全局哈希表 `offdevs`**  
  使用 `rhashtable` 实现，以 `net_device *` 为键，快速查找对应的 `bpf_offload_netdev` 实例。

- **读写信号量 `bpf_devs_lock`**  
  保护 `offdevs` 哈希表及其中所有 `bpf_offload_netdev` 结构的并发访问。注意：持有此锁时不能获取 RTNL 锁。

### 主要函数

- **`bpf_prog_dev_bound_init()`**  
  初始化 BPF 程序与网络设备的绑定关系，根据 `prog_flags` 决定是仅绑定（`BPF_F_XDP_DEV_BOUND_ONLY`）还是请求硬件卸载。

- **`bpf_prog_dev_bound_inherit()`**  
  在 BPF 程序复制（如 `bpf_prog_clone`）时继承原程序的设备绑定属性。

- **`bpf_prog_offload_verifier_prep()`**  
  在 BPF 验证器准备阶段调用卸载设备的 `prepare` 回调，为后续卸载做准备。

- **`__bpf_offload_dev_netdev_register()` / `__bpf_offload_dev_netdev_unregister()`**  
  内部函数，用于注册/注销网络设备的 BPF 卸载上下文。

- **`__bpf_prog_offload_destroy()` / `__bpf_map_offload_destroy()`**  
  销毁已卸载的 BPF 程序或映射，调用驱动提供的清理回调。

- **`bpf_map_offload_ndo()`**  
  通过 `ndo_bpf` 网络设备操作接口向驱动发送 BPF 映射相关命令（如释放）。

## 3. 关键实现

### 设备绑定与卸载区分
- 通过 `prog->aux->offload_requested` 标志区分“仅绑定”和“请求卸载”两种模式。
- 仅当 `offload_requested == true` 且设备支持 `ndo_bpf` 时，才尝试硬件卸载。
- 纯绑定模式（`BPF_F_XDP_DEV_BOUND_ONLY`）也会创建 `bpf_offload_netdev` 条目，但其 `offdev` 字段为 NULL。

### 安全并发控制
- 使用 `bpf_devs_lock`（读写信号量）保护所有对 `offdevs` 哈希表及其中对象的访问。
- 明确规定：持有 `bpf_devs_lock` 时不得获取 RTNL 锁，避免死锁。
- 在设备注销时（`__bpf_offload_dev_netdev_unregister`），若存在备用设备（`altdev`），会将程序和映射迁移到该设备；否则执行销毁流程。

### 资源迁移与清理
- 当一个支持卸载的网络设备被移除时，系统尝试将该设备上的 BPF 程序和映射迁移到同一 `bpf_offload_dev` 下的其他可用设备。
- 若无备用设备，则调用驱动提供的 `destroy` 回调清理硬件状态，并释放内核数据结构。

### 验证器集成
- `bpf_prog_offload_verifier_prep()` 在验证前调用驱动的 `prepare` 回调，允许驱动对 BPF 指令进行预处理或转换，以适配硬件指令集。

## 4. 依赖关系

- **网络子系统**：依赖 `net_device` 结构及 `ndo_bpf` 操作接口。
- **BPF 核心框架**：使用 `bpf_prog`、`bpf_map`、`bpf_verifier` 等核心数据结构和接口。
- **XDP 支持**：与 `net/xdp.h` 集成，支持 XDP 程序的设备绑定和卸载。
- **内核同步原语**：使用 `rwsem`、`rhashtable`、`list_head` 等通用内核机制。
- **RTNL 锁**：部分操作（如设备注销）要求调用者持有 RTNL 锁（通过 `ASSERT_RTNL()` 验证）。

## 5. 使用场景

1. **BPF 程序加载**：用户通过 `bpf(BPF_PROG_LOAD, ...)` 系统调用加载 XDP 或 TC 分类器程序时，若指定 `prog_ifindex` 和相应标志，会触发 `bpf_prog_dev_bound_init()`，建立程序与设备的绑定关系。

2. **硬件卸载**：当智能网卡驱动（如 `nfp`）注册了 `bpf_prog_offload_ops` 并实现 `ndo_bpf` 接口后，内核可将验证通过的 BPF 程序卸载到硬件执行。

3. **程序克隆**：在 BPF 程序被复制（如用于 tail call）时，通过 `bpf_prog_dev_bound_inherit()` 继承原程序的设备绑定属性。

4. **设备热插拔**：当支持 BPF 卸载的网络设备被移除时，内核自动迁移或销毁关联的 BPF 资源，确保系统稳定性。

5. **BPF 映射卸载**：支持将 BPF map（如 hash、array）卸载到硬件，由驱动管理其生命周期，通过 `bpf_map_offload_ndo()` 与驱动交互。