# power\wakelock.c

> 自动生成时间: 2025-10-25 15:29:10
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `power\wakelock.c`

---

# `power/wakelock.c` 技术文档

## 1. 文件概述

`power/wakelock.c` 实现了 Linux 内核中面向用户空间的 **wakelock（唤醒锁）机制**，允许用户空间程序通过 sysfs 接口创建、激活和释放唤醒锁，以防止系统在特定任务执行期间进入低功耗状态（如 suspend）。该实现借鉴了 Android 系统中的 wakelock 接口，但基于标准 Linux 内核的 `wakeup_source` 基础设施，提供更安全、可配置的用户空间电源管理能力。

## 2. 核心功能

### 主要数据结构

- **`struct wakelock`**  
  表示一个用户空间可操作的唤醒锁对象：
  - `name`：唤醒锁名称（用户指定）
  - `node`：用于在红黑树 `wakelocks_tree` 中组织所有 wakelock
  - `ws`：指向内核 `wakeup_source` 对象，实际执行电源管理逻辑
  - `lru`（条件编译）：用于垃圾回收（GC）机制的 LRU 链表节点（当 `CONFIG_PM_WAKELOCKS_GC` 启用时）

### 主要函数

- **`pm_show_wakelocks(char *buf, bool show_active)`**  
  将当前所有（活跃或非活跃）wakelock 名称输出到缓冲区，供 sysfs 读取（如 `/sys/power/wake_lock` 或 `/sys/power/wake_unlock`）。

- **`pm_wake_lock(const char *buf)`**  
  用户空间通过写入 `/sys/power/wake_lock` 触发此函数，用于**获取**指定名称的 wakelock。支持可选超时参数（单位：纳秒）。

- **`pm_wake_unlock(const char *buf)`**  
  用户空间通过写入 `/sys/power/wake_unlock` 触发此函数，用于**释放**指定名称的 wakelock。

- **`wakelock_lookup_add(const char *name, size_t len, bool add_if_not_found)`**  
  在全局红黑树中查找或创建 wakelock 对象，是 `pm_wake_lock` 和 `pm_wake_unlock` 的核心辅助函数。

- **`__wakelocks_gc(struct work_struct *work)`**（条件编译）  
  垃圾回收工作函数，定期清理长时间未使用且非活跃的 wakelock 对象（当 `CONFIG_PM_WAKELOCKS_GC` 启用时）。

### 辅助机制

- **数量限制**：通过 `CONFIG_PM_WAKELOCKS_LIMIT` 控制系统中 wakelock 的最大数量。
- **LRU 管理**：通过 `wakelocks_lru_add` / `wakelocks_lru_most_recent` 维护最近使用顺序。
- **自动回收**：通过 `wakelocks_gc()` 触发异步 GC 工作队列。

## 3. 关键实现

### 红黑树管理
所有 `wakelock` 对象通过名称作为键，存储在全局红黑树 `wakelocks_tree` 中，确保 O(log n) 时间复杂度的查找、插入和删除操作。

### 唤醒源集成
每个 `wakelock` 封装一个 `wakeup_source`（通过 `wakeup_source_register()` 创建），实际的电源阻止逻辑由内核 PM 子系统的 `wakeup_source` 机制处理：
- `__pm_stay_awake(ws)`：永久保持唤醒（直到显式释放）
- `__pm_wakeup_event(ws, timeout_ms)`：带超时的唤醒
- `__pm_relax(ws)`：释放唤醒锁

### 安全与权限控制
- 仅具备 `CAP_BLOCK_SUSPEND` 能力的进程可操作 wakelock（防止普通用户滥用导致无法休眠）。
- 名称解析严格处理空格和换行符，防止注入或解析错误。

### 垃圾回收机制（可选）
当启用 `CONFIG_PM_WAKELOCKS_GC`：
- 每次访问 wakelock 时将其移至 LRU 链表头部（`wakelocks_lru_most_recent`）。
- 每进行 `WL_GC_COUNT_MAX`（默认 100）次操作后，调度 GC 工作。
- GC 遍历 LRU 链表（从最旧开始），删除满足以下条件的对象：
  - 非活跃（`!active`）
  - 空闲时间超过 `WL_GC_TIME_SEC`（默认 300 秒）

### 数量限制（可选）
当 `CONFIG_PM_WAKELOCKS_LIMIT > 0` 时，系统维护 `number_of_wakelocks` 计数器，防止用户空间创建过多 wakelock 耗尽内存。

## 4. 依赖关系

- **内核头文件**：
  - `<linux/wakeup_source.h>`（通过 `"power.h"` 间接包含）：提供 `wakeup_source` 相关 API
  - `<linux/sysfs.h>`：通过 `sysfs_emit_at` 实现 sysfs 输出
  - `<linux/workqueue.h>`：用于 GC 异步任务调度
  - `<linux/rbtree.h>`：红黑树数据结构支持
  - `<linux/capability.h>`：权限检查

- **内核子系统**：
  - **电源管理 (PM) 子系统**：依赖 `wakeup_source` 基础设施实现实际的 suspend 阻止逻辑。
  - **sysfs**：通过 sysfs 文件（如 `/sys/power/wake_lock`）暴露用户接口。
  - **内存管理**：使用 `kzalloc`/`kstrndup`/`kfree` 管理动态内存。

- **配置选项**：
  - `CONFIG_PM_WAKELOCKS`：主开关
  - `CONFIG_PM_WAKELOCKS_LIMIT`：限制最大数量
  - `CONFIG_PM_WAKELOCKS_GC`：启用自动垃圾回收

## 5. 使用场景

- **Android 兼容层**：为基于 Android 的系统提供标准 Linux 内核上的 wakelock 支持，无需修改用户空间应用。
- **用户空间电源控制**：允许特权应用（如媒体播放器、下载管理器）在执行关键任务时阻止系统休眠。
- **调试与监控**：通过读取 `/sys/power/wake_lock` 查看当前活跃的 wakelock，辅助电源问题诊断。
- **资源受限设备**：通过 `CONFIG_PM_WAKELOCKS_LIMIT` 和 GC 机制防止内存泄漏，适用于嵌入式或移动设备。