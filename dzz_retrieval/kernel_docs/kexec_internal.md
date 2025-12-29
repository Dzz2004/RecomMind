# kexec_internal.h

> 自动生成时间: 2025-10-25 14:27:04
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kexec_internal.h`

---

# kexec_internal.h 技术文档

## 文件概述

`kexec_internal.h` 是 Linux 内核中 kexec 子系统的内部头文件，定义了 kexec 核心功能所需的内部函数、数据结构和同步机制。该文件为 kexec 的实现提供底层支持，包括内核镜像的分配、加载、校验、释放以及崩溃转储（crash dump）场景下的并发控制。此头文件仅供 kexec 相关的内部实现使用，不对外暴露给其他子系统。

## 核心功能

### 数据结构
- `struct kimage`：kexec 内核镜像的核心控制结构（定义在 `<linux/kexec.h>` 中，此处仅使用）
- `struct kexec_segment`：描述要加载的内存段（定义在 `<linux/kexec.h>` 中）
- `struct kexec_buf`：用于内存洞查找的缓冲区描述结构（在 `CONFIG_KEXEC_HANDOVER` 下使用）

### 主要函数

#### 镜像管理
- `do_kimage_alloc_init(void)`：分配并初始化一个新的 `kimage` 结构
- `kimage_free(struct kimage *image)`：释放整个 kexec 镜像及其相关资源
- `kimage_free_page_list(struct list_head *list)`：释放页链表中的所有页面

#### 段处理与校验
- `sanity_check_segment_list(struct kimage *image)`：对镜像的段列表进行合法性校验
- `kimage_load_segment(struct kimage *image, struct kexec_segment *segment)`：将指定段加载到目标内存位置
- `kimage_terminate(struct kimage *image)`：终止镜像加载过程，清理中间状态

#### 内存范围检查
- `kimage_is_destination_range(struct kimage *image, unsigned long start, unsigned long end)`：判断指定内存范围是否属于镜像的目标加载区域

#### 文件式 kexec 支持（`CONFIG_KEXEC_FILE`）
- `kimage_file_post_load_cleanup(struct kimage *image)`：在基于文件的 kexec 加载完成后执行清理工作
- `kexec_purgatory[]` 和 `kexec_purgatory_size`：purgatory 代码段（用于验证和跳转的中间代码）及其大小

#### 交接式 kexec 支持（`CONFIG_KEXEC_HANDOVER`）
- `kho_locate_mem_hole(struct kexec_buf *kbuf, int (*func)(struct resource *, void *))`：在系统内存中定位可用于加载的空洞
- `kho_fill_kimage(struct kimage *image)`：填充交接式 kexec 所需的镜像信息

#### 并发控制
- `kexec_trylock(void)`：尝试获取 kexec 全局锁（NMI 安全）
- `kexec_unlock(void)`：释放 kexec 全局锁

### 全局变量
- `atomic_t __kexec_lock`：用于序列化对 `kexec_crash_image` 的访问，确保在 NMI 上下文（如崩溃转储）中安全

## 关键实现

### NMI 安全的锁机制
由于 `__crash_kexec()` 可能在 `nmi_panic()` 中被调用，任何对崩溃镜像（`kexec_crash_image`）的访问都必须是 NMI 安全的。为此，该文件使用了一个基于 `atomic_cmpxchg_acquire()` 和 `atomic_set_release()` 的简单原子锁 `__kexec_lock`，避免使用可能睡眠或依赖中断的常规锁原语。

### 条件编译支持
- **`CONFIG_KEXEC_FILE`**：启用基于文件的 kexec（如从 ELF 或 bzImage 文件加载），引入 purgatory 支持和相关清理函数。
- **`CONFIG_KEXEC_HANDOVER`**：启用交接式 kexec 功能，允许在跳转前执行特定架构的交接代码，提供内存洞定位和镜像填充接口。

### 默认空实现
对于未启用的配置选项（如无 `CONFIG_KEXEC_FILE` 或 `CONFIG_KEXEC_HANDOVER`），相关函数提供内联空实现，确保编译通过且无运行时开销。

## 依赖关系

- **头文件依赖**：
  - `<linux/kexec.h>`：定义了 `kexec_segment`、`kimage` 等公共接口
  - `<linux/purgatory.h>`（仅 `CONFIG_KEXEC_FILE`）：提供 purgatory 相关定义
- **配置依赖**：
  - `CONFIG_KEXEC`：kexec 基础功能
  - `CONFIG_KEXEC_FILE`：文件式 kexec 支持
  - `CONFIG_KEXEC_HANDOVER`：交接式 kexec 支持
- **模块依赖**：被 `kernel/kexec.c`、`kernel/kexec_file.c` 等 kexec 核心实现文件包含，不被其他子系统直接引用。

## 使用场景

- **正常 kexec 重启**：用户空间通过 `kexec_load` 系统调用加载新内核，内核使用本文件中的函数分配镜像、校验段、加载内容并最终跳转。
- **崩溃转储（kdump）**：系统崩溃时，`__crash_kexec()` 被调用，使用本文件提供的 NMI 安全锁机制访问预加载的崩溃内核镜像，并执行跳转以保存内存转储。
- **基于文件的内核加载**：当使用 `kexec_file_load` 系统调用时，内核解析内核镜像文件，利用 purgatory 验证签名或执行跳转逻辑，相关清理由 `kimage_file_post_load_cleanup` 处理。
- **架构特定交接**：在支持 `CONFIG_KEXEC_HANDOVER` 的架构上，跳转前需填充特定信息或定位合适内存区域，由 `kho_*` 系列函数支持。