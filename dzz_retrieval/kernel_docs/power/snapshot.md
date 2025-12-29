# power\snapshot.c

> 自动生成时间: 2025-10-25 15:25:19
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `power\snapshot.c`

---

# `power/snapshot.c` 技术文档

## 1. 文件概述

`power/snapshot.c` 是 Linux 内核休眠（hibernation）子系统的核心实现文件之一，负责系统内存快照（snapshot）的创建与恢复。该文件为软件挂起到磁盘（swsusp, Software Suspend）机制提供底层支持，主要功能包括：

- 在休眠过程中捕获系统内存状态并生成可持久化的映像（image）
- 在恢复过程中将映像内容还原到原始内存位置
- 管理用于存储映像数据的“安全页”（safe pages），避免恢复时覆盖关键内核数据
- 提供内存页的保护机制，确保恢复过程的安全性

该文件是内核电源管理（PM）子系统中休眠功能的关键组成部分。

## 2. 核心功能

### 主要全局变量
- `reserved_size`：为设备驱动在冻结回调中预留的内存大小（可通过 `/sys/power/reserved_size` 调整）
- `image_size`：期望的休眠映像最大尺寸（可通过 `/sys/power/image_size` 调整）
- `restore_pblist`：指向 PBE（Page Backup Entry）链表的指针，用于处理恢复时内存地址冲突
- `safe_pages_list`：空闲“安全页”链表，用于临时存储恢复过程中的数据

### 关键数据结构
- `struct linked_page`：用于构建页链表的结构体，每页包含一个指向下一页的指针和有效数据区
- `struct chain_allocator`：用于从页链中分配小对象的分配器（定义未完整，但用途明确）

### 核心函数
- `get_image_page()`：分配用于休眠映像的内存页，并根据需要确保其为“安全页”
- `__get_safe_page()` / `get_safe_page()`：从安全页池中获取已清零的页
- `recycle_safe_page()`：将使用完毕的安全页归还到池中
- `free_image_page()` / `free_list_of_pages()`：释放映像页或整条页链
- `hibernate_map_page()` / `hibernate_unmap_page()`：控制页在直接映射区的可访问性
- `hibernate_restore_protect_page()` / `hibernate_restore_unprotect_page()`：在恢复阶段临时修改页保护属性（仅在启用严格内核 RWX 时有效）

### 辅助函数（声明但未定义）
- `swsusp_page_is_free()`
- `swsusp_set_page_forbidden()`
- `swsusp_unset_page_forbidden()`

这些函数用于标记和查询页的状态（如 `PageNosave`、`PageNosaveFree`），通常在 `swap.c` 或其他相关文件中实现。

## 3. 关键实现

### 安全页管理机制
- **安全页**：指在“恢复内核”（resume kernel）启动后未被使用的物理页，可用于临时存储原始系统映像数据。
- 在恢复阶段，若目标页已被恢复内核占用，则需通过 PBE 链表暂存数据，待后续安全写回。
- `get_image_page()` 在 `safe_needed=PG_SAFE` 时会跳过已被使用的页（通过 `swsusp_page_is_free()` 判断），并将其标记为 `PageNosaveFree` 以便后续释放。

### 内存保护机制
- 当启用 `CONFIG_STRICT_KERNEL_RWX` 且架构支持 `set_memory_*` 时，恢复过程会临时将映像页设为只读（`set_memory_ro`），防止意外写入。
- 该机制通过 `hibernate_restore_protection` 开关控制，由 `enable_restore_image_protection()` 启用。

### 直接映射区页表操作
- 使用 `set_direct_map_default_noflush()` / `set_direct_map_invalid_noflush()` 控制页在内核直接映射区的可访问性。
- 操作失败时会打印警告，但不中断流程，确保兼容性。
- 无效映射后需手动调用 `flush_tlb_kernel_range()` 刷新 TLB。

### 内存分配策略
- 映像页通过 `get_zeroed_page()` 或 `alloc_page()` 分配，并统一标记为 `PageNosave` 和 `PageNosaveFree`。
- `allocated_unsafe_pages` 计数器跟踪因冲突而被跳过的“不安全页”数量。
- `chain_allocator` 设计用于高效分配大量小对象（如 PBE 条目），避免频繁页分配。

## 4. 依赖关系

### 内核配置依赖
- `CONFIG_HIBERNATION`：休眠功能总开关
- `CONFIG_STRICT_KERNEL_RWX` + `CONFIG_ARCH_HAS_SET_MEMORY`：启用恢复阶段页保护
- `CONFIG_ARCH_HAS_SET_DIRECT_MAP`：支持直接映射区页属性修改

### 头文件依赖
- **内存管理**：`<linux/mm.h>`, `<linux/highmem.h>`, `<linux/page-flags.h>`（隐含）
- **电源管理**：`<linux/suspend.h>`, `<linux/pm.h>`, `"power.h"`
- **架构相关**：`<asm/mmu_context.h>`, `<asm/tlbflush.h>`, `<asm/io.h>`
- **通用内核**：`<linux/slab.h>`, `<linux/spinlock.h>`, `<linux/bitops.h>`

### 功能依赖
- 依赖 `swsusp` 的页状态标记机制（`PageNosave*` 系列标志）
- 与 `swap.c` 协同工作，后者负责映像的 I/O 操作
- 依赖架构特定的内存保护函数（如 x86 的 `set_memory_ro/rw`）

## 5. 使用场景

### 休眠（Hibernation）流程
1. **准备阶段**：系统冻结进程和设备，计算所需映像大小
2. **快照创建**：
   - 调用 `get_image_page()` 分配内存
   - 使用 `hibernate_unmap_page()` 临时移除冲突页的映射
   - 将内存内容压缩并写入交换分区/文件
3. **关机**：系统断电
4. **恢复阶段**：
   - “恢复内核”启动，加载映像到内存
   - 通过 `get_safe_page()` 获取安全页暂存冲突数据
   - 使用 PBE 链表管理地址冲突
   - 调用 `hibernate_restore_protect_page()` 保护映像页（若启用）
   - 逐步还原原始内核状态并跳转

### 关键调用路径
- 用户空间写入 `/sys/power/disk` 触发休眠 → `hibernate()` → `create_image()` → 本文件函数
- 恢复内核启动 → `snapshot_read()` / `snapshot_write()` → 本文件的页分配与保护函数

该文件确保了休眠映像在创建和恢复过程中的内存安全性和完整性，是 Linux 休眠功能可靠性的基石。