# tsacct.c

> 自动生成时间: 2025-10-25 17:42:02
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `tsacct.c`

---

# tsacct.c 技术文档

## 1. 文件概述

`tsacct.c` 是 Linux 内核中实现任务统计（taskstats）接口下系统记账（accounting）功能的核心文件。它负责收集进程/任务的资源使用信息，包括基本记账（basic accounting）和扩展记账（extended accounting）两类数据。这些数据通过 `taskstats` 接口暴露给用户空间，用于系统监控、资源审计和性能分析等用途。

## 2. 核心功能

### 主要函数

- **`bacct_add_tsk()`**  
  填充任务的基本记账信息到 `struct taskstats` 结构体中，包括进程 ID、父进程 ID、用户/组 ID、CPU 时间、启动时间、退出码、调度策略、nice 值、缺页次数、命令名等。

- **`xacct_add_tsk()`**（仅当 `CONFIG_TASK_XACCT` 启用时）  
  填充任务的扩展记账信息，包括内存使用积分（RSS/VM）、I/O 字节数、系统调用次数等。

- **`acct_update_integrals()`**（仅当 `CONFIG_TASK_XACCT` 启用时）  
  在中断上下文中安全地更新任务的内存使用积分（RSS 和虚拟内存的时间积分）。

- **`acct_account_cputime()`**（仅当 `CONFIG_TASK_XACCT` 启用时）  
  在已知 CPU 时间更新后，直接调用内部函数更新内存积分，避免重复获取时间。

- **`acct_clear_integrals()`**（仅当 `CONFIG_TASK_XACCT` 启用时）  
  清除任务结构体中的内存积分字段，通常在进程创建或复用时调用。

### 关键数据结构

- **`struct taskstats`**  
  用户空间通过 netlink 接口获取的统计信息结构体，包含 `ac_*` 前缀的各类记账字段。

- **`struct task_struct` 中的扩展字段**（仅当 `CONFIG_TASK_XACCT` 启用时）：
  - `acct_rss_mem1`：RSS 内存使用的时间积分（单位：页·纳秒 / 1024）
  - `acct_vm_mem1`：虚拟内存使用的时间积分（单位：页·纳秒 / 1024）
  - `acct_timexpd`：上次更新积分时的累计 CPU 时间（纳秒）

## 3. 关键实现

### 基本记账实现细节

- **时间计算**：
  - `ac_etime`：任务自启动以来的经过时间（微秒）。
  - `ac_tgetime`：整个线程组自组长启动以来的经过时间（微秒）。
  - `ac_btime` / `ac_btime64`：任务启动的绝对时间（Unix 时间戳），前者限制为 32 位以兼容旧接口。

- **身份与关系信息**：
  - 使用 `from_kuid_munged()` 和 `from_kgid_munged()` 将内核 UID/GID 映射到指定用户命名空间。
  - 父进程 ID（`ac_ppid`）通过 RCU 读取 `real_parent`，并在进程已退出时设为 0。

- **CPU 时间**：
  - 使用 `task_cputime()` 获取任务及其子线程的累计用户态和内核态 CPU 时间（纳秒）。
  - 同时提供原始时间和按 CPU 频率缩放后的时间（`ac_utimescaled` / `ac_stimescaled`）。

- **退出与特权标志**：
  - 根据任务标志（如 `PF_EXITING`、`PF_SUPERPRIV` 等）设置 `ac_flag` 中的对应位（`AXSIG`、`ASU` 等）。

### 扩展记账实现细节（`CONFIG_TASK_XACCT`）

- **内存积分算法**：
  - 通过 `__acct_update_integrals()` 定期累积 `RSS × 时间` 和 `VM × 时间`。
  - 积分单位为“页·纳秒”，右移 10 位（即除以 1024）防止溢出。
  - 最终在 `xacct_add_tsk()` 中转换为 **MB·微秒**（通过 `PAGE_SIZE / (1000 * KB)`）。

- **高水位内存统计**：
  - 从 `mm_struct` 中获取历史最高 RSS 和 VM 值，并转换为 KB 单位。

- **I/O 统计**：
  - 从 `task_struct->ioac` 获取字符级和字节级的读写统计。
  - 使用 `KB_MASK` 对结果向下对齐到 KB 边界（即清除低 10 位）。
  - 若未启用 `CONFIG_TASK_IO_ACCOUNTING`，则 I/O 字节字段置零。

- **中断安全更新**：
  - `acct_update_integrals()` 使用 `local_irq_save/restore` 禁用本地中断，确保在中断上下文中安全更新。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/tsacct_kern.h>`：定义 `taskstats` 结构和相关接口。
  - `<linux/acct.h>`：提供记账相关的常量和类型。
  - `<linux/sched/*.h>`：访问任务调度、CPU 时间、凭证等信息。
  - `<linux/mm.h>`：访问内存管理结构（如 `mm_struct`）。
  - `<linux/jiffies.h>` 和 `<linux/kernel.h>`：时间转换和基础宏。

- **配置依赖**：
  - 基本记账功能始终编译。
  - 扩展记账功能（`xacct_add_tsk` 及相关函数）依赖 `CONFIG_TASK_XACCT`。
  - I/O 字节统计依赖 `CONFIG_TASK_IO_ACCOUNTING`。

- **与其他子系统交互**：
  - **调度子系统**：通过 `task_cputime()` 获取 CPU 时间。
  - **内存管理子系统**：通过 `get_task_mm()` 和 `get_mm_hiwater_*` 获取内存使用情况。
  - **用户命名空间**：通过 `user_ns` 参数进行 UID/GID 映射。
  - **进程管理**：访问 `task_struct` 的各种字段（如 `start_time`、`exit_code`、`flags` 等）。

## 5. 使用场景

- **用户空间监控工具**：如 `nmon`、`atop`、`sadc` 等通过 taskstats netlink 接口获取进程资源使用详情。
- **作业调度系统**：HPC 或容器平台（如 Slurm、Kubernetes）利用扩展记账数据进行资源配额和计费。
- **系统审计**：记录进程的 CPU、内存、I/O 消耗，用于安全分析或性能瓶颈定位。
- **内核自身记账**：在进程退出或通过 `TASKSTATS_CMD_ATTR_PID` 查询时，填充并返回 `taskstats` 数据。
- **cgroup v1/v2 集成**：部分记账数据可被 cgroup 控制器复用或聚合。