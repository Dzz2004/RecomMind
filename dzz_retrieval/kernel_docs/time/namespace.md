# time\namespace.c

> 自动生成时间: 2025-10-25 16:40:48
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `time\namespace.c`

---

# time/namespace.c 技术文档

## 1. 文件概述

`time/namespace.c` 实现了 Linux 内核中的 **时间命名空间（time namespace）** 功能，允许不同进程组拥有独立的时间视图。该机制主要用于容器化环境中，使容器内的进程能够看到与宿主机或其他容器不同的系统时间（特别是 `CLOCK_MONOTONIC` 和 `CLOCK_BOOTTIME` 等单调时钟）。时间命名空间通过偏移量（offset）机制实现，不影响真实硬件时钟，仅在用户空间通过 VDSO（虚拟动态共享对象）提供转换后的时间值。

## 2. 核心功能

### 主要函数

| 函数 | 功能描述 |
|------|--------|
| `do_timens_ktime_to_host()` | 将时间命名空间中的时间值转换回宿主机时间（减去偏移量），用于内核内部时间比较 |
| `clone_time_ns()` | 克隆一个时间命名空间，分配资源并初始化 VVAR 页面 |
| `copy_time_ns()` | 根据 `CLONE_NEWTIME` 标志决定是克隆还是复用现有时间命名空间 |
| `timens_setup_vdso_data()` | 在 VDSO 数据页中设置时间偏移量，供用户空间读取 |
| `find_timens_vvar_page()` | 为进程查找其所属时间命名空间的 VVAR 页面 |
| `timens_set_vvar_page()` | 初始化时间命名空间的 VVAR 页面（仅首次进入时执行） |
| `free_time_ns()` | 释放时间命名空间占用的资源 |
| `timens_commit()` | 在任务切换到新时间命名空间时提交配置（设置 VVAR 和 VDSO） |
| `timens_install()` | 安装新的时间命名空间到当前进程（需权限检查） |
| `timens_on_fork()` | 子进程 fork 时继承父进程的 `time_ns_for_children` |

### 关键数据结构

- `struct time_namespace`：时间命名空间的核心结构，包含：
  - `vvar_page`：用于 VDSO 的特殊内存页
  - `offsets`：`monotonic` 和 `boottime` 时钟的偏移量
  - `frozen_offsets`：标志位，表示偏移量是否已固化（防止重复初始化）
  - `user_ns`：所属的用户命名空间
  - `ucounts`：资源计数器，限制时间命名空间创建数量

- `struct timens_offsets`：存储 `CLOCK_MONOTONIC` 和 `CLOCK_BOOTTIME` 的偏移量（`timespec64` 格式）

- `struct timens_offset`：VDSO 中使用的偏移量结构（`sec` + `nsec`）

## 3. 关键实现

### 时间偏移转换机制
- `do_timens_ktime_to_host()` 负责将命名空间内的时间值（如定时器到期时间）转换为宿主机视角的时间。
- 对于 `CLOCK_MONOTONIC` 和 `CLOCK_BOOTTIME`，减去对应的偏移量。
- 若转换后时间小于 0，则视为已过期，返回 0。
- 转换结果被限制在 `[0, KTIME_MAX]` 范围内。

### VDSO 集成
- 时间命名空间通过 **VVAR 页面** 向用户空间暴露偏移量。
- 正常进程的 VDSO 布局：`VVAR → PVCLOCK → HVCLOCK`
- 时间命名空间进程的 VDSO 布局：`TIMENS → PVCLOCK → HVCLOCK → VVAR`
- `timens_setup_vdso_data()` 在 VVAR 页面中设置 `clock_mode = VDSO_CLOCKMODE_TIMENS` 并填充各时钟的偏移量。
- 用户空间 VDSO 代码根据 `clock_mode` 决定是否应用偏移。

### 偏移量初始化保护
- 使用全局 `offset_lock` 互斥锁确保 `vvar_page` 仅被初始化一次。
- `frozen_offsets` 标志位避免重复初始化，提高性能（快路径无锁）。

### 资源管理与权限控制
- 通过 `ucounts` 限制每个用户命名空间可创建的时间命名空间数量（防 DoS）。
- `timens_install()` 要求调用者在**目标命名空间**和**当前命名空间**均具备 `CAP_SYS_ADMIN` 权限。
- 仅允许单线程进程（`current_is_single_threaded()`）切换时间命名空间，避免多线程一致性问题。

### 进程继承模型
- 每个进程拥有两个时间命名空间指针：
  - `time_ns`：当前生效的时间命名空间
  - `time_ns_for_children`：子进程将继承的时间命名空间
- `timens_on_fork()` 确保子进程正确继承父进程的 `time_ns_for_children`

## 4. 依赖关系

| 依赖模块 | 用途 |
|---------|------|
| `<linux/user_namespace.h>` | 用户命名空间支持，用于权限隔离和资源计数 |
| `<linux/proc_ns.h>` | 命名空间 proc 接口（如 `/proc/PID/ns/time`） |
| `<vdso/datapage.h>` | VDSO 数据页结构定义 |
| `<linux/clocksource.h>` | 时钟源相关常量（如 `CS_BASES`） |
| `<linux/sched/*.h>` | 进程调度和 nsproxy 管理 |
| `<linux/cred.h>` | 凭据和权限检查（`ns_capable()`） |
| `<linux/mm.h>` | 内存管理（`alloc_page()`、`vm_area_struct`） |

## 5. 使用场景

1. **容器时间隔离**  
   容器运行时（如 LXC、systemd-nspawn）可通过 `unshare(CLONE_NEWTIME)` 创建独立时间视图，使容器内 `CLOCK_MONOTONIC` 从 0 开始计时，便于测试或迁移。

2. **系统时间回滚测试**  
   开发者可在时间命名空间中设置负偏移量，模拟系统时间回退场景，验证应用程序的健壮性。

3. **沙箱环境**  
   安全沙箱可限制进程看到的时间范围，防止基于时间的侧信道攻击。

4. **VDSO 优化路径**  
   用户空间通过 VDSO 直接读取偏移后的时间，无需系统调用，性能开销极低。

5. **命名空间组合**  
   时间命名空间通常与 PID、mount、user 等命名空间联合使用，构建完整的隔离环境。