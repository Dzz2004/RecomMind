# module\sysfs.c

> 自动生成时间: 2025-10-25 15:08:12
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `module\sysfs.c`

---

# module/sysfs.c 技术文档

## 1. 文件概述

`module/sysfs.c` 是 Linux 内核模块子系统中负责为已加载内核模块在 sysfs 虚拟文件系统中创建和管理属性接口的核心实现文件。该文件通过 sysfs 向用户空间暴露模块的元信息，包括节区（sections）地址、SHT_NOTE 类型节区内容、模块依赖关系（holders）以及模块信息（modinfo）等。这些信息对调试、监控和模块管理至关重要。

## 2. 核心功能

### 主要数据结构

- **`struct module_sect_attr`**  
  表示单个 ELF 节区的二进制属性，包含节区虚拟地址和对应的 `bin_attribute`。
  
- **`struct module_sect_attrs`**  
  管理模块所有非空节区的属性组（`attribute_group`），包含节区数量和动态数组 `attrs[]`。

- **`struct module_notes_attrs`**  
  管理模块中类型为 `SHT_NOTE` 的节区内容，通过二进制文件暴露其原始数据。

- **`struct module_attribute`**  
  用于表示模块的通用属性（如 `version`、`license` 等 modinfo 字段），由外部定义并在此注册到 sysfs。

### 主要函数

- **`add_sect_attrs()` / `remove_sect_attrs()`**  
  在 `/sys/module/<modname>/sections/` 下为每个非空 ELF 节区创建只读二进制文件，显示其加载地址（受 `kallsyms_show_value()` 权限控制）。

- **`add_notes_attrs()` / `remove_notes_attrs()`**  
  在 `/sys/module/<modname>/notes/` 下为每个 `SHT_NOTE` 类型节区创建二进制文件，直接暴露其原始内容。

- **`add_usage_links()` / `del_usage_links()`**  
  在模块依赖关系启用（`CONFIG_MODULE_UNLOAD`）时，为每个被当前模块使用的其他模块在其 `holders/` 目录下创建指向当前模块的符号链接。

- **`module_add_modinfo_attrs()` / `module_remove_modinfo_attrs()`**  
  将模块的 modinfo 字段（如 `author`、`description` 等）注册为 sysfs 中的普通属性文件。

## 3. 关键实现

### 节区地址显示（`module_sect_read`）

- 使用 `scnprintf` 将地址格式化为 `"0x<addr>\n"` 字符串。
- 由于 `bin_attribute` 的 `read` 回调需处理任意 `pos` 和 `count`，但地址只需从位置 0 读取，故对非零 `pos` 返回 `-EINVAL`。
- 为避免 `sprintf` 写入尾部 NUL 字符导致用户空间读取截断，使用 bounce buffer 中转数据。

### 动态内存布局（`module_sect_attrs`）

- 使用灵活数组成员（FAM）`attrs[]` 存储多个 `module_sect_attr`。
- 通过 `struct_size()` 计算结构体总大小，并额外分配空间存放 `bin_attrs` 指针数组。
- `bin_attrs` 指针数组紧邻结构体末尾，通过指针偏移访问。

### 权限控制（`kallsyms_show_value`）

- 节区地址是否显示为实际值（如 `0xffffffffc0001234`）或 `0x0`，取决于当前进程凭证是否具有 `kallsyms` 地址查看权限（通常需 `CAP_SYSLOG`）。

### SHT_NOTE 节区暴露

- 复用 `sect_attrs` 中已分配的节区名称字符串，避免重复分配。
- `bin_attribute.private` 直接指向节区在内核空间的虚拟地址，`module_notes_read` 通过 `memcpy` 返回原始数据。

### 模块依赖链接

- 依赖关系通过 `module_use` 链表维护。
- 每个被依赖模块的 `holders_dir`（即 `/sys/module/<target>/holders/`）下创建指向当前模块 kobject 的符号链接，名称为当前模块名。

## 4. 依赖关系

- **内核配置依赖**：
  - `CONFIG_KALLSYMS`：启用节区地址和 notes 节区的 sysfs 接口。
  - `CONFIG_MODULE_UNLOAD`：启用模块依赖关系的符号链接。
- **头文件依赖**：
  - `<linux/sysfs.h>`：提供 sysfs 属性和组操作接口。
  - `<linux/kallsyms.h>`：提供符号地址权限检查函数 `kallsyms_show_value()`。
  - `"internal.h"`：包含模块子系统内部定义（如 `struct load_info`、`sect_empty()` 等）。
- **数据结构依赖**：
  - `struct module`：包含 `sect_attrs`、`notes_attrs`、`modinfo_attrs` 等字段用于存储 sysfs 状态。
  - `struct load_info`：提供模块加载时的 ELF 头、节区头和字符串表信息。

## 5. 使用场景

- **系统调试与分析**：  
  用户可通过 `/sys/module/<mod>/sections/.text` 等文件查看模块各节区的加载地址，辅助内核调试和性能分析。

- **安全审计**：  
  通过检查模块的 license、author、description 等 modinfo 属性，验证模块合法性。

- **依赖关系追踪**：  
  通过 `holders/` 目录下的符号链接，确定哪些模块依赖于当前模块，辅助模块卸载决策。

- **固件与元数据提取**：  
  某些模块将固件或构建信息嵌入 `SHT_NOTE` 节区，用户空间工具可通过 `/sys/module/<mod>/notes/` 直接读取这些数据。

- **内核开发与测试**：  
  开发者可利用这些接口验证模块加载行为、节区布局和符号解析结果。