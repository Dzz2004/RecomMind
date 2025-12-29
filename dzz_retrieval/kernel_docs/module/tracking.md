# module\tracking.c

> 自动生成时间: 2025-10-25 15:08:52
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `module\tracking.c`

---

# module/tracking.c 技术文档

## 1. 文件概述

`module/tracking.c` 实现了对已卸载但带有污染标记（tainted）的内核模块的跟踪机制。该功能用于记录那些在卸载时已被标记为“污染”（tainted）的模块信息，包括模块名称、污染标志类型以及重复卸载的次数。这些信息可用于内核调试、安全审计或故障分析，帮助开发者识别可能导致系统不稳定或不可信状态的模块行为。

## 2. 核心功能

### 数据结构
- `struct mod_unload_taint`（定义在 `internal.h` 中）：
  - `name`：模块名称（最多 `MODULE_NAME_LEN` 字节）
  - `taints`：模块的污染标志位掩码
  - `count`：该模块（同名且污染标志有交集）被卸载的次数
  - `list`：用于链入全局链表 `unloaded_tainted_modules`

### 全局变量
- `unloaded_tainted_modules`：全局 RCU 保护的链表头，存储所有已卸载的污染模块记录
- `mod_debugfs_root`：外部声明的 debugfs 根目录入口（由模块子系统提供）

### 主要函数
- `try_add_tainted_module(struct module *mod)`  
  尝试将带有污染标志的模块添加到跟踪列表中。若同名模块且污染标志有重叠，则仅递增计数；否则分配新条目并加入链表。

- `print_unloaded_tainted_modules(void)`  
  在内核日志中打印所有已跟踪的卸载污染模块信息，格式为：`模块名(污染标志):计数`。

- `unloaded_tainted_modules_seq_*` 系列函数（仅当 `CONFIG_DEBUG_FS` 启用时）  
  实现 debugfs 接口 `/sys/kernel/debug/modules/unloaded_tainted`，以 seq_file 方式暴露跟踪数据。

- `unloaded_tainted_modules_init(void)`  
  模块初始化函数，注册 debugfs 文件。

## 3. 关键实现

### 污染模块去重与计数逻辑
- 在 `try_add_tainted_module()` 中，通过遍历 `unloaded_tainted_modules` 链表，检查是否存在**同名**且**污染标志有交集**（`mod_taint->taints & mod->taints`）的条目。
- 若存在，则仅将 `count` 字段加一，避免重复记录相同污染行为。
- 若不存在，则分配新 `mod_unload_taint` 结构体，拷贝模块名和污染标志，并初始化 `count` 为 1，然后通过 `list_add_rcu()` 安全加入链表。

### 并发安全机制
- 所有链表遍历操作均使用 **RCU（Read-Copy-Update）** 机制保护：
  - 写操作（如 `list_add_rcu`）在持有 `module_mutex` 时执行（由 `module_assert_mutex_or_preempt()` 保证）
  - 读操作（如 `print_unloaded_tainted_modules` 和 debugfs 序列化函数）使用 `rcu_read_lock()` / `rcu_read_unlock()`
- `list_for_each_entry_rcu` 宏配合 `lockdep_is_held(&module_mutex)` 提供锁依赖检查，确保正确性。

### DebugFS 接口实现
- 使用标准 `seq_file` 接口实现高效、可分页的文件读取。
- `unloaded_tainted_modules_seq_start/next/stop` 封装了 RCU 读端临界区。
- `unloaded_tainted_modules_seq_show` 调用 `module_flags_taint()` 将污染位掩码转换为可读字符串（如 "P", "O", "E" 等）。

### 内存管理
- 动态分配 `mod_unload_taint` 结构体使用 `kmalloc(..., GFP_KERNEL)`，失败时返回 `-ENOMEM`。
- 条目一旦加入链表，其生命周期由 RCU 机制管理，但当前代码未实现显式释放（通常在系统关机或模块子系统清理时处理）。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/module.h>`：模块核心定义、`module_mutex`、污染标志相关 API
  - `<linux/rculist.h>`：RCU 安全的链表操作
  - `<linux/debugfs.h>`：debugfs 文件系统支持
  - `"internal.h"`：包含 `struct mod_unload_taint` 定义及 `module_flags_taint()` 声明

- **外部符号**：
  - `mod_debugfs_root`：由 `kernel/module.c` 导出，作为模块子系统的 debugfs 根目录
  - `module_flags_taint()`：在 `kernel/module.c` 中实现，用于将污染位转换为字符串

- **配置依赖**：
  - `CONFIG_DEBUG_FS`：控制是否编译 debugfs 接口

## 5. 使用场景

- **内核崩溃或错误诊断**：当系统出现异常时，可通过 `print_unloaded_tainted_modules()` 输出或 debugfs 文件查看历史上卸载的污染模块，辅助定位问题根源。
- **安全审计**：系统管理员可通过 `/sys/kernel/debug/modules/unloaded_tainted` 监控是否有加载过带污染标志（如专有模块、强制加载等）的模块，即使这些模块已被卸载。
- **内核测试与验证**：在自动化测试中，可验证模块污染行为是否被正确记录和跟踪。
- **模块生命周期分析**：结合其他跟踪机制，分析模块加载/卸载模式及其对系统可信状态的影响。