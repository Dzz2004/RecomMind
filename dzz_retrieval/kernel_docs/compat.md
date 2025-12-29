# compat.c

> 自动生成时间: 2025-10-25 12:52:31
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `compat.c`

---

# compat.c 技术文档

## 文件概述

`compat.c` 是 Linux 内核中用于提供 32 位系统调用兼容性支持的核心文件，主要运行在 64 位内核上。该文件实现了将 32 位用户空间程序发出的系统调用转换为内核内部 64 位数据结构和接口所需的适配逻辑，确保 32 位应用程序能够在 64 位系统上正常运行。其核心功能包括信号处理、资源使用统计（rusage）、CPU 亲和性设置、位图操作以及信号集转换等兼容层封装。

## 核心功能

### 主要函数

- `compat_sigprocmask`：32 位兼容版的 `sigprocmask` 系统调用，用于操作进程的信号掩码。
- `put_compat_rusage`：将内核的 `struct rusage` 转换为 32 位兼容格式并复制到用户空间。
- `compat_get_user_cpu_mask`：从用户空间读取 32 位 CPU 亲和性位图并转换为内核 `cpumask`。
- `compat_sched_setaffinity` / `compat_sched_getaffinity`：32 位兼容的 CPU 亲和性设置与获取系统调用。
- `get_compat_sigevent`：将 32 位 `sigevent` 结构从用户空间复制并转换为内核格式。
- `compat_get_bitmap` / `compat_put_bitmap`：在 32 位用户空间与 64 位内核之间安全地传输位图数据。
- `get_compat_sigset`：将 32 位信号集（`compat_sigset_t`）转换为内核内部的 `sigset_t`。

### 关键数据结构

- `compat_sigset_t`：32 位信号集表示。
- `compat_rusage`：32 位资源使用统计结构。
- `compat_sigevent`：32 位信号事件描述结构。
- `compat_ulong_t`：32 位无符号长整型（通常为 `u32`）。

## 关键实现

### 信号掩码处理（`compat_sigprocmask`）

该函数仅操作信号掩码的第一个字（32 位），通过 `compat_sig_setmask` 直接内存拷贝实现 `SIG_SETMASK` 行为。对于 `SIG_BLOCK` 和 `SIG_UNBLOCK`，则调用内核通用的 `sigaddsetmask` 和 `sigdelsetmask` 辅助函数。特别地，它会自动屏蔽 `SIGKILL` 和 `SIGSTOP`，因为这两个信号不可被阻塞。

### 位图转换（`compat_get_bitmap` / `compat_put_bitmap`）

由于 64 位内核中 `unsigned long` 为 64 位，而 32 位用户空间使用 32 位 `compat_ulong_t`，位图需进行高低位重组：
- **读取**：每两个 32 位值组合成一个 64 位内核值（低位在前，高位在后）。
- **写入**：将一个 64 位内核值拆分为两个 32 位值写回用户空间。
使用 `user_read_access_begin`/`user_write_access_end` 配合 `unsafe_get/put_user` 实现高效、安全的批量访问。

### 字节序处理（`get_compat_sigset`）

在大端（Big-Endian）架构上，32 位信号集的高低 32 位在内存中的排列与小端不同，需显式重组为 64 位内核信号字。小端架构可直接内存拷贝。

### CPU 亲和性兼容（`sched_setaffinity`/`getaffinity`）

- **设置**：通过 `compat_get_user_cpu_mask` 将用户传入的 32 位位图转换为内核 `cpumask`，再调用通用 `sched_setaffinity`。
- **获取**：先调用通用接口获取内核 `cpumask`，再通过 `compat_put_bitmap` 转换回 32 位格式返回给用户。返回长度为实际写入的字节数。

### 资源使用统计（`put_compat_rusage`）

逐字段将 64 位 `rusage` 中的时间（`tv_sec`/`tv_usec`）及其他统计值复制到 32 位结构体，确保字段对齐和截断安全，最后通过 `copy_to_user` 返回。

## 依赖关系

- **头文件依赖**：
  - `<linux/compat.h>`：提供兼容层宏定义和类型（如 `COMPAT_SYSCALL_DEFINE`）。
  - `<linux/uaccess.h>`：用户空间内存访问接口（`get_user`、`put_user` 等）。
  - `<linux/sched.h>`、`<linux/cpumask.h>`：调度和 CPU 亲和性相关 API。
  - `<linux/signal.h>`：信号处理核心接口。
  - `<linux/posix-timers.h>`：`sigevent` 相关定义。
- **内核模块依赖**：
  - 调度子系统（`kernel/sched/`）：`sched_setaffinity`/`getaffinity` 实现。
  - 信号子系统（`kernel/signal.c`）：信号掩码操作函数。
  - 内存管理：`GFP_KERNEL` 内存分配。
- **架构依赖**：通过 `__ARCH_WANT_SYS_SIGPROCMASK` 宏控制是否编译 `sigprocmask` 兼容实现，依赖 `__BIG_ENDIAN` 处理字节序差异。

## 使用场景

1. **32 位应用程序在 64 位内核上运行**：当 32 位 ELF 程序执行系统调用（如 `sigprocmask`、`sched_setaffinity`）时，内核通过此文件中的兼容层函数处理参数转换。
2. **跨架构二进制兼容**：在 x86_64、ARM64 等支持 32 位兼容模式的架构上，该文件是运行旧版 32 位软件的关键组件。
3. **系统调用拦截与转换**：安全模块（如 SELinux）或容器运行时可能依赖此兼容层正确解析 32 位进程的系统调用参数。
4. **性能监控工具**：32 位 `getrusage` 调用通过 `put_compat_rusage` 获取资源统计信息。
5. **实时/多线程应用**：32 位程序使用 `timer_create` 等 POSIX 定时器接口时，`sigevent` 结构通过 `get_compat_sigevent` 转换。