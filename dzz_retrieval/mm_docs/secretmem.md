# secretmem.c

> 自动生成时间: 2025-12-07 17:16:50
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `secretmem.c`

---

# secretmem.c 技术文档

## 1. 文件概述

`secretmem.c` 实现了 Linux 内核中的 **Secret Memory（秘密内存）** 功能，提供了一种安全的、不可交换（non-swappable）、不可转储（non-dumpable）且对内核页表隐藏的匿名内存区域。该功能通过新增系统调用 `memfd_secret(2)` 暴露给用户空间，用于创建具有特殊安全属性的内存文件描述符。此类内存主要用于存储敏感数据（如加密密钥），防止其被意外泄露到 swap、core dump 或通过 `/proc/pid/maps` 被探测。

## 2. 核心功能

### 主要函数
- `memfd_secret(unsigned int flags)`：系统调用入口，创建 secret memory 文件描述符。
- `secretmem_fault(struct vm_fault *vmf)`：处理缺页异常，按需分配并锁定秘密内存页。
- `secretmem_mmap(struct file *file, struct vm_area_struct *vma)`：设置 VMA 属性，启用 `VM_LOCKED | VM_DONTDUMP` 并绑定 fault handler。
- `secretmem_release(struct inode *inode, struct file *file)`：释放文件时减少用户计数。
- `secretmem_file_create(unsigned long flags)`：创建基于伪文件系统的 secret memory 文件对象。
- `secretmem_init(void)`：模块初始化，挂载 secretmem 伪文件系统。

### 关键数据结构
- `secretmem_fops`：文件操作结构体，定义 `.mmap` 和 `.release` 方法。
- `secretmem_vm_ops`：VMA 操作结构体，仅实现 `.fault` 回调。
- `secretmem_aops`：地址空间操作结构体，包含：
  - `.free_folio`：释放页面前恢复直接映射并清零。
  - `.migrate_folio`：返回 `-EBUSY` 禁止迁移。
  - `.dirty_folio`：空操作（`noop_dirty_folio`），禁止脏页标记。
- `secretmem_iops`：inode 操作结构体，限制文件大小不可修改（除初始为 0 外）。

### 全局变量
- `secretmem_enable`：模块参数，控制是否启用 secretmem 功能（默认启用）。
- `secretmem_users`：原子计数器，跟踪当前活跃的 secret memory 用户数量。
- `secretmem_mnt`：指向 secretmem 伪文件系统的内核挂载点。

## 3. 关键实现

### 内存安全性保障
- **直接映射移除**：在 `secretmem_fault()` 中分配新页后，调用 `set_direct_map_invalid_noflush()` 将该物理页从内核直接映射区（direct map）中移除，使内核无法通过常规线性地址访问该页内容，增强对抗内核漏洞利用的能力。
- **页面清零与恢复**：在 `secretmem_free_folio()` 中，先调用 `set_direct_map_default_noflush()` 恢复直接映射，再使用 `folio_zero_segment()` 安全清零页面内容，防止敏感数据残留。
- **TLB 刷新**：分配新页并修改直接映射后，调用 `flush_tlb_kernel_range()` 刷新内核 TLB，确保 CPU 不再缓存旧映射。

### 内存管理特性
- **不可交换 & 不可回收**：通过 `mapping_set_unevictable()` 标记 address_space 为不可驱逐，确保页面不会被 swap 出或被内存回收机制回收。
- **禁止迁移**：`.migrate_folio` 返回 `-EBUSY`，阻止 CMA、内存热插拔等场景下的页面迁移。
- **禁止写脏**：使用 `noop_dirty_folio` 防止页面被标记为 dirty，避免写回行为。
- **强制锁定**：`secretmem_mmap()` 强制设置 `VM_LOCKED`，结合 `mlock_future_ok()` 检查，确保内存常驻物理 RAM。

### 文件系统与权限控制
- 基于 `anon_inode` 构建伪文件系统（magic: `SECRETMEM_MAGIC`），挂载时设置 `MNT_NOEXEC` 禁止执行。
- 文件大小只能为 0，`setattr` 操作拒绝任何非零的 `ATTR_SIZE` 修改。
- 文件描述符默认具有 `O_RDWR` 权限，但实际 I/O 通过 mmap 访问。

### 系统调用验证
- 仅当 `secretmem_enable=1` 且平台支持 `can_set_direct_map()`（如 x86 的 `set_memory_valid()`）时才启用。
- 参数 `flags` 必须为 `O_CLOEXEC` 或 0，其他位均视为非法。

## 4. 依赖关系

- **架构支持**：依赖 `asm/tlbflush.h` 和 `set_memory.h` 提供的 `set_direct_map_*` 及 TLB 刷新接口，目前主要在 x86 上实现。
- **内存管理子系统**：重度依赖 `mm/` 下的 `filemap`、`folio`、`mlock`、`swap` 等机制。
- **VFS 层**：使用 `pseudo_fs.h` 和 `anon_inode` 基础设施创建安全 inode。
- **UAPI**：通过 `uapi/linux/magic.h` 定义文件系统 magic number。
- **模块参数**：使用 `module_param_named` 提供运行时开关。

## 5. 使用场景

- **敏感数据保护**：应用程序（如加密库、密钥管理服务）可使用 `memfd_secret()` 创建内存区域存储私钥、会话密钥等，防止其出现在 swap 分区或 core dump 文件中。
- **安全隔离**：由于页面从内核直接映射中移除，即使内核存在任意地址读取漏洞，攻击者也难以直接定位和提取 secret memory 中的数据。
- **高性能安全内存**：相比传统 `mlock()` + `mmap()` 方案，secret memory 提供更严格的访问控制和自动清零机制，适用于对安全性要求极高的场景。
- **容器与虚拟化**：可在容器或 VM 中为可信应用提供受保护的内存空间，降低侧信道攻击风险。