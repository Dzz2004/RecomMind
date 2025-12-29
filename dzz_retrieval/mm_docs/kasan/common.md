# kasan\common.c

> 自动生成时间: 2025-12-07 16:12:35
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\common.c`

---

# kasan\common.c 技术文档

## 1. 文件概述

`kasan\common.c` 是 Linux 内核地址消毒器（Kernel Address SANitizer, KASAN）的核心实现文件之一，包含 KASAN 的通用功能代码。该文件为不同 KASAN 模式（如 Generic、SW_TAGS、HW_TAGS）提供共享的基础设施，包括内存毒化/解毒操作、栈跟踪记录、slab 对象生命周期管理、页级和 slab 级内存状态维护等。其主要目标是检测内核中的内存越界访问、使用已释放内存（Use-After-Free）、重复释放（Double-Free）等内存安全问题。

## 2. 核心功能

### 主要函数

| 函数 | 功能描述 |
|------|--------|
| `kasan_addr_to_slab()` | 将虚拟地址转换为对应的 slab 结构体指针 |
| `kasan_save_stack()` | 保存当前调用栈到 stack depot，并返回句柄 |
| `kasan_set_track()` | 记录当前分配/释放操作的进程 PID 和调用栈 |
| `kasan_enable_current()` / `kasan_disable_current()` | 控制当前任务的 KASAN 检查深度（用于临时禁用） |
| `__kasan_unpoison_range()` | 解毒指定内存区域 |
| `kasan_unpoison_task_stack()` / `kasan_unpoison_task_stack_below()` | 解毒任务栈（完整或部分） |
| `__kasan_unpoison_pages()` / `__kasan_poison_pages()` | 对页面进行解毒/毒化操作 |
| `__kasan_poison_slab()` | 毒化整个 slab 块（包括 redzone） |
| `__kasan_unpoison_object_data()` / `__kasan_poison_object_data()` | 对 slab 对象的有效数据区域进行解毒/毒化 |
| `__kasan_init_slab_obj()` | 初始化 slab 对象（包括元数据和标签分配） |
| `__kasan_slab_free()` / `____kasan_slab_free()` | 处理 slab 对象释放前的 KASAN 检查与毒化 |
| `__kasan_kfree_large()` / `____kasan_kfree_large()` | 处理大块内存（非 slab）释放的 KASAN 检查 |
| `__kasan_slab_alloc()` | 处理 slab 对象分配后的 KASAN 解毒与初始化 |

### 数据结构

- `struct kasan_track`：用于记录内存分配/释放的上下文信息（PID + 调用栈）
- 使用 `depot_stack_handle_t` 类型通过 stack depot 机制高效存储调用栈

## 3. 关键实现

### 标签分配策略（Tag Assignment）
在支持硬件/软件标签的 KASAN 模式（如 SW_TAGS）中，`assign_tag()` 函数根据缓存特性决定标签分配方式：
- **普通缓存**：每次分配时生成随机标签
- **带构造函数（ctor）或 SLAB_TYPESAFE_BY_RCU 的缓存**：在 slab 创建时预分配固定标签，确保对象在整个生命周期内标签一致，避免 RCU 期间或构造函数保存的指针因标签变化而失效

### 内存毒化粒度
- 使用 `KASAN_GRANULE_SIZE`（通常为 8 字节）作为最小毒化单位
- 对象毒化范围为 `round_up(object_size, KASAN_GRANULE_SIZE)`，确保覆盖整个分配区域
- 不同毒化类型使用不同标记值（如 `KASAN_SLAB_FREE`, `KASAN_PAGE_FREE`, `KASAN_SLAB_REDZONE`）

### 释放检查逻辑
`____kasan_slab_free()` 实现了完整的释放前验证：
1. 检查地址是否属于有效 slab 对象
2. 验证是否为非法释放（非对象起始地址）
3. 检测重复释放（通过检查内存是否已毒化）
4. 对合法释放执行毒化并加入隔离区（quarantine）

### 栈跟踪优化
- 使用 `stack_depot` 机制避免重复存储相同调用栈
- 通过 `kasan_stack_collection_enabled()` 控制是否收集释放时的栈信息
- 支持在不可睡眠上下文中安全地保存栈（`can_alloc=false`）

### 高端内存处理
- 显式跳过高端内存（HighMem）页面的 KASAN 操作（`PageHighMem()` 检查）
- 通过 `kasan_sample_page_alloc()` 实现基于概率的采样，降低性能开销

## 4. 依赖关系

### 内核子系统依赖
- **内存管理（MM）**：依赖 `virt_to_slab()`, `page_address()`, `folio` 相关 API
- **Slab 分配器**：与 `slab.h` 紧密集成，处理 `kmem_cache` 和 slab 生命周期
- **Stack Trace**：使用 `stack_trace_save()` 和 `stack_depot` 存储调用栈
- **KFENCE**：通过 `is_kfence_address()` 与 KFENCE 内存调试器协同工作
- **RCU**：特殊处理 `SLAB_TYPESAFE_BY_RCU` 缓存的释放行为

### KASAN 内部依赖
- 依赖架构特定的 KASAN 实现（`kasan_arch_is_ready()`）
- 调用底层毒化原语（`kasan_unpoison()`, `kasan_poison()`）
- 使用 `set_tag()`/`get_tag()` 进行地址标签操作（仅在 TAG 模式下生效）

### 配置选项依赖
- `CONFIG_KASAN_GENERIC` / `CONFIG_KASAN_SW_TAGS` / `CONFIG_KASAN_HW_TAGS`
- `CONFIG_KASAN_STACK`：控制栈内存的毒化行为
- `CONFIG_STACKDEPOT`：提供调用栈存储支持

## 5. 使用场景

### 内存分配路径
- 在 `kmem_cache_alloc()` 和 `kmalloc()` 路径中调用 `__kasan_slab_alloc()` 解毒新分配的对象
- 在 slab 创建时通过 `__kasan_init_slab_obj()` 初始化对象元数据和标签

### 内存释放路径
- 在 `kmem_cache_free()` 和 `kfree()` 路径中调用 `__kasan_slab_free()` 验证并毒化释放的对象
- 处理大块内存释放（`__kasan_kfree_large()`）和 mempool 释放（`__kasan_slab_free_mempool()`）

### 栈保护
- 在任务创建/切换时通过 `kasan_unpoison_task_stack()` 管理栈内存状态
- 在中断/异常返回路径中调用 `kasan_unpoison_task_stack_below()` 动态解毒活跃栈区域

### 调试与诊断
- 当检测到内存错误时，通过保存的 `kasan_track` 信息生成详细的错误报告
- 隔离区（quarantine）机制延迟实际内存释放，提高 Use-After-Free 检测率

### 特殊上下文处理
- 在不可睡眠上下文（如中断）中安全地执行 KASAN 操作
- 通过 `kasan_enable_current()`/`kasan_disable_current()` 临时禁用 KASAN 检查（如在 KASAN 自身代码中）