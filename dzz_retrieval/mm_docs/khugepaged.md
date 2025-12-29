# khugepaged.c

> 自动生成时间: 2025-12-07 16:26:37
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `khugepaged.c`

---

# khugepaged.c 技术文档

## 1. 文件概述

`khugepaged.c` 是 Linux 内核中透明大页（Transparent Huge Page, THP）子系统的核心组件之一，负责在后台异步地将符合条件的小页（4KB）合并为大页（通常为 2MB 的 PMD 级别大页）。该文件实现了名为 `khugepaged` 的内核线程及其相关扫描、合并逻辑，旨在提升内存访问性能并减少 TLB 压力。通过周期性扫描进程地址空间，识别可合并区域，并尝试分配和填充大页，从而优化系统整体内存效率。

## 2. 核心功能

### 主要数据结构

- **`enum scan_result`**  
  定义了页面扫描过程中可能返回的各种结果状态码，用于控制合并流程的决策（如失败原因、成功条件等）。

- **`struct collapse_control`**  
  控制页面折叠（collapse）过程的上下文信息，包括是否由 `khugepaged` 发起、各 NUMA 节点的负载统计及分配回退掩码。

- **`struct khugepaged_mm_slot`**  
  表示正在被 `khugepaged` 扫描的每个 `mm_struct`（进程地址空间）的元数据槽位，继承自通用 `mm_slot` 结构。

- **`struct khugepaged_scan`**  
  全局扫描游标，记录当前扫描的 `mm` 列表头、当前 `mm_slot` 及下一次扫描的虚拟地址。

### 全局变量

- `khugepaged_thread`：指向后台 `khugepaged` 内核线程的 `task_struct`。
- `khugepaged_pages_to_scan`：每次扫描迭代处理的 PTE 或 VMA 数量。
- `khugepaged_scan_sleep_millisecs` / `khugepaged_alloc_sleep_millisecs`：控制扫描与内存分配的休眠间隔。
- `khugepaged_max_ptes_none/swap/shared`：限制在合并过程中允许存在的未映射、交换或共享 PTE 的最大数量。
- `mm_slots_hash`：哈希表，用于快速查找正在被扫描的 `mm_struct`。
- `khugepaged_scan`：全局唯一的扫描状态结构体。

### Sysfs 接口（CONFIG_SYSFS）

提供用户空间可配置参数：
- `scan_sleep_millisecs`：扫描间隔
- `alloc_sleep_millisecs`：分配失败后的重试间隔
- `pages_to_scan`：每次扫描的页数
- `pages_collapsed` / `full_scans`：只读统计信息
- `defrag`：是否启用内存碎片整理
- `max_ptes_none` / `max_ptes_swap`：控制合并容忍度

## 3. 关键实现

### 后台扫描机制
- 使用单一线程 `khugepaged` 循环遍历所有注册到 `mm_slots_hash` 中的进程地址空间。
- 每次从 `khugepaged_scan.mm_head` 列表中取出一个 `mm_slot`，按虚拟地址顺序扫描其 VMA 区域。
- 扫描粒度由 `khugepaged_pages_to_scan` 控制，默认为 4096 页（8×512），每轮扫描后休眠 `khugepaged_scan_sleep_millisecs` 毫秒。

### 大页合并条件
- 仅对支持透明大页的 VMA（如匿名私有映射）进行处理。
- 检查目标 2MB 区域内：
  - 已映射的小页数量足够多；
  - 未映射（none）、交换（swap）或共享（shared）的 PTE 数量不超过 `khugepaged_max_ptes_*` 阈值；
  - 所有页面满足可合并条件（如非 KSM、非 compound、已加入 LRU、引用计数合适等）。
- 若满足条件，则分配一个新大页，复制小页内容，并更新页表。

### 内存分配与回退策略
- 优先在本地 NUMA 节点分配大页。
- 若分配失败且启用了 `defrag`，则尝试内存压缩（compaction）。
- 支持基于 `alloc_nmask` 的跨节点分配回退。

### 并发与同步
- 使用 `khugepaged_mutex` 保护关键操作（如添加/移除 mm slot）。
- 通过 `mm_slot` 机制确保同一 `mm` 不被重复扫描。
- 利用 RCU 和页锁（`trylock_page()`）避免与用户态访问或其它内核路径冲突。

### 统计与追踪
- 更新 `khugepaged_pages_collapsed` 和 `khugepaged_full_scans` 等统计计数器。
- 集成 `trace/events/huge_memory.h` 提供详细的合并事件追踪点。

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`、`<linux/rmap.h>`、`<linux/swap.h>` 等，进行页表遍历、反向映射、页面迁移等操作。
- **透明大页框架**：与 `huge_memory.c` 协同工作，共享 THP 配置标志（如 `TRANSPARENT_HUGEPAGE_DEFRAG_KHUGEPAGED_FLAG`）。
- **KSM（Kernel Samepage Merging）**：检查页面是否已被 KSM 标记，避免合并 KSM 页面。
- **Userfaultfd**：检测 `UFFD_WP`（用户态写保护）标记，防止非法合并。
- **NUMA 与内存策略**：使用 `nodemask_t` 和 NUMA 感知分配。
- **内核线程与调度**：基于 `kthread` 框架实现后台任务，支持 freezer（挂起/恢复）。
- **Sysfs**：通过 sysfs 向用户空间暴露 tunable 参数（需 `CONFIG_SYSFS`）。

## 5. 使用场景

- **通用服务器负载**：在数据库、虚拟化、大数据处理等内存密集型应用中，自动提升 TLB 覆盖率，降低缺页开销。
- **延迟敏感型应用**：通过后台预合并，避免运行时同步分配大页导致的延迟毛刺。
- **内存碎片整理**：配合 `defrag` 选项，在内存紧张时主动整理碎片以促进大页分配。
- **动态调优**：管理员可通过 sysfs 实时调整扫描频率、合并激进程度等参数，平衡性能与内存开销。
- **NUMA 系统优化**：在多节点系统中，结合本地分配策略提升内存访问局部性。