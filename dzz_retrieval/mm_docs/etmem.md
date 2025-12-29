# etmem.c

> 自动生成时间: 2025-12-07 15:58:34
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `etmem.c`

---

# etmem.c 技术文档

## 1. 文件概述

`etmem.c` 是 Linux 内核中用于支持 **eBPF Transparent Memory (etmem)** 功能的核心模块之一，主要提供内核态页面交换（swap）的控制接口和辅助函数。该文件实现了对特定用户虚拟地址对应物理页的提取、隔离以及加入待交换页链表的功能，并通过 sysfs 接口允许用户空间动态启用或禁用内核交换行为。

## 2. 核心功能

### 全局变量
- `enable_kernel_swap`：一个只读频繁（`__read_mostly`）的布尔变量，控制是否允许内核执行页面交换操作，默认为 `true`。

### 导出函数
- `kernel_swap_enabled(void)`：返回当前内核交换功能是否启用。
- `add_page_for_swap(struct page *page, struct list_head *pagelist)`：尝试将指定页面从 LRU 链表中隔离并添加到待交换页链表中。
- `get_page_from_vaddr(struct mm_struct *mm, unsigned long vaddr)`：根据进程地址空间和虚拟地址获取对应的物理页结构体（`struct page`）。

### Sysfs 属性接口
- `kernel_swap_enable_attr`：通过 `/sys/.../kernel_swap_enable` 提供用户空间读写接口，用于动态控制 `enable_kernel_swap` 的值。

## 3. 关键实现

### 内核交换开关机制
- 使用 `READ_ONCE()` 和 `WRITE_ONCE()` 保证对 `enable_kernel_swap` 的原子访问，避免编译器优化导致的竞态问题。
- 提供 sysfs 的 show/store 回调函数，支持字符串 `"true"/"1"` 启用、`"false"/"0"` 禁用，其他输入返回 `-EINVAL`。

### 页面提取 (`get_page_from_vaddr`)
- 在 `mmap_read_lock` 保护下查找虚拟地址对应的 VMA。
- 拒绝处理 `VM_LOCKED`（锁定内存）的 VMA。
- 使用 `follow_page()` 配合 `FOLL_GET | FOLL_DUMP` 标志获取页面，并增加引用计数。
- 成功时返回带引用的 `struct page*`，失败返回 `NULL`。

### 页面隔离与入队 (`add_page_for_swap`)
- 检查页面映射计数（`page_mapcount > 1`）或多进程共享情况，若存在则拒绝交换（返回 `-EACCES`）。
- 不支持透明大页（`PageHuge`）交换。
- 调用 `folio_isolate_lru()` 尝试将页面从 LRU 链表中隔离：
  - 若失败，释放页面引用并返回 `-EBUSY`。
  - 若成功，进一步判断页面是否不可回收（`PageUnevictable`）：
    - 若是，则调用 `putback_lru_page()` 放回 LRU；
    - 否则，将页面头（`head->lru`）加入传入的 `pagelist` 链表尾部。
- 最终返回 0 表示成功。

## 4. 依赖关系

- **内存管理子系统**：依赖 `<linux/mm.h>`、`<linux/pagemap.h>`、`<linux/swap.h>` 等头文件，使用 `follow_page`、`page_mapcount`、`PageHuge`、`folio_isolate_lru` 等核心 MM 接口。
- **LRU 管理**：调用 `putback_lru_page` 和 `folio_isolate_lru` 与内核的页面回收机制紧密集成。
- **内存控制组（cgroup）**：包含 `<linux/memcontrol.h>`，可能用于后续扩展基于 cgroup 的交换策略。
- **Sysfs 子系统**：通过 `kobj_attribute` 和 `__ATTR` 宏注册可配置属性，依赖 `<linux/sysctl.h>`（尽管未直接使用 sysctl，但包含相关基础设施）。
- **内部头文件**：包含 `"internal.h"`，可能引用 mm 子系统的私有接口。

## 5. 使用场景

- **eBPF 驱动的内存优化工具（如 etmem）**：用户空间工具通过 eBPF 程序识别冷热内存区域后，调用此模块提供的接口将冷页主动加入交换队列，实现精细化内存回收。
- **动态调控内核交换行为**：系统管理员可通过写 `/sys/.../kernel_swap_enable` 临时关闭内核自动交换，配合用户态策略进行更可控的内存管理。
- **调试与性能分析**：在内存压力测试或交换策略研究中，可结合此接口精确控制哪些页面参与交换，便于实验验证。
- **容器或云环境中的内存 QoS**：结合 memcg，未来可扩展为按 cgroup 控制交换行为，提升多租户环境下的内存服务质量。