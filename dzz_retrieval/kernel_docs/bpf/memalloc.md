# bpf\memalloc.c

> 自动生成时间: 2025-10-25 12:19:22
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\memalloc.c`

---

# `bpf/memalloc.c` 技术文档

## 1. 文件概述

`bpf/memalloc.c` 实现了一个专用于 BPF（Berkeley Packet Filter）程序的内存分配器，支持在任意上下文（包括 NMI、中断、不可抢占上下文等）中安全地分配和释放小块内存。该分配器通过每 CPU 的多级缓存桶（per-CPU per-bucket free list）机制，避免在 BPF 程序执行路径中直接调用可能不安全的 `kmalloc()`。缓存桶的填充和回收由 `irq_work` 异步完成，确保主执行路径的低延迟和高可靠性。

## 2. 核心功能

### 主要数据结构

- **`struct bpf_mem_cache`**  
  每个缓存桶的核心结构，包含：
  - `free_llist` / `free_llist_extra`：无锁链表（llist），用于存储空闲对象。
  - `active`：本地原子计数器，用于保护对 `free_llist` 的并发访问。
  - `refill_work`：`irq_work` 结构，用于触发异步填充。
  - `objcg`：对象 cgroup 指针，用于内存记账。
  - `unit_size`：该缓存桶中对象的固定大小。
  - `free_cnt`、`low_watermark`、`high_watermark`、`batch`：缓存管理参数。
  - `percpu_size`：标识是否为 per-CPU 分配。
  - RCU 相关字段（`free_by_rcu`、`rcu` 等）：用于延迟释放内存，避免在不可睡眠上下文中调用 `kfree`。

- **`struct bpf_mem_caches`**  
  包含 `NUM_CACHES`（11 个）不同大小的 `bpf_mem_cache` 实例，对应预定义的内存块尺寸。

- **`sizes[NUM_CACHES]`**  
  定义了 11 种支持的分配尺寸：`{96, 192, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096}` 字节。

- **`size_index[24]`**  
  查找表，将请求大小（≤192 字节）映射到对应的缓存桶索引。

### 主要函数

- **`bpf_mem_cache_idx(size_t size)`**  
  根据请求大小返回对应的缓存桶索引（0~10），超出 `BPF_MEM_ALLOC_SIZE_MAX`（4096）则返回 -1。

- **`__alloc()`**  
  底层分配函数，根据是否为 per-CPU 类型调用 `kmalloc_node` 或 `__alloc_percpu_gfp`。

- **`add_obj_to_free_list()`**  
  将对象安全地加入当前 CPU 的空闲链表，使用 `active` 计数器保护。

- **`alloc_bulk()`**  
  批量分配对象并填充缓存桶，优先从延迟释放队列（如 `free_by_rcu_ttrace`）回收，再尝试从全局分配器分配。

- **`free_one()` / `free_all()`**  
  释放单个或多个对象，区分普通和 per-CPU 类型。

- **`__free_rcu()` / `__free_rcu_tasks_trace()`**  
  RCU 回调函数，用于在宽限期结束后真正释放内存。

- **`enque_to_free()` / `do_call_rcu_ttrace()`**  
  将待释放对象加入 RCU 延迟队列，并触发 RCU 宽限期。

## 3. 关键实现

### 内存布局与对齐
- 每个分配的对象末尾附加 8 字节的 `struct llist_node`，用于无锁链表管理。
- 所有分配均对齐至 8 字节边界。

### 并发控制
- 使用 `local_t active` 计数器保护对 `free_llist` 的访问。在分配/释放时，通过 `inc_active()`/`dec_active()` 禁用中断（尤其在 `CONFIG_PREEMPT_RT` 下），确保 NMI 或中断上下文不会破坏链表结构。
- `free_llist_extra` 用于在 `active` 忙时暂存释放对象，避免失败。

### 异步填充机制
- 当缓存桶水位低于 `low_watermark` 时，通过 `irq_work` 触发 `alloc_bulk()`。
- `alloc_bulk()` 优先从 RCU 延迟释放队列中回收对象，减少全局分配压力。
- 使用 `set_active_memcg()` 确保内存分配计入正确的 memcg。

### RCU 延迟释放
- 在不可睡眠上下文（如 NMI）中释放内存时，对象被加入 `free_by_rcu_ttrace` 队列。
- 通过 `call_rcu_tasks_trace()` 或 `call_rcu()` 触发宽限期，之后在软中断上下文中真正释放。
- 支持 `rcu_trace_implies_rcu_gp()` 优化，避免双重 RCU 调用。

### 尺寸映射策略
- 对 ≤192 字节的请求，使用 `size_index` 查找表快速定位桶。
- 对 >192 字节的请求，使用 `fls(size - 1) - 2` 计算桶索引，覆盖 256~4096 字节范围。

## 4. 依赖关系

- **内存管理**：依赖 `<linux/mm.h>`、`<linux/memcontrol.h>` 进行底层分配和 memcg 记账。
- **BPF 子系统**：通过 `<linux/bpf.h>` 和 `<linux/bpf_mem_alloc.h>` 与 BPF 运行时集成。
- **无锁数据结构**：使用 `<linux/llist.h>` 提供的无锁链表。
- **中断与延迟执行**：依赖 `<linux/irq_work.h>` 实现异步填充。
- **RCU 机制**：使用 RCU 和 RCU Tasks Trace 宽限期实现安全延迟释放。
- **架构相关**：使用 `<asm/local.h>` 的 per-CPU 原子操作。

## 5. 使用场景

- **BPF tracing 程序**：当 BPF 程序 attach 到 `kprobe`、`fentry` 等 hook 点时，可能运行在任意内核上下文（包括 NMI、中断、不可抢占区域）。此时标准 `kmalloc` 不安全，必须使用本分配器。
- **高可靠性内存分配**：在不允许睡眠、不能触发内存回收的上下文中，提供确定性的内存分配能力。
- **低延迟要求**：通过 per-CPU 缓存避免锁竞争和全局分配器开销，满足 BPF 程序对性能的严苛要求。
- **内存隔离与记账**：支持通过 `objcg` 将 BPF 内存消耗计入特定 cgroup，便于资源控制。