# power\power.h

> 自动生成时间: 2025-10-25 15:22:40
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `power\power.h`

---

# `power/power.h` 技术文档

## 1. 文件概述

`power/power.h` 是 Linux 内核电源管理子系统中的核心头文件，主要用于定义与**休眠（Hibernation）**和**挂起（Suspend）**相关的数据结构、宏、函数声明和配置选项。该文件为内核的系统级电源状态转换（特别是 S4 休眠状态）提供统一的接口抽象，同时支持架构无关的快照（snapshot）机制、内存位图管理、交换设备操作以及调试和测试功能。

## 2. 核心功能

### 主要数据结构

- **`struct swsusp_info`**  
  描述休眠镜像的元数据信息，包括内核版本、物理页数、CPU 数量、镜像大小等，按页对齐（`__aligned(PAGE_SIZE)`），用于在休眠/恢复过程中验证镜像兼容性。

- **`struct snapshot_handle`**  
  快照操作句柄，用于抽象镜像数据的读写过程。通过 `snapshot_read_next()` 和 `snapshot_write_next()` 实现对镜像的流式访问，屏蔽底层 PBE（Page Backup Entry）结构细节，便于未来格式演进。

### 关键宏定义

- **`power_attr` / `power_attr_ro`**  
  用于在 sysfs 中创建可读写或只读的电源属性文件（如 `/sys/power/state`）。

- **`PAGES_FOR_IO` / `SPARE_PAGES`**  
  定义休眠过程中保留的内存页数：前者（约 4MB）确保 I/O 操作不因缺页失败，后者（1MB）供设备驱动在 `.suspend()` 回调中分配内存。

- **休眠标志位（`SF_*`）**  
  定义镜像头中传递的控制标志，如 `SF_PLATFORM_MODE`（平台模式）、`SF_NOCOMPRESS_MODE`（禁用压缩）、`SF_CRC32_MODE`（启用 CRC32 校验）等。

- **测试级别枚举（`TEST_*`）**  
  支持分阶段挂起测试（如冻结进程、挂起设备、平台操作等），用于调试电源管理流程。

### 核心函数声明

- **休眠控制**  
  - `hibernation_snapshot()` / `hibernation_restore()`：执行休眠快照创建或恢复。
  - `hibernation_platform_enter()`：进入平台特定的休眠状态。
  - `hibernation_in_progress()`：判断是否处于休眠流程中。

- **快照操作**  
  - `snapshot_read_next()` / `snapshot_write_next()`：流式读写镜像数据。
  - `snapshot_get_image_size()`：获取镜像总大小。
  - `snapshot_additional_pages()`：计算指定内存区域额外所需的页数。

- **内存与交换管理**  
  - `create_basic_memory_bitmaps()` / `free_basic_memory_bitmaps()`：创建/释放用于跟踪可休眠内存的位图。
  - `alloc_swapdev_block()` / `free_all_swap_pages()`：在交换设备上分配/释放休眠镜像块。
  - `swsusp_read()` / `swsusp_write()`：从/向交换设备读写休眠镜像。

- **进程冻结**  
  - `suspend_freeze_processes()`：冻结用户空间进程和内核线程（带错误回滚）。

- **调试与辅助**  
  - `swsusp_show_speed()`：显示休眠/恢复的数据传输速率。
  - `pm_restrict_gfp_mask()` / `pm_restore_gfp_mask()`：限制/恢复内存分配掩码以避免休眠期间分配不可移动内存。

## 3. 关键实现

- **架构无关的休眠头处理**  
  通过 `CONFIG_ARCH_HIBERNATION_HEADER` 条件编译，允许架构层实现 `arch_hibernation_header_save()` 和 `arch_hibernation_header_restore()`，用于保存/验证架构特定数据（如寄存器状态），最大尺寸限制为 `MAX_ARCH_HEADER_SIZE`。

- **镜像保护机制**  
  在 `CONFIG_STRICT_KERNEL_RWX` 启用时，调用 `enable_restore_image_protection()` 确保恢复镜像的内存区域具有正确的执行权限。

- **流式镜像访问抽象**  
  `snapshot_handle` 机制将复杂的 PBE 链表操作封装为简单的字节流读写接口，使上层（如用户空间工具或存储驱动）无需了解镜像内部结构，提升可维护性。

- **内存预留策略**  
  通过 `PAGES_FOR_IO` 和 `SPARE_PAGES` 预留关键内存，防止休眠过程中因内存不足导致 I/O 或驱动回调失败，保障休眠流程的原子性。

- **错误安全的进程冻结**  
  `suspend_freeze_processes()` 在冻结失败时自动回滚（解冻已冻结任务），避免系统处于不一致状态。

## 4. 依赖关系

- **头文件依赖**  
  - `<linux/suspend.h>`：挂起/休眠状态定义。
  - `<linux/suspend_ioctls.h>`：休眠 ioctl 命令。
  - `<linux/freezer.h>`：进程冻结/解冻接口。
  - `<linux/cpu.h>` / `<linux/cpuidle.h>`：CPU 热插拔和空闲管理。
  - `<linux/utsname.h>`：内核版本信息。

- **模块依赖**  
  - **`kernel/power/snapshot.c`**：实现快照创建、内存位图、镜像读写等核心逻辑。
  - **`kernel/power/hibernate.c`**：休眠流程控制、平台交互。
  - **`kernel/power/suspend.c`**：挂起设备和进入低功耗状态。
  - **`kernel/power/swsusp.c`**：交换设备上的休眠镜像管理。
  - **架构特定代码**：通过 `arch_hibernation_header_*` 钩子集成。

- **配置依赖**  
  功能受多个 Kconfig 选项控制，如 `CONFIG_HIBERNATION`、`CONFIG_SUSPEND`、`CONFIG_PM_SLEEP_DEBUG`、`CONFIG_HIGHMEM` 等。

## 5. 使用场景

- **系统休眠（S4）**  
  当用户触发休眠（如 `echo disk > /sys/power/state`）时，内核调用 `hibernation_snapshot()` 创建内存镜像，通过 `swsusp_write()` 写入交换分区，关机后从镜像恢复。

- **挂起（S3）流程**  
  在 `suspend_devices_and_enter()` 中冻结进程、挂起设备、进入平台低功耗状态，恢复时逆向执行。

- **调试与测试**  
  通过 `pm_test_level` 设置测试级别，分阶段验证电源管理各环节（如仅测试冻结进程）；`suspend_test_start/finish` 用于性能分析。

- **用户空间交互**  
  通过 sysfs 属性（如 `image_size`、`resume`）配置休眠参数；通过 `snapshot_read_next()` 向用户空间工具（如 `uswsusp`）提供镜像数据流。

- **驱动兼容性保障**  
  预留 `SPARE_PAGES` 确保设备驱动在 `.suspend()` 回调中能安全分配内存，避免休眠失败。