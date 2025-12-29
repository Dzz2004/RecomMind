# gup_test.c

> 自动生成时间: 2025-12-07 16:03:14
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `gup_test.c`

---

# gup_test.c 技术文档

## 1. 文件概述

`gup_test.c` 是 Linux 内核中用于测试 **Get User Pages (GUP)** 相关接口的调试模块。该文件提供了多种 ioctl 接口，用于对 `get_user_pages()`、`get_user_pages_fast()`、`pin_user_pages()` 及其变体进行性能基准测试（benchmark）、功能验证和页面状态检查。特别地，它支持对长期固定（longterm pinning）和 DMA 固定（DMA-pinned）语义的验证，并可选择性地转储指定用户页的详细信息。该模块通常通过 debugfs 暴露接口供用户空间测试程序调用。

## 2. 核心功能

### 主要函数

- `__gup_test_ioctl(unsigned int cmd, struct gup_test *gup)`  
  核心测试函数，根据不同的命令执行对应的 GUP/PIN 操作，记录耗时，并在操作后验证页面状态或转储页面信息。

- `put_back_pages(...)`  
  根据命令类型，使用 `put_page()` 或 `unpin_user_pages()` 正确释放之前获取/固定的页面。

- `verify_dma_pinned(...)`  
  验证在 PIN 类命令下获取的页面是否正确标记为 DMA-pinned（以及 longterm-pinnable），若不符合预期则触发警告并 dump 页面。

- `dump_pages_test(...)`  
  根据用户指定的页索引（1-based），转储对应页面的详细信息到内核日志。

- `pin_longterm_test_start/stop/read(...)`  
  实现一个独立的长期固定测试接口，允许用户空间启动、停止和读取被长期固定的用户页面内容。

- `pin_longterm_test_ioctl(...)`  
  为 `PIN_LONGTERM_TEST_*` 系列命令提供 ioctl 入口，通过互斥锁保护全局状态。

### 关键数据结构

- `struct gup_test`（定义于 `gup_test.h`）  
  用户空间传入的测试参数结构体，包含：
  - `addr`: 起始用户虚拟地址
  - `size`: 总字节数
  - `nr_pages_per_call`: 每次 GUP 调用尝试获取的页数
  - `gup_flags`: 传递给 GUP 函数的标志（如 `FOLL_WRITE`）
  - `test_flags`: 测试专用标志（如 `GUP_TEST_FLAG_DUMP_PAGES_USE_PIN`）
  - `which_pages[GUP_TEST_MAX_PAGES_TO_DUMP]`: 指定要 dump 的页索引（1-based）
  - `get_delta_usec` / `put_delta_usec`: 返回 GUP 和 put 操作的耗时（微秒）

- `struct pin_longterm_test`（定义于 `gup_test.h`）  
  用于 `PIN_LONGTERM_TEST_START` 命令的参数结构体，包含地址、大小和标志（如是否使用 write 或 fast 路径）。

### 全局变量

- `pin_longterm_test_mutex`: 保护长期固定测试的互斥锁。
- `pin_longterm_test_pages`: 指向长期固定页面数组的指针。
- `pin_longterm_test_nr_pages`: 已成功固定的页面数量。

## 3. 关键实现

### GUP/PIN 操作分发
`__gup_test_ioctl` 函数通过 `switch(cmd)` 分发到不同的 GUP/PIN 接口：
- **Fast 路径**（`_FAST_BENCHMARK`）：使用无 mmap 锁的 `*_fast` 版本。
- **基本路径**（`_BASIC_TEST`）：使用需持有 `mmap_read_lock` 的标准版本。
- **Longterm 固定**：在 `pin_user_pages` 调用中额外传入 `FOLL_LONGTERM` 标志。
- **Dump 测试**：根据 `test_flags` 决定使用 pin 还是 get 方式获取页面。

### 页面释放策略
`put_back_pages` 根据命令类型区分释放方式：
- 对于 `get_user_pages` 获取的页面，使用 `put_page()`。
- 对于 `pin_user_pages` 获取的页面，必须使用 `unpin_user_pages()` 以正确处理 DMA-pinned 状态。

### DMA-pinned 状态验证
`verify_dma_pinned` 在 PIN 类操作后遍历所有页面：
- 使用 `folio_maybe_dma_pinned()` 检查页面是否被标记为 DMA-pinned。
- 对于 `PIN_LONGTERM_BENCHMARK`，额外使用 `folio_is_longterm_pinnable()` 验证页面是否适合长期固定。
- 若验证失败，调用 `dump_page()` 输出详细诊断信息。

### 长期固定测试机制
`pin_longterm_test_*` 系列函数实现了一个状态保持型测试：
- **START**: 分配页面数组，循环调用 pin 接口直到完成或出错，保存结果到全局变量。
- **STOP**: 释放所有已固定的页面并清理全局状态。
- **READ**: 将每个固定页面的内容通过 `kmap_local_page()` 映射后拷贝到用户空间指定地址。

### 内存与锁管理
- 使用 `kvcalloc/kvfree` 分配/释放大块页面指针数组。
- 非 fast 路径操作需持有 `mmap_read_lock`，并通过 `mmap_read_lock_killable` 支持信号中断。
- 长期固定测试通过 `DEFINE_MUTEX` 保证多进程/线程安全。

## 4. 依赖关系

- **核心内存管理子系统**：依赖 `<linux/mm.h>` 提供的 `get_user_pages*`、`pin_user_pages*`、`put_page`、`unpin_user_pages` 等接口。
- **高内存支持**：使用 `<linux/highmem.h>` 中的 `kmap_local_page`/`kunmap_local` 访问高内存页面。
- **用户空间交互**：依赖 `<linux/uaccess.h>` 的 `copy_from_user`/`copy_to_user`。
- **时间测量**：使用 `<linux/ktime.h>` 进行高精度耗时统计。
- **调试接口**：通过 `<linux/debugfs.h>`（虽未直接使用，但通常与 debugfs 配合）暴露测试入口。
- **内部头文件**：包含 `"gup_test.h"` 定义的 ioctl 命令和数据结构。

## 5. 使用场景

- **GUP/PIN 接口回归测试**：验证内核 GUP 相关函数在不同 flags 和路径下的正确性。
- **性能基准测试**：测量 `get_user_pages_fast` vs `get_user_pages`、`pin` vs `get` 等操作的性能差异。
- **DMA-pinned 语义验证**：确保驱动或子系统在需要 DMA 安全固定页面时，正确使用 pin 接口并得到预期的页面状态。
- **长期固定行为测试**：专门测试 `FOLL_LONGTERM` 场景下页面的可固定性和生命周期管理。
- **页面状态调试**：通过 `DUMP_USER_PAGES_TEST` 命令，在出现问题时 dump 特定用户页的内核元数据（如引用计数、映射信息等）。
- **开发与故障排查**：内核开发者在修改 GUP 相关代码后，使用此模块快速验证变更影响。