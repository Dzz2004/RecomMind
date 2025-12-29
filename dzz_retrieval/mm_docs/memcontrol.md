# memcontrol.c

> 自动生成时间: 2025-12-07 16:39:41
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `memcontrol.c`

---

# memcontrol.c 技术文档

## 1. 文件概述

`memcontrol.c` 是 Linux 内核中内存控制组（Memory Cgroup, memcg）的核心实现文件，负责对进程组的内存资源进行隔离、限制、统计和回收。该文件实现了基于 cgroup v1 和 v2 的统一内存控制器，支持用户内存、内核内存、套接字内存以及 BPF 内存等多种内存类型的细粒度管理，并集成了内存压力通知（vmpressure）、OOM 控制、页面回收等关键机制。

## 2. 核心功能

### 主要全局变量
- `memory_cgrp_subsys`：cgroup 子系统实例，注册为内存控制器。
- `root_mem_cgroup`：根内存控制组，所有未显式归属的内存默认计入此组。
- `int_active_memcg`（per-CPU）：中断上下文中使用的活跃 memcg 指针。
- `cgroup_memory_nosocket` / `cgroup_memory_nokmem` / `cgroup_memory_nobpf`：控制是否启用套接字、内核内存、BPF 内存的会计功能。
- `memcg_kmem_online_key` / `memcg_bpf_enabled_key`：静态分支键，用于优化内存会计路径。

### 关键数据结构
- `struct mem_cgroup`：内存控制组的核心结构，包含内存计数器、LRU 链表、压力监控、OOM 状态等。
- `struct obj_cgroup`：用于内核对象（如 slab）内存会计的辅助结构，通过引用计数管理生命周期。

### 主要函数
- `mem_cgroup_css_from_folio()`：根据 folio 获取其所属 memcg 的 cgroup_subsys_state（css）。
- `page_cgroup_ino()`：获取页面所归属 memcg 的 cgroup inode 编号（用于 procfs 等接口）。
- `obj_cgroup_release()`：当 obj_cgroup 引用计数归零时释放剩余未清账的内存页。
- `obj_cgroup_alloc()`：分配并初始化一个新的 obj_cgroup 实例。
- `memcg_reparent_objcgs()`：在 memcg 被销毁时，将其关联的 obj_cgroup 重新归属到父 memcg。
- `mem_cgroup_kmem_disabled()`：查询内核内存会计是否被禁用。
- `memcg_to_vmpressure()` / `vmpressure_to_memcg()`：在 memcg 与 vmpressure 结构之间相互转换。

## 3. 关键实现

### 内存会计模型
- **统一层级模型**：支持 cgroup v2 的统一层级（unified hierarchy），同时兼容 v1 的多层级模式。
- **锁无关页面跟踪**：通过 per-CPU stock 机制减少高频内存分配/释放路径上的锁竞争。
- **对象级内存会计**：使用 `obj_cgroup` 对 slab 等内核对象进行精确计费，支持延迟清账（deferred uncharge）。

### 生命周期管理
- `obj_cgroup` 使用 `percpu_ref` 引用计数机制，确保在所有 CPU 上的操作完成后再释放资源。
- 在 memcg 销毁时，通过 `memcg_reparent_objcgs()` 将未释放的 obj_cgroup 安全迁移至父 memcg，避免内存泄漏。

### 中断上下文支持
- 通过 `int_active_memcg` per-CPU 变量，在中断或软中断上下文中临时绑定当前 memcg，使得网络、块设备等子系统可在中断中正确进行内存会计。

### 内存压力监控
- 每个 memcg 内嵌 `struct vmpressure`，用于检测内存压力等级（low/medium/critical），触发用户态通知或后台回收。

### 安全与健壮性
- `page_cgroup_ino()` 明确标注为“racy”，仅适用于不要求强一致性的只读接口（如 `/proc/pid/smaps`）。
- 在 `obj_cgroup_release()` 中校验 `nr_charged_bytes` 是否对齐 PAGE_SIZE，防止非整页残留导致会计错误。

## 4. 依赖关系

### 头文件依赖
- **核心内存管理**：`<linux/mm.h>`, `<linux/page_counter.h>`, `<linux/vmpressure.h>`, `<linux/swap.h>`
- **cgroup 基础设施**：`<linux/cgroup.h>`, `"internal.h"`
- **slab 分配器**：`"slab.h"`, `"memcontrol-v1.h"`
- **网络子系统**：`<net/sock.h>`（用于 socket 内存会计）
- **追踪与调试**：`<trace/events/vmscan.h>`, `<linux/kmemleak.h>`

### 功能依赖
- **页面回收**：与 vmscan 子系统紧密集成，参与 LRU 链表管理和直接/后台回收。
- **OOM Killer**：提供 memcg 级别的 OOM 判定和 victim 选择支持。
- **PSI（Pressure Stall Information）**：与 psi 子系统协作提供资源压力指标。
- **Writeback 控制**：通过 `CONFIG_CGROUP_WRITEBACK` 支持脏页回写带宽限制。
- **Zswap 与交换**：与 zswap、swap_cgroup 协同管理压缩交换内存。

## 5. 使用场景

- **容器资源隔离**：Docker、Kubernetes 等容器运行时通过 memcg 限制单个容器的内存使用上限。
- **多租户系统**：云平台利用 memcg 防止单个租户耗尽系统内存。
- **内核内存防护**：通过 `memory.kmem.limit_in_bytes` 限制 slab 等内核内存，防止内核内存耗尽（KMEM accounting）。
- **内存压力响应**：应用程序监听 memory.pressure 接口，在内存紧张时主动释放缓存。
- **性能分析**：通过 `/sys/fs/cgroup/memory/.../memory.stat` 等接口监控各 memcg 的内存分布和回收行为。
- **OOM 管理**：当 memcg 超限时触发局部 OOM，仅杀死该组内进程，不影响系统其他部分。