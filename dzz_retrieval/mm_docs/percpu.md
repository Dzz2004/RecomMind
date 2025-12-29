# percpu.c

> 自动生成时间: 2025-12-07 17:11:13
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `percpu.c`

---

# percpu.c 技术文档

## 1. 文件概述

`percpu.c` 是 Linux 内核中实现每 CPU（per-CPU）内存分配器的核心文件。该分配器用于管理静态和动态的 per-CPU 内存区域，支持在多处理器系统中为每个 CPU 分配独立但布局一致的内存块。其设计兼顾了 NUMA 架构下的性能优化、内存控制组（memcg）感知能力以及对原子上下文分配的支持。该分配器通过“块（chunk）-单元（unit）”模型组织内存，并特别处理包含内核静态 per-CPU 变量的首个内存块。

## 2. 核心功能

### 主要数据结构
- `struct pcpu_chunk`：表示一个 per-CPU 内存块，包含多个单元（每个 CPU 一个），管理分配位图、空闲信息等。
- `pcpu_chunk_lists`：按最大连续空闲区域大小分槽（slot）组织的块链表数组，用于快速查找合适大小的空闲块。
- `pcpu_first_chunk`：指向包含内核静态 per-CPU 变量的首个特殊内存块。
- `pcpu_reserved_chunk`：可选的保留内存块，用于服务特定保留区域的分配（如内核模块的静态 per-CPU 变量）。

### 关键全局变量
- `pcpu_base_addr`：per-CPU 区域的基地址，用于地址与 per-CPU 指针之间的转换。
- `pcpu_unit_map` / `pcpu_unit_offsets`：CPU 到其对应内存单元的映射及偏移。
- `pcpu_nr_groups` / `pcpu_group_offsets` / `pcpu_group_sizes`：基于 NUMA 节点分组的信息，用于虚拟内存分配。
- `pcpu_lock`：保护所有内部数据结构的自旋锁。
- `pcpu_alloc_mutex`：保护块创建/销毁、填充/释放等重型操作的互斥锁。

### 核心机制
- **地址转换宏**：`__addr_to_pcpu_ptr()` 和 `__pcpu_ptr_to_addr()`，用于普通虚拟地址与 per-CPU 指针之间的相互转换。
- **异步平衡工作**：`pcpu_balance_workfn()` 工作队列函数，用于异步地填充或释放内存页以维持空闲页数量在合理范围（`PCPU_EMPTY_POP_PAGES_LOW/HIGH`）。
- **内存槽管理**：使用位图（bitmap）跟踪块内分配状态，通过分槽（slot）机制加速分配查找。

## 3. 关键实现

### 内存组织模型
- **Chunk-Unit 模型**：内存被划分为多个 Chunk，每个 Chunk 包含 `pcpu_nr_units` 个 Unit（通常每个可能的 CPU 对应一个 Unit）。所有 Unit 在各自 Chunk 内具有相同的内存布局。
- **首个 Chunk 特殊处理**：首个 Chunk 的布局为 `<Static | [Reserved] | Dynamic>`。静态部分包含编译时确定的内核 per-CPU 变量；保留部分（可选）用于内核模块；动态部分用于运行时分配。
- **NUMA 感知**：Units 根据底层机器的 NUMA 属性进行分组，以优化内存访问局部性。

### 分配策略
- **分槽（Slot）管理**：空闲 Chunk 按其最大连续空闲区域大小放入不同 Slot。分配时优先从最满（即最大空闲区域最小但足够）的 Chunk 开始尝试，以提高内存利用率。
- **位图管理**：每个 Chunk 使用两个位图：
  - **分配位图（alloc map）**：记录每个最小分配单元（`PCPU_MIN_ALLOC_SIZE`）的占用状态，在每次分配/释放时更新。
  - **边界位图（boundary map）**：仅在分配时更新，用于快速合并相邻空闲块。
- **Memcg 感知**：通过 `__GFP_ACCOUNT` 标志区分是否为内存控制组感知的分配。Memcg 感知分配和非感知（或 root cgroup）分配使用两套独立的 Chunk 集合。

### 内存管理与优化
- **惰性填充（Lazy Population）**：Chunk 的物理页按需填充，且同一 Chunk 的所有 Unit 同步增长。
- **异步平衡**：当原子分配失败或空闲页数量超出阈值时，调度 `pcpu_balance_work` 工作项，异步地填充新页或释放完全空闲的页，避免在关键路径上执行耗时操作。
- **页到 Chunk 的反向映射**：利用 `struct page` 的 `index` 字段存储指向所属 Chunk 的指针，便于快速定位。

### 地址转换
- 在 SMP 系统中，per-CPU 指针是相对于 `__per_cpu_start` 的偏移量。通过 `pcpu_base_addr` 进行重定位，实现从 per-CPU 指针到实际虚拟地址的转换。
- 在 UP（单处理器）系统中，per-CPU 指针直接等同于虚拟地址。

## 4. 依赖关系

- **架构相关代码**：依赖 `asm/percpu.h` 提供的 `__addr_to_pcpu_ptr` 和 `__pcpu_ptr_to_addr` 宏（若架构有特殊需求），以及 `asm/cacheflush.h`、`asm/tlbflush.h` 进行缓存和 TLB 管理。
- **内存管理子系统**：重度依赖 `mm.h`、`vmalloc.h`、`memblock.h` 进行底层内存分配和管理。
- **调度与同步**：使用 `spinlock.h`、`mutex.h`、`workqueue.h` 实现并发控制和异步操作。
- **其他核心子系统**：
  - `cpumask.h`：处理 CPU 掩码和在线 CPU 信息。
  - `memcontrol.h`：集成内存控制组（cgroup）功能。
  - `kmemleak.h`：支持内存泄漏检测。
  - `trace/events/percpu.h`：提供跟踪点用于调试和性能分析。
- **内部头文件**：包含 `percpu-internal.h`，定义了分配器内部使用的数据结构和辅助函数。

## 5. 使用场景

- **内核初始化**：在系统启动早期，通过 `pcpu_setup_first_chunk()` 初始化首个 Chunk，将链接器生成的静态 per-CPU 变量（位于 `__per_cpu_start` 到 `__per_cpu_end`）映射到 per-CPU 内存区域。
- **内核模块加载**：为内核模块中的静态 per-CPU 变量分配空间（通常使用保留区域或动态分配）。
- **运行时动态分配**：内核代码通过 `alloc_percpu()`、`__alloc_percpu()` 等 API 在运行时申请 per-CPU 内存，用于存储每个 CPU 独立的数据结构（如统计计数器、缓冲区等）。
- **高性能路径**：由于 per-CPU 内存访问无需加锁，常用于中断处理、软中断、RCU 回调等对性能敏感的上下文中。
- **内存资源控制**：当进程属于非 root 内存 cgroup 且分配请求带有 `__GFP_ACCOUNT` 标志时，分配的 per-CPU 内存会计入该 cgroup 的内存使用量。