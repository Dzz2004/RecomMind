# rseq.c

> 自动生成时间: 2025-10-25 15:54:26
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rseq.c`

---

# rseq.c 技术文档

## 文件概述

`rseq.c` 实现了 Linux 内核对 **Restartable Sequences（可重启序列）** 系统调用的支持。该机制允许用户空间程序在不使用重量级原子操作的前提下，高效地执行与调度器抢占、信号投递和 CPU 迁移相关的**伪原子操作**，特别适用于高性能的每 CPU（per-CPU）数据结构操作。该文件负责管理用户空间注册的 `struct rseq` TLS（线程局部存储）区域，并在任务被抢占、迁移或收到信号时，安全地中止并重定向用户空间执行流。

## 核心功能

### 主要数据结构
- `struct rseq`：用户空间注册的 TLS 结构，包含 `cpu_id_start`、`cpu_id`、`node_id`、`mm_cid` 和 `rseq_cs`（critical section 描述符指针）等字段。
- `struct rseq_cs`：用户空间关键区（critical section）的描述结构，包含起始地址、提交地址、中止地址和标志位。

### 主要函数
- `rseq_update_cpu_node_id(struct task_struct *t)`  
  更新任务的 `rseq` TLS 区域中的 CPU ID、NUMA 节点 ID 和内存上下文 ID（mm_cid），用于反映当前执行上下文。
  
- `rseq_reset_rseq_cpu_node_id(struct task_struct *t)`  
  将任务的 `rseq` TLS 区域重置为初始状态（`cpu_id` 设为 `RSEQ_CPU_ID_UNINITIALIZED`）。

- `rseq_get_rseq_cs_ptr_val(struct rseq __user *rseq, u64 *rseq_cs)`  
  从用户空间 `rseq` 结构中安全读取 `rseq_cs` 指针值。

- `rseq_get_rseq_cs(struct task_struct *t, struct rseq_cs *rseq_cs)`  
  若 `rseq_cs` 指针有效，则从用户空间复制并验证 `struct rseq_cs` 内容（代码片段未完整展示）。

- `rseq_validate_ro_fields(struct task_struct *t)`（仅在 `CONFIG_DEBUG_RSEQ` 下启用）  
  验证用户空间 `rseq` 结构中应为只读的字段是否与内核副本一致，防止用户空间篡改。

### 宏定义
- `rseq_unsafe_put_user()`：在写入用户空间 `rseq` 字段的同时，同步更新内核中的副本（调试模式下），确保状态一致性。
- `RSEQ_CS_NO_RESTART_FLAGS`：定义关键区中禁止因抢占、信号或迁移而重启的标志组合。

## 关键实现

### 可重启序列执行模型
用户空间关键区执行流程如下：
1. 将关键区描述符地址写入 TLS 的 `rseq->rseq_cs`；
2. 比较 `cpu_id_start` 与当前 `cpu_id`，不一致则跳转至 `abort_ip`；
3. 执行关键区操作；
4. 成功提交后继续正常执行。

若在步骤 1–3 之间发生**抢占、CPU 迁移或信号投递**，内核会：
- 清空 `rseq->rseq_cs`（设为 NULL）；
- 将用户空间返回地址设置为 `abort_ip`；
- 恢复执行时跳转至中止处理逻辑。

### 安全访问与调试支持
- 使用 `user_read_access_begin/end()` 和 `user_write_access_begin/end()` 确保对用户空间内存的安全访问。
- 在 `CONFIG_DEBUG_RSEQ` 模式下，内核维护 `rseq` 字段的内核副本，并在每次更新前后校验用户空间只读字段的一致性，防止恶意或错误的用户空间修改。
- 通过 `trace_rseq_update()` 提供跟踪点，便于性能分析和调试。

### 兼容性处理
- 原始 `rseq` 结构大小为 32 字节（`ORIG_RSEQ_SIZE`）；
- 对于扩展字段（如 `mm_cid`），仅在 `t->rseq_len > ORIG_RSEQ_SIZE` 时才进行更新或重置，确保向后兼容。

## 依赖关系

- **调度子系统**：依赖 `raw_smp_processor_id()` 获取当前 CPU，`task_mm_cid()` 获取内存上下文 ID。
- **内存管理**：使用 `cpu_to_node()` 获取 NUMA 节点信息。
- **用户空间访问**：依赖 `uaccess.h` 提供的安全用户空间读写原语（如 `unsafe_get_user`/`unsafe_put_user`）。
- **跟踪系统**：通过 `trace/events/rseq.h` 集成内核跟踪基础设施。
- **架构支持**：依赖 `asm/ptrace.h` 处理信号/抢占后的用户空间返回地址重定向（完整实现位于架构相关代码中）。

## 使用场景

- **高性能 per-CPU 操作**：如无锁计数器、每 CPU 队列等，避免传统原子操作或锁的开销。
- **实时/低延迟应用**：减少因内核同步原语引入的延迟抖动。
- **用户空间调度器/运行时**：如 Go、Java 虚拟机等，用于实现高效的线程本地状态管理。
- **系统调用 `sys_rseq()`**：由用户空间通过 `rseq(2)` 系统调用注册或注销 `rseq` TLS 区域，本文件提供内核侧支持逻辑（注册/注销时调用 `rseq_update_cpu_node_id` 或 `rseq_reset_rseq_cpu_node_id`）。