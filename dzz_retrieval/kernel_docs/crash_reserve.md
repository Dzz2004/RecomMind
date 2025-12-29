# crash_reserve.c

> 自动生成时间: 2025-10-25 12:57:30
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `crash_reserve.c`

---

# crash_reserve.c 技术文档

## 1. 文件概述

`crash_reserve.c` 是 Linux 内核中用于解析和处理 `crashkernel=` 内核命令行参数的核心实现文件。该文件的主要功能是根据用户在启动参数中指定的内存预留策略，计算并返回用于 kdump 机制的崩溃内核（crash kernel）所需的内存大小和基地址。此预留内存区域在系统发生内核崩溃时，供第二个内核（即 crash kernel）加载并执行内存转储（dump）操作。

## 2. 核心功能

### 数据结构

- **`crashk_res`**: 全局 `struct resource`，表示主崩溃内核预留内存区域，类型为 `IORESOURCE_SYSTEM_RAM`，描述符为 `IORES_DESC_CRASH_KERNEL`。
- **`crashk_low_res`**: 全局 `struct resource`，用于某些架构（如 x86_64）中需要额外预留的低位内存区域（通常用于 32 位兼容或 DMA）。

### 主要函数

- **`parse_crashkernel_mem()`**: 解析扩展格式的 `crashkernel=ramsize-range:size[@offset]` 命令行。
- **`parse_crashkernel_simple()`**: 解析传统简单格式 `crashkernel=size[@offset]`。
- **`parse_crashkernel_suffix()`**: 解析带后缀的格式，如 `crashkernel=size,high` 或 `crashkernel=size,low`。
- **`get_last_crashkernel()`**: 在命令行中查找最后一个匹配的 `crashkernel=` 参数（支持后缀过滤）。
- **`__parse_crashkernel()`**: 内部通用解析入口，根据是否存在冒号自动选择解析策略。
- **`parse_crashkernel()`**: **对外公开的主入口函数**，由架构相关代码调用，支持普通模式和 `high/low` 模式。

## 3. 关键实现

### 命令行格式支持

该文件支持三种 `crashkernel=` 参数格式：

1. **简单格式**：`crashkernel=size[@offset]`  
   直接指定预留大小和可选偏移。

2. **内存范围格式**：`crashkernel=ramsize-range:size[@offset]`  
   根据系统总内存（`system_ram`）落在哪个区间来动态选择预留大小。例如：  
   `crashkernel=512M-2G:64M,2G-:128M`

3. **后缀格式（仅当 `CONFIG_ARCH_HAS_GENERIC_CRASHKERNEL_RESERVATION` 启用时）**：
   - `crashkernel=size,high`：指定高位内存预留大小。
   - `crashkernel=size,low`：指定低位内存预留大小（若未指定，默认使用 `DEFAULT_CRASH_KERNEL_LOW_SIZE`）。

### 解析逻辑流程

- `parse_crashkernel()` 首先尝试解析标准格式。
- 若失败且架构支持 `high/low` 模式，则尝试解析 `crashkernel=,high` 和 `crashkernel=,low`。
- 使用 `get_last_crashkernel()` 确保使用命令行中**最后一个**有效的 `crashkernel=` 参数，避免早期参数被覆盖。
- 在范围匹配模式中，对 `system_ram` 向上舍入到 128MB 边界，以兼容固件保留内存导致的物理内存与系统可见内存不一致问题。

### 内存校验

- 所有解析出的 `crash_size` 必须大于 0 且小于 `total_mem`（舍入后的系统内存）。
- 地址范围必须满足 `end > start`。
- 命令行语法错误（如缺少 `:`、`-` 或非法字符）会返回 `-EINVAL` 并打印警告。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/kexec.h>`：kexec 和 crash kernel 核心接口。
  - `<linux/memblock.h>`：底层内存管理，用于后续内存预留。
  - `<linux/resource.h>`（隐含）：`struct resource` 定义。
  - `<asm/sections.h>`：内核段信息。
  - `"kexec_internal.h"` 和 `"kallsyms_internal.h"`：kexec 内部实现。
- **配置依赖**：
  - `CONFIG_KEXEC`：kexec 功能启用。
  - `CONFIG_ARCH_HAS_GENERIC_CRASHKERNEL_RESERVATION`：决定是否支持 `high/low` 后缀模式（如 x86、ARM64 等架构启用）。
- **架构交互**：该文件提供通用解析逻辑，由各架构的 `setup_arch()` 或类似初始化函数调用 `parse_crashkernel()`，并将结果用于 `memblock_reserve()` 或设置 `crashk_res` 资源。

## 5. 使用场景

- **kdump 机制初始化**：在内核启动早期（`__init` 阶段），解析 `crashkernel=` 参数，确定为崩溃转储预留的物理内存区域。
- **多格式兼容**：支持从旧版简单参数到新版动态范围参数的平滑过渡，确保不同发行版和用户配置的兼容性。
- **高低内存分离架构**：在 64 位系统中，当 crash kernel 需要同时使用高位内存（主内核镜像）和低位内存（用于 32 位驱动或旧设备 DMA）时，通过 `high/low` 后缀分别指定两部分大小。
- **资源注册**：解析结果最终用于填充 `crashk_res` 和 `crashk_low_res`，供 `/proc/iomem` 显示，并在 kexec 加载 crash kernel 时作为可用内存范围依据。