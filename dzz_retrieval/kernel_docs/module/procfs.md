# module\procfs.c

> 自动生成时间: 2025-10-25 15:05:15
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `module\procfs.c`

---

# module/procfs.c 技术文档

## 1. 文件概述

`module/procfs.c` 是 Linux 内核中用于在 `/proc/modules` 文件中导出已加载内核模块信息的实现文件。该文件通过 procfs 接口向用户空间提供模块名称、大小、引用计数、依赖关系、加载状态、内存地址以及污染标志等关键信息，是内核模块管理与调试的重要组成部分。

## 2. 核心功能

### 主要函数

- `print_unload_info(struct seq_file *m, struct module *mod)`  
  根据是否启用 `CONFIG_MODULE_UNLOAD` 配置，输出模块的引用计数和依赖模块列表，或占位符。

- `m_start(struct seq_file *m, loff_t *pos)`  
  seq_file 迭代器的起始函数，获取模块列表的互斥锁并定位起始位置。

- `m_next(struct seq_file *m, void *p, loff_t *pos)`  
  seq_file 迭代器的下一个元素函数。

- `m_stop(struct seq_file *m, void *p)`  
  seq_file 迭代器的结束函数，释放模块列表互斥锁。

- `module_total_size(struct module *mod)`  
  计算模块所有内存段（如代码、只读数据、可写数据等）的总大小。

- `m_show(struct seq_file *m, void *p)`  
  格式化输出单个模块的详细信息到 seq_file。

- `modules_open(struct inode *inode, struct file *file)`  
  打开 `/proc/modules` 文件时的回调，初始化 seq_file 并根据权限决定是否隐藏内核地址。

- `proc_modules_init(void)`  
  模块初始化函数，注册 `/proc/modules` 条目。

### 主要数据结构

- `modules_op`：`seq_operations` 结构体，定义了遍历模块列表的迭代器操作。
- `modules_proc_ops`：`proc_ops` 结构体，定义了 `/proc/modules` 文件的文件操作接口。

## 3. 关键实现

### 模块信息格式化输出
`m_show()` 函数按照固定格式输出每行模块信息：
```
<name> <total_size> <refcount> <deps>, <state> <address> [taint_flags]
```
- **引用计数与依赖**：在启用 `CONFIG_MODULE_UNLOAD` 时，遍历 `mod->source_list` 输出依赖该模块的其他模块；若模块无 `exit` 函数，则标记为 `[permanent]`。
- **地址隐藏机制**：通过 `kallsyms_show_value()` 判断当前凭证是否有权查看内核地址。若无权限，`seq_file->private` 被设为非 NULL（值为 `(void *)8ul`），`m_show()` 中据此将地址输出为 `0x0`（实际由 `%px` 在私有模式下自动处理为 `0`）。
- **模块状态**：根据 `mod->state` 显示 “Loading”、“Unloading” 或 “Live”。

### 内存大小计算
`module_total_size()` 遍历所有 `mod_mem_type` 类型（如 `MOD_TEXT`, `MOD_RODATA`, `MOD_DATA` 等），累加各段内存大小，反映模块实际占用的内核内存总量。

### 安全与权限控制
复用 `/proc/kallsyms` 的地址可见性逻辑，确保只有具备 `CAP_SYSLOG` 权限的进程才能查看模块的内核内存地址，防止信息泄露。

### 模块状态过滤
自动跳过 `MODULE_STATE_UNFORMED` 状态的模块（尚未完全初始化），避免输出不完整或无效信息。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/module.h>`：模块核心数据结构和 API。
  - `<linux/kallsyms.h>`：提供 `kallsyms_show_value()` 用于地址可见性判断。
  - `<linux/proc_fs.h>` 和 `<linux/seq_file.h>`：procfs 和 seq_file 接口。
  - `"internal.h"`：模块子系统内部头文件，包含 `module_mem_type` 等定义。

- **内核配置依赖**：
  - `CONFIG_MODULE_UNLOAD`：决定是否支持模块卸载及引用计数/依赖信息输出。

- **全局数据结构**：
  - `modules`：全局模块链表（定义于 `kernel/module/main.c`）。
  - `module_mutex`：保护模块链表的全局互斥锁。

## 5. 使用场景

- **系统监控与调试**：用户通过 `cat /proc/modules` 查看当前加载的模块及其状态，用于诊断模块加载问题或内存占用。
- **依赖分析**：工具（如 `lsmod`）解析依赖字段，构建模块依赖图，辅助安全审计或卸载顺序决策。
- **性能分析**：oprofile 等性能工具利用模块地址信息进行符号解析和性能采样。
- **安全审计**：通过模块污染标志（taints）判断系统是否加载了非官方或专有模块，评估系统可信度。
- **自动化脚本**：系统服务或安装程序通过解析 `/proc/modules` 内容判断特定模块是否已加载。