# params.c

> 自动生成时间: 2025-10-25 15:15:19
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `params.c`

---

# params.c 技术文档

## 1. 文件概述

`params.c` 是 Linux 内核中用于解析内核命令行参数（kernel command line）和模块参数（module parameters）的核心辅助文件。它提供了一套通用的参数解析框架，支持从字符串形式的参数值转换为内核内部数据类型，并允许注册自定义参数处理函数。该文件实现了参数的设置、获取、内存管理、安全检查以及未知参数的回调处理机制，是内核启动参数和模块参数系统的基础组件。

## 2. 核心功能

### 主要函数

- `parameq(const char *a, const char *b)` / `parameqn(...)`：比较两个参数名是否相等，将 `-` 视为 `_`（兼容命令行习惯）。
- `parse_one(...)`：解析单个参数（如 `foo=bar`），在参数表中查找匹配项并调用其 `set` 操作。
- `parse_args(...)`：解析完整的参数字符串（如 `"foo=bar,baz=1"`），按逗号或空格分隔，逐个调用 `parse_one`。
- `param_set_*` / `param_get_*` 系列函数：为标准数据类型（byte、int、ulong 等）提供参数设置和获取操作。
- `param_set_charp` / `param_get_charp` / `param_free_charp`：处理字符串类型参数，支持动态内存分配与释放。
- `param_set_bool` / `param_get_bool`：处理布尔类型参数，支持 `y/n/Y/N/0/1` 等输入格式。
- `param_check_unsafe(...)`：检查参数是否为“危险”或“硬件相关”，并在安全锁定（lockdown）模式下限制访问。

### 主要数据结构

- `struct kernel_param`：描述一个内核参数，包含名称、操作函数集（`ops`）、参数地址（`arg`）、所属模块（`mod`）和安全标志（`flags`）。
- `struct kernel_param_ops`：定义参数的操作接口，包括 `set`（设置）、`get`（获取）和可选的 `free`（释放）函数。
- `struct kmalloced_param`：用于跟踪通过 `kmalloc` 分配的字符串参数内存，便于统一释放。

### 宏定义

- `STANDARD_PARAM_DEF(name, type, format, strtolfn)`：用于快速定义标准类型参数的 `set`/`get` 函数和 `ops` 结构体。

## 3. 关键实现

### 参数名等价处理
函数 `dash2underscore()` 将连字符 `-` 转换为下划线 `_`，使得命令行中 `foo-bar=1` 可以匹配内核中名为 `foo_bar` 的参数，提升用户友好性。

### 内存管理机制
对于字符串参数（`charp` 类型），使用 `kmalloced_param` 链表跟踪所有动态分配的内存。在早期启动阶段（slab 分配器不可用时），直接使用命令行字符串指针；后期则分配新内存并复制内容。`maybe_kfree_parameter()` 在参数重设或模块卸载时安全释放内存。

### 并发与锁机制
在 `CONFIG_SYSFS` 启用时，使用互斥锁（`param_lock` 或模块私有 `param_lock`）保护参数设置操作，防止并发修改。`check_kparam_locked()` 在调试模式下验证锁状态。

### 安全限制
通过 `param_check_unsafe()` 检查参数标志：
- 若参数标记为 `KERNEL_PARAM_FL_HWPARAM` 且系统处于 `LOCKDOWN_MODULE_PARAMETERS` 锁定状态，则拒绝设置（返回 `-EPERM`）。
- 若参数标记为 `KERNEL_PARAM_FL_UNSAFE`，则设置时打印警告并污染内核（`add_taint(TAINT_USER)`）。

### 参数解析流程
`parse_args()` 使用 `next_arg()` 拆分参数字符串，对每个 `param=val` 调用 `parse_one()`。若未找到匹配参数且提供了 `unknown` 回调，则交由回调处理；否则报错。支持以 `--` 终止解析。

### 标准类型支持
通过 `STANDARD_PARAM_DEF` 宏自动生成多种整数类型（byte/short/int/long/ulong/ullong/hexint）的参数操作函数，统一使用 `kstrto*` 系列函数进行字符串到数值的转换。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/kernel.h>`：基础内核 API
  - `<linux/kstrtox.h>`：字符串转数值函数（`kstrtoull` 等）
  - `<linux/module.h>` / `<linux/moduleparam.h>`：模块参数相关定义
  - `<linux/security.h>`：安全锁定（lockdown）检查
  - `<linux/slab.h>`：内存分配（`kmalloc`/`kfree`）
  - `<linux/ctype.h>`：字符处理（`skip_spaces` 等）

- **配置依赖**：
  - `CONFIG_SYSFS`：启用参数锁机制
  - `CONFIG_MODULES`：区分内置参数与模块参数的锁

- **导出符号**：
  - 所有 `param_set_*`、`param_get_*`、`param_ops_*` 均通过 `EXPORT_SYMBOL` 导出，供模块使用。
  - `param_set_uint_minmax` 通过 `EXPORT_SYMBOL_GPL` 导出，用于带范围检查的无符号整数参数。

## 5. 使用场景

- **内核启动参数解析**：在 `start_kernel()` 阶段，通过 `parse_args()` 解析 `boot_command_line`，设置内核全局变量（如 `initcall_debug`、`loglevel` 等）。
- **内核模块参数处理**：模块加载时（`init_module` 系统调用），解析用户传入的参数字符串，调用对应参数的 `set` 函数初始化模块变量。
- **sysfs 参数接口**：当 `CONFIG_SYSFS` 启用时，模块参数会暴露在 `/sys/module/<modname>/parameters/` 下，读写操作分别调用 `get` 和 `set` 函数。
- **动态参数调整**：运行时可通过 `sysfs` 或 `modprobe` 修改模块参数值，触发 `param_set_*` 函数执行。
- **安全敏感系统**：在启用了内核锁定（lockdown）的系统中，阻止用户空间修改关键硬件参数，增强系统安全性。