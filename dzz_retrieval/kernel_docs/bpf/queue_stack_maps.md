# bpf\queue_stack_maps.c

> 自动生成时间: 2025-10-25 12:28:15
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\queue_stack_maps.c`

---

# bpf/queue_stack_maps.c 技术文档

## 1. 文件概述

`bpf/queue_stack_maps.c` 实现了 BPF（Berkeley Packet Filter）子系统中的两种特殊映射类型：**队列（Queue）** 和 **栈（Stack）**。这两种映射提供先进先出（FIFO）和后进先出（LIFO）的数据结构语义，用于在 eBPF 程序与用户空间之间高效传递数据。该文件定义了共享的底层数据结构 `struct bpf_queue_stack`，并通过两套不同的操作函数（`queue_map_ops` 和 `stack_map_ops`）分别暴露队列和栈的行为。

## 2. 核心功能

### 主要数据结构

- **`struct bpf_queue_stack`**  
  队列/栈映射的底层实现结构体，包含：
  - `struct bpf_map map`：继承自通用 BPF 映射结构
  - `raw_spinlock_t lock`：保护并发访问的原始自旋锁
  - `u32 head, tail`：环形缓冲区的头尾指针
  - `u32 size`：缓冲区实际大小（`max_entries + 1`）
  - `char elements[]`：变长数组，存储实际元素数据（8 字节对齐）

### 主要函数

- **内存管理**
  - `queue_stack_map_alloc_check()`：验证创建参数合法性
  - `queue_stack_map_alloc()`：分配并初始化映射内存
  - `queue_stack_map_free()`：释放映射内存
  - `queue_stack_map_mem_usage()`：计算内存占用

- **通用操作（返回错误）**
  - `queue_stack_map_lookup_elem()`：不支持按键查找（返回 `NULL`）
  - `queue_stack_map_update_elem()`：不支持按键更新（返回 `-EINVAL`）
  - `queue_stack_map_delete_elem()`：不支持按键删除（返回 `-EINVAL`）
  - `queue_stack_map_get_next_key()`：不支持迭代（返回 `-EINVAL`）

- **队列专用操作**
  - `queue_map_peek_elem()`：查看队首元素（不删除）
  - `queue_map_pop_elem()`：弹出队首元素

- **栈专用操作**
  - `stack_map_peek_elem()`：查看栈顶元素（不删除）
  - `stack_map_pop_elem()`：弹出栈顶元素

- **共享写入操作**
  - `queue_stack_map_push_elem()`：向队列尾部/栈顶部插入元素（支持 `BPF_EXIST` 覆盖模式）

- **辅助函数**
  - `bpf_queue_stack()`：从 `bpf_map` 指针转换为具体结构体指针
  - `queue_stack_map_is_empty()`：判断是否为空
  - `queue_stack_map_is_full()`：判断是否已满

### 操作函数表

- **`queue_map_ops`**：队列映射的操作函数集合
- **`stack_map_ops`**：栈映射的操作函数集合

## 3. 关键实现

### 环形缓冲区设计
- 使用 `head` 和 `tail` 指针实现环形缓冲区
- 缓冲区实际大小为 `max_entries + 1`，通过牺牲一个槽位区分空/满状态：
  - **空条件**：`head == tail`
  - **满条件**：`(head + 1) % size == tail`

### 并发安全机制
- 使用 `raw_spinlock_t` 保护所有操作
- 特殊处理 NMI（不可屏蔽中断）上下文：
  - 在 NMI 中使用 `raw_spin_trylock_irqsave()` 避免死锁
  - 在其他上下文使用 `raw_spin_lock_irqsave()`

### 队列 vs 栈行为差异
- **队列（FIFO）**：
  - `pop/peek` 操作从 `tail` 读取
  - `push` 操作写入 `head`
- **栈（LIFO）**：
  - `pop/peek` 操作从 `head - 1` 读取
  - `push` 操作写入 `head`

### 覆盖写入策略
- 当缓冲区满时，若指定 `BPF_EXIST` 标志：
  - **队列**：自动推进 `tail` 指针覆盖最旧元素
  - **栈**：自动推进 `tail` 指针（逻辑上丢弃最旧元素）

### 内存布局
- 元数据（`struct bpf_queue_stack`）与元素存储区（`elements[]`）连续分配
- 元素存储区按 8 字节对齐，确保跨架构兼容性

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/bpf.h>`：BPF 核心定义
  - `<linux/list.h>`：内核链表操作
  - `<linux/slab.h>`：内存分配接口
  - `<linux/btf_ids.h>`：BTF（BPF Type Format）类型信息
  - `"percpu_freelist.h"`：每 CPU 空闲列表（虽包含但未直接使用）

- **内核子系统**：
  - **BPF 子系统**：作为 BPF 映射类型注册到核心框架
  - **内存管理子系统**：通过 `bpf_map_area_alloc/free` 分配内存
  - **锁机制**：依赖内核自旋锁实现并发控制

- **BTF 支持**：
  - 通过 `BTF_ID_LIST_SINGLE` 声明类型信息，支持运行时类型检查

## 5. 使用场景

- **eBPF 程序与用户空间通信**：
  - 用户空间通过 `bpf()` 系统调用操作队列/栈
  - eBPF 程序通过 `bpf_map_push/pop/peek_elem()` 辅助函数访问

- **高性能数据传递**：
  - 适用于需要顺序处理数据的场景（如事件日志、采样数据）
  - 队列用于生产者-消费者模型
  - 栈用于需要后进先出语义的场景（如调用栈跟踪）

- **资源受限环境**：
  - 固定大小缓冲区避免动态内存分配开销
  - 无锁设计（仅自旋锁）保证低延迟

- **典型应用**：
  - 网络数据包采样（队列）
  - 函数调用跟踪（栈）
  - 性能监控事件缓冲（队列）