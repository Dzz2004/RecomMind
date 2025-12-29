# bpf\percpu_freelist.c

> 自动生成时间: 2025-10-25 12:23:09
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\percpu_freelist.c`

---

# `bpf/percpu_freelist.c` 技术文档

## 1. 文件概述

`percpu_freelist.c` 实现了一个高性能、可被中断上下文（包括 NMI）安全访问的每 CPU（per-CPU）无锁自由链表（freelist）数据结构。该结构主要用于 BPF 子系统中，为需要在高并发、低延迟场景下频繁分配/释放小对象的组件（如 BPF map）提供内存管理支持。其设计目标是在常规上下文中优先使用本地 CPU 的链表以避免跨 CPU 争用，同时在中断（尤其是 NMI）上下文中通过尝试锁和备用链表保证操作的可行性。

## 2. 核心功能

### 主要数据结构
- `struct pcpu_freelist`：全局自由链表控制结构，包含：
  - `freelist`：指向 per-CPU 的 `pcpu_freelist_head` 数组
  - `extralist`：全局备用链表（带自旋锁），用于在无法访问 per-CPU 链表时（如 NMI）暂存节点
- `struct pcpu_freelist_head`：每个 CPU 对应的链表头，包含：
  - `lock`：原始自旋锁（`raw_spinlock_t`），用于保护链表操作
  - `first`：指向链表第一个节点的指针
- `struct pcpu_freelist_node`：链表节点结构（定义在头文件中），仅包含 `next` 指针

### 主要函数
- **初始化/销毁**：
  - `pcpu_freelist_init()`：分配 per-CPU 链表头并初始化锁
  - `pcpu_freelist_destroy()`：释放 per-CPU 链表内存
- **填充链表**：
  - `pcpu_freelist_populate()`：将预分配的内存块按元素均匀分配到各 CPU 链表
- **入队操作**：
  - `pcpu_freelist_push()`：带中断保护的公共入队接口
  - `__pcpu_freelist_push()`：内部入队入口，根据上下文选择实现
  - `___pcpu_freelist_push()`：常规上下文入队（加锁）
  - `___pcpu_freelist_push_nmi()`：NMI 上下文入队（尝试锁 + 备用链表）
- **出队操作**：
  - `pcpu_freelist_pop()`：带中断保护的公共出队接口
  - `__pcpu_freelist_pop()`：内部出队入口，根据上下文选择实现
  - `___pcpu_freelist_pop()`：常规上下文出队（加锁）
  - `___pcpu_freelist_pop_nmi()`：NMI 上下文出队（尝试锁 + 备用链表）

## 3. 关键实现

### 上下文感知操作
- 通过 `in_nmi()` 检测当前是否处于 NMI 上下文：
  - **常规上下文**：直接操作当前 CPU 的链表（`this_cpu_ptr`），使用阻塞式自旋锁
  - **NMI 上下文**：遍历所有 CPU 尝试获取链表锁（`raw_spin_trylock`），失败则使用全局 `extralist`

### 无锁读优化
- 使用 `READ_ONCE()`/`WRITE_ONCE()` 确保对 `first` 指针的原子访问，避免编译器优化导致的竞态

### 负载均衡填充
- `pcpu_freelist_populate()` 将元素均匀分配到各 CPU 链表：
  - 基础数量 = `总元素数 / CPU数`
  - 前 `余数` 个 CPU 额外分配 1 个元素
- 填充时无需加锁（因结构尚未对外可见）

### 备用链表机制
- `extralist` 作为全局后备存储：
  - 当 NMI 上下文无法获取任何 per-CPU 锁时，尝试推入 `extralist`
  - 出队时若 per-CPU 链表为空，则尝试从 `extralist` 获取

### 中断保护
- 公共接口 `pcpu_freelist_push/pop` 通过 `local_irq_save/restore` 禁用本地中断，确保操作原子性

## 4. 依赖关系

- **头文件依赖**：
  - `percpu_freelist.h`：定义核心数据结构和函数声明
- **内核子系统依赖**：
  - **Per-CPU 内存管理**：使用 `alloc_percpu`/`free_percpu` 和 `per_cpu_ptr`
  - **SMP 支持**：依赖 `raw_smp_processor_id()` 和 CPU 掩码操作
  - **中断管理**：使用 `local_irq_save/restore` 和 `in_nmi()`
  - **内存屏障**：隐式依赖 `READ_ONCE`/`WRITE_ONCE` 的内存序语义
- **主要使用者**：
  - BPF 子系统（特别是 `bpf_map` 实现如 `arraymap`、`hashtab` 等）
  - 其他需要 NMI 安全内存池的内核组件

## 5. 使用场景

- **BPF Map 内存池**：为 BPF map 的键值对存储提供快速分配/释放能力，尤其在 tracepoint/kprobe 等 NMI 可能触发的场景中保证可靠性
- **高并发无锁分配**：在常规上下文中通过 per-CPU 链表实现近乎无锁的分配性能
- **中断安全内存管理**：在 hardirq、softirq、NMI 等不可睡眠上下文中安全回收/分配内存节点
- **预分配内存管理**：配合 `pcpu_freelist_populate` 实现批量预分配，避免运行时内存分配开销