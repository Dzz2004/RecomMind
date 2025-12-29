# auditfilter.c

> 自动生成时间: 2025-10-25 11:52:34
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `auditfilter.c`

---

# auditfilter.c 技术文档

## 文件概述

`auditfilter.c` 是 Linux 内核审计子系统（Audit Subsystem）的核心组件之一，负责实现审计事件的过滤机制。该文件提供了审计规则的解析、存储、匹配和释放功能，支持基于系统调用、文件路径、用户身份、LSM（Linux Security Module）标签等多种条件的细粒度事件过滤。通过维护多个过滤规则链表，内核能够在事件发生时快速判断是否需要记录或忽略该事件。

## 核心功能

### 主要数据结构

- **`audit_filter_list[AUDIT_NR_FILTERS]`**：全局数组，包含 8 个链表头，分别对应不同类型的审计过滤器（如 `AUDIT_FILTER_EXIT`、`AUDIT_FILTER_USER` 等）。
- **`audit_rules_list[AUDIT_NR_FILTERS]`**：与 `audit_filter_list` 并行的规则链表，用于规则管理。
- **`audit_entry`**：审计规则的内核表示，包含 `audit_krule` 结构，用于存储规则字段、操作、动作等信息。
- **`audit_field`**：表示单个过滤字段，支持整数、字符串、LSM 安全上下文等多种类型。
- **`classes[AUDIT_SYSCALL_CLASSES]`**：系统调用分类映射表，用于将系统调用分组（如信号类、网络类等）。

### 主要函数

- **`audit_free_rule()` / `audit_free_rule_rcu()`**：释放审计规则及其关联资源（如 watch、LSM 规则、字符串等），支持 RCU 安全释放。
- **`audit_init_entry()`**：分配并初始化一个新的审计规则条目。
- **`audit_unpack_string()`**：从用户空间缓冲区解包字符串字段，用于规则解析。
- **`audit_to_inode()`**：处理基于 inode 的审计规则字段。
- **`audit_register_class()` / `audit_match_class()`**：注册和匹配系统调用分类。
- **`audit_to_entry_common()`**：将用户空间传入的 `audit_rule_data` 转换为内核内部的 `audit_entry` 表示。
- **`audit_match_signal()`**（仅在 `CONFIG_AUDITSYSCALL` 下）：判断规则是否匹配信号类系统调用。

## 关键实现

### 锁与并发控制

- 使用 **`audit_filter_mutex`** 互斥锁保护对过滤规则链表的写操作和阻塞读操作。
- 规则遍历和匹配过程使用 **RCU（Read-Copy-Update）** 机制，确保高并发下的读性能。
- 修改规则时必须**复制整个结构体**并替换链表中的旧条目，而非原地修改，以保证 RCU 读取的安全性。

### 规则解析与转换

- `audit_to_entry_common()` 是规则解析的核心函数，负责：
  - 验证规则合法性（动作、字段数量、过滤器类型等）
  - 初始化内核规则结构
  - 处理系统调用分类位图（将分类位展开为具体系统调用掩码）
- 支持多种比较操作符（等于、不等于、位掩码、位测试、大小比较等），通过 `audit_ops[]` 数组映射。

### LSM 集成

- 支持 SELinux 等 LSM 框架的安全上下文字段（如 `AUDIT_SUBJ_USER`、`AUDIT_OBJ_ROLE` 等）。
- 使用 `security_audit_rule_free()` 释放 LSM 规则，确保与安全模块的解耦。

### 系统调用分类

- 通过 `audit_register_class()` 动态注册系统调用分组（如信号、文件、网络等）。
- 在规则匹配时，自动将分类位扩展为对应的系统调用位掩码，简化用户空间规则配置。

## 依赖关系

- **`<linux/audit.h>`**：定义审计子系统的公共接口、常量和数据结构。
- **`<linux/security.h>`**：提供 LSM 审计规则的注册与释放接口。
- **`<linux/rcupdate.h>`**（隐式）：通过 RCU 机制实现无锁读取。
- **`audit.h`（本地头文件）**：包含审计子系统内部定义。
- **`CONFIG_AUDITSYSCALL`**：条件编译依赖，启用系统调用审计相关功能。
- **Netlink 子系统**：通过 netlink 接收用户空间下发的审计规则。

## 使用场景

1. **审计规则加载**：当用户空间工具（如 `auditctl`）通过 netlink 发送审计规则时，内核调用本文件中的解析函数将规则转换为内核格式并插入对应过滤链表。
2. **事件过滤**：在系统调用入口/出口、文件访问、进程创建等关键路径上，审计钩子函数调用本模块的匹配逻辑，判断当前事件是否应被记录。
3. **规则更新与删除**：管理员动态修改审计策略时，内核通过 `audit_filter_mutex` 保护规则链表的修改操作，并利用 RCU 机制安全替换旧规则。
4. **LSM 审计集成**：当 SELinux 或其他 LSM 启用审计时，安全上下文相关的过滤规则通过本模块进行匹配。
5. **系统调用分组监控**：用户可基于系统调用类别（如“所有信号相关调用”）设置规则，无需逐个指定系统调用号。