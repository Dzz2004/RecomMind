# damon\ops-common.c

> 自动生成时间: 2025-12-07 15:48:50
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `damon\ops-common.c`

---

# `damon/ops-common.c` 技术文档

## 1. 文件概述

`damon/ops-common.c` 是 Linux 内核中 **DAMON（Data Access MONitor）** 子系统的一部分，提供与底层内存访问监控相关的通用操作原语。该文件实现了用于获取页面信息、标记页面为“旧”（即非活跃）、以及基于访问频率和区域年龄计算内存区域“热度”或“冷度”评分的核心函数，为 DAMON 的策略决策（如 DAMOS：DAMON-based Operation Schemes）提供基础支持。

## 2. 核心功能

### 主要函数：

- **`damon_get_folio(unsigned long pfn)`**  
  根据物理页帧号（PFN）安全地获取对应的在线 `struct folio` 对象，前提是该 folio 在 LRU 链表中且可成功增加引用计数。

- **`damon_ptep_mkold(pte_t *pte, struct vm_area_struct *vma, unsigned long addr)`**  
  将指定 PTE（页表项）所映射的页面标记为“旧”（idle），并清除其年轻（young）状态（如有），适用于普通 4KB 页面。

- **`damon_pmdp_mkold(pmd_t *pmd, struct vm_area_struct *vma, unsigned long addr)`**  
  功能同上，但作用于 PMD（页中间目录）项，用于透明大页（Transparent Huge Page, THP），仅在 `CONFIG_TRANSPARENT_HUGEPAGE` 启用时有效。

- **`damon_hot_score(struct damon_ctx *c, struct damon_region *r, struct damos *s)`**  
  基于区域的访问次数（`nr_accesses`）和年龄（`age`），结合策略权重，计算该区域的“热度”评分（范围 `[0, DAMOS_MAX_SCORE]`）。

- **`damon_cold_score(struct damon_ctx *c, struct damon_region *r, struct damos *s)`**  
  返回区域的“冷度”评分，即 `DAMOS_MAX_SCORE - 热度评分`。

### 关键宏定义：

- `DAMON_MAX_SUBSCORE`：子评分最大值（100），用于归一化。
- `DAMON_MAX_AGE_IN_LOG`：年龄对数尺度的最大值（32），用于将线性年龄转换为对数尺度。

## 3. 关键实现

### 页面获取 (`damon_get_folio`)
- 调用 `pfn_to_online_page()` 获取对应 PFN 的 `struct page`。
- 排除尾页（`PageTail`）以确保只处理 folio 头页。
- 检查 folio 是否在 LRU 链表中（`folio_test_lru`）并尝试增加引用计数（`folio_try_get`）。
- 进行二次验证以防止并发修改导致状态不一致，若验证失败则释放引用并返回 `NULL`。

### 页面标记为“旧” (`damon_*_mkold`)
- 通过 `damon_get_folio` 安全获取 folio。
- 调用 `ptep_clear_young_notify` / `pmdp_clear_young_notify` 清除硬件/软件的“young”位，并通知 MMU notifier。
- 若页面曾被访问（young 位被置位），则调用 `folio_set_young` 更新 folio 的软件状态。
- 最终调用 `folio_set_idle` 显式标记该 folio 为 idle（未被近期访问）。
- 函数结束前释放 folio 引用。

### 热度评分算法 (`damon_hot_score`)
1. **频率子评分**：  
   将区域访问次数 `r->nr_accesses` 归一化到 `[0, 100]`，基于当前上下文的最大可能访问次数（由 `damon_max_nr_accesses()` 提供）。

2. **年龄子评分**：  
   - 将区域年龄（单位：聚合间隔次数）转换为秒数。
   - 使用对数尺度（右移计数）将年龄压缩到 `[0, 32]` 范围。
   - **关键逻辑**：若频率为 0（从未访问），则年龄越大表示越“冷”，因此将 `age_in_log` 取负值。
   - 将 `age_in_log` 平移到 `[0, 64]` 区间，再缩放到 `[0, 100]` 作为年龄子评分。

3. **加权平均与归一化**：  
   - 使用策略 `s->quota.weight_nr_accesses` 和 `s->quota.weight_age` 对两个子评分加权平均。
   - 最终将结果缩放到 DAMOS 评分范围 `[0, DAMOS_MAX_SCORE]`。

## 4. 依赖关系

- **内核头文件依赖**：
  - `<linux/mmu_notifier.h>`：用于 `*_clear_young_notify` 的 MMU 通知机制。
  - `<linux/page_idle.h>`：提供 `folio_set_idle()` 等页面空闲状态管理接口。
  - `<linux/pagemap.h>` 和 `<linux/rmap.h>`：提供页面到 folio 转换、LRU 状态检查等内存管理原语。
- **内部依赖**：
  - `"ops-common.h"`：声明本文件中实现的函数。
  - 依赖 DAMON 核心结构体：`struct damon_ctx`、`struct damon_region`、`struct damos`。
- **配置依赖**：
  - `damon_pmdp_mkold` 依赖 `CONFIG_TRANSPARENT_HUGEPAGE`。

## 5. 使用场景

- **DAMON 监控阶段**：在定期采样内存访问模式时，DAMON 需要将已监控的页面重置为“旧”状态，以便下次采样能检测到新的访问。`damon_ptep_mkold` 和 `damon_pmdp_mkold` 用于此目的。
- **DAMOS 策略执行**：当 DAMON 启用基于策略的操作（如内存回收、迁移、THP 降级等）时，需对内存区域进行热度排序。`damon_hot_score` 和 `damon_cold_score` 为 DAMOS 提供统一的评分机制，使策略可根据用户配置的权重（访问频率 vs. 年龄）动态评估区域价值。
- **内存优化工具链**：该文件是 `mm/damon/` 子系统的基础组件，服务于 `damon_reclaim`、`damon_lru_sort` 等高级内存管理特性。