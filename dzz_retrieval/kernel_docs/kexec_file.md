# kexec_file.c

> 自动生成时间: 2025-10-25 14:25:27
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kexec_file.c`

---

# kexec_file.c 技术文档

## 文件概述

`kexec_file.c` 是 Linux 内核中实现 `kexec_file_load` 系统调用的核心文件，用于支持通过文件描述符加载新内核镜像、initrd 和命令行参数，从而在不重启固件的情况下实现内核热替换（kexec）。该文件负责从用户空间读取内核镜像文件、验证其格式与签名（若启用）、解析并加载到内核预留内存区域，并为后续跳转到新内核做好准备。相比传统的基于内存段的 `kexec_load`，`kexec_file_load` 提供了更安全、更简洁的接口，尤其适用于启用了安全启动（Secure Boot）或内核锁定（Lockdown）的系统。

## 核心功能

### 主要函数

- **`kexec_image_probe_default`**  
  遍历注册的 `kexec_file_loaders` 列表，调用各加载器的 `probe` 函数以识别内核镜像格式（如 ELF、PE 等），并设置对应的 `kexec_file_ops`。

- **`kexec_image_load_default`**  
  调用已识别加载器的 `load` 方法，将内核、initrd 和命令行参数解析为可执行的内存段布局。

- **`kexec_image_post_load_cleanup_default`**  
  调用加载器的 `cleanup` 回调，释放加载器私有数据。

- **`kimage_file_post_load_cleanup`**  
  释放临时分配的内核缓冲区、initrd 缓冲区、命令行缓冲区、purgatory 相关数据及 IMA 缓冲区，并调用架构特定清理函数。

- **`kimage_file_prepare_segments`**  
  从文件描述符读取内核和 initrd 数据，验证签名（若启用），处理命令行，集成 IMA 测量缓冲区，调用加载器进行段布局构建。

- **`kimage_file_alloc_init`**  
  分配并初始化 `kimage` 结构体，设置文件模式标志，处理崩溃转储（crash dump）场景，并调用段准备和校验逻辑。

- **`kimage_validate_signature` / `kexec_image_verify_sig`**  
  在 `CONFIG_KEXEC_SIG` 启用时，验证内核镜像的数字签名，支持强制签名模式（`sig_enforce`）。

- **`set_kexec_sig_enforced`**  
  供其他内核组件（如 lockdown）调用，强制启用内核镜像签名验证。

### 关键数据结构

- **`struct kimage`**  
  表示一个待加载的 kexec 镜像，包含内核/ initrd/ 命令行缓冲区、段列表、加载器私有数据、purgatory 信息等。

- **`struct kexec_file_ops`**  
  定义镜像加载器的操作集，包括 `probe`、`load`、`cleanup` 和 `verify_sig` 等回调函数。

- **`kexec_file_loaders`**  
  全局数组，注册了支持的镜像格式加载器（如 ELF、PE 等）。

## 关键实现

### 镜像格式自动探测
通过 `kexec_image_probe_default` 遍历 `kexec_file_loaders`，依次调用各加载器的 `probe` 函数尝试识别镜像格式。首个返回成功的加载器被选中，并将其 `kexec_file_ops` 赋值给 `image->fops`。

### 安全签名验证
当 `CONFIG_KEXEC_SIG` 启用时：
- 若 `CONFIG_KEXEC_SIG_FORCE` 或 `set_kexec_sig_enforced()` 被调用，则强制要求有效签名，否则拒绝加载。
- 支持通过 IMA（Integrity Measurement Architecture）进行替代验证：若 IMA 能保证对 kexec 镜像进行签名评估，即使内核处于 `LOCKDOWN_KEXEC` 状态也允许加载。
- 对于 PE 格式镜像（`CONFIG_SIGNED_PE_FILE_VERIFICATION`），使用 `verify_pefile_signature` 验证 UEFI Secure Boot 风格的签名。

### 内存管理与清理
- 内核和 initrd 使用 `vfree` 分配大块内存（因可能超过 `kmalloc` 限制）。
- 命令行使用 `memdup_user` 从用户空间复制。
- 所有临时缓冲区在 `kimage_file_post_load_cleanup` 中统一释放，确保错误路径下无内存泄漏。
- 架构相关清理通过 `arch_kimage_file_post_load_cleanup` 扩展。

### IMA 集成
- 调用 `ima_kexec_cmdline` 记录命令行的完整性度量。
- 通过 `ima_add_kexec_buffer` 将 IMA 测量列表传递给下一个内核。

### 崩溃转储支持
若设置了 `KEXEC_FILE_ON_CRASH` 标志，则：
- 设置 `image->type = KEXEC_TYPE_CRASH`
- 使用 `crashk_res.start` 作为控制页起始地址
- 启用崩溃内核专用的内存分配策略

## 依赖关系

- **架构相关代码**：依赖 `arch_kexec_kernel_image_probe`、`arch_kimage_file_post_load_cleanup` 等架构特定函数（通常在 `arch/*/kernel/kexec*` 中实现）。
- **安全子系统**：
  - `CONFIG_KEXEC_SIG` 依赖 `crypto/hash.h` 和 `crypto/sha2.h` 进行哈希计算。
  - `CONFIG_SIGNED_PE_FILE_VERIFICATION` 依赖 `verify_pefile_signature`（来自 `integrity/pefile`）。
  - `CONFIG_IMA_KEXEC` 依赖 IMA 子系统提供 `ima_add_kexec_buffer` 和 `ima_appraise_signature`。
- **内存管理**：使用 `vmalloc`/`vfree` 处理大文件，`memblock` 用于早期内存分配。
- **文件系统**：通过 `kernel_read_file_from_fd` 从文件描述符安全读取内核镜像。
- **kexec 核心**：依赖 `kexec_internal.h` 中定义的内部结构和函数（如 `do_kimage_alloc_init`、`sanity_check_segment_list`）。

## 使用场景

1. **常规内核热替换**  
   用户空间工具（如 `kexec-tools`）调用 `kexec_file_load` 系统调用，传入新内核、initrd 和命令行文件描述符，实现快速重启。

2. **崩溃转储（kdump）**  
   在系统崩溃时，通过 `KEXEC_FILE_ON_CRASH` 标志加载捕获内核（capture kernel），保存内存转储。

3. **安全启动环境**  
   在启用了 UEFI Secure Boot 或内核 Lockdown 的系统中，通过签名验证确保仅加载受信任的内核镜像。

4. **完整性保护系统**  
   与 IMA 集成，在加载新内核前验证其完整性，并将测量结果传递给下一内核，支持可信链延续。

5. **调试与开发**  
   通过 `KEXEC_FILE_DEBUG` 标志启用详细日志输出，辅助内核加载过程的调试。