# vmscan.c

> 自动生成时间: 2025-12-07 17:33:46
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `vmscan.c`

---

# vmscan.c 技术文档

## 1. 文件概述

`vmscan.c` 是 Linux 内核内存管理子系统中的核心文件，主要负责**页面回收（page reclaim）**机制的实现。该文件实现了内核在内存压力下如何选择并释放不再活跃或可回收的物理页帧（pages），以维持系统可用内存水位。其核心功能包括：

- 实现 `kswapd` 内核线程，用于后台异步回收内存
- 提供直接回收（direct reclaim）路径，供分配器在内存不足时同步触发
- 管理匿名页（anonymous pages）和文件缓存页（file-backed pages）的回收策略
- 支持基于内存控制组（memcg）的层级化内存回收
- 与交换（swap）、压缩（compaction）、OOM killer 等子系统协同工作

## 2. 核心功能

### 主要数据结构

- **`struct scan_control`**  
  页面回收上下文控制结构，包含本次回收操作的所有参数和状态：
  - `nr_to_reclaim`：目标回收页数
  - `target_mem_cgroup`：目标内存 cgroup（用于 memcg 回收）
  - `may_unmap` / `may_swap` / `may_writepage`：控制是否允许解除映射、交换、写回
  - `priority`：扫描优先级（0~12，值越低压力越大）
  - `order`：请求分配的阶数（影响回收激进程度）
  - `nr_scanned` / `nr_reclaimed`：已扫描和已回收页数统计
  - `anon_cost` / `file_cost`：用于平衡匿名页与文件页回收比例

- **全局变量**
  - `vm_swappiness`（默认 60）：控制系统倾向于回收匿名页（需 swap）还是文件页（可丢弃）

### 主要函数（部分在代码片段中体现）

- `cgroup_reclaim()` / `root_reclaim()`：判断当前回收是否针对特定 memcg 或全局
- `writeback_throttling_sane()`：判断是否可使用标准脏页限流机制
- `set_task_reclaim_state()` / `flush_reclaim_state()`：管理任务的 slab 回收状态
- （注：核心回收函数如 `shrink_lruvec()`、`kswapd()` 等未在片段中展示）

## 3. 关键实现

### 内存回收控制逻辑

- **回收目标决策**：通过 `scan_control` 结构传递回收上下文，区分直接回收（分配失败触发）与 kswapd 后台回收。
- **LRU 链管理**：利用 `prefetchw_prev_lru_folio` 宏优化 LRU 链遍历时的 CPU 缓存预取性能。
- **Memcg 集成**：
  - 若 `target_mem_cgroup` 非空，则优先回收该 cgroup 的内存
  - 支持 `memory.low` 保护机制：当常规回收无法满足需求且跳过受保护 cgroup 时，会触发二次强制回收（`memcg_low_reclaim`）
- **脏页处理策略**：
  - 在传统 memcg 模式下，禁用标准 `balance_dirty_pages()` 限流，改用直接阻塞回收（`writeback_throttling_sane()` 判断）
  - 通过 `may_writepage` 控制是否在 laptop mode 下批量写回脏页

### 回收统计与状态同步

- **Slab 回收计数**：通过 `reclaim_state` 结构将非 LRU 回收（如 slab 释放）计入全局统计，但**仅在全局回收时计入**，避免 memcg 回收时高估实际效果导致欠回收。
- **PSI/Trace 集成**：包含 `<trace/events/vmscan.h>` 用于性能分析，支持压力状态指示器（PSI）监控内存压力。

## 4. 依赖关系

### 头文件依赖

- **核心内存管理**：`<linux/mm.h>`, `<linux/gfp.h>`, `<linux/swap.h>`, `<linux/vmstat.h>`
- **LRU 与反向映射**：`<linux/rmap.h>`, `<linux/pagemap.h>`
- **内存控制组**：`<linux/memcontrol.h>`
- **IO 与写回**：`<linux/writeback.h>`, `<linux/backing-dev.h>`
- **压缩与迁移**：`<linux/compaction.h>`, `<linux/migrate.h>`
- **体系结构相关**：`<asm/tlbflush.h>`

### 子系统交互

- **Swap 子系统**：通过 `swapops.h` 和 `swap.h` 实现匿名页换出
- **Slab 分配器**：通过 `reclaim_state` 接收 slab 回收通知
- **OOM Killer**：当回收无法释放足够内存时触发
- **Khugepaged**：大页合并/拆分与回收协同
- **Memory Tiering**：支持分层内存架构中的页降级（demotion）控制

## 5. 使用场景

- **内存分配失败时的直接回收**：当 `alloc_pages()` 等分配函数无法满足请求时，同步调用回收路径。
- **kswapd 后台回收**：当空闲内存低于 `watermark[low]` 时，唤醒 `kswapd` 线程异步回收至 `watermark[high]`。
- **Memcg 内存超限时的层级回收**：当某个 cgroup 超过其内存限制时，仅回收该 cgroup 及其子树的页面。
- **系统休眠（Hibernation）**：通过 `hibernation_mode` 标志优化休眠过程中的内存回收。
- **主动内存回收（Proactive Reclaim）**：用户空间通过 `memory.reclaim` 接口触发预清回收。
- **内存压缩准备**：当 `compaction_ready` 置位时，回收操作会为后续内存压缩腾出连续空间。