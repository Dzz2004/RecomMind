# bpf\stackmap.c

> 自动生成时间: 2025-10-25 12:30:30
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\stackmap.c`

---

# `bpf/stackmap.c` 技术文档

## 1. 文件概述

`bpf/stackmap.c` 实现了 BPF（Berkeley Packet Filter）子系统中的 **栈映射（stack map）** 功能，用于高效地存储和查询用户态或内核态的调用栈（call stack）信息。该映射支持两种模式：
- **原始 IP 地址模式**：直接存储程序计数器（PC）地址。
- **Build ID + 偏移量模式**：将 IP 地址转换为对应二进制文件的 Build ID 和相对于该文件的偏移量，便于符号化解析且不受 ASLR 影响。

该文件为 BPF 程序提供 `bpf_get_stackid()` 辅助函数的后端实现，是性能分析、追踪和调试工具（如 perf、bpftrace）的关键组件。

## 2. 核心功能

### 主要数据结构

- **`struct stack_map_bucket`**  
  哈希桶中的条目，包含：
  - `fnode`：用于 per-CPU 自由链表管理
  - `hash`：调用栈内容的哈希值
  - `nr`：栈帧数量
  - `data[]`：变长数组，存储栈数据（`u64` IP 或 `struct bpf_stack_build_id`）

- **`struct bpf_stack_map`**  
  BPF 栈映射的私有结构，继承自 `struct bpf_map`，包含：
  - `elems`：预分配的桶内存池
  - `freelist`：per-CPU 自由链表，用于高效分配/回收桶
  - `n_buckets`：哈希表桶数量（2 的幂）
  - `buckets[]`：哈希桶指针数组

- **`struct bpf_stack_build_id`**（外部定义）  
  Build ID 模式下的栈帧表示，包含：
  - `status`：状态（`BPF_STACK_BUILD_ID_IP` 或 `BPF_STACK_BUILD_ID_VALID`）
  - `ip`：原始 IP（仅当 status 为 IP 时有效）
  - `offset`：相对于映射起始地址的偏移
  - `build_id[]`：Build ID 字节数组

### 主要函数

- **`stack_map_alloc()`**  
  BPF 栈映射的分配器，验证属性、预分配内存、初始化自由链表和调用链缓冲区。

- **`__bpf_get_stackid()`**  
  核心逻辑：根据传入的调用栈生成唯一 ID，执行哈希查找、比较和插入。

- **`stack_map_get_build_id_offset()`**  
  将原始 IP 地址转换为 Build ID + 偏移量格式，需持有 mmap 读锁。

- **`get_callchain_entry_for_task()`**  
  从指定任务结构中提取内核态调用栈（仅在 `CONFIG_STACKTRACE` 启用时有效）。

- **`bpf_get_stackid()`**（BPF_CALL_3 宏定义）  
  BPF 程序调用的入口点，根据寄存器上下文获取当前调用栈并返回其 ID。

## 3. 关键实现

### 哈希表设计
- 使用 **开放寻址 + 覆盖替换** 策略：每个桶 ID 对应唯一哈希桶，冲突时直接替换旧条目。
- 哈希函数为 `jhash2()`，对栈 IP 数组进行哈希。
- 桶数量为 `max_entries` 的 2 次幂，通过位掩码 `hash & (n_buckets - 1)` 快速定位。

### 内存管理
- **预分配内存池**：在映射创建时一次性分配所有桶内存（`smap->elems`）。
- **Per-CPU 自由链表**：使用 `pcpu_freelist` 实现无锁、高效的桶分配/回收，避免运行时内存分配开销。

### Build ID 转换
- 通过 `find_vma()` 查找 IP 所属的 VMA（虚拟内存区域）。
- 调用 `build_id_parse()` 从 VMA 的 ELF 头中提取 Build ID。
- 计算偏移量：`offset = (vma->vm_pgoff << PAGE_SHIFT) + ip - vma->vm_start`。
- **锁机制**：使用 `mmap_read_trylock()` 获取 mmap 读锁，失败时回退到原始 IP 模式。
- **中断上下文安全**：通过 `mmap_unlock_irq_work` 机制确保在中断上下文中安全释放 mmap 锁。

### 快速比较优化
- 若设置 `BPF_F_FAST_STACK_CMP` 标志，仅比较哈希值，不进行内容 memcmp，适用于对哈希冲突不敏感的场景。

### 栈深度限制
- 最大栈深度由 `sysctl_perf_event_max_stack` 控制，映射的 `value_size` 必须是单个栈帧大小的整数倍且不超过该限制。

## 4. 依赖关系

- **BPF 核心**：`<linux/bpf.h>`、`bpf_map` 基础设施
- **内存管理**：`<linux/percpu.h>`（per-CPU 自由链表）、`bpf_map_area_alloc/free`
- **栈追踪**：`<linux/stacktrace.h>`、`<linux/perf_event.h>`（调用链缓冲区）
- **Build ID 支持**：`<linux/buildid.h>`、VMA 操作（`find_vma`、`range_in_vma`）
- **内存映射锁**：`mmap_unlock_work.h`（安全释放 mmap 锁）
- **哈希函数**：`<linux/jhash.h>`
- **配置选项**：`CONFIG_STACKTRACE`（内核栈追踪支持）

## 5. 使用场景

- **性能分析**：BPF 程序通过 `bpf_get_stackid()` 获取当前调用栈 ID，后续通过 `bpf_map_lookup_elem()` 读取完整栈内容，用于火焰图生成。
- **系统追踪**：结合 kprobe/uprobe，记录特定函数调用时的完整调用上下文。
- **安全监控**：检测异常调用路径（如敏感系统调用的调用者）。
- **调试工具**：为 `perf`、`bpftrace`、`bcc` 等工具提供高效的栈存储后端。
- **Build ID 模式**：在 ASLR（地址空间布局随机化）环境下，通过 Build ID + 偏移实现稳定的符号化解析，适用于长期运行的监控场景。