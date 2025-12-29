# kexec.c

> 自动生成时间: 2025-10-25 14:23:16
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kexec.c`

---

# kexec.c 技术文档

## 1. 文件概述

`kexec.c` 是 Linux 内核中实现 `kexec_load` 系统调用的核心源文件，负责加载新内核镜像以支持在不重启硬件的情况下切换到另一个内核（即“热启动”）。该机制广泛用于快速重启、内核崩溃转储（crash dump）以及高可用性系统中。文件主要处理用户空间传入的内核镜像段、进行安全性和合法性校验、分配必要的控制结构和内存页，并调用架构相关代码完成最终的加载准备。

## 2. 核心功能

### 主要函数

- **`kimage_alloc_init()`**  
  分配并初始化 `kimage` 控制结构，验证段列表合法性，分配控制代码页和交换页（非崩溃场景）。

- **`do_kexec_load()`**  
  执行 `kexec_load` 的核心逻辑：加锁、释放旧镜像、调用 `kimage_alloc_init()`、准备架构相关资源、复制段数据、设置最终镜像指针。

- **`kexec_load_check()`**  
  执行权限、安全模块（LSM/IMA）、锁定策略（LOCKDOWN）及参数合法性检查。

- **`SYSCALL_DEFINE4(kexec_load)`**  
  64 位系统调用入口，从用户空间复制 `kexec_segment` 数组并调用 `do_kexec_load()`。

- **`COMPAT_SYSCALL_DEFINE4(kexec_load)`**  
  32 位兼容系统调用入口，处理 `compat_kexec_segment` 结构的转换。

### 关键数据结构

- **`struct kimage`**（定义于 `kexec_internal.h`）  
  表示一个待加载的内核镜像，包含入口地址、段信息、控制页、交换页、类型（普通/崩溃）等字段。

- **`struct kexec_segment`**  
  描述一个内存段，包含用户缓冲区地址/大小（`buf`/`bufsz`）和目标物理地址/大小（`mem`/`memsz`）。

## 3. 关键实现

### 镜像加载流程
1. **权限与安全校验**：通过 `kexec_load_check()` 确保调用者具有 `CAP_SYS_BOOT` 能力，并通过 LSM 和内核锁定机制（如 `LOCKDOWN_KEXEC`）防止绕过模块加载限制。
2. **崩溃内核特殊处理**：
   - 若设置了 `KEXEC_ON_CRASH` 标志，则镜像类型为 `KEXEC_TYPE_CRASH`。
   - 入口地址必须位于 `crashk_res`（崩溃保留内存区域）内。
   - 控制页固定为 `crashk_res.start`，且不分配交换页。
   - 加载过程中需临时解除对崩溃内存区域的保护（`arch_kexec_unprotect_crashkres()`），加载完成后重新保护。
3. **内存分配**：
   - 使用 `kimage_alloc_control_pages()` 分配控制代码页（大小为 `KEXEC_CONTROL_PAGE_SIZE`）。
   - 普通镜像额外分配一个交换页用于段加载时的页面交换。
4. **段加载**：遍历所有段，调用 `kimage_load_segment()` 将用户数据复制到目标物理内存。
5. **架构适配**：
   - 调用 `machine_kexec_prepare()` 进行架构特定的准备（如设置页表、禁用中断等）。
   - 调用 `kimage_crash_copy_vmcoreinfo()` 在准备完成后更新崩溃转储所需的 `vmcoreinfo` 数据。
   - 最终调用 `machine_kexec_post_load()` 完成架构相关后处理。

### 并发控制
- 使用 `kexec_trylock()`/`kexec_unlock()` 互斥锁防止多个进程同时加载崩溃内核，避免破坏保留内存区域。

### 兼容性支持
- 通过 `COMPAT_SYSCALL_DEFINE4` 处理 32 位用户程序在 64 位内核上的调用，将 `compat_ptr` 转换为原生指针。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/kexec.h>`：定义 `kexec_segment`、`KEXEC_*` 常量及公共接口。
  - `"kexec_internal.h"`：包含 `kimage` 结构及内部函数声明（如 `do_kimage_alloc_init`、`kimage_free`）。
  - `<linux/security.h>`：提供 LSM 安全钩子（`security_kernel_load_data`、`security_locked_down`）。
  - `<linux/crash_dump.h>`（隐式）：通过 `CONFIG_CRASH_DUMP` 条件编译使用 `crashk_res`。

- **架构相关代码**：
  - `arch_kexec_protect_crashkres()` / `arch_kexec_unprotect_crashkres()`：由各架构实现，用于保护/解除保护崩溃内存区域。
  - `machine_kexec_prepare()` / `machine_kexec_post_load()`：架构特定的镜像准备和后处理函数。

- **内存管理子系统**：
  - 依赖 `vmalloc`、`slab` 分配器及 `kimage_alloc_control_pages()`（通常基于 `alloc_pages()`）。

## 5. 使用场景

- **快速系统重启**：通过 `kexec` 工具加载新内核并跳转，跳过 BIOS/UEFI 和硬件初始化阶段，显著缩短重启时间。
- **内核崩溃转储（kdump）**：
  - 系统崩溃前预先加载一个“捕获内核”（通过 `KEXEC_ON_CRASH` 标志）。
  - 崩溃时直接跳转至捕获内核，将原内核内存保存为 `vmcore` 文件用于事后分析。
- **高可用性系统**：在关键服务中实现无缝内核切换，减少停机时间。
- **内核开发与测试**：快速迭代测试新内核版本，无需物理重启。