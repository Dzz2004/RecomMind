# folio-compat.c

> 自动生成时间: 2025-12-07 16:01:42
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `folio-compat.c`

---

# folio-compat.c 技术文档

## 1. 文件概述

`folio-compat.c` 是 Linux 内核中用于提供 **页（page）与 folio 兼容层** 的实现文件。该文件定义了一系列围绕传统 `struct page` 接口的包装函数，内部实际调用基于 `struct folio` 的新式接口。其目的是在内核逐步迁移到 folio 抽象的过程中，保持对现有 page-based API 的兼容性，避免大规模修改调用者代码。所有使用这些函数的调用点最终应被重构为直接使用 folio 接口。

## 2. 核心功能

### 主要导出函数列表：

| 函数名 | 功能说明 |
|--------|--------|
| `page_mapping()` | 获取 page 所属的 address_space（通过 folio 映射） |
| `unlock_page()` | 解锁 page（委托给 folio_unlock） |
| `end_page_writeback()` | 结束 page 的写回状态 |
| `wait_on_page_writeback()` | 等待 page 写回完成 |
| `wait_for_stable_page()` | 等待 page 稳定（如等待写入设备完成） |
| `mark_page_accessed()` | 标记 page 为已访问（用于 LRU 管理） |
| `set_page_writeback()` | 设置 page 为正在写回状态 |
| `set_page_dirty()` | 标记 page 为脏页 |
| `__set_page_dirty_nobuffers()` | 在无 buffer_heads 情况下标记 page 为脏 |
| `clear_page_dirty_for_io()` | 为 I/O 清除 page 的脏标记 |
| `redirty_page_for_writepage()` | 在写回失败时重新标记 page 为脏 |
| `add_to_page_cache_lru()` | 将 page 添加到页缓存并加入 LRU |
| `pagecache_get_page()` | 从页缓存中获取指定索引的 page |
| `grab_cache_page_write_begin()` | 为写操作准备获取页缓存中的 page |
| `isolate_lru_page()` | 从 LRU 链表中隔离 page（仅支持 head page） |
| `putback_lru_page()` | 将隔离的 page 放回 LRU 链表 |

> 注：所有函数均通过 `page_folio(page)` 将 `struct page *` 转换为 `struct folio *`，再调用对应的 folio 接口。

## 3. 关键实现

- **Page 到 Folio 的转换**：  
  所有函数均使用 `page_folio(page)` 宏将传入的 `struct page *` 转换为所属的 `struct folio *`。该宏能正确处理复合页（compound page），返回其 head page 对应的 folio。

- **尾页（Tail Page）保护**：  
  在 `isolate_lru_page()` 中显式检查是否为 tail page（`PageTail(page)`），若是则发出警告并拒绝操作。因为 LRU 操作只能作用于 head page（即 folio 本身）。

- **非内联设计**：  
  文件注释明确指出，这些函数“bloat the callers too much to make inline”（若内联会导致调用者代码膨胀过大），因此以普通函数形式实现并导出符号。

- **页缓存获取逻辑**：  
  `pagecache_get_page()` 调用 `__filemap_get_folio()` 获取 folio，成功后通过 `folio_file_page(folio, index)` 返回对应偏移的 `struct page *`（支持大 folio 包含多个 page 的情况）。

- **写回与脏页管理**：  
  脏页和写回相关操作（如 `set_page_dirty`, `clear_page_dirty_for_io` 等）全部委托给 folio 层的等效函数，确保状态一致性维护在 folio 粒度。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/migrate.h>`：页面迁移相关（间接依赖）
  - `<linux/pagemap.h>`：页缓存核心接口
  - `<linux/rmap.h>`：反向映射（可能被 folio 函数间接使用）
  - `<linux/swap.h>`：交换子系统（folio 实现可能涉及）
  - `"internal.h"`：内核内存管理内部头文件，包含 folio 相关定义

- **模块依赖**：
  - **Folio 子系统**：所有实现依赖于 `mm/folio.c`、`mm/filemap.c` 等提供的 folio 基础操作。
  - **页缓存（Page Cache）**：`add_to_page_cache_lru`、`pagecache_get_page` 等依赖地址空间（address_space）和页缓存机制。
  - **LRU 管理**：`isolate_lru_page` 和 `putback_lru_page` 依赖内存回收子系统的 LRU 链表操作。
  - **写回（Writeback）子系统**：脏页标记、写回等待等与 `writeback_control` 和 bdi 机制紧密耦合。

## 5. 使用场景

- **文件系统层**：  
  文件系统（如 ext4、XFS）在读写页缓存时仍大量使用 `struct page *` 接口，通过本文件提供的兼容函数间接操作 folio。

- **块设备与 I/O 层**：  
  在提交 I/O 前调用 `clear_page_dirty_for_io`，I/O 完成后调用 `end_page_writeback`，这些路径通过兼容层过渡到 folio。

- **内存管理子系统**：  
  页面回收（kswapd）、迁移（memory hotplug, compaction）等场景中，需隔离或放回 LRU 页面，使用 `isolate_lru_page` / `putback_lru_page`。

- **内核模块兼容性**：  
  第三方或旧版内核模块若尚未适配 folio，可继续使用传统 page API，由本文件提供运行时兼容。

- **写回控制路径**：  
  `write_cache_pages()` 等通用写回例程中调用 `redirty_page_for_writepage`、`set_page_writeback` 等，通过此兼容层维持行为一致。

> 该文件是内核从 page-centric 向 folio-centric 架构演进过程中的关键兼容桥梁，目标是在未来完全移除后，所有调用点直接使用 folio API。