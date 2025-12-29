# power\swap.c

> 自动生成时间: 2025-10-25 15:27:36
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `power\swap.c`

---

# `power/swap.c` 技术文档

## 1. 文件概述

`power/swap.c` 是 Linux 内核电源管理子系统中负责**休眠（hibernation）功能**的核心文件之一，主要实现将系统内存镜像（suspend image）**写入交换分区（swap）** 以及从交换分区**恢复镜像**的功能。该文件通过管理交换空间的分配、镜像数据的读写、校验和跟踪机制，确保休眠/恢复过程的可靠性和完整性。

## 2. 核心功能

### 主要数据结构

- **`struct swap_map_page`**  
  用于记录写入交换分区的每个内存页对应的扇区位置，支持链式结构（通过 `next_swap` 字段链接多个 map 页）。

- **`struct swap_map_handle`**  
  管理交换映射的句柄，包含当前 map 页、map 链表、当前扇区、起始扇区、CRC32 校验值等信息。

- **`struct swsusp_header`**  
  休眠镜像头部结构，存储在交换分区固定位置（`swsusp_resume_block`），包含魔数（`HIBERNATE_SIG`）、镜像起始扇区、硬件签名、CRC32 校验等元数据。

- **`struct swsusp_extent`**  
  使用红黑树（`rb_root swsusp_extents`）跟踪已分配的交换页范围，用于错误恢复时释放已分配的交换空间。

- **`struct hib_bio_batch`**  
  用于批量提交 BIO 请求，支持异步 I/O 和错误处理，提升休眠/恢复性能。

### 主要函数

- **`alloc_swapdev_block(int swap)`**  
  从指定交换设备分配一个交换页，并将其记录到 `swsusp_extents` 红黑树中。

- **`free_all_swap_pages(int swap)`**  
  释放所有在休眠过程中分配的交换页，并清空 `swsusp_extents` 树。

- **`swsusp_swap_in_use(void)`**  
  检查是否有交换页已被分配用于休眠。

- **`hib_submit_io()` / `hib_end_io()` / `hib_wait_io()`**  
  封装块设备 I/O 操作，支持同步/异步读写交换分区，处理缓存一致性（如 `flush_icache_range`）。

- **`mark_swapfiles()`**  
  在交换分区头部写入休眠标识（`HIBERNATE_SIG`）和镜像元数据，标记该交换分区包含有效休眠镜像。

- **`low_free_pages()` / `reqd_free_pages()`**  
  计算系统中可用的低内存页数量，确保休眠过程中保留足够内存用于 I/O 操作。

## 3. 关键实现

### 交换映射管理
- 使用链式 `swap_map_page` 结构记录所有被写入交换分区的内存页位置。
- 每个 `swap_map_page` 可存储 `MAP_PAGE_ENTRIES = (PAGE_SIZE / sizeof(sector_t) - 1)` 个扇区地址，最后一个字段用于指向下一个 map 页。
- 映射信息本身也写入交换分区，形成自描述的镜像结构。

### 交换页跟踪与错误恢复
- 通过红黑树 `swsusp_extents` 动态记录所有已分配的交换页范围。
- 支持相邻区间的自动合并，减少内存开销。
- 若休眠失败，可通过 `free_all_swap_pages()` 安全释放所有已分配交换页。

### I/O 优化与缓存一致性
- 使用 `hib_bio_batch` 批量提交 BIO，结合 `blk_plug` 机制减少 I/O 中断。
- 在读取镜像页后，若 `clean_pages_on_read` 为真，则调用 `flush_icache_range` 确保指令缓存一致性（对某些架构如 ARM/MIPS 必需）。
- 支持 CRC32 校验（`swsusp_header->crc32`），用于验证镜像完整性。

### 内存压力控制
- `reqd_free_pages()` 保留至少一半的低内存页，防止在写入镜像时因内存不足导致系统崩溃。

### 休眠标识与硬件签名
- 交换分区头部原为 `SWAP-SPACE` 或 `SWAPSPACE2`，休眠时替换为 `S1SUSPEND`（`HIBERNATE_SIG`）。
- 可选写入硬件签名（`swsusp_hardware_signature`），防止在不同硬件上错误恢复。

## 4. 依赖关系

- **块设备层**：依赖 `<linux/blkdev.h>`、`<linux/bio.h>` 进行底层 I/O 操作。
- **内存管理**：依赖 `<linux/swap.h>`、`<linux/swapops.h>` 管理交换页分配与释放。
- **电源管理核心**：包含 `"power.h"`，与 `swsusp.c`、`snapshot.c` 等协同工作。
- **压缩支持**：包含 `<linux/lzo.h>`，为后续压缩镜像提供接口（尽管本文件未直接实现压缩）。
- **校验与调试**：使用 `<linux/crc32.h>` 进行数据校验，`<linux/ktime.h>` 用于性能追踪。

## 5. 使用场景

- **系统休眠（Suspend-to-Disk / Hibernation）**：  
  当用户执行 `echo disk > /sys/power/state` 时，内核调用此模块将内存镜像写入交换分区。

- **系统恢复（Resume from Hibernation）**：  
  启动时若检测到交换分区包含有效 `HIBERNATE_SIG`，内核使用此模块从交换分区读取镜像并恢复系统状态。

- **交换分区管理**：  
  在休眠过程中动态分配和跟踪交换页，确保不与常规 swap 使用冲突，并在失败时安全回滚。

- **跨架构支持**：  
  通过 `clean_pages_on_read` 机制适配需要指令缓存刷新的 CPU 架构，保证恢复后代码可正确执行。