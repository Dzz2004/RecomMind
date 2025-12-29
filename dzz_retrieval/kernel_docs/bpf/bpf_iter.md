# bpf\bpf_iter.c

> 自动生成时间: 2025-10-25 11:58:22
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\bpf_iter.c`

---

# bpf/bpf_iter.c 技术文档

## 1. 文件概述

`bpf_iter.c` 是 Linux 内核中 BPF（Berkeley Packet Filter）子系统的一部分，实现了 **BPF 迭代器（BPF Iterator）** 的核心机制。BPF 迭代器是一种特殊的 BPF 程序类型，允许用户空间通过文件接口（如 `/sys/fs/bpf/` 下的文件）安全、高效地遍历内核中的数据结构（如任务、映射、网络连接等），而无需引入新的系统调用或暴露原始内核指针。

该文件负责：
- 管理 BPF 迭代器目标（target）的注册与注销
- 实现自定义的 `seq_file` 读取逻辑（`bpf_seq_read`）
- 管理迭代器会话的私有数据和生命周期
- 提供文件操作接口（`file_operations`）供用户空间读取

## 2. 核心功能

### 主要数据结构

| 结构体 | 说明 |
|--------|------|
| `struct bpf_iter_target_info` | 表示一个 BPF 迭代器目标的注册信息，包含 `bpf_iter_reg` 和缓存的 BTF ID |
| `struct bpf_iter_link` | 继承自 `bpf_link`，用于将 BPF 程序与特定迭代器目标关联 |
| `struct bpf_iter_priv_data` | `seq_file` 的私有数据，包含目标信息、BPF 程序、会话 ID、序列号等状态 |

### 主要函数

| 函数 | 功能 |
|------|------|
| `bpf_iter_reg_target()` | 注册一个新的 BPF 迭代器目标类型 |
| `bpf_iter_unreg_target()` | 注销已注册的 BPF 迭代器目标 |
| `bpf_iter_prog_supported()` | 检查 BPF 程序是否为有效的迭代器程序（基于函数名前缀和 BTF ID 匹配） |
| `bpf_seq_read()` | 自定义的 `seq_file` 读取实现，支持 BPF 程序在 `start/next/show/stop` 回调中执行 |
| `iter_open()` / `iter_release()` | 文件打开/释放回调，初始化和清理迭代器会话 |
| `bpf_iter_inc_seq_num()` / `bpf_iter_dec_seq_num()` | 管理当前迭代对象的序列号（用于跳过对象时回退） |
| `bpf_iter_done_stop()` | 标记迭代已正常结束 |

### 全局变量

- `targets`：已注册迭代器目标的链表
- `session_id`：全局递增的会话 ID，用于区分不同迭代会话
- `bpf_iter_fops`：提供给 VFS 的文件操作接口

## 3. 关键实现

### BPF 迭代器工作流程
1. **注册**：内核子系统（如 `task_iter`、`map_iter`）通过 `bpf_iter_reg_target()` 注册其迭代器实现（`bpf_iter_reg`）。
2. **程序加载**：用户加载 BPF 程序时，若其 `attach_func_name` 以 `bpf_iter_` 开头，则调用 `bpf_iter_prog_supported()` 验证并绑定到对应目标。
3. **文件打开**：用户打开 BPF 迭代器链接创建的文件时，`iter_open()` 调用 `prepare_seq_file()` 初始化 `seq_file`。
4. **数据读取**：`bpf_seq_read()` 驱动迭代过程：
   - 调用 `seq->op->start()` 获取首个对象
   - 循环调用 `next()` 和 `show()`，其中 `show()` 可能执行 BPF 程序生成输出
   - 支持在 `show()` 中返回 `>0` 跳过当前对象（通过 `bpf_iter_dec_seq_num()` 回退序列号）
   - 限制最大迭代对象数（`MAX_ITER_OBJECTS = 1,000,000`）防止无限循环
   - 支持可抢占目标（`BPF_ITER_RESCHED` 特性）在循环中调用 `cond_resched()`
5. **结束**：`stop()` 回调被调用，可能再次执行 BPF 程序进行清理。

### 安全与健壮性机制
- **溢出保护**：检查 `seq_has_overflowed()` 防止缓冲区溢出，返回 `-E2BIG`
- **对象数量限制**：防止恶意程序导致内核长时间占用 CPU
- **序列号管理**：精确跟踪当前迭代位置，支持对象跳过
- **会话隔离**：每个文件打开对应独立的 `session_id` 和私有数据

### BTF ID 缓存优化
- 首次匹配目标时，将程序的 `attach_btf_id` 缓存到 `tinfo->btf_id`
- 后续程序可直接通过 BTF ID 快速匹配，避免字符串比较

## 4. 依赖关系

- **BPF 核心**：依赖 `linux/bpf.h`、`bpf_link` 机制和 BPF 程序管理（`bpf_prog_put`）
- **VFS/seq_file**：基于 `linux/fs.h` 和 `seq_file` 框架实现迭代输出
- **内存管理**：使用 `kvmalloc` 分配大缓冲区（`PAGE_SIZE << 3`）
- **RCU/锁机制**：使用 `mutex`（`targets_mutex`, `link_mutex`）保护全局链表
- **BTF（BPF Type Format）**：通过 `attach_btf_id` 和函数名匹配程序与目标
- **调度器**：支持可抢占目标时调用 `cond_resched()`

## 5. 使用场景

1. **内核数据遍历**：用户空间安全读取内核内部数据结构，例如：
   - 遍历所有进程（`bpf_iter_task`）
   - 遍历 BPF 映射内容（`bpf_iter_map_elem`）
   - 遍历网络连接（`bpf_iter_tcp`）
2. **调试与监控**：替代 `/proc` 或 `debugfs` 接口，提供更灵活、可编程的数据导出
3. **性能分析**：高效收集内核状态快照，避免频繁系统调用开销
4. **安全审计**：以只读方式检查内核对象，无需暴露原始指针或增加系统调用

> **注**：该文件被截断，实际 `bpf_iter_prog_supported()` 函数未完整显示，但核心逻辑已涵盖。完整实现还需处理 `ctx_arg_info` 等上下文参数配置。