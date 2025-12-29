# hardware_message.c

> 自动生成时间: 2025-10-25 13:43:47
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `hardware_message.c`

---

# hardware_message.c 技术文档

## 文件概述

`hardware_message.c` 是麒麟操作系统（Kylin Linux Advanced Desktop/Server，简称 KLAS/KLAD）内核中用于向用户发出硬件或驱动程序支持状态警告的专用模块。该文件定义了一系列函数，用于在内核启动或驱动加载过程中，根据硬件或驱动的生命周期状态（如“已弃用”、“不再维护”、“已禁用”或“技术预览”）向系统日志输出高优先级的 `pr_crit()` 警告信息。这些函数仅在启用了 `CONFIG_KYLIN_DIFFERENCES` 内核配置选项时生效，体现了麒麟操作系统对特定硬件兼容性与支持策略的管理机制。

## 核心功能

### 主要函数

| 函数名 | 功能描述 |
|--------|--------|
| `mark_hardware_unmaintained()` | 标记特定硬件设备为“不再维护”，输出包含设备描述的严重警告 |
| `mark_driver_unmaintained()` | 标记驱动程序为“不再维护”，适用于无法关联具体硬件的通用驱动 |
| `mark_hardware_deprecated()` | 标记特定硬件为“已弃用”，提示将在未来版本停止维护 |
| `mark_driver_deprecated()` | 标记驱动为“已弃用”，适用于抽象或高层驱动 |
| `mark_hardware_disabled()` | 标记硬件支持已被完全禁用，设备无法在当前版本使用 |
| `mark_tech_preview()` | 标记驱动或子系统为“技术预览”状态（函数声明未完整实现） |

### 数据结构与常量

- `DEV_DESC_LEN`：定义设备描述字符串的最大长度（256 字节）
- 使用 `va_list` 和可变参数处理设备描述格式化

### 导出符号

所有上述函数均通过 `EXPORT_SYMBOL()` 导出，可供其他内核模块调用。

## 关键实现

### 条件编译控制

所有函数的实现均被 `#ifdef CONFIG_KYLIN_DIFFERENCES` 包裹，确保仅在麒麟定制内核中启用该功能，避免对上游 Linux 内核造成影响。

### 驱动/模块名称解析逻辑

函数优先使用传入的 `driver_name` 参数；若为空且启用了 `CONFIG_MODULES`，则回退到从 `struct module *mod` 中提取模块名；若两者均不可用，则使用默认字符串 `"Kernel"`。

### 可变参数处理

对于硬件相关的函数（`_hardware_*`），使用 `va_start`/`vsnprintf`/`va_end` 机制格式化设备描述信息，支持动态构造设备标识（如 PCI ID、设备型号等）。

### 日志级别

统一使用 `pr_crit()` 输出 **Critical** 级别日志，确保警告信息在系统日志中高亮显示，引起管理员注意。

### 生命周期状态语义

- **Deprecated（已弃用）**：当前仍可用，但计划在未来主版本中转为“不再维护”或“禁用”
- **Unmaintained（不再维护）**：仅修复安全或严重问题，常规更新已停止
- **Disabled（已禁用）**：当前版本已完全移除支持
- **Tech Preview（技术预览）**：新功能，测试有限，不保证稳定性与支持（函数未完整实现）

## 依赖关系

### 头文件依赖

- `<linux/kernel.h>`：提供 `pr_crit()`、`vsnprintf()`、`va_list` 等内核日志与字符串处理接口
- `<linux/module.h>`：提供 `struct module` 定义及模块相关信息

### 内核配置依赖

- **必需**：`CONFIG_KYLIN_DIFFERENCES` — 启用麒麟特有差异功能
- **可选**：`CONFIG_MODULES` — 支持从模块指针获取名称（若未启用模块，则跳过该路径）

### 符号导出

所有函数通过 `EXPORT_SYMBOL()` 导出，供其他驱动模块在初始化时调用，以声明自身支持状态。

## 使用场景

1. **驱动弃用通知**  
   当某硬件厂商停止维护某款网卡，麒麟内核团队决定在下一主版本移除支持。当前版本中，该驱动在 `probe()` 时调用 `mark_hardware_deprecated()`，提示用户规划迁移。

2. **通用驱动生命周期管理**  
   某旧版 RAID 管理驱动因上游废弃，麒麟将其标记为“不再维护”，调用 `mark_driver_unmaintained()`，适用于所有使用该驱动的系统。

3. **已禁用硬件检测**  
   用户尝试加载已被内核配置禁用的旧显卡驱动，驱动框架调用 `mark_hardware_disabled()` 明确告知设备不可用。

4. **新技术预览**  
   引入实验性文件系统或新硬件支持时，通过 `mark_tech_preview()` 声明其非生产就绪状态（注：当前代码中该函数未实现完整逻辑）。

5. **发布合规性**  
   所有调用必须记录于 KLAS/KLAD 发行说明，并获得管理层审批，确保用户对硬件支持变更有明确预期。