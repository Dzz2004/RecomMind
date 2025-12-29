# bpf\inode.c

> 自动生成时间: 2025-10-25 12:12:33
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\inode.c`

---

# `bpf/inode.c` 技术文档

## 1. 文件概述

`bpf/inode.c` 实现了一个轻量级的虚拟文件系统（称为 **bpffs**），用于支持 eBPF 对象（包括 BPF 程序、映射和链接）的 **pinning（持久化）机制**。该文件系统允许用户空间通过标准文件系统操作（如 `mkdir`、`create`、`unlink` 等）将 BPF 对象绑定到文件系统路径，从而在进程退出后仍能保持对这些对象的引用，避免被内核自动释放。此机制是 `bpf(2)` 系统调用中 `BPF_OBJ_PIN` 和 `BPF_OBJ_GET` 功能的后端支撑。

## 2. 核心功能

### 主要数据结构

- `enum bpf_type`：枚举类型，标识 BPF 对象类型（`BPF_TYPE_PROG`、`BPF_TYPE_MAP`、`BPF_TYPE_LINK`）。
- `struct map_iter`：用于 BPF map 序列化遍历的迭代器结构，包含当前 key 和完成标志。
- `const struct inode_operations`：分别为目录、程序、映射、链接定义的 inode 操作集合（`bpf_dir_iops`、`bpf_prog_iops` 等）。
- `const struct file_operations`：
  - `bpffs_map_fops`：支持对支持 `seq_show` 的 BPF map 进行 `cat` 读取。
  - `bpffs_obj_fops`：通用只读文件操作，打开即返回 `-EIO`，防止误操作。

### 主要函数

- `bpf_any_get()` / `bpf_any_put()`：根据对象类型统一增加/减少引用计数。
- `bpf_fd_probe_obj()`：通过文件描述符探测并获取对应的 BPF 对象及其类型。
- `bpf_get_inode()`：为 bpffs 创建新的 inode（支持目录、普通文件、符号链接）。
- `bpf_inode_type()`：根据 inode 的 `i_op` 字段反推其对应的 BPF 对象类型。
- `bpf_dentry_finalize()`：完成 dentry 与 inode 的绑定并更新父目录时间戳。
- `bpf_mkdir()`：实现 bpffs 中的目录创建。
- `bpf_mkprog()` / `bpf_mkmap()` / `bpf_mklink()`：分别创建 BPF 程序、映射、链接对应的文件 inode。
- `map_iter_alloc()` / `map_iter_free()`：管理 map 遍历迭代器的生命周期。
- `map_seq_*` 系列函数：实现 BPF map 的 `seq_file` 遍历接口，用于 `cat` 输出。
- `bpffs_map_open()` / `bpffs_map_release()`：map 文件的打开与释放，初始化 seq_file 上下文。
- `bpf_lookup()`：自定义 lookup 逻辑，禁止文件名中包含 `.`（保留用于未来扩展）。

## 3. 关键实现

### BPF 对象引用管理
通过 `bpf_any_get()` 和 `bpf_any_put()` 封装不同 BPF 对象（prog/map/link）的引用计数操作，确保在 inode 创建和销毁时正确持有/释放内核对象，防止内存泄漏或提前释放。

### 对象类型识别
利用 `inode->i_op` 指针的唯一性（分别指向 `bpf_prog_iops`、`bpf_map_iops` 等空结构体）作为类型标签，在运行时通过指针比较快速判断 inode 对应的 BPF 对象类型。

### BPF Map 的可读性支持
对于支持 `map_seq_show_elem` 操作的 BPF map（如 hash、array 等），通过 `seq_file` 机制实现 `cat /sys/fs/bpf/map_name` 输出内容。输出包含警告信息，强调格式不稳定，仅用于调试。

### 安全与扩展性设计
- 文件名中禁止出现 `.` 字符（如 `foo.bar`），为未来在 bpffs 中引入特殊文件（如元数据、控制接口）预留命名空间。
- 普通 BPF 对象文件（prog/link 或不支持 seq_show 的 map）使用 `bpffs_obj_fops`，其 `open` 返回 `-EIO`，防止用户误读/误写导致未定义行为。

### 虚拟文件系统集成
基于 `simple_fs` 框架（如 `simple_dir_operations`、`simple_lookup`）构建，仅重写必要操作（如 `mkdir`、`lookup`、`create` 逻辑由上层调用 `bpf_mk*` 实现），保持代码简洁。

## 4. 依赖关系

- **BPF 子系统核心**：依赖 `<linux/bpf.h>`、`<linux/filter.h>` 提供的 `bpf_prog_*`、`bpf_map_*`、`bpf_link_*` 等核心 API。
- **VFS 层**：依赖标准 VFS 接口（`<linux/fs.h>`、`<linux/namei.h>`、`<linux/dcache.h>`）实现 inode、dentry、file 操作。
- **预加载机制**：包含 `"preload/bpf_preload.h"`，可能用于内核启动时预加载 BPF 对象。
- **迭代器支持**：若 BPF link 为 iterator 类型，会使用 `bpf_iter_fops`（定义在其他文件中）。

## 5. 使用场景

- **BPF 对象持久化**：用户空间工具（如 `bpftool`）调用 `bpf(BPF_OBJ_PIN, ...)` 将 map/prog/link pin 到 `/sys/fs/bpf/` 下的路径，内核通过本文件创建对应 inode 并持有对象引用。
- **跨进程共享 BPF 对象**：多个进程可通过 `bpf(BPF_OBJ_GET, ...)` 从同一 bpffs 路径获取已 pin 对象的 fd，实现共享。
- **调试与可观测性**：支持 `seq_show` 的 map 可通过 `cat` 命令查看内容，辅助开发调试（注意：非稳定接口）。
- **系统启动预加载**：结合 `bpf_preload` 机制，在内核初始化阶段将关键 BPF 程序/映射 pin 到 bpffs，供后续服务使用。