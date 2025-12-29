# bpf\bpf_cgrp_storage.c

> 自动生成时间: 2025-10-25 11:57:02
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\bpf_cgrp_storage.c`

---

# bpf_cgrp_storage.c 技术文档

## 文件概述

`bpf_cgrp_storage.c` 实现了 BPF cgroup 存储（cgroup storage）机制，为 BPF 程序提供了一种在 cgroup 对象上附加和访问私有数据的能力。该机制基于通用的 `bpf_local_storage` 框架，专用于 cgroup 上下文，允许 BPF 程序通过 cgroup 文件描述符或直接引用 cgroup 结构体来读写与特定 cgroup 关联的键值数据。该文件定义了专用的 BPF map 类型及其操作函数，并提供了两个 BPF 辅助函数供 BPF 程序调用。

## 核心功能

### 数据结构

- **`cgroup_cache`**：通过 `DEFINE_BPF_STORAGE_CACHE` 定义的 per-cpu 缓存，用于加速 `bpf_local_storage` 的分配和回收。
- **`bpf_cgrp_storage_busy`**：per-cpu 计数器，用于实现轻量级的 per-cpu 锁，防止在 RCU 临界区内递归调用存储操作。

### 主要函数

#### 锁机制函数
- `bpf_cgrp_storage_lock()` / `bpf_cgrp_storage_unlock()`：获取/释放 per-cpu 忙锁，禁用迁移以保证临界区安全。
- `bpf_cgrp_storage_trylock()`：尝试获取忙锁，若当前 CPU 已持有锁则失败返回。

#### 存储管理函数
- `bpf_cgrp_storage_free(struct cgroup *cgroup)`：在 cgroup 销毁时释放其关联的 BPF 本地存储。
- `cgroup_storage_lookup()`：内部辅助函数，根据 cgroup 和 map 查找对应的存储数据。
- `cgroup_storage_delete()`：内部辅助函数，从 cgroup 的存储中删除指定 map 的条目。

#### BPF Map 操作函数
- `bpf_cgrp_storage_lookup_elem()`：通过 cgroup fd 查找 map 中的元素。
- `bpf_cgrp_storage_update_elem()`：通过 cgroup fd 更新或插入 map 中的元素。
- `bpf_cgrp_storage_delete_elem()`：通过 cgroup fd 删除 map 中的元素。
- `cgroup_storage_map_alloc()` / `cgroup_storage_map_free()`：分配和释放 cgroup 存储类型的 BPF map。

#### BPF 辅助函数
- `bpf_cgrp_storage_get()`：BPF 程序可调用的辅助函数，用于获取或创建与指定 cgroup 关联的存储数据。
- `bpf_cgrp_storage_delete()`：BPF 程序可调用的辅助函数，用于删除与指定 cgroup 关联的存储数据。

#### 操作结构体
- `cgrp_storage_map_ops`：实现 `bpf_map_ops` 接口，定义 cgroup 存储 map 的行为。
- `bpf_cgrp_storage_get_proto` / `bpf_cgrp_storage_delete_proto`：定义两个 BPF 辅助函数的调用协议。

## 关键实现

### 锁机制设计
为避免在 RCU 读侧临界区中发生递归调用（例如在 cgroup 回调中再次访问存储），该模块实现了轻量级的 per-cpu 忙锁：
- 使用 `migrate_disable()`/`migrate_enable()` 禁用 CPU 迁移，确保临界区不会被调度到其他 CPU。
- 通过 per-cpu 计数器 `bpf_cgrp_storage_busy` 跟踪是否已进入临界区，`trylock` 仅在计数为 0 时成功。
- 此设计允许在非递归场景下安全地执行存储操作，同时在递归场景下快速失败。

### 存储查找与更新
- 所有存储操作均通过通用的 `bpf_local_storage` 框架实现，`cgroup_storage_ptr()` 提供 cgroup 对象到其存储指针的映射。
- `bpf_cgrp_storage_get()` 辅助函数在 RCU 临界区内运行，仅当 cgroup 未被销毁（`percpu_ref_is_dying` 为假）且请求创建标志时才分配新存储。
- 用户空间通过 cgroup fd 操作 map，内核通过 `cgroup_get_from_fd()` 获取 cgroup 引用，确保操作期间 cgroup 不被释放。

### 内存管理
- 使用专用的 per-cpu 缓存 `cgroup_cache` 优化 `bpf_local_storage` 结构的分配性能。
- 在 map 释放时，通过 `bpf_local_storage_map_free()` 清理所有关联的存储，并等待 RCU 宽限期以确保安全回收。

## 依赖关系

- **`<linux/bpf_local_storage.h>`**：核心依赖，提供通用的本地存储框架实现。
- **`<linux/cgroup.h>`**：依赖 cgroup 子系统，使用 `cgroup_get_from_fd()`、`cgroup_put()` 等接口。
- **`<linux/bpf.h>`**：BPF 核心头文件，定义 map 操作和辅助函数协议。
- **`<linux/btf.h>`**：支持 BTF 类型信息，用于类型安全的 BPF 程序验证。
- **RCU 机制**：所有存储访问均在 RCU 读侧临界区内进行，确保存储结构的并发安全。

## 使用场景

1. **BPF 程序监控 cgroup 资源使用**：BPF 程序可通过 `bpf_cgrp_storage_get()` 为每个 cgroup 维护自定义统计信息（如网络流量、CPU 时间等）。
2. **策略实施**：在 cgroup 级别实施安全或资源控制策略，将策略状态存储在 cgroup 的 BPF 存储中。
3. **用户空间工具集成**：用户空间程序通过 cgroup fd 与 BPF map 交互，读取或更新特定 cgroup 的 BPF 数据，实现监控或配置功能。
4. **cgroup 生命周期管理**：当 cgroup 被销毁时，自动调用 `bpf_cgrp_storage_free()` 清理关联的 BPF 存储，防止内存泄漏。