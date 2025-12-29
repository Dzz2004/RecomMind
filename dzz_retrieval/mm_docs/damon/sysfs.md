# damon\sysfs.c

> 自动生成时间: 2025-12-07 15:52:10
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `damon\sysfs.c`

---

# damon/sysfs.c 技术文档

## 1. 文件概述

`damon/sysfs.c` 是 Linux 内核中 DAMON（Data Access MONitor）子系统的 sysfs 接口实现文件。该文件通过 sysfs 提供用户空间可配置的接口，用于动态管理 DAMON 监控目标（如进程 PID）及其对应的内存区域（regions）。用户可通过标准文件系统操作（读/写）来设置监控目标数量、每个目标的 PID 以及其监控的虚拟地址范围（起始和结束地址），从而实现对 DAMON 行为的灵活控制。

## 2. 核心功能

### 主要数据结构
- `struct damon_sysfs_region`：表示一个内存监控区域，包含起始地址（`start`）和结束地址（`end`）。
- `struct damon_sysfs_regions`：表示一个目标进程的所有监控区域集合，包含区域数组和数量。
- `struct damon_sysfs_target`：表示一个 DAMON 监控目标，包含进程 PID 和对应的 regions 对象。
- `struct damon_sysfs_targets`：表示所有监控目标的集合，包含 targets 数组和数量。

### 主要函数
- **Region 层级**：
  - `damon_sysfs_region_alloc()`：分配并初始化 region 对象。
  - `start_show()` / `start_store()`：读取/写入 region 起始地址。
  - `end_show()` / `end_store()`：读取/写入 region 结束地址。
  - `damon_sysfs_region_release()`：释放 region 对象。

- **Regions 层级**：
  - `damon_sysfs_regions_alloc()`：分配 regions 对象。
  - `damon_sysfs_regions_add_dirs()`：根据指定数量动态创建 region 子目录。
  - `damon_sysfs_regions_rm_dirs()`：删除所有 region 子目录并释放资源。
  - `nr_regions_show()` / `nr_regions_store()`：读取/设置 regions 数量。

- **Target 层级**：
  - `damon_sysfs_target_alloc()`：分配 target 对象。
  - `damon_sysfs_target_add_dirs()`：为目标创建 regions 子目录。
  - `damon_sysfs_target_rm_dirs()`：删除目标的 regions 子目录。
  - `pid_target_show()` / `pid_target_store()`：读取/设置目标进程 PID。

- **Targets 层级**：
  - `damon_sysfs_targets_alloc()`：分配 targets 对象。
  - `damon_sysfs_targets_add_dirs()`：根据指定数量动态创建 target 子目录。
  - `damon_sysfs_targets_rm_dirs()`：删除所有 target 子目录并释放资源。

## 3. 关键实现

- **分层 sysfs 目录结构**：  
  实现了四层嵌套的 sysfs 目录结构：  
  `targets/` → `targets/<index>/` → `targets/<index>/regions/` → `targets/<index>/regions/<index>/`  
  每层通过 `kobject` 和 `kobj_type` 管理生命周期和属性操作。

- **动态目录管理**：  
  通过写入 `nr_regions` 或上层 targets 的数量，动态创建或销毁对应数量的子目录。例如，向 `targets/nr_targets` 写入 `3` 会创建 `0/`、`1/`、`2/` 三个 target 目录。

- **并发控制**：  
  在修改 regions 数量时使用全局互斥锁 `damon_sysfs_lock`（定义在 `sysfs-common.h` 中），防止并发修改导致状态不一致。

- **内存安全**：  
  所有分配均使用 `kzalloc` 初始化，并在失败路径中进行完整的资源回滚（如 `damon_sysfs_regions_add_dirs` 失败时调用 `damon_sysfs_regions_rm_dirs` 清理已分配对象）。

- **属性权限**：  
  所有 sysfs 属性均设置为 `0600`（仅 root 可读写），确保安全性。

## 4. 依赖关系

- **内部依赖**：
  - `sysfs-common.h`：提供全局锁 `damon_sysfs_lock` 和通用 sysfs 操作辅助函数。
  - `damon.h`（间接）：使用 `struct damon_addr_range` 定义内存区域。

- **内核核心依赖**：
  - `<linux/kobject.h>`：提供 kobject 基础设施（通过 `sysfs-common.h` 间接包含）。
  - `<linux/slab.h>`：提供内存分配函数 `kzalloc`、`kmalloc_array`。
  - `<linux/pid.h>` 和 `<linux/sched.h>`：用于进程相关操作（尽管当前代码未直接使用，但为未来扩展预留）。

## 5. 使用场景

- **DAMON 配置**：  
  用户空间工具（如 `damo`）通过写入 sysfs 文件配置 DAMON 监控目标。例如：
  ```bash
  echo 1 > /sys/kernel/mm/damon/targets/nr_targets
  echo 1234 > /sys/kernel/mm/damon/targets/0/pid_target
  echo 2 > /sys/kernel/mm/damon/targets/0/regions/nr_regions
  echo 0x100000 > /sys/kernel/mm/damon/targets/0/regions/0/start
  echo 0x200000 > /sys/kernel/mm/damon/targets/0/regions/0/end
  ```

- **动态调整监控范围**：  
  在 DAMON 运行时，可动态增减监控目标或修改内存区域，无需重启内核模块。

- **调试与监控**：  
  通过读取 sysfs 文件验证当前 DAMON 配置状态，辅助调试内存访问模式分析任务。