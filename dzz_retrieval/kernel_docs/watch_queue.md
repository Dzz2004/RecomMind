# watch_queue.c

> 自动生成时间: 2025-10-25 17:50:31
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `watch_queue.c`

---

# watch_queue.c 技术文档

## 文件概述

`watch_queue.c` 实现了 Linux 内核中的**监视队列**（Watch Queue）机制，这是一种基于管道（pipe）构建的通用事件通知系统。该机制允许内核子系统（如文件系统、密钥管理、设备驱动等）向用户空间异步发送结构化通知。用户空间通过创建特殊类型的管道并关联监视队列，即可接收来自内核的各类事件通知。该文件定义了通知的投递、过滤、缓冲管理及与管道集成的核心逻辑。

## 核心功能

### 主要函数

- **`__post_watch_notification()`**  
  核心通知投递函数。遍历指定 `watch_list` 中所有匹配 `id` 的监视器（`watch`），对每个关联的 `watch_queue` 应用过滤规则、安全检查，并将通知写入底层管道。

- **`post_one_notification()`**  
  将单个通知写入指定 `watch_queue` 的底层管道缓冲区。负责从预分配的通知页中获取空闲槽位、填充数据、更新管道头指针并唤醒等待读取的进程。

- **`filter_watch_notification()`**  
  根据 `watch_filter` 中的类型、子类型和信息掩码规则，判断是否允许特定通知通过。

- **`watch_queue_set_size()`**  
  为监视队列分配预分配的通知缓冲区（页数组和位图），并调整底层管道的环形缓冲区大小。

- **`watch_queue_pipe_buf_release()`**  
  管道缓冲区释放回调。当用户空间读取完通知后，将对应的通知槽位在位图中标记为空闲，供后续复用。

### 关键数据结构

- **`struct watch_queue`**  
  表示一个监视队列，包含：
  - 指向底层 `pipe_inode_info` 的指针
  - 预分配的通知页数组（`notes`）
  - 通知槽位空闲位图（`notes_bitmap`）
  - 通知过滤器（`filter`）
  - 保护锁（`lock`）

- **`struct watch_notification`**  
  通用通知记录格式，包含类型（`type`）、子类型（`subtype`）、信息字段（`info`，含长度和ID）及可变负载。

- **`struct watch_filter` / `struct watch_type_filter`**  
  定义通知过滤规则，支持按类型、子类型及信息字段的位掩码进行精确过滤。

- **`watch_queue_pipe_buf_ops`**  
  自定义的 `pipe_buf_operations`，用于管理监视队列专用管道缓冲区的生命周期。

## 关键实现

### 基于管道的通知传输
- 监视队列复用内核管道（`pipe_inode_info`）作为通知传输通道，利用其成熟的读写、轮询、异步通知机制。
- 通过自定义 `pipe_buf_operations`（`watch_queue_pipe_buf_ops`）实现通知槽位的回收：当用户读取通知后，`release` 回调将对应槽位在 `notes_bitmap` 中置位，标记为空闲。

### 预分配通知缓冲区
- 通知数据存储在预分配的内核页（`notes`）中，每页划分为多个固定大小（128字节）的槽位（`WATCH_QUEUE_NOTE_SIZE`）。
- 使用位图（`notes_bitmap`）跟踪槽位使用状态，1 表示空闲。投递通知时通过 `find_first_bit()` 快速查找空闲槽位。
- 缓冲区大小由用户通过 `watch_queue_set_size()` 设置（1-512个通知），并受管道缓冲区配额限制。

### 通知投递流程
1. **匹配监视器**：遍历 `watch_list`，查找 `id` 匹配的 `watch`。
2. **应用过滤**：若队列配置了过滤器，调用 `filter_watch_notification()` 决定是否丢弃。
3. **安全检查**：调用 LSM 钩子 `security_post_notification()` 进行权限验证。
4. **写入管道**：
   - 获取空闲通知槽位，复制通知数据。
   - 构造 `pipe_buffer` 指向该槽位，设置自定义操作集。
   - 更新管道 `head` 指针，唤醒等待读取的进程。
   - 若缓冲区满，标记前一个缓冲区为 `PIPE_BUF_FLAG_LOSS` 表示丢包。

### 并发与同步
- **RCU 保护**：`watch_list` 和 `watch_queue` 的访问通过 RCU 机制保护，确保遍历时结构体不被释放。
- **自旋锁**：
  - `wqueue->lock`：保护 `wqueue` 状态（如 `pipe` 指针有效性）。
  - `pipe->rd_wait.lock`：保护管道环形缓冲区的读写操作。
- **原子操作**：管道 `head` 指针使用 `smp_store_release()` 更新，确保与 `pipe_read()` 的同步。

## 依赖关系

- **管道子系统**（`fs/pipe.c`）  
  依赖管道的核心数据结构（`pipe_inode_info`、`pipe_buffer`）和操作接口（`pipe_buf()`、`pipe_full()`、`generic_pipe_buf_*`）。

- **内存管理**  
  使用 `alloc_page()`、`kmap_atomic()` 管理通知缓冲区页，`bitmap_alloc()` 管理槽位位图。

- **安全模块**（LSM）  
  通过 `security_post_notification()` 钩子集成安全策略。

- **用户空间接口**  
  与 `fs/watch_queue.c` 中的系统调用（如 `watch_queue_set_size()`）协同工作，后者负责创建监视队列并与管道关联。

- **头文件依赖**  
  `linux/watch_queue.h`（核心数据结构定义）、`linux/pipe_fs_i.h`（管道内部接口）。

## 使用场景

- **文件系统事件监控**  
  如 `fsnotify` 子系统可通过监视队列向用户空间报告文件访问、修改等事件。

- **密钥管理通知**  
  内核密钥环（`KEYS`）子系统使用该机制通知密钥状态变更（如过期、撤销）。

- **设备事件上报**  
  设备驱动可利用监视队列异步上报硬件状态变化或错误事件。

- **通用内核事件分发**  
  任何需要向特权用户空间守护进程（如 `systemd`）发送结构化事件的内核子系统均可集成此机制。

- **用户空间消费**  
  应用程序通过 `open("/dev/watch_queue")` 获取监视队列文件描述符，调用 `ioctl()` 设置缓冲区大小和过滤器，然后像读取普通管道一样接收通知。