# power\hibernate.c

> 自动生成时间: 2025-10-25 15:21:06
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `power\hibernate.c`

---

# `power/hibernate.c` 技术文档

## 1. 文件概述

`power/hibernate.c` 是 Linux 内核中实现**休眠（Hibernation，又称 Suspend-to-Disk）**功能的核心源文件。该文件负责协调系统进入和退出休眠状态的全过程，包括冻结用户空间进程、保存内存镜像到磁盘（通常为交换分区）、关闭系统，以及在下次启动时从磁盘恢复内存状态并唤醒系统。它提供了平台无关的休眠控制逻辑，并通过 `platform_hibernation_ops` 接口支持特定硬件平台的定制化操作。

## 2. 核心功能

### 主要全局变量
- `nocompress`, `noresume`, `nohibernate`, `resume_wait`, `resume_delay`: 控制休眠行为的内核启动参数标志。
- `resume_file[256]`: 指定用于恢复的设备路径（默认为 `CONFIG_PM_STD_PARTITION`）。
- `swsusp_resume_device` / `swsusp_resume_block`: 解析后的恢复设备标识（设备号 + 起始扇区）。
- `in_suspend`: 标记系统是否正处于休眠流程中（使用 `__nosavedata` 避免被休眠镜像保存）。
- `hibernation_mode`: 当前休眠模式（如 `HIBERNATION_SHUTDOWN`, `HIBERNATION_PLATFORM` 等）。
- `freezer_test_done`: 用于调试，标记冻结测试是否完成。
- `hibernation_ops`: 指向平台特定休眠操作的回调函数结构体。
- `hibernate_atomic`: 原子计数器，用于确保休眠操作的互斥性。

### 主要函数
- **休眠控制接口**:
  - `hibernate_acquire()` / `hibernate_release()`: 获取/释放休眠操作权限（基于原子计数器）。
  - `hibernation_in_progress()`: 检查是否有休眠正在进行。
  - `hibernation_available()`: 判断当前系统是否允许休眠（检查安全锁定、secret memory 等限制）。
  - `hibernation_set_ops()`: 设置平台特定的休眠操作回调（导出符号）。
  - `system_entering_hibernation()`: 查询是否正在执行平台休眠（导出符号）。

- **平台操作封装**:
  - `platform_begin()`, `platform_end()`, `platform_pre_snapshot()`, `platform_leave()`, `platform_finish()`, `platform_pre_restore()`, `platform_restore_cleanup()`, `platform_recover()`: 封装对 `hibernation_ops` 中各回调函数的调用，处理平台模式开关逻辑。

- **辅助功能**:
  - `swsusp_show_speed()`: 计算并打印休眠/恢复过程中的 I/O 速度（如内存页保存/加载速率）。
  - `arch_resume_nosmt()` (弱符号): 架构相关函数，用于在恢复后禁用同步多线程（SMT）。

- **调试支持** (`CONFIG_PM_DEBUG`):
  - `hibernation_test()`: 在指定测试级别下模拟休眠延迟，用于验证恢复流程。

## 3. 关键实现

### 休眠流程控制
- 使用 `hibernate_atomic` 原子变量实现**单次休眠互斥**：`hibernate_acquire()` 尝试将计数器减 1（仅当值为 1 时成功），确保同一时间只有一个休眠操作进行。
- `hibernation_available()` 综合判断休眠可行性：需未设置 `nohibernate`、未被内核锁定（`LOCKDOWN_HIBERNATION`）、且无 `secretmem` 或 CXL 内存活动。

### 平台操作抽象
- 通过 `struct platform_hibernation_ops` 提供**平台无关的休眠框架**。该结构体包含完整的休眠生命周期回调（如 `begin`, `pre_snapshot`, `enter`, `pre_restore`, `leave` 等）。
- `hibernation_set_ops()` 在设置有效操作集时自动切换 `hibernation_mode` 为 `HIBERNATION_PLATFORM`；若取消设置则回退到 `HIBERNATION_SHUTDOWN`。
- 所有平台操作函数（如 `platform_pre_snapshot()`）均通过 `platform_mode` 参数和 `hibernation_ops` 指针进行条件调用，保证无平台支持时的兼容性。

### 调试与性能监控
- `swsusp_show_speed()` 利用高精度时间戳（`ktime_t`）计算操作耗时，并以 **KB/s 和 MB/s** 格式输出内存镜像处理速度，便于性能分析。
- `CONFIG_PM_DEBUG` 编译选项启用休眠测试模式：`hibernation_test()` 可在指定阶段插入延迟，模拟休眠后立即恢复，用于验证恢复路径。

### 安全与限制
- 集成内核安全机制：通过 `security_locked_down(LOCKDOWN_HIBERNATION)` 阻止在锁定状态下休眠。
- 检测特殊内存使用：`secretmem_active()` 和 `cxl_mem_active()` 确保敏感内存或 CXL 设备未激活时才允许休眠，防止数据泄露或状态不一致。

## 4. 依赖关系

- **头文件依赖**:
  - `<linux/suspend.h>`, `<linux/pm.h>`: 电源管理核心接口和数据结构。
  - `<linux/blkdev.h>`, `<linux/fs.h>`: 用于访问休眠镜像存储设备（块设备/文件系统）。
  - `<linux/freezer.h>`: 进程冻结/解冻机制。
  - `<linux/security.h>`: 内核安全锁定检查。
  - `<linux/secretmem.h>`, `<linux/cxl_mem.h>`: 特殊内存活动检测。
  - `"power.h"`: 本地电源管理私有头文件。

- **模块交互**:
  - **设备驱动**: 通过 `device_suspend()`/`device_resume()` 调用驱动的休眠/恢复回调。
  - **内存快照子系统** (`swsusp`): 依赖 `kernel/power/snapshot.c` 实现内存镜像的创建与恢复。
  - **交换子系统**: 休眠镜像通常写入交换分区，需与 `mm/swapfile.c` 协同。
  - **平台驱动**: 通过 `hibernation_set_ops()` 注册的平台驱动（如 ACPI）提供硬件特定操作。

## 5. 使用场景

- **系统休眠 (Suspend-to-Disk)**:
  - 用户执行 `echo disk > /sys/power/state` 时，内核调用此文件中的流程保存内存状态到磁盘并关机。
  - 下次开机时，引导加载程序（如 GRUB）检测到休眠镜像，内核通过 `resume=` 参数指定的设备加载镜像并恢复系统状态。

- **混合休眠 (Hybrid Sleep)**:
  - 结合 `suspend-to-ram` 和 `suspend-to-disk`，先休眠到内存，若电源失效则从磁盘恢复。

- **内核调试与测试**:
  - 通过 `pm_test_level` 和 `pm_test_delay` 参数测试休眠恢复路径的正确性。
  - 使用 `swsusp_show_speed()` 分析休眠/恢复性能瓶颈。

- **安全敏感环境**:
  - 在启用了内核锁定（Lockdown）或使用 `secretmem` 的系统中，自动禁用休眠功能以保障安全。