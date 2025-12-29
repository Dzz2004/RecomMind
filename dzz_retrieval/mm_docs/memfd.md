# memfd.c

> 自动生成时间: 2025-12-07 16:40:22
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `memfd.c`

---

# memfd.c 技术文档

## 1. 文件概述

`memfd.c` 实现了 Linux 内核中的 `memfd_create()` 系统调用及其配套的文件密封（file sealing）机制。该文件最初是 `shmem.c` 的一部分，后被拆分出来以同时支持 tmpfs 和 hugetlbfs 文件系统。其核心功能包括：

- 创建匿名内存文件（memfd），无需关联磁盘或文件系统路径
- 提供文件密封（sealing）能力，允许对共享内存区域施加不可逆的操作限制
- 支持普通页和大页（hugetlb）两种内存分配模式
- 通过引用计数检测和等待机制确保密封操作的安全性

## 2. 核心功能

### 主要函数

| 函数 | 功能描述 |
|------|---------|
| `memfd_alloc_folio()` | 为 memfd 文件分配 folio（页），支持普通页和大页模式 |
| `memfd_wait_for_pins()` | 等待所有被外部引用（如 GUP、DMA）的 folio 释放，用于 SEAL_WRITE 密封前的安全检查 |
| `memfd_tag_pins()` | 扫描地址空间，标记具有额外引用计数的 folio |
| `memfd_add_seals()` | 向文件添加密封标志，实现不可逆的访问控制 |
| `memfd_get_seals()` | 获取文件当前的密封标志 |
| `memfd_fcntl()` | 处理 F_ADD_SEALS 和 F_GET_SEALS fcntl 命令 |

### 关键数据结构和常量

- **密封标志**：
  - `F_SEAL_SEAL`：禁止进一步添加密封
  - `F_SEAL_WRITE`：禁止写入
  - `F_SEAL_GROW/SHRINK`：禁止文件增长/缩小
  - `F_SEAL_EXEC`：禁止修改执行权限位
  - `F_SEAL_FUTURE_WRITE`：禁止未来写入（与 EXEC 相关）

- **memfd 标志**：
  - `MFD_CLOEXEC`：close-on-exec
  - `MFD_ALLOW_SEALING`：允许密封
  - `MFD_HUGETLB`：使用大页
  - `MFD_NOEXEC_SEAL` / `MFD_EXEC`：控制执行权限

- **内部标记**：
  - `MEMFD_TAG_PINNED`：复用 `PAGECACHE_TAG_TOWRITE` 标记被外部引用的 folio

## 3. 关键实现

### 文件密封机制

密封是一种**单向、不可逆**的访问控制机制：
- 密封只能添加，不能移除
- 一旦设置 `F_SEAL_SEAL`，不能再添加任何密封
- 密封作用于整个 inode，影响所有文件描述符

### 引用计数检测算法

为安全实现 `SEAL_WRITE`，内核需确保无外部引用：
1. **标记阶段** (`memfd_tag_pins`)：
   - 遍历 radix tree 中的所有 folio
   - 对 `folio_ref_count() - folio_mapcount() != folio_nr_pages()` 的 folio 标记为 PINNED
   - 表示存在非映射引用（如 GUP、DMA）

2. **等待阶段** (`memfd_wait_for_pins`)：
   - 最多进行 5 次扫描（LAST_SCAN = 4）
   - 指数退避等待（(HZ << scan) / 200）
   - 最后一次扫描清理标记并返回 `-EBUSY`（如有残留引用）

### 大页支持

通过条件编译支持 hugetlbfs：
- 检测 `is_file_hugepages()` 判断是否大页模式
- 使用 `htlb_alloc_mask()` 并清除 `__GFP_HIGHMEM | __GFP_MOVABLE`
- 调用 hugetlb 专用分配和缓存接口

### 执行权限密封

`F_SEAL_EXEC` 具有特殊语义：
- 若文件已有执行权限（`i_mode & 0111`），自动添加 `WRITE|GROW|SHRINK|FUTURE_WRITE` 密封
- 实现 W^X（Write XOR Execute）安全策略

## 4. 依赖关系

### 内核模块依赖

- **内存管理**：
  - `<linux/mm.h>`：folio 操作、GFP 标志
  - `<linux/pagemap.h>`：address_space、radix tree 操作
  - `<linux/shmem_fs.h>`：tmpfs inode 结构（`SHMEM_I`）
  
- **文件系统**：
  - `<linux/hugetlb.h>`：大页支持（`HUGETLBFS_I`）
  - `<linux/fs.h>` / `<linux/vfs.h>`：VFS 层接口
  
- **同步机制**：
  - `<linux/sched/signal.h>`：可杀等待（`schedule_timeout_killable`）
  - XArray 锁（`xas_lock_irq`）保证并发安全

### 复用设计

- **标记复用**：使用 `PAGECACHE_TAG_TOWRITE` 作为 `MEMFD_TAG_PINNED`，因 tmpfs/hugetlbfs 不使用此标记
- **代码共享**：同时服务 tmpfs 和 hugetlbfs，通过 `memfd_file_seals_ptr()` 抽象 inode 访问

## 5. 使用场景

### 用户态应用场景

1. **安全共享内存**：
   - 多进程通过 `memfd_create()` 创建共享内存
   - 生产者添加 `SEAL_WRITE` 后传递 fd 给消费者，确保数据不可篡改

2. **动态代码加载**：
   - JIT 编译器创建可执行 memfd
   - 写入代码后密封 `SEAL_WRITE`，防止后续修改（配合 `SEAL_EXEC`）

3. **容器/沙箱**：
   - 限制不受信任进程对共享内存的操作能力
   - 通过密封防止恶意进程破坏共享状态

### 内核内部使用

1. **GUP（Get User Pages）集成**：
   - `memfd_alloc_folio()` 被 `gup.c` 调用，处理 memfd 的缺页
   - 确保 DMA/GUP 场景下密封的安全性

2. **大页优化**：
   - 通过 `MFD_HUGETLB` 标志创建大页 memfd
   - 适用于需要大块连续内存的高性能场景（如 DPDK）

3. **安全增强**：
   - `sysctl_memfd_noexec` 控制默认执行权限
   - 防止 memfd 被滥用于代码注入攻击