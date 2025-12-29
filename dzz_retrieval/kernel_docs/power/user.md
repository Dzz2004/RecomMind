# power\user.c

> 自动生成时间: 2025-10-25 15:28:21
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `power\user.c`

---

# power/user.c 技术文档

## 1. 文件概述

`power/user.c` 是 Linux 内核中实现用户空间与休眠（Hibernate）/恢复（Resume）功能交互的核心接口文件。该文件通过字符设备 `/dev/snapshot` 向用户空间提供对系统内存快照的读写能力，支持创建休眠镜像（保存系统状态）和从镜像恢复系统状态。它实现了软件休眠机制的用户态控制路径，是 hibernation 子系统的关键组成部分。

## 2. 核心功能

### 主要数据结构
- **`struct snapshot_data`**：保存当前快照操作的上下文状态，包括：
  - `handle`：快照操作句柄（`struct snapshot_handle`）
  - `swap`：使用的交换分区类型索引
  - `mode`：打开模式（`O_RDONLY` 表示休眠，`O_WRONLY` 表示恢复）
  - `frozen`：是否已冻结用户进程
  - `ready`：快照是否准备就绪
  - `platform_support`：是否启用平台特定的休眠支持（如 ACPI S4）
  - `free_bitmaps`：是否需要释放内存位图
  - `dev`：恢复所用的设备号

- **`static bool need_wait`**：标志是否需要等待设备探测完成（用于恢复流程）

### 主要函数
- **`snapshot_open()`**：设备打开函数，初始化快照上下文，根据打开模式（读/写）执行休眠或恢复的前期准备。
- **`snapshot_release()`**：设备关闭函数，清理资源，释放内存位图，解冻进程，发送 PM 通知。
- **`snapshot_read()`**：从内存快照中读取数据到用户空间（用于休眠时保存镜像）。
- **`snapshot_write()`**：从用户空间写入数据到内存快照（用于恢复时加载镜像）。
- **`snapshot_ioctl()`**：设备控制接口，支持多种休眠/恢复控制命令。
- **`snapshot_set_swap_area()`**：设置恢复时使用的交换区域（兼容 32/64 位系统调用）。
- **`is_hibernate_resume_dev()`**：判断指定设备是否为当前休眠恢复设备。

### 关键 ioctl 命令
- `SNAPSHOT_FREEZE`：冻结用户空间进程。
- `SNAPSHOT_UNFREEZE`：解冻用户空间进程。
- `SNAPSHOT_CREATE_IMAGE`：创建内存快照镜像（休眠）。
- `SNAPSHOT_ATOMIC_RESTORE`：原子性地从镜像恢复系统。
- `SNAPSHOT_FREE`：释放快照相关内存。
- `SNAPSHOT_PREF_IMAGE_SIZE` / `SNAPSHOT_GET_IMAGE_SIZE`：设置/获取镜像大小。
- `SNAPSHOT_AVAIL_SWAP_SIZE` / `SNAPSHOT_ALLOC_SWAP_PAGE`：管理交换空间分配。

## 3. 关键实现

### 休眠（Suspend-to-Disk）流程
1. 用户空间以 `O_RDONLY` 打开 `/dev/snapshot`。
2. 调用 `SNAPSHOT_FREEZE` 冻结所有用户进程。
3. 调用 `SNAPSHOT_CREATE_IMAGE` 创建内存快照，内核将可恢复的内存页信息组织成镜像。
4. 用户空间通过 `read()` 系统调用从设备读取镜像数据，并写入交换分区。
5. 系统关机。

### 恢复（Resume）流程
1. 启动时内核检测到休眠镜像，但用户空间需主动参与恢复。
2. 用户空间以 `O_WRONLY` 打开 `/dev/snapshot`。
3. 通过 `ioctl(SNAPSHOT_SET_SWAP_AREA)` 指定镜像所在的交换设备。
4. 用户空间从交换分区读取镜像数据，通过 `write()` 写入 `/dev/snapshot`。
5. 调用 `SNAPSHOT_FREEZE` 冻结当前进程（为恢复做准备）。
6. 调用 `SNAPSHOT_ATOMIC_RESTORE` 触发内核原子恢复，跳转回休眠时的执行上下文。

### 内存管理
- 使用 `create_basic_memory_bitmaps()` / `free_basic_memory_bitmaps()` 管理内存页的位图，标记哪些页需要保存/恢复。
- 通过 `swsusp_free()` 释放休眠专用的内存缓冲区。
- `alloc_swapdev_block()` 用于在休眠过程中分配交换页。

### 同步与锁机制
- 使用 `lock_system_sleep()` / `unlock_system_sleep()` 确保休眠操作的原子性。
- 通过 `mutex_trylock(&system_transition_mutex)` 防止并发的系统状态转换。
- `lock_device_hotplug()` 防止设备热插拔干扰休眠过程。

### 兼容性处理
- 通过 `in_compat_syscall()` 区分 32 位和 64 位系统调用，使用 `compat_resume_swap_area` 结构保证 ABI 兼容。

## 4. 依赖关系

- **`<linux/suspend.h>` / `power.h`**：休眠核心逻辑和数据结构定义。
- **`<linux/swap.h>` / `<linux/swapops.h>`**：交换子系统接口，用于管理休眠镜像的存储。
- **`<linux/freezer.h>`**：进程冻结/解冻机制。
- **`<linux/pm.h>`**：电源管理通知链（`pm_notifier_call_chain`）。
- **`<linux/miscdevice.h>`**：注册 `/dev/snapshot` 字符设备。
- **`<linux/uaccess.h>`**：用户空间内存访问（`copy_from_user` 等）。
- **`<linux/compat.h>`**：32/64 位系统调用兼容层。
- **`hibernate.c`**：依赖 `hibernate_acquire()` / `hibernate_release()` 管理休眠资源。

## 5. 使用场景

- **系统休眠（Hibernation）**：当用户执行 `systemctl hibernate` 或类似命令时，用户空间工具（如 `uswsusp` 或 `systemd-hibernate`) 通过此接口保存系统状态到交换分区。
- **系统恢复（Resume）**：在内核启动早期，initramfs 中的恢复工具（如 `resume` 脚本）通过此接口从交换分区加载镜像并触发恢复。
- **调试与测试**：开发人员可通过直接操作 `/dev/snapshot` 设备测试休眠/恢复逻辑。
- **定制休眠方案**：嵌入式或特殊用途系统可基于此接口实现自定义的休眠存储后端（如存储到文件而非交换分区）。