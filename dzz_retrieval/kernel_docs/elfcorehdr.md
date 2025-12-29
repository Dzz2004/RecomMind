# elfcorehdr.c

> 自动生成时间: 2025-10-25 13:17:58
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `elfcorehdr.c`

---

# elfcorehdr.c 技术文档

## 1. 文件概述

`elfcorehdr.c` 是 Linux 内核中用于支持崩溃转储（crash dump）机制的关键文件之一。该文件主要负责解析并存储由崩溃内核（即发生 panic 的原始内核）通过 `kexec` 机制传递给捕获内核（capture kernel）的 ELF 核心转储头（ELF core header）的物理地址和大小。此信息用于后续在 `/proc/vmcore` 中构建完整的内存转储镜像，并被 `is_kdump_kernel()` 函数用于判断当前内核是否为 kdump 捕获内核。

## 2. 核心功能

### 全局变量

- **`elfcorehdr_addr`**  
  类型：`unsigned long long`  
  作用：存储崩溃内核所生成的 ELF 核心头在物理内存中的起始地址。初始值为 `ELFCORE_ADDR_MAX`，表示无效地址。该变量被导出（`EXPORT_SYMBOL_GPL`），供其他内核模块使用。

- **`elfcorehdr_size`**  
  类型：`unsigned long long`  
  作用：存储 ELF 核心头的大小（以字节为单位）。

### 内核启动参数处理函数

- **`setup_elfcorehdr(char *arg)`**  
  类型：`__init` 函数，通过 `early_param` 注册为内核启动参数处理器  
  作用：解析内核命令行参数 `elfcorehdr=`，从中提取 ELF 核心头的地址和大小。

## 3. 关键实现

### 参数解析逻辑

`setup_elfcorehdr()` 函数按照如下语法解析 `elfcorehdr=` 参数：

```
elfcorehdr=[size[KMG]@]offset[KMG]
```

- 若参数格式为 `offset`（如 `0x1000000`），则仅设置 `elfcorehdr_addr = offset`，`elfcorehdr_size` 保持为 0。
- 若参数格式为 `size@offset`（如 `0x1000@0x2000000`），则：
  - 首先调用 `memparse(arg, &end)` 解析 `size`，存入 `elfcorehdr_addr`（临时）；
  - 检测到 `@` 字符后，将该值赋给 `elfcorehdr_size`；
  - 再次调用 `memparse(end + 1, &end)` 解析 `offset`，作为真正的 `elfcorehdr_addr`。

该函数使用 `memparse()` 辅助函数支持带单位后缀（K、M、G）的内存大小解析。

### 早期参数注册

通过 `early_param("elfcorehdr", setup_elfcorehdr)` 将该参数处理函数注册为**早期启动参数**，确保在内核初始化早期（甚至在内存子系统完全初始化前）即可解析该参数，以便后续崩溃转储机制正确识别转储头位置。

### 变量作用域设计

`elfcorehdr_addr` 被置于 `CONFIG_CRASH_DUMP` 条件下（而非更窄的 `CONFIG_PROC_VMCORE`），因为除了 `/proc/vmcore` 使用外，`is_kdump_kernel()` 函数也依赖该变量判断当前是否为 kdump 内核（即是否从崩溃中恢复启动）。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/crash_dump.h>`：定义 `ELFCORE_ADDR_MAX` 和 `is_kdump_kernel()` 相关接口。
  - `<linux/init.h>`：提供 `__init` 和 `early_param` 宏。
  - `<linux/kernel.h>`：基础内核头文件。
  - `<linux/errno.h>`：错误码定义（如 `-EINVAL`）。
  - `<linux/export.h>`：用于 `EXPORT_SYMBOL_GPL`。

- **功能依赖**：
  - 依赖 `kexec` 机制：崩溃内核通过 `kexec` 加载捕获内核，并在启动参数中传递 `elfcorehdr=`。
  - 被 `fs/proc/vmcore.c` 使用：用于构建 `/proc/vmcore` 的 ELF 结构。
  - 被 `kernel/crash_dump.c` 中的 `is_kdump_kernel()` 使用：判断是否为 kdump 内核。

## 5. 使用场景

- **kdump 流程**：
  1. 主内核发生 panic；
  2. 通过 `kexec` 启动预先加载的捕获内核；
  3. 捕获内核启动时，内核命令行包含 `elfcorehdr=size@addr`；
  4. `setup_elfcorehdr()` 在早期初始化阶段解析该参数，设置 `elfcorehdr_addr` 和 `elfcorehdr_size`；
  5. 用户空间工具（如 `makedumpfile` 或 `crash`）通过读取 `/proc/vmcore` 获取完整内存转储，其 ELF 头信息即来源于此。

- **内核自检**：
  - `is_kdump_kernel()` 通过检查 `elfcorehdr_addr != ELFCORE_ADDR_MAX` 判断当前是否为 kdump 捕获内核，从而调整某些初始化行为（如跳过部分硬件初始化）。