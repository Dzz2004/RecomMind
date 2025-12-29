# mmap.c

> 自动生成时间: 2025-12-07 16:51:22
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `mmap.c`

---

# mmap.c 技术文档

## 1. 文件概述

`mm/mmap.c` 是 Linux 内核内存管理子系统的核心源文件之一，主要负责虚拟内存区域（VMA, Virtual Memory Area）的创建、修改、删除以及与用户空间 `mmap()` 和 `brk()` 系统调用相关的逻辑实现。该文件实现了进程地址空间的动态扩展（如堆的 `brk` 调整）、文件映射、匿名映射、VMA 结构的生命周期管理、页表保护属性更新等关键功能，并为内核其他子系统（如安全模块、性能分析、内存压缩等）提供底层支持。

## 2. 核心功能

### 主要函数
- `vma_set_page_prot()`：根据 VMA 的标志位（`vm_flags`）更新其页表保护属性（`vm_page_prot`），并处理写时通知（writenotify）逻辑。
- `unlink_file_vma()`：从文件的地址空间映射树（`i_mmap`）中移除一个基于文件的 VMA，用于在释放前隐藏 VMA。
- `unlink_file_vma_batch_*()` 系列函数：批量处理多个 VMA 从同一文件映射树中的移除操作，提升性能。
- `remove_vma()`：关闭并释放一个 VMA 结构，包括调用 `vma_close()`、释放关联文件引用和内存策略。
- `check_brk_limits()`：检查 `brk` 扩展请求是否满足地址空间分配和内存锁定限制。
- `SYSCALL_DEFINE1(brk, ...)`：实现 `brk()` 系统调用，用于调整进程数据段（堆）的结束地址。
- `do_brk_flags()`（声明）：实际执行 `brk` 扩展逻辑的内部函数（定义在其他位置）。

### 关键数据结构
- `struct vm_area_struct`（VMA）：表示进程地址空间中的一段连续虚拟内存区域，包含起始/结束地址、访问权限、映射文件、操作函数指针等。
- `struct unlink_vma_file_batch`：用于批量处理文件 VMA 解链操作的临时结构。
- `struct vma_iterator`：用于高效遍历 VMA 树的迭代器（基于 Maple Tree）。

### 全局变量
- `mmap_rnd_bits` / `mmap_rnd_compat_bits`：控制 ASLR（地址空间布局随机化）中 mmap 基址随机化位数的可调参数。
- `ignore_rlimit_data`：内核启动参数，用于忽略 `RLIMIT_DATA` 资源限制（调试用途）。

## 3. 关键实现

### VMA 页表保护属性更新
`vma_set_page_prot()` 函数通过 `vm_pgprot_modify()` 将 VMA 的标志位（如 `VM_READ`、`VM_WRITE`、`VM_EXEC`、`VM_SHARED`）转换为底层架构相关的页表项保护位（`pgprot_t`）。特别地，当 VMA 需要写时通知（例如用于 COW 或跟踪）时，会临时清除 `VM_SHARED` 标志以生成非共享的写保护页表项，确保写操作能触发缺页异常。

### 文件 VMA 批量解链优化
为避免频繁加锁/解锁文件地址空间的 `i_mmap_rwsem`，内核引入了批量解链机制。`unlink_file_vma_batch_add()` 将待处理的 VMA 缓存到批次结构中，仅当遇到不同文件或批次满时才批量处理，显著减少锁竞争开销。

### `brk()` 系统调用实现
`brk()` 系统调用处理进程堆的扩展或收缩：
- **收缩**：直接调用 `do_vma_munmap()` 释放多余内存区域。
- **扩展**：
  1. 检查是否超出 `RLIMIT_DATA` 限制；
  2. 验证新堆顶与栈之间保留足够的安全间隙（`stack_guard_gap`）；
  3. 调用 `do_brk_flags()` 创建新的匿名 VMA；
  4. 更新 `mm->brk` 指针。
- 支持 `CONFIG_COMPAT_BRK` 选项以兼容旧版 ABI 的堆起始地址行为。

### 地址空间随机化（ASLR）
通过 `mmap_rnd_bits` 等全局变量，内核允许动态调整 mmap 区域基址的随机化熵值，增强系统安全性。这些值受架构配置（`CONFIG_ARCH_MMAP_RND_BITS*`）约束，并可通过 `/proc/sys/kernel/` 接口运行时调整。

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`、`<linux/vmalloc.h>`、`"internal.h"` 等提供的 VMA 操作、页表管理、内存分配接口。
- **文件系统**：通过 `struct file` 和 `address_space` 与 VFS 层交互，处理文件映射（`shmem_fs.h` 用于 tmpfs/shm）。
- **安全子系统**：集成 LSM（`<linux/security.h>`）钩子，支持安全策略检查。
- **硬件架构**：依赖 `<asm/mmu_context.h>`、`<asm/tlb.h>` 等架构相关头文件处理 TLB 刷新和页表格式。
- **其他子系统**：
  - 用户态缺页处理（`userfaultfd_k.h`）
  - 内存压缩（`ksm.h`）
  - 大页支持（`hugetlb.h`）
  - 性能事件（`perf_event.h`）
  - OOM Killer（`oom.h`）

## 5. 使用场景

- **用户程序调用 `mmap()`/`munmap()`**：创建/销毁内存映射（文件映射、匿名映射、共享内存等）。
- **动态内存分配**：`malloc()` 等库函数通过 `brk()` 或 `mmap()` 向内核申请堆内存。
- **进程加载**：ELF 加载器使用 `mmap()` 映射可执行文件段和共享库。
- **IPC 通信**：POSIX 共享内存（`shm_open` + `mmap`）和 System V 共享内存依赖此模块。
- **内核子系统协作**：
  - KSM（Kernel Samepage Merging）扫描 VMA 进行内存去重；
  - userfaultfd 监控 VMA 的缺页事件；
  - perf 工具通过 VMA 信息关联性能采样到代码位置；
  - 安全模块（如 SELinux）在映射时实施访问控制。