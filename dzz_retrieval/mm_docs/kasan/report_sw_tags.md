# kasan\report_sw_tags.c

> 自动生成时间: 2025-12-07 16:20:00
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\report_sw_tags.c`

---

# kasan/report_sw_tags.c 技术文档

## 1. 文件概述

`kasan/report_sw_tags.c` 是 Linux 内核中软件标签（Software Tag-based）KASAN（Kernel Address Sanitizer）子系统的一部分，专门用于实现基于软件标签的内存错误检测机制中的**错误报告功能**。该文件提供了在检测到内存访问违规时，用于定位错误地址、解析内存标签、获取分配大小以及打印诊断信息的核心函数。它与硬件标签（Hardware Tag-based）KASAN 的报告逻辑分离，专用于纯软件实现的标签方案。

## 2. 核心功能

### 主要函数

- **`kasan_find_first_bad_addr(const void *addr, size_t size)`**  
  在给定内存区域 `[addr, addr + size)` 中查找第一个标签不匹配的地址（即“坏地址”）。

- **`kasan_get_alloc_size(void *object, struct kmem_cache *cache)`**  
  根据 slab 对象的 KASAN 元数据推断其实际分配大小（仅适用于未释放的对象）。

- **`kasan_metadata_fetch_row(char *buffer, void *row)`**  
  从指定内存行对应的 shadow 内存区域复制元数据到缓冲区，用于调试输出。

- **`kasan_print_tags(u8 addr_tag, const void *addr)`**  
  打印指针携带的标签（pointer tag）和目标内存位置存储的标签（memory tag），用于诊断标签不匹配问题。

- **`kasan_print_address_stack_frame(const void *addr)`** （条件编译：`CONFIG_KASAN_STACK`）  
  若错误地址位于当前任务的栈上，则打印相关信息。

### 数据结构
本文件未定义新的全局数据结构，主要操作内核已有的 `struct kmem_cache` 和 KASAN shadow 内存布局。

## 3. 关键实现

### 软件标签机制基础
- 每个 8 字节对齐的内存块（granule）对应一个字节的 shadow 内存。
- 指针高字节（Top Byte）存储“地址标签”（address tag），shadow 内存存储“内存标签”（memory tag）。
- 合法访问要求两者相等；否则触发 KASAN 报告。

### `kasan_find_first_bad_addr`
- 使用 `get_tag(addr)` 提取指针的地址标签。
- 使用 `kasan_reset_tag(addr)` 清除标签得到真实地址。
- 遍历 `[p, end)` 区间，以 `KASAN_GRANULE_SIZE`（通常为 8）为步长。
- 比较每个 granule 对应的 shadow 值与地址标签，返回首个不匹配地址。

### `kasan_get_alloc_size`
- 直接访问对象起始地址对应的 shadow 内存（跳过 `addr_has_metadata` 检查，因 slab 对象必有 metadata）。
- 从对象起始处逐 granule 检查 shadow 值：
  - 若为 `KASAN_TAG_INVALID`，表示分配边界，返回当前累计大小。
  - 否则累加 `KASAN_GRANULE_SIZE`。
- 最大不超过 `cache->object_size`。

### 标签打印与栈检测
- `kasan_print_tags` 直接读取 shadow 内存值并与指针标签对比输出。
- `kasan_print_address_stack_frame` 利用 `object_is_on_stack()` 判断地址是否属于当前任务栈，并输出任务名和 PID。

## 4. 依赖关系

- **KASAN 核心模块**：依赖 `kasan.h` 中定义的宏（如 `kasan_mem_to_shadow`, `get_tag`, `KASAN_GRANULE_SIZE` 等）。
- **内存管理子系统**：使用 `struct kmem_cache`（来自 `slab.h`）获取对象大小信息。
- **内核通用设施**：
  - `printk` 用于错误输出；
  - `stackdepot` / `stacktrace` 用于调用栈记录（虽未直接调用，但报告流程会用到）；
  - `task_struct` 相关字段（`comm`, `pid`）用于标识出错任务。
- **架构相关代码**：通过 `<asm/sections.h>` 获取内核段信息（间接支持地址合法性判断）。
- **配置选项**：`CONFIG_KASAN_STACK` 控制栈检测功能的编译。

## 5. 使用场景

- **内存越界访问检测**：当发生 out-of-bounds 访问时，KASAN 核心调用 `kasan_find_first_bad_addr` 定位精确错误地址。
- **Use-after-free 检测**：释放对象后其 shadow 被设为 `KASAN_TAG_INVALID`，后续访问触发标签不匹配，通过 `kasan_print_tags` 显示标签差异。
- **错误报告生成**：在 KASAN 报告流程中，调用 `kasan_get_alloc_size` 推断原始分配大小，辅助诊断。
- **调试信息输出**：`kasan_metadata_fetch_row` 供调试工具或详细报告使用，转储 shadow 内容。
- **栈变量错误诊断**：若非法地址位于栈上，`kasan_print_address_stack_frame` 提供上下文信息，帮助定位局部变量生命周期问题。