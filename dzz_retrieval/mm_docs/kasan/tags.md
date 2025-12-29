# kasan\tags.c

> 自动生成时间: 2025-12-07 16:22:41
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\tags.c`

---

# kasan/tags.c 技术文档

## 1. 文件概述

`kasan/tags.c` 是 Linux 内核中 **KASAN（Kernel Address Sanitizer）** 框架的一部分，专门用于 **基于标签（tag-based）的 KASAN 实现**。该文件主要负责管理内存分配/释放时的 **调用栈信息收集机制**，通过一个环形缓冲区（stack ring）记录对象的分配与释放上下文，以便在检测到内存错误时提供更详细的诊断信息。

## 2. 核心功能

### 主要数据结构
- `enum kasan_arg_stacktrace`：定义 KASAN 栈追踪的配置选项（默认、关闭、开启）。
- `struct kasan_stack_ring`：全局环形缓冲区结构，用于存储内存操作的调用栈信息。
- `struct kasan_stack_ring_entry`（隐式定义）：环形缓冲区中的单个条目，包含对象指针、大小、PID、调用栈句柄及操作类型（分配/释放）。

### 主要函数
- `early_kasan_flag_stacktrace()`：解析内核启动参数 `kasan.stacktrace=off/on`。
- `early_kasan_flag_stack_ring_size()`：解析内核启动参数 `kasan.stack_ring_size=<size>`。
- `kasan_init_tags()`：初始化 KASAN 标签模式下的栈追踪功能和环形缓冲区。
- `save_stack_info()`：内部函数，将内存操作的上下文信息写入环形缓冲区。
- `kasan_save_alloc_info()`：供分配路径调用，保存分配时的栈信息。
- `kasan_save_free_info()`：供释放路径调用，保存释放时的栈信息。

### 全局变量
- `kasan_arg_stacktrace`：启动阶段解析的栈追踪配置。
- `kasan_flag_stacktrace`：运行时控制是否启用栈追踪的静态分支键（static key）。
- `stack_ring`：全局环形缓冲区实例，包含锁、大小、条目数组和当前位置计数器。

## 3. 关键实现

### 栈追踪开关机制
- 使用 `DEFINE_STATIC_KEY_TRUE(kasan_flag_stacktrace)` 默认启用栈追踪。
- 通过 `static_branch_enable/disable()` 在初始化阶段根据启动参数动态调整，避免运行时分支开销。

### 环形缓冲区并发安全写入
- 使用读写锁 `stack_ring.lock` 保护写入过程，防止与错误报告时的读取冲突。
- 采用 **无锁算法** 更新环形缓冲区条目：
  - 每个条目初始指针为 `NULL`。
  - 写入前使用 `try_cmpxchg()` 将条目指针从 `NULL` 原子地替换为 `STACK_RING_BUSY_PTR`（值为 `(void *)1`），标记为“忙”。
  - 若竞争失败（已被其他 CPU 占用），则重试下一个位置。
- 最终通过 `smp_store_release()` 发布对象指针，确保与错误报告中的 `smp_load_acquire()` 形成内存屏障配对，保证数据可见性。

### 启动参数支持
- `kasan.stacktrace=off/on`：显式控制是否收集分配/释放栈信息。
- `kasan.stack_ring_size=<N>`：自定义环形缓冲区大小（单位：条目数），默认为 `32KB / sizeof(entry)`（即 `KASAN_STACK_RING_SIZE_DEFAULT = 32 << 10` 字节，但实际按条目数量分配）。

### 初始化流程
- 若启用栈追踪且未指定缓冲区大小，则使用默认值。
- 使用 `memblock_alloc()` 在早期启动阶段分配连续物理内存作为环形缓冲区。
- 分配失败时打印警告并自动禁用栈追踪功能。

## 4. 依赖关系

- **KASAN 核心模块**：依赖 `kasan.h` 提供的通用接口（如 `kasan_save_stack()`）。
- **内存管理子系统**：使用 `memblock` 进行早期内存分配，依赖 `slab.h` 获取 slab 缓存信息（如 `object_size`）。
- **同步原语**：使用读写锁（`rwlock`）和原子操作（`atomic64_fetch_add`, `try_cmpxchg`）。
- **静态分支优化**：依赖 `linux/static_key.h` 实现零开销的条件判断。
- **堆栈解引用**：依赖内核的 `stackdepot` 机制（通过 `depot_stack_handle_t`）压缩存储调用栈。

## 5. 使用场景

- **内存错误诊断**：当 KASAN 检测到 use-after-free、out-of-bounds 等错误时，若启用了栈追踪，可通过 `kasan_complete_mode_report_info()` 遍历 `stack_ring` 查找对应对象的分配/释放记录，输出完整的调用栈以辅助调试。
- **性能敏感环境**：用户可通过 `kasan.stacktrace=off` 禁用栈收集，在保留基本内存检测能力的同时降低运行时开销。
- **资源受限系统**：通过 `kasan.stack_ring_size` 调整缓冲区大小，平衡诊断信息量与内存占用。
- **内核开发与测试**：在启用 KASAN 的开发版本中，此功能为开发者提供关键的内存生命周期上下文，加速 bug 定位。