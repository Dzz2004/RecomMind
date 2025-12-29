# audit_tree.c

> 自动生成时间: 2025-10-25 11:51:22
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `audit_tree.c`

---

# audit_tree.c 技术文档

## 1. 文件概述

`audit_tree.c` 是 Linux 内核审计子系统中用于实现**目录树监控**（audit tree watching）的核心模块。该文件提供了对整个目录树（而不仅仅是单个 inode）进行审计监控的能力，通过将审计规则与目录路径关联，并在文件系统事件（如创建、删除、重命名等）发生时高效匹配规则。其核心机制基于 `fsnotify` 框架，在 inode 级别挂载通知标记（mark），并通过引用计数、RCU（Read-Copy-Update）和哈希表等技术保证高并发下的安全性和性能。

## 2. 核心功能

### 主要数据结构

- **`struct audit_tree`**  
  表示一个被监控的目录树。包含路径名、引用计数、关联的规则列表、关联的 chunk 列表等。
  
- **`struct audit_chunk`**  
  表示与一个或多个 inode 关联的监控单元。每个 chunk 通过 `fsnotify_mark` 附加到 inode 上，并维护多个 `audit_tree` 的所有者关系（`owners[]` 数组）。

- **`struct audit_tree_mark`**  
  封装 `fsnotify_mark`，作为 chunk 与 inode 之间的桥梁，属于 `fsnotify` 框架的扩展标记类型。

- **`struct audit_node`**  
  嵌入在 `audit_chunk` 中，表示 chunk 与某个 `audit_tree` 的关联关系，包含 owner 指针和索引。

### 主要函数

- **`alloc_tree(const char *s)`**  
  分配并初始化一个新的 `audit_tree` 实例。

- **`get_tree()` / `put_tree()`**  
  对 `audit_tree` 进行引用计数管理，`put_tree` 在引用归零时使用 RCU 安全释放。

- **`audit_tree_lookup(const struct inode *inode)`**  
  在 RCU 读临界区内，根据 inode 查找对应的 `audit_chunk`，并增加其引用计数。

- **`audit_tree_match(struct audit_chunk *chunk, struct audit_tree *tree)`**  
  检查给定 chunk 是否属于指定的 audit tree。

- **`alloc_chunk(int count)`**  
  分配包含指定数量 `audit_node` 的 chunk。

- **`insert_hash(struct audit_chunk *chunk)`**  
  将 chunk 插入全局哈希表，用于快速查找。

- **`audit_mark_put_chunk()` / `audit_put_chunk()`**  
  安全释放 chunk 的引用，结合 RCU 机制确保并发安全。

- **`replace_mark_chunk()` / `replace_chunk()`**  
  在标记或 chunk 更新时进行原子替换（代码片段中 `replace_chunk` 未完整）。

## 3. 关键实现

### 哈希与查找机制
- 使用 `inode->i_fsnotify_marks` 的地址作为哈希键（`inode_to_key`），确保每个 inode 对应唯一键。
- 全局哈希表 `chunk_hash_heads[HASH_SIZE]`（大小为 128）配合 `hash_lock` 自旋锁保护写操作。
- 查找操作（`audit_tree_lookup`）在 RCU 读锁下进行，通过 `READ_ONCE()` 和 `smp_wmb()` 保证内存可见性。

### 引用计数与生命周期管理
- `audit_tree` 使用 `refcount_t` 管理引用，来源包括：关联的审计规则、chunk 中的 owner 引用。
- `audit_chunk` 使用 `atomic_long_t refs`，其中一份引用由 `fsnotify_mark` 持有。
- 所有释放操作均通过 RCU（`call_rcu` / `kfree_rcu`）延迟执行，确保并发读取安全。

### 与 fsnotify 集成
- 每个被监控的 inode 通过 `audit_tree_mark`（继承 `fsnotify_mark`）关联一个 `audit_chunk`。
- 当 inode 被删除或 untag 时，`fsnotify` 框架回调 `audit_tree_destroy_watch` 释放 mark。
- `mark->mask = FS_IN_IGNORED` 表示仅用于内部结构关联，不主动监听事件（实际事件由审计规则触发匹配）。

### 循环链表组织
- `tree->chunks`：链接所有包含该 tree 的 chunk 中的 `audit_node.list`。
- `chunk->trees`：链接所有以该 chunk 为根的 tree 的 `same_root` 链表。
- `tree->rules`：链接所有引用该 tree 的审计规则。
- 这些链表分别由 `hash_lock` 或 `audit_filter_mutex` 保护。

### 索引位标记
- `audit_node.index` 的最高位（MSB）用于标记“可能需要回滚”的临时状态，辅助复杂操作（如树重构）的清理逻辑。

## 4. 依赖关系

- **`<linux/fsnotify_backend.h>`**：依赖 fsnotify 框架实现 inode 级别事件通知和标记管理。
- **`<linux/namei.h>` / `<linux/mount.h>`**：用于路径解析和挂载点处理（虽未在片段中直接调用，但 audit 树需处理跨挂载点语义）。
- **`audit.h`**：与审计核心模块交互，提供 `audit_tree_path()` 等接口供规则匹配使用。
- **`<linux/rcupdate.h>`**：使用 RCU 机制保证并发安全。
- **`<linux/slab.h>`**：使用 `kmem_cache` 高效分配 `audit_tree_mark` 对象。

## 5. 使用场景

- **审计规则匹配**：当用户通过 `auditctl` 添加 `-w /path/to/dir -p wa -k key` 类型规则时，内核将 `/path/to/dir` 注册为 `audit_tree`。
- **路径遍历监控**：在 `audit_inode()` 和 `audit_inode_child()` 中，内核收集路径上所有 inode 对应的 `audit_chunk`，用于后续与 `AUDIT_TREE` 类型规则匹配。
- **动态目录结构变更**：当目录树内发生文件创建、删除、重命名或 inode 删除时，通过 fsnotify 机制触发 chunk 更新或 prune（修剪）操作，由专用内核线程 `prune_thread` 处理延迟清理。
- **资源回收**：当审计规则被删除或监控目录被移除时，相关 `audit_tree` 和 `audit_chunk` 通过引用计数和 RCU 安全释放，避免内存泄漏。