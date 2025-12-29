# page_io.c

> 自动生成时间: 2025-12-07 17:03:03
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `page_io.c`

---

# page_io.c 技术文档

## 1. 文件概述

`page_io.c` 是 Linux 内核内存管理子系统中负责页面交换 I/O 操作的核心文件。该文件实现了将匿名页写入交换设备（swap-out）和从交换设备读回内存（swap-in）的底层机制，包括基于 `bio` 的块设备交换路径和基于文件系统的直接 I/O 交换路径。此外，还提供了通用的交换文件激活逻辑，用于在启用交换文件时构建物理块到交换页的映射。

## 2. 核心功能

### 主要函数

- `__end_swap_bio_write()` / `end_swap_bio_write()`：处理交换写操作完成的回调，处理写错误并结束写回。
- `__end_swap_bio_read()` / `end_swap_bio_read()`：处理交换读操作完成的回调，设置页面 uptodate 状态或报告读错误。
- `generic_swapfile_activate()`：为基于文件的交换设备（如 swapfile）构建连续的物理块映射，填充 `swap_info_struct`。
- `swap_writepage()`：页面写回交换区的主入口函数，支持 zswap 压缩缓存、内存控制组限制等特性。
- `swap_writepage_fs()`：通过文件系统直接 I/O 路径（如 swap-over-NFS）执行交换写操作。
- `sio_pool_init()`：初始化用于异步交换 I/O 的内存池。
- `sio_write_complete()`：处理基于 kiocb 的异步交换写完成回调。

### 关键数据结构

- `struct swap_iocb`：封装用于文件系统交换 I/O 的 `kiocb` 和 `bio_vec` 数组，支持批量交换页写入。
- `sio_pool`：`mempool_t` 类型的内存池，用于分配 `swap_iocb` 结构，避免高内存压力下分配失败。

## 3. 关键实现

### 交换 I/O 完成处理
- 写操作失败时，页面被重新标记为 dirty 并清除 `PG_reclaim` 标志，防止被错误回收，同时输出限频警告日志。
- 读操作失败仅输出警告；成功则设置 `PG_uptodate` 并解锁页面。

### 交换文件激活 (`generic_swapfile_activate`)
- 遍历交换文件的逻辑块，使用 `bmap()` 获取物理块号。
- 验证每个 PAGE_SIZE 对齐区域的物理块是否连续且对齐。
- 通过 `add_swap_extent()` 将有效的交换页范围注册到交换子系统。
- 计算交换空间的物理跨度（`span`），用于优化交换分配策略。

### 交换写入路径选择
- 默认使用 `__swap_writepage()`（基于 `bio` 的块设备路径）。
- 若启用了 zswap 且压缩存储成功，则跳过磁盘 I/O。
- 若内存控制组禁用 zswap 回写，则返回 `AOP_WRITEPAGE_ACTIVATE` 以保留页面在内存中。
- 对于 NFS 等不支持 `bmap` 的文件系统，使用 `swap_writepage_fs()` 路径，通过 `kiocb` 异步 DIO 写入。

### 异步交换 I/O 批处理
- `swap_writepage_fs()` 支持通过 `wbc->swap_plug` 合并多个相邻页面的写请求到同一个 `swap_iocb`。
- 利用 `mempool` 保证在内存紧张时仍能分配 I/O 控制块。
- 完成回调中处理部分写入错误，标记所有相关页面为 dirty 并结束写回。

### 资源统计与控制
- 通过 `count_swpout_vm_event()` 更新透明大页（THP）和普通页的交换出计数。
- 在配置了 MEMCG 和 BLK_CGROUP 时，通过 `bio_associate_blkg_from_page()` 将 I/O 请求关联到页面所属的 blkcg，实现 I/O 资源隔离。

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`、`<linux/swap.h>`、`<linux/pagemap.h>` 等，与页面回收、反向映射、内存控制组紧密集成。
- **块设备层**：通过 `<linux/bio.h>`、`<linux/blkdev.h>` 与块 I/O 子系统交互。
- **文件系统接口**：使用 `bmap()` 和 `kiocb` 与具体文件系统（如 ext4、xfs）或网络文件系统（如 NFS）协作。
- **压缩子系统**：集成 `<linux/zswap.h>`，支持透明压缩交换缓存。
- **资源控制器**：依赖 MEMCG 和 BLK_CGROUP 实现内存与 I/O 的多租户隔离。
- **内部头文件**：包含本地 `"swap.h"` 获取交换子系统私有接口。

## 5. 使用场景

- **系统内存不足时**：页面回收机制调用 `swap_writepage()` 将匿名页换出到交换设备。
- **启用交换文件时**：`swapon` 系统调用执行 `generic_swapfile_activate()` 初始化交换文件的物理布局。
- **从交换区缺页中断**：当访问已换出页面时，内核通过 `end_swap_bio_read` 路径将数据读回内存。
- **容器环境**：在启用内存和 I/O 控制组的系统中，确保交换 I/O 正确归属到对应 cgroup。
- **使用压缩交换缓存**：当 zswap 启用时，优先尝试压缩页面而非立即写入慢速交换设备。
- **网络交换场景**：在无本地块设备的环境中（如云实例使用 NFS 作为交换后端），通过 `swap_writepage_fs()` 路径完成交换。