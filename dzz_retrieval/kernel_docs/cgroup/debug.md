# cgroup\debug.c

> 自动生成时间: 2025-10-25 12:44:09
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cgroup\debug.c`

---

# cgroup/debug.c 技术文档

## 1. 文件概述

`cgroup/debug.c` 实现了一个专用于 cgroup 内核子系统调试的控制器（debug controller）。该控制器提供了一系列只读接口，用于暴露 cgroup 内部状态信息，包括任务计数、css_set（控制组子系统状态集合）结构、引用计数、层级关系、子系统掩码等。**该控制器仅用于内核开发和调试目的，其接口不稳定，可能随时变更或移除**。

## 2. 核心功能

### 主要函数

- **`debug_css_alloc()` / `debug_css_free()`**  
  分配和释放 debug 控制器的 `cgroup_subsys_state`（css）结构体。

- **`debug_taskcount_read()`**  
  返回指定 cgroup 中的任务数量。

- **`current_css_set_read()`**  
  显示当前进程所属的 `css_set` 地址、引用计数及其包含的所有子系统的 css 实例。

- **`current_css_set_refcount_read()`**  
  返回当前进程所属 `css_set` 的引用计数。

- **`current_css_set_cg_links_read()`**  
  列出当前进程所属 `css_set` 关联的所有 cgroup 及其根层级 ID。

- **`cgroup_css_links_read()`**  
  显示指定 cgroup 所有关联的 `css_set`，包括每个 `css_set` 的引用计数、任务列表、是否为 dead 状态、线程化关系等详细信息。

- **`cgroup_subsys_states_read()`**  
  列出指定 cgroup 中所有已启用子系统的 `css` 实例，包括其 ID、父 css ID 和在线计数。

- **`cgroup_masks_read()`**  
  显示 cgroup 的 `subtree_control` 和 `subtree_ss_mask` 掩码所启用的子系统列表。

- **`releasable_read()`**  
  判断该 cgroup 是否可被释放（即无任务且无在线子 cgroup）。

### 数据结构

- **`debug_legacy_files[]`**  
  为 cgroup v1 提供的调试文件接口数组。

- **`debug_files[]`**  
  为 cgroup v2 提供的调试文件接口数组（文件名略有简化）。

## 3. 关键实现

- **内存管理**：`debug_css_alloc()` 使用 `kzalloc()` 分配最小的 `css` 结构体，不包含额外数据，仅用于占位。
  
- **并发安全**：所有读取 `css_set` 或 cgroup 状态的函数均使用 `css_set_lock` 自旋锁和 RCU 机制保护，确保在遍历链表或访问共享结构时的数据一致性。

- **引用计数分析**：`cgroup_css_links_read()` 不仅打印 `css_set` 的引用计数，还计算“额外引用”（`refcount - nr_tasks`），并特别处理 `init_css_set` 的额外引用，帮助开发者识别潜在的引用泄漏。

- **线程化 cgroup 支持**：通过检查 `dom_cset` 和 `threaded_csets` 链表，清晰展示线程化 cgroup 中 `css_set` 的主从关系。

- **任务列表截断**：为避免输出过长，每个 `css_set` 最多显示 25 个任务 PID，超出部分以省略号和数量提示。

- **接口版本区分**：分别定义 `debug_legacy_files`（v1）和 `debug_files`（v2）两套文件接口，适配不同 cgroup 版本的命名规范。

## 4. 依赖关系

- **头文件依赖**：
  - `linux/ctype.h`、`linux/mm.h`、`linux/slab.h`：基础内核功能。
  - `"cgroup-internal.h"`：cgroup 内部核心数据结构和 API，如 `css_set`、`cgroup_subsys`、`cgroup_kn_lock_live()` 等。

- **内核子系统依赖**：
  - **cgroup 核心框架**：依赖 cgroup 的层级管理、css 生命周期、kernfs 文件系统接口。
  - **RCU 机制**：用于安全地读取 `task_css_set(current)`。
  - **进程管理**：通过 `current` 获取当前任务，使用 `task_pid_vnr()` 获取 PID。

## 5. 使用场景

- **内核开发调试**：开发者可通过挂载 debug controller，读取 `/sys/fs/cgroup/.../debug/` 下的文件，检查 cgroup 内部状态是否符合预期。
  
- **问题诊断**：
  - 通过 `releasable` 判断 cgroup 无法自动销毁的原因。
  - 通过 `css_links` 和 `current_css_set` 分析 `css_set` 引用计数异常或任务归属错误。
  - 通过 `masks` 验证子系统启用/禁用策略是否生效。

- **教学与理解**：帮助开发者理解 cgroup 的内部数据结构（如 `css_set`、`cgrp_cset_link`）及其相互关系。

> **注意**：该控制器默认不编译进生产内核，仅在启用 `CONFIG_CGROUP_DEBUG` 时可用，且其接口不保证向后兼容。