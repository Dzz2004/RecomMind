# bpf\reuseport_array.c

> 自动生成时间: 2025-10-25 12:29:05
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\reuseport_array.c`

---

# `bpf/reuseport_array.c` 技术文档

## 1. 文件概述

`bpf/reuseport_array.c` 实现了一个特殊的 BPF map 类型——**reuseport array**，用于将支持 `SO_REUSEPORT` 的 TCP/UDP socket 与 BPF 程序关联。该 map 允许用户空间通过文件描述符（fd）将 socket 注册到 map 中，BPF 程序（如 `BPF_SK_REUSEPORT_SELECT`）可在运行时根据负载均衡策略选择目标 socket。此机制主要用于实现用户态可编程的 socket 选择逻辑，提升高并发网络服务的负载均衡能力。

## 2. 核心功能

### 数据结构
- **`struct reuseport_array`**  
  继承自 `struct bpf_map`，其 `ptrs[]` 成员是一个 RCU 保护的 `struct sock *` 数组，每个元素指向一个已注册的 `SO_REUSEPORT` socket。

### 主要函数
- **`bpf_sk_reuseport_detach(struct sock *sk)`**  
  从 reuseport array 中安全移除指定 socket，通常在 socket 关闭或断开连接时调用。
  
- **`reuseport_array_alloc_check()`**  
  验证 map 创建参数，仅允许 `value_size` 为 `sizeof(u32)` 或 `sizeof(u64)`（用于传递 fd）。

- **`reuseport_array_lookup_elem()`**  
  通过 key（索引）查找对应的 socket 指针（RCU 读取）。

- **`reuseport_array_delete_elem()`**  
  从 map 中删除指定索引的 socket（需持有 `reuseport_lock`）。

- **`reuseport_array_free()`**  
  释放整个 reuseport array，清理所有关联的 socket 引用。

- **`reuseport_array_alloc()`**  
  分配并初始化 reuseport array 内存。

- **`bpf_fd_reuseport_array_lookup_elem()`**  
  用户态 lookup 接口：返回 socket 的 cookie（`u64`），而非内核指针。

- **`bpf_fd_reuseport_array_update_elem()`**  
  用户态 update 接口：通过 fd 将 socket 注册到 map 指定索引位置。

- **`reuseport_array_get_next_key()`**  
  支持遍历 map 的下一个有效 key（代码片段未完整，但功能明确）。

- **`reuseport_array_update_check()`**  
  验证待注册 socket 是否满足条件（协议、地址族、SO_REUSEPORT 状态等）。

## 3. 关键实现

### 并发安全机制
- **双重锁保护**：  
  - `reuseport_lock`（全局自旋锁）：保护 map 与 reuseport 组的一致性。  
  - `sk->sk_callback_lock`（socket 自旋锁）：保护 `sk_user_data` 字段的读写，避免与 `bpf_sk_reuseport_detach()` 竞争。
- **RCU 机制**：  
  `ptrs[]` 数组通过 RCU 读取（`rcu_dereference()`），写入时使用 `RCU_INIT_POINTER()` 或 `rcu_assign_pointer()`，确保无锁读取的安全性。
- **引用解耦**：  
  在 `reuseport_array_free()` 中，通过 `sk_callback_lock` 清理 `sk_user_data`，确保 array 释放前所有 socket 停止引用它。

### Socket 注册验证
`reuseport_array_update_check()` 严格校验 socket：
- 协议必须为 TCP/UDP；
- 地址族必须为 IPv4/IPv6；
- socket 必须已绑定（`sk_hashed`）且启用 `SO_REUSEPORT`（`sk_reuseport_cb` 非空）；
- `sk_user_data` 未被占用（避免重复注册）。

### 用户态接口设计
- **Update 操作**：传入 fd，内核通过 `sockfd_lookup()` 获取 socket，并验证其有效性。
- **Lookup 操作**：返回 `__sock_gen_cookie(sk)`（唯一 socket 标识），而非内核地址，防止信息泄露。

### 内存布局
- 使用 `struct_size(array, ptrs, max_entries)` 动态分配连续内存，包含 map 元数据和指针数组。

## 4. 依赖关系

- **BPF 子系统**：  
  依赖 `bpf_map` 基础框架（`<linux/bpf.h>`），通过 `bpf_map_area_alloc/free` 管理内存。
- **网络子系统**：  
  - `SO_REUSEPORT` 机制（`<net/sock_reuseport.h>`）；  
  - socket 核心结构（`struct sock`）及其状态标志（`sk_hashed`, `sk_reuseport_cb`）；  
  - socket 生命周期管理（`sock_diag.h`）。
- **同步原语**：  
  依赖 RCU、自旋锁（`reuseport_lock`）和 BH 锁（`sk_callback_lock`）。
- **BTF 支持**：  
  通过 `BTF_ID` 宏导出类型信息（`<linux/btf_ids.h>`）。

## 5. 使用场景

1. **用户态负载均衡**：  
   应用程序创建多个 `SO_REUSEPORT` socket，通过 BPF map 注册到内核。BPF 程序（如 `BPF_SK_REUSEPORT_SELECT`）根据自定义策略（如一致性哈希）选择目标 socket，实现高效分发。

2. **服务热更新**：  
   新旧服务实例的 socket 可同时注册到 map，BPF 程序平滑切换流量，避免连接中断。

3. **安全隔离**：  
   通过 BPF 程序限制特定流量仅路由到指定 socket，增强服务安全性。

4. **性能监控**：  
   结合 BPF tracepoint，监控 reuseport socket 的选择分布，优化负载均衡策略。