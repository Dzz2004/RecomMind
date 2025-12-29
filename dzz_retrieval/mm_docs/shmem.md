# shmem.c

> 自动生成时间: 2025-12-07 17:17:29
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `shmem.c`

---

# shmem.c 技术文档

## 1. 文件概述

`shmem.c` 实现了 Linux 内核中的 **共享内存虚拟文件系统（tmpfs）**，它基于 `ramfs` 扩展而来，支持使用交换空间（swap）并遵守资源限制，从而成为一个完全可用的内存文件系统。该文件系统用于实现 POSIX 共享内存、匿名映射（如 `/dev/zero`）、`memfd_create()` 创建的内存文件以及 tmpfs 挂载点（如 `/tmp` 或 `/dev/shm`）。其核心特点是：数据存储在内存中，可被换出到 swap，支持稀疏文件，并受内存和 inode 配额限制。

## 2. 核心功能

### 主要数据结构
- `struct shmem_falloc`：用于 `fallocate` 操作与缺页处理之间的通信，记录预分配范围、已分配页数等。
- `struct shmem_options`：解析挂载选项（如 size、nr_inodes、huge、uid/gid 等）时使用的临时结构。
- `struct shmem_sb_info`：超级块私有信息，包含块/ inode 配额、内存策略、配额计数器等。
- `struct shmem_inode_info`：inode 私有信息，扩展标准 inode 以支持共享内存特性。

### 关键函数
- `shmem_acct_size()` / `shmem_unacct_size()`：对固定大小 VM 对象进行内存预占（如共享内存映射）。
- `shmem_acct_blocks()` / `shmem_unacct_blocks()`：对 tmpfs 稀疏文件按实际分配页进行内存核算。
- `shmem_inode_acct_blocks()` / `shmem_inode_unacct_blocks()`：结合文件系统配额（`max_blocks`）和磁盘配额（`dquot`）进行块分配/释放。
- `shmem_swapin_folio()`：从 swap 中换入指定页。
- `vma_is_anon_shmem()`：判断 VMA 是否为匿名共享内存映射。
- `SHMEM_SB()`：宏，快速获取超级块的 `shmem_sb_info`。

### 全局操作结构体
- `shmem_ops`：超级块操作（如 `statfs`、`put_super`）。
- `shmem_aops`：地址空间操作（如 `readpage`、`writepage`、`set_page_dirty`）。
- `shmem_file_operations`：文件操作（如 `read`、`write`、`mmap`）。
- `shmem_inode_operations`：普通文件 inode 操作。
- `shmem_dir_inode_operations`：目录 inode 操作。
- `shmem_special_inode_operations`：特殊文件（设备、socket）inode 操作。
- `shmem_vm_ops` / `shmem_anon_vm_ops`：VMA 操作结构体，分别用于 tmpfs 文件映射和匿名共享内存映射。

## 3. 关键实现

### 内存核算机制
- **预占模式（Pre-accounting）**：用于 `shmem_file_setup()` 创建的固定大小对象（如 POSIX 共享内存），在创建时即核算全部内存（通过 `shmem_acct_size`），避免运行时 OOM。
- **增量核算（Incremental accounting）**：用于 tmpfs 文件，仅在实际分配页面时核算（通过 `shmem_acct_blocks`），支持大稀疏文件。失败返回 `-ENOSPC` 而非 `-ENOMEM`，使用户态收到 `SIGBUS` 而非触发 OOM killer。

### 配额管理
- 使用 `percpu_counter` 高效跟踪已用块数（`used_blocks`），并与挂载时指定的 `max_blocks` 限制比较。
- 集成内核通用配额子系统（`dquot_alloc_block_nodirty` / `dquot_free_block_nodirty`），支持用户/组配额。

### 大页（Huge Page）支持
- 通过 `huge` 挂载选项和 `madvise(MADV_HUGEPAGE)` 控制透明大页（THP）行为。
- 维护多个位图（`huge_shmem_orders_*`）记录不同场景下允许的大页阶数。

### fallocate 与缺页协同
- `shmem_falloc` 结构通过 `inode->i_private` 在 `fallocate` 和 `shmem_fault`/`shmem_writepage` 之间传递状态。
- 使用等待队列（`waitq`）确保在 punch hole 操作期间，访问空洞的缺页请求会等待操作完成。

### 匿名 vs 命名共享内存
- **匿名共享内存**：由 `shmem_zero_setup()` 创建（如 `/dev/zero` 映射），使用 `shmem_anon_vm_ops`。
- **命名共享内存**：通过 tmpfs 文件系统接口创建（如 `shm_open()`），使用 `shmem_vm_ops`。

## 4. 依赖关系

- **内存管理子系统**：依赖 `mm/` 中的页分配、swap、rmap、mempolicy、hugetlb 等机制。
- **VFS 层**：实现标准文件系统接口（`super_operations`, `inode_operations` 等）。
- **安全模块**：调用 LSM 钩子（`security_vm_enough_memory_mm`）进行内存安全检查。
- **配额子系统**：通过 `dquot_*` 函数集成磁盘配额功能。
- **swap 子系统**：通过 `swap.h` 和 `swapops.h` 实现页面换入换出。
- **其他**：依赖 `ramfs` 基础结构、`xattr`、`posix_acl`、`splice`、`falloc` 等通用内核组件。

## 5. 使用场景

- **POSIX 共享内存**：`shm_open()` / `shm_unlink()` 创建的共享内存对象。
- **System V 共享内存**：`shmget()` / `shmat()` 使用的底层存储。
- **匿名映射**：`mmap()` 映射 `/dev/zero` 或 `MAP_ANONYMOUS | MAP_SHARED` 创建的共享内存区域。
- **tmpfs 文件系统**：挂载 tmpfs（如 `/dev/shm`）后创建的文件和目录。
- **memfd 文件**：通过 `memfd_create()` 系统调用创建的匿名内存文件，支持密封（sealing）和共享。
- **内核内部用途**：作为某些需要临时可换出内存缓冲区的子系统的后端存储。