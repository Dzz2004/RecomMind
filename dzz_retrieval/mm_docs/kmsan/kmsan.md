# kmsan\kmsan.h

> 自动生成时间: 2025-12-07 16:31:25
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kmsan\kmsan.h`

---

# `kmsan/kmsan.h` 技术文档

## 文件概述

`kmsan.h` 是 Linux 内核内存安全检测工具 **Kernel Memory Sanitizer (KMSAN)** 的核心头文件，定义了 KMSAN 运行时所需的数据结构、宏、全局变量和函数接口。KMSAN 用于检测内核中未初始化内存的使用（use-of-uninitialized-value）问题，通过维护每字节数据的**影子（shadow）** 和**起源（origin）** 元数据，在运行时追踪内存初始化状态并报告错误。

该头文件为编译器插桩（instrumentation）生成的代码提供运行时支持，并确保 KMSAN 自身执行过程的安全性和一致性。

## 核心功能

### 宏定义
- `KMSAN_ALLOCA_MAGIC_ORIGIN` / `KMSAN_CHAIN_MAGIC_ORIGIN`：特殊起源 ID，用于标识栈分配或起源链操作。
- `KMSAN_POISON_*`：内存毒化（poisoning）模式标志（不检查、检查、释放后毒化）。
- `KMSAN_ORIGIN_SIZE`：起源元数据大小（4 字节）。
- `KMSAN_MAX_ORIGIN_DEPTH`：起源链最大深度（7 层）。
- `KMSAN_STACK_DEPTH`：堆栈跟踪深度（64 帧）。
- `KMSAN_META_SHADOW` / `KMSAN_META_ORIGIN`：元数据类型标识符。
- `KMSAN_WARN_ON(cond)`：带状态禁用和可选 panic 的断言宏。

### 全局变量
- `kmsan_enabled`：KMSAN 是否启用（bool）。
- `panic_on_kmsan`：检测到错误时是否触发内核 panic（int）。

### 数据结构
- `struct shadow_origin_ptr`：包含指向影子和起源元数据的指针对。
- `struct kmsan_ctx`（声明于其他文件）：每个任务/每 CPU 的 KMSAN 上下文，含 `kmsan_in_runtime` 标志。

### 主要函数
- **元数据访问**：
  - `kmsan_get_shadow_origin_ptr()`：获取指定地址范围的影子/起源指针。
  - `kmsan_get_metadata()`：根据类型（影子/起源）返回元数据地址。
- **初始化与设置**：
  - `kmsan_init_alloc_meta_for_range()`：为指定虚拟地址范围预分配元数据。
  - `kmsan_setup_meta()`：为物理页关联影子页和起源页。
- **错误报告**：
  - `kmsan_report()`：报告未初始化内存使用错误。
  - `kmsan_print_origin()`：打印起源堆栈信息。
- **运行时控制**：
  - `kmsan_enter_runtime()` / `kmsan_leave_runtime()`：标记进入/离开 KMSAN 运行时。
  - `kmsan_in_runtime()`：判断当前是否处于 KMSAN 运行时上下文。
- **堆栈处理**：
  - `kmsan_save_stack()` / `kmsan_save_stack_with_flags()`：保存当前调用栈并返回句柄。
  - 起源链辅助函数（`kmsan_extra_bits`, `kmsan_uaf_from_eb`, `kmsan_depth_from_eb`）。
- **内部操作（非递归安全）**：
  - `kmsan_internal_memmove_metadata()`：复制元数据。
  - `kmsan_internal_poison_memory()` / `kmsan_internal_unpoison_memory()`：毒化/解毒内存。
  - `kmsan_internal_set_shadow_origin()`：直接设置影子和起源值。
  - `kmsan_internal_chain_origin()`：构建起源链。
  - `kmsan_internal_task_create()`：初始化新任务的 KMSAN 上下文。
  - `kmsan_internal_check_memory()`：主动检查内存初始化状态。
- **地址空间判断**：
  - `kmsan_internal_is_module_addr()` / `kmsan_internal_is_vmalloc_addr()`：安全判断地址是否属于模块或 vmalloc 区域。

## 关键实现

### 运行时递归防护
KMSAN 使用 `kmsan_in_runtime()` 检查防止运行时函数被自身插桩代码递归调用：
- 检查硬中断嵌套层数（>1）或 NMI 上下文时直接返回 `true`。
- 否则查询 per-task/per-CPU 上下文中的 `kmsan_in_runtime` 计数器。
- `kmsan_enter_runtime()`/`kmsan_leave_runtime()` 通过原子增减该计数器管理入口区域。

### 起源（Origin）压缩存储
利用 `stackdepot` 的额外位（extra bits）存储起源链信息：
- 最低位表示是否为 Use-After-Free（UAF）。
- 高位存储起源链深度（最大 7，故需 3 位，共使用 4 位）。
- 通过 `kmsan_extra_bits()` 打包，`kmsan_uaf_from_eb()` 和 `kmsan_depth_from_eb()` 解包。

### 错误报告机制
`kmsan_report()` 支持细粒度报告：
- 对同一内存访问中不同起源的未初始化字节分段报告（通过 `off_first`/`off_last`）。
- 支持多种错误场景（如 `REASON_COPY_TO_USER` 表示向用户态泄露未初始化数据）。

### 元数据布局
- 影子（shadow）：每字节对应 1 字节，标记是否初始化。
- 起源（origin）：每 4 字节数据对应 4 字节起源 ID（`KMSAN_ORIGIN_SIZE=4`）。
- 元数据独立映射，通过 `kmsan_get_metadata()` 动态计算地址。

### 安全断言
`KMSAN_WARN_ON()` 在条件成立时：
1. 禁用 KMSAN（`kmsan_enabled = false`）。
2. 若 `panic_on_kmsan` 启用，则调用 `BUG()`（避免在 uaccess 上下文中调用 `panic()`）。

## 依赖关系

- **架构相关**：依赖 `<asm/pgtable_64_types.h>` 获取 `MODULES_VADDR`、`VMALLOC_START` 等地址边界（仅限 64 位）。
- **内核子系统**：
  - 内存管理（`<linux/mm.h>`）：页分配、vmalloc 处理。
  - 调度器（`<linux/sched.h>`）：任务结构体中的 `kmsan_ctx`。
  - 中断/NMI（`<linux/irqflags.h>`, `<linux/nmi.h>`）：运行时上下文判断。
  - 堆栈跟踪（`<linux/stacktrace.h>`, `<linux/stackdepot.h>`）：起源信息存储。
- **编译器支持**：需 Clang 编译器插桩生成对 `kmsan_get_shadow_origin_ptr()` 等函数的调用。

## 使用场景

1. **编译器插桩**：Clang 在访问内存前插入对 `kmsan_get_shadow_origin_ptr()` 的调用，检查影子状态。
2. **内存分配/释放**：
   - `kmalloc`/`kfree`、`vmalloc`/`vfree` 等路径调用 `kmsan_internal_poison_memory()` 标记未初始化或释放状态。
   - 页面分配器通过 `kmsan_setup_meta()` 关联元数据页。
3. **错误检测**：
   - 当插桩代码发现未初始化内存被使用时，调用 `kmsan_report()` 输出详细错误。
   - 显式检查点（如系统调用出口）调用 `kmsan_internal_check_memory()` 防止泄露。
4. **任务创建**：`copy_process()` 调用 `kmsan_internal_task_create()` 初始化子进程 KMSAN 上下文。
5. **元数据操作**：`memcpy`/`memmove` 等函数的 KMSAN 版本调用 `kmsan_internal_memmove_metadata()` 同步元数据。