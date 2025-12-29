# truncate.c

> 自动生成时间: 2025-12-07 17:29:19
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `truncate.c`

---

# truncate.c 技术文档

## 1. 文件概述

`mm/truncate.c` 是 Linux 内核内存管理子系统中的关键文件，主要负责从地址空间（`address_space`）中移除页面（pages/folios），以响应文件截断（truncate）、内存回收或硬件错误等操作。该文件实现了对页缓存（page cache）中指定范围页面的安全清理、无效化和移除逻辑，确保在截断过程中不会破坏正在进行的 I/O 操作，并正确处理各种特殊映射（如 tmpfs、DAX）。

## 2. 核心功能

### 主要函数

- **`clear_shadow_entries()`**  
  清除地址空间中指定范围内的 shadow entries（用于工作集检测的占位符），但跳过 shmem 和 DAX 映射。

- **`truncate_folio_batch_exceptionals()`**  
  从 folio 批处理中移除异常条目（exceptional entries，如 swap 或 DAX 条目），并根据映射类型执行相应的清理操作。

- **`folio_invalidate()`**  
  使 folio 的指定字节范围无效，调用底层文件系统的 `invalidate_folio` 回调，确保脏缓冲区被正确处理。

- **`truncate_cleanup_folio()`**  
  对 folio 执行截断前的清理工作：解除映射、调用 invalidate、清除脏标记和 mapped-to-disk 标记。

- **`truncate_inode_folio()`**  
  完全移除一个属于指定地址空间的 folio，前提是其映射未改变。

- **`truncate_inode_partial_folio()`**  
  处理跨越截断边界的 partial folio：零化截断范围内的数据，必要时拆分大 folio。

- **`generic_error_remove_page()`**  
  用于硬件内存损坏场景，安全地从页缓存中移除指定页面。

- **`mapping_evict_folio()`**  
  安全地驱逐一个未使用、干净的 folio 出页缓存，常用于内存回收路径。

- **`truncate_inode_pages_range()`**  
  （声明未完整显示）截断地址空间中指定字节范围 `[lstart, lend]` 内的所有页面，包括处理非页对齐边界。

### 关键数据结构
- `struct address_space`：表示文件或块设备的页缓存容器。
- `struct folio`：内核 5.14+ 引入的页面抽象，替代部分 `struct page` 用法。
- XArray（`i_pages`）：用于高效存储和查找 folio 及异常条目。

## 3. 关键实现

### 异常条目处理
- 使用 `xa_is_value()` 判断 XArray 中的条目是否为异常值（非 folio）。
- 对 DAX 映射，调用 `dax_delete_mapping_entry()` 特殊处理。
- 对普通映射，在持有 inode 锁和 XArray 自旋锁的情况下，将异常条目置为 `NULL`。

### 截断安全性
- 在操作 folio 前检查 `folio->mapping` 是否仍指向原始 `address_space`，防止并发 reclaim 或 tmpfs swizzling 导致的 UAF。
- 调用 `folio_wait_writeback()` 确保写回完成后再修改或释放 folio。
- 对 partial folio，先零化截断区域再尝试拆分，避免数据泄露。

### 锁与同步
- 使用 `i_lock`（inode 锁）保护对 `i_pages` XArray 的批量修改。
- XArray 操作使用 `xas_lock_irq()` 禁用中断以保证原子性。
- 对 shrinkable 映射（如 tmpfs），截断后调用 `inode_add_lru()` 将 inode 加入 LRU 链表以便后续回收。

### 内存屏障与标记清理
- `folio_cancel_dirty()` 在 invalidate 后调用，防止某些文件系统（如 ext3）在 invalidate 后重新置脏。
- `folio_clear_mappedtodisk()` 清除“已写入磁盘”标记，确保截断后状态一致。

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`, `<linux/swap.h>`, `<linux/pagevec.h>` 等提供的页面操作原语。
- **文件系统接口**：通过 `address_space_operations` 中的 `invalidate_folio` 回调与具体文件系统交互。
- **特殊文件系统**：
  - `shmem_fs.h`：处理 tmpfs/shmem 映射的特殊逻辑（跳过 shadow entries 清理）。
  - `dax.h`：处理 DAX（Direct Access）映射的异常条目删除。
- **反向映射（rmap）**：通过 `rmap.h` 提供的 `unmap_mapping_folio()` 解除用户页表映射。
- **内部头文件**：`internal.h` 提供 mm 子系统内部辅助函数。

## 5. 使用场景

- **文件截断（truncate/ftruncate）**：当用户调用截断系统调用时，VFS 层调用 `truncate_inode_pages_range()` 清理超出新文件大小的页缓存。
- **内存压力回收**：在内存不足时，kswapd 或直接回收路径调用 `mapping_evict_folio()` 驱逐干净未用页面。
- **硬件错误处理**：内存发生不可纠正错误（UCE）时，通过 `generic_error_remove_page()` 从页缓存中移除损坏页面。
- **文件系统卸载/失效**：在 inode 失效或超级块卸载过程中，清理关联的页缓存。
- **tmpfs/shmem 管理**：虽然 shmem 有自管理逻辑，但通用截断路径仍会调用相关函数处理边界情况。