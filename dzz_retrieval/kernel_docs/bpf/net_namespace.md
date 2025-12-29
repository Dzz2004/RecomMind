# bpf\net_namespace.c

> 自动生成时间: 2025-10-25 12:21:41
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\net_namespace.c`

---

# `bpf/net_namespace.c` 技术文档

## 1. 文件概述

`bpf/net_namespace.c` 实现了 BPF（Berkeley Packet Filter）程序与网络命名空间（netns）的绑定机制。该文件提供了将 BPF 程序附加到特定网络命名空间的能力，并通过 `bpf_link` 抽象支持动态附加、更新、查询和自动清理。核心目标是允许 BPF 程序在特定网络命名空间上下文中执行，例如用于 socket 查找（`SK_LOOKUP`）或流量解析（`FLOW_DISSECTOR`）等场景，同时确保在命名空间销毁时自动解除绑定，避免资源泄漏。

## 2. 核心功能

### 数据结构

- **`struct bpf_netns_link`**  
  表示一个附加到网络命名空间的 BPF 链接对象，包含：
  - `link`：继承自通用 `bpf_link` 结构
  - `type`：标准 BPF 附加类型（如 `BPF_SK_LOOKUP`）
  - `netns_type`：内部网络命名空间专用的附加类型（如 `NETNS_BPF_SK_LOOKUP`）
  - `net`：指向所属 `struct net` 的指针（不持有引用，依赖锁保护）
  - `node`：用于将链接加入 per-netns、per-type 的链表

- **`netns_bpf_mutex`**  
  全局互斥锁，保护所有对网络命名空间中 BPF 附加状态的并发修改。

### 主要函数

- **`bpf_netns_link_release()`**  
  释放 BPF 链接：从链表中删除，更新运行数组，减少静态分支计数器。

- **`bpf_netns_link_detach()`**  
  用户触发的解绑操作，调用 `release` 逻辑。

- **`bpf_netns_link_dealloc()`**  
  释放链接结构体内存。

- **`bpf_netns_link_update_prog()`**  
  安全地替换链接中的 BPF 程序（需类型一致）。

- **`bpf_netns_link_fill_info()` / `bpf_netns_link_show_fdinfo()`**  
  提供链接信息查询接口，用于 `bpf_obj_get_info_by_fd` 和 `/proc/<pid>/fdinfo/`。

- **`netns_bpf_prog_query()`**  
  查询指定网络命名空间中某类型已附加的 BPF 程序 ID 列表。

- **`netns_bpf_prog_attach()`**  
  将 BPF 程序直接附加到当前网络命名空间（仅支持部分类型，且不允许与 `bpf_link` 混用）。

- **`netns_bpf_attach_type_need()` / `netns_bpf_attach_type_unneed()`**  
  管理静态分支（static key）的启用/禁用，用于性能优化（如 `bpf_sk_lookup_enabled`）。

- **`__netns_bpf_prog_query()`**  
  内部查询实现，需在 `netns_bpf_mutex` 保护下调用。

- **`link_index()` / `link_count()` / `fill_prog_array()`**  
  辅助函数，用于维护链接链表与运行程序数组的映射关系。

## 3. 关键实现

### 自动解绑机制
- `bpf_netns_link` 不持有 `struct net` 的引用计数，而是依赖网络命名空间销毁流程中的 `pre_exit` 回调（在其他文件中实现）将 `net` 字段置为 `NULL`。
- 所有访问 `net` 字段的操作必须在 `netns_bpf_mutex` 保护下进行，以避免与命名空间销毁过程竞争。

### 运行数组管理
- 每个网络命名空间的 `struct net->bpf.run_array[type]` 是一个 RCU 保护的 `bpf_prog_array`，存储当前激活的 BPF 程序指针。
- 添加/删除链接时，会重新分配并填充新的 `bpf_prog_array`，然后通过 RCU 原子替换，确保执行路径无锁。

### 静态分支优化
- 对于 `NETNS_BPF_SK_LOOKUP` 等关键路径，使用 `static_branch_inc/dec` 控制内联优化开关（`bpf_sk_lookup_enabled`），避免在无程序附加时产生性能开销。

### 附加模式互斥
- `netns_bpf_prog_attach()` 仅允许在没有 `bpf_link` 附加的情况下直接附加程序（通过检查 `list_empty(&net->bpf.links[type])`），防止传统附加与链接机制混用导致状态不一致。

### 安全更新
- `bpf_netns_link_update_prog()` 使用 `link_index()` 定位程序在数组中的位置，并通过 `bpf_prog_array_update_at()` 原子替换，确保更新过程线程安全。

## 4. 依赖关系

- **`<linux/bpf.h>` / `<linux/filter.h>`**：BPF 核心基础设施，包括 `bpf_link`、`bpf_prog`、`bpf_prog_array` 等定义。
- **`<linux/bpf-netns.h>`**：定义网络命名空间专用的 BPF 附加类型（`enum netns_bpf_attach_type`）和辅助函数（如 `to_netns_bpf_attach_type()`）。
- **`<net/net_namespace.h>`**：提供 `struct net` 及其 `bpf` 子结构（包含 `links[]` 和 `run_array[]`）。
- **`CONFIG_INET`**：`SK_LOOKUP` 功能依赖 IPv4/IPv6 网络栈支持。
- **`flow_dissector_bpf_prog_attach_check()`**：来自网络核心层，用于验证 `FLOW_DISSECTOR` 程序的合法性。

## 5. 使用场景

- **Socket 查找重定向**：用户通过 `BPF_SK_LOOKUP` 类型将 BPF 程序附加到 netns，实现自定义 socket 匹配逻辑（如服务网格、负载均衡）。
- **流量解析扩展**：通过 `BPF_FLOW_DISSECTOR` 附加程序，扩展内核对非标准协议的解析能力。
- **命名空间隔离的 BPF 策略**：在容器或虚拟化环境中，为每个网络命名空间部署独立的 BPF 网络策略。
- **动态程序管理**：通过 `bpf_link` API 实现程序的原子更新、查询和自动清理，适用于长时间运行的服务。
- **调试与监控**：通过 `fdinfo` 或 `bpf_obj_get_info_by_fd` 获取链接的命名空间和附加类型信息，辅助调试。