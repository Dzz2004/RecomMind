# bpf\cpumap.c

> 自动生成时间: 2025-10-25 12:06:36
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\cpumap.c`

---

# bpf/cpumap.c 技术文档

## 文件概述

`bpf/cpumap.c` 实现了 BPF CPU Map（cpumap）这一内核数据结构，主要用于 XDP（eXpress Data Path）框架中的跨 CPU 重定向功能。该机制允许 XDP 程序通过 `bpf_redirect_map()` 辅助函数将原始 XDP 数据帧重定向到指定的目标 CPU，由目标 CPU 上运行的专用内核线程（kthread）接收并将其转换为 `sk_buff` 后送入常规网络协议栈处理。cpumap 的核心目标是实现高性能、低延迟的网络预过滤，通过将 XDP 处理阶段与主网络栈解耦，提升系统在 10Gbps 及以上速率下的可扩展性和隔离性。

## 核心功能

### 主要数据结构

- **`struct bpf_cpu_map`**  
  表示整个 CPU Map 对象，继承自 `struct bpf_map`，包含一个指向 `bpf_cpu_map_entry` 指针数组的 `cpu_map` 成员，用于按 CPU ID 索引目标条目。

- **`struct bpf_cpu_map_entry`**  
  表示映射到单个目标 CPU 的条目，关键成员包括：
  - `cpu`：目标 CPU 编号
  - `queue`：`ptr_ring` 类型的无锁环形缓冲队列，用于暂存重定向的 XDP 帧
  - `kthread`：绑定到该 CPU 的消费者内核线程
  - `prog`：可选的附加 BPF 程序，在帧入队后、送入协议栈前执行二次处理
  - `bulkq`：每 CPU 的批量入队缓存（`xdp_bulk_queue`），用于提升入队性能

- **`struct xdp_bulk_queue`**  
  每 CPU 的批量队列结构，用于暂存最多 `CPU_MAP_BULK_SIZE`（默认 8）个待入队的 XDP 帧，减少对共享 `ptr_ring` 的频繁访问。

### 主要函数

- **`cpu_map_alloc()`**  
  分配并初始化一个新的 CPU Map 实例，校验属性合法性（如 key/value 大小、最大条目数不超过 `NR_CPUS`）。

- **`cpu_map_kthread_run()`**  
  目标 CPU 上运行的消费者内核线程主循环，从 `ptr_ring` 队列批量消费 XDP 帧，执行可选 BPF 程序，并将结果帧转换为 `sk_buff` 送入网络栈。

- **`cpu_map_bpf_prog_run_xdp()`**  
  在消费线程中执行附加的 XDP 类型 BPF 程序，支持 `XDP_PASS`、`XDP_REDIRECT`、`XDP_DROP` 等动作。

- **`cpu_map_bpf_prog_run_skb()`**  
  处理已转换为 `sk_buff` 的数据包（通常来自重定向失败或特殊路径），执行通用 XDP BPF 程序。

- **`__cpu_map_ring_cleanup()`**  
  安全清理 `ptr_ring` 队列中的残留帧，确保资源正确释放。

## 关键实现

### 无锁批量入队与消费

- **生产者侧（XDP 程序）**：使用每 CPU 的 `xdp_bulk_queue` 缓存待入队帧。当缓存满或需要 flush 时，一次性将批量帧原子地推入目标 CPU 条目的 `ptr_ring` 队列，减少锁竞争。
- **消费者侧（kthread）**：每个 `bpf_cpu_map_entry` 绑定一个专用 kthread，独占消费其 `ptr_ring`。通过 `__ptr_ring_consume_batched()` 批量获取帧，提升吞吐。

### 跨 CPU 重定向流程

1. XDP 程序调用 `bpf_redirect_map(map, cpu_id, 0)`。
2. 内核将当前 XDP 帧暂存到当前 CPU 对应目标 `cpu_id` 的 `bulkq` 中。
3. 在驱动 `->poll()` 结束或显式 flush 时，将 `bulkq` 中的帧批量推入目标 CPU 的 `ptr_ring`。
4. 目标 CPU 的 kthread 被唤醒，消费帧，执行可选 BPF 程序，转换为 `sk_buff` 并调用 `netif_receive_skb_list()` 送入协议栈。

### BPF 程序二次处理

每个 `bpf_cpu_map_entry` 可关联一个 BPF 程序。消费线程在处理帧前会执行该程序，支持进一步过滤、修改或重定向（如再次重定向到设备或另一个 CPU），增强了灵活性。

### 内存与资源管理

- 使用 `__ptr_set_bit(0, &ptr)` 标记 `sk_buff` 指针（最低位为 1），普通 XDP 帧指针最低位为 0，便于在清理时区分类型。
- kthread 在退出前确保队列为空，防止内存泄漏。
- 通过 RCU 机制安全地更新和释放 map 条目。

## 依赖关系

- **BPF 子系统**：依赖 `bpf.h`、`filter.h` 提供 map 基础框架、BPF 程序执行接口。
- **XDP 框架**：依赖 `xdp.h`、`xdp_frame` 结构及 `xdp_do_redirect()` 等重定向机制。
- **网络核心**：使用 `netdevice.h` 的 `netif_receive_skb_list()` 将数据包送入协议栈。
- **内核同步原语**：使用 `ptr_ring`（无锁环形缓冲区）、`completion`（线程启动同步）、`rcu_work`（延迟释放）。
- **调度与线程**：依赖 `kthread` 创建 CPU 绑定的消费者线程。
- **追踪**：集成 `trace/events/xdp.h` 提供 XDP 事件追踪。

## 使用场景

- **高性能网络预过滤**：在专用 CPU 上运行 XDP 程序进行 DDoS 防御、ACL 过滤等，将合法流量重定向到其他 CPU 的协议栈处理，避免主 CPU 过载。
- **负载均衡**：将流量按策略分发到多个 CPU，提升多核系统的网络处理能力。
- **服务链（Service Chaining）**：通过级联 cpumap 和 devmap，构建复杂的流量处理流水线。
- **隔离关键路径**：将 XDP 处理与应用层网络处理隔离到不同 CPU，减少相互干扰，保障低延迟。