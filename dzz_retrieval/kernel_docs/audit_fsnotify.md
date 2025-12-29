# audit_fsnotify.c

> 自动生成时间: 2025-10-25 11:50:38
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `audit_fsnotify.c`

---

# audit_fsnotify.c 技术文档

## 1. 文件概述

`audit_fsnotify.c` 是 Linux 内核审计子系统（audit subsystem）中用于通过 **fsnotify** 机制监控文件系统事件的核心实现文件。该文件负责为审计规则中指定的路径创建并管理 **fsnotify 标记（mark）**，以跟踪目标文件或目录的创建、删除、移动等事件，并在文件系统对象发生变更时自动更新或移除对应的审计规则。其主要作用是实现对审计规则所监控路径的动态维护，确保即使目标 inode 发生变化（如被删除、重命名或替换），审计系统仍能正确响应或清理无效规则。

## 2. 核心功能

### 数据结构

- **`struct audit_fsnotify_mark`**  
  表示与审计规则关联的 fsnotify 标记，包含：
  - `dev`：目标 inode 所在的设备号
  - `ino`：目标 inode 编号
  - `path`：原始监控路径字符串
  - `mark`：嵌入的 `fsnotify_mark` 结构，用于注册到 fsnotify 子系统
  - `rule`：指向关联的审计规则 `audit_krule`

### 主要函数

- **`audit_alloc_mark()`**  
  为给定的审计规则和路径分配并初始化一个 `audit_fsnotify_mark`，解析路径、获取 inode，并将 mark 注册到 fsnotify 系统。

- **`audit_remove_mark()` / `audit_remove_mark_rule()`**  
  从 fsnotify 系统中移除指定的 mark，并释放相关资源。

- **`audit_mark_handle_event()`**  
  fsnotify 事件回调函数，处理 `FS_CREATE`、`FS_DELETE`、`FS_MOVE_SELF` 等事件，更新 mark 的 inode 信息或自动移除失效规则。

- **`audit_autoremove_mark_rule()`**  
  当监控目标被删除或卸载时，自动从审计规则链表中删除对应的规则，并记录配置变更日志。

- **`audit_mark_compare()` / `audit_mark_path()`**  
  提供对 mark 的 inode/dev 比较和路径访问接口，供审计匹配逻辑使用。

- **`audit_fsnotify_init()`**  
  初始化 audit 专用的 fsnotify group，注册操作回调。

## 3. 关键实现

### fsnotify 集成机制
- 审计系统通过 `fsnotify_alloc_group()` 创建专属的 `audit_fsnotify_group`，仅监听 `AUDIT_FS_EVENTS` 定义的事件（`FS_MOVE`、`FS_CREATE`、`FS_DELETE`、`FS_DELETE_SELF`、`FS_MOVE_SELF`）。
- 每个监控路径对应一个 `audit_fsnotify_mark`，该 mark 实际附加在**父目录的 inode** 上（因需监控子项变化），但其 `dev`/`ino`/`path` 字段描述的是**子项（child）** 的信息。

### 路径解析与 mark 创建
- `audit_alloc_mark()` 要求路径为绝对路径且不能以 `/` 结尾。
- 使用 `kern_path_locked()` 安全地解析路径并获取 dentry 和 inode，确保在持有 inode 锁期间完成初始化。
- 成功后调用 `fsnotify_add_inode_mark()` 将 mark 关联到父目录 inode。

### 事件处理逻辑
- **创建/移动事件**（`FS_CREATE`/`FS_MOVED_TO` 等）：  
  通过 `audit_compare_dname_path()` 比对事件中的文件名与 mark 的原始路径。若匹配，则调用 `audit_update_mark()` 更新 mark 的 `dev`/`ino` 为新 inode 的值。
- **自删除/卸载事件**（`FS_DELETE_SELF`/`FS_UNMOUNT`/`FS_MOVE_SELF`）：  
  触发 `audit_autoremove_mark_rule()`，自动删除关联的审计规则，并通过 `audit_log_start()` 记录 `AUDIT_CONFIG_CHANGE` 日志。

### 自动清理机制
- 当监控目标被删除或文件系统卸载时，审计规则会自动移除，避免悬挂引用。
- `fsnotify` 的 `free_mark` 回调 `audit_fsnotify_free_mark()` 确保 mark 内存被正确释放。

## 4. 依赖关系

- **fsnotify 子系统**：  
  依赖 `<linux/fsnotify_backend.h>` 提供的 `fsnotify_mark`、`fsnotify_group`、事件掩码等核心接口。
- **审计核心模块**：  
  依赖 `audit.h` 中定义的 `audit_krule`、`audit_entry`、`audit_log_*` 等结构和日志函数。
- **VFS 层**：  
  使用 `kern_path_locked()`、`dentry`、`inode` 等 VFS 接口解析路径和获取元数据。
- **内存管理**：  
  使用 `kzalloc()`/`kfree()` 分配和释放 mark 及路径字符串。
- **安全模块**：  
  包含 `<linux/security.h>`，可能与 LSM 集成（尽管本文件未直接调用）。

## 5. 使用场景

- **审计规则监控文件路径**：  
  当用户通过 `auditctl -w /etc/passwd -p wa` 添加路径监控规则时，内核调用 `audit_alloc_mark()` 创建 fsnotify mark，实现对 `/etc/passwd` 的写入和属性变更审计。
- **动态文件系统变更响应**：  
  若被监控文件被 `mv` 重命名或 `rm` 删除，`audit_mark_handle_event()` 会更新 inode 信息或自动移除规则，确保审计策略的准确性。
- **系统启动/模块初始化**：  
  通过 `device_initcall(audit_fsnotify_init)` 在内核初始化阶段创建 audit fsnotify group，为后续规则注册提供基础。
- **审计日志记录**：  
  规则自动移除时，通过 `audit_mark_log_rule_change()` 生成 `AUDIT_CONFIG_CHANGE` 日志，供管理员审计配置变更。