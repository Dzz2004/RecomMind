# audit_watch.c

> 自动生成时间: 2025-10-25 11:52:01
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `audit_watch.c`

---

# audit_watch.c 技术文档

## 1. 文件概述

`audit_watch.c` 是 Linux 内核审计子系统（Audit Subsystem）中用于实现文件路径监控的核心模块。该文件通过与 `fsnotify` 机制集成，实现对指定路径的动态 inode 监控。当被监控的文件或目录发生创建、删除、移动或卸载等事件时，审计系统能够自动更新规则中关联的 inode 信息，确保审计规则持续有效。该机制解决了传统基于路径的监控在文件系统结构变化时失效的问题。

## 2. 核心功能

### 主要数据结构

- **`struct audit_watch`**  
  表示一个审计监控项，包含：
  - `count`：引用计数
  - `dev` / `ino`：关联的设备号和 inode 号（初始为未设置状态）
  - `path`：原始监控路径字符串
  - `parent`：指向所属父目录的 `audit_parent` 结构
  - `wlist`：挂载到父目录监控列表的链表节点
  - `rules`：关联的审计规则链表头

- **`struct audit_parent`**  
  表示被监控路径的父目录，包含：
  - `watches`：该父目录下所有 `audit_watch` 的链表头
  - `mark`：嵌入的 `fsnotify_mark`，用于注册到 VFS 通知系统

### 主要函数

- **`audit_to_watch()`**  
  将用户空间传入的路径字符串转换为内核 `audit_watch` 对象，并绑定到审计规则

- **`audit_init_watch()` / `audit_init_parent()`**  
  初始化 `audit_watch` 和 `audit_parent` 结构

- **`audit_dupe_watch()`**  
  复制监控项（用于 inode 变更时的规则更新）

- **`audit_update_watch()`**  
  核心回调函数，处理文件系统事件（如重命名、删除）并更新所有关联规则的 inode 信息

- **`audit_watch_compare()`**  
  比较监控项与给定 inode/dev 是否匹配

- **`audit_get_watch()` / `audit_put_watch()`**  
  引用计数管理接口

- **`audit_remove_watch()`**  
  从父目录监控列表中移除监控项

## 3. 关键实现

### 引用计数机制
- **`audit_watch`**：使用 `refcount_t` 管理生命周期，每个关联的审计规则持有引用
- **`audit_parent`**：通过 `fsnotify_mark` 的引用计数管理，每个子监控项持有父目录引用

### fsnotify 集成
- 创建专用 `fsnotify_group` (`audit_watch_group`)
- 监控事件类型：`FS_MOVE | FS_CREATE | FS_DELETE | FS_DELETE_SELF | FS_MOVE_SELF | FS_UNMOUNT`
- 通过 `fsnotify_add_inode_mark()` 在父目录 inode 上注册监控标记

### 动态 inode 更新流程
1. 文件系统事件触发 `audit_update_watch()` 回调
2. 根据事件中的 dentry 名称匹配对应 `audit_watch`
3. 创建新 `audit_watch` 副本并更新 inode/dev 信息
4. 遍历原监控项关联的所有规则：
   - 从旧 inode 哈希表移除规则
   - 创建规则副本并绑定到新监控项
   - 插入新 inode 对应的哈希表
5. 记录配置变更日志（`AUDIT_CONFIG_CHANGE`）

### 路径解析策略
- 仅支持绝对路径（以 `/` 开头）
- 不支持目录路径（路径末尾不能为 `/`）
- 仅允许用于 `AUDIT_FILTER_EXIT` 和 `AUDIT_FILTER_URING_EXIT` 规则类型

## 4. 依赖关系

- **核心依赖**：
  - `fsnotify` 子系统（`<linux/fsnotify_backend.h>`）：提供文件系统事件通知
  - 审计核心模块（`audit.h`）：规则管理、日志记录、哈希表操作
  - VFS 层（`<linux/fs.h>`, `<linux/namei.h>`）：inode/dentry 操作

- **关键交互**：
  - 通过 `audit_filter_mutex` 与审计规则管理模块同步
  - 调用 `audit_filter_inodes()` 确保事件发生时的审计记录完整性
  - 使用 `audit_inode_hash` 哈希表管理基于 inode 的规则索引

## 5. 使用场景

1. **审计规则动态维护**  
   当用户通过 `auditctl -w /path/to/file` 添加路径监控时，内核将路径解析为 inode 并注册 fsnotify 监控。后续文件移动/重命名时自动更新规则绑定的 inode。

2. **文件系统事件响应**  
   处理以下场景：
   - 文件被移动到监控目录（触发 `FS_CREATE`）
   - 监控文件被重命名（触发 `FS_MOVE`）
   - 监控目录被卸载（触发 `FS_UNMOUNT`）
   - 监控文件被删除（触发 `FS_DELETE`）

3. **审计日志完整性保障**  
   在 inode 变更过程中，通过 `audit_filter_inodes()` 确保变更期间的系统调用仍能被正确审计，避免监控间隙。

4. **资源生命周期管理**  
   通过引用计数确保：
   - 规则存在时监控项不被释放
   - 父目录无监控项时自动清理 fsnotify 标记
   - 路径字符串内存的安全回收