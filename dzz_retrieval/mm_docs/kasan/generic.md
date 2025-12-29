# kasan\generic.c

> 自动生成时间: 2025-12-07 16:13:15
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\generic.c`

---

# kasan/generic.c 技术文档

## 1. 文件概述

`kasan/generic.c` 是 Linux 内核地址消毒器（Kernel Address Sanitizer, KASAN）的核心通用实现文件。该文件提供了与具体硬件架构无关的内存访问检查逻辑，用于在运行时检测内核中的非法内存访问（如越界读写、使用已释放内存等）。KASAN 通过维护一个影子内存（shadow memory）区域来跟踪每个内存字节的可访问状态，并在每次内存访问前进行验证。

## 2. 核心功能

### 主要函数

- **内存中毒检测函数**：
  - `memory_is_poisoned_1()`：检测单字节访问是否中毒
  - `memory_is_poisoned_2_4_8()`：检测2/4/8字节访问是否中毒
  - `memory_is_poisoned_16()`：检测16字节访问是否中毒
  - `memory_is_poisoned_n()`：检测任意长度内存访问是否中毒
  - `memory_is_poisoned()`：根据编译时常量大小选择最优检测函数

- **内存非零检测函数**：
  - `bytes_is_nonzero()`：逐字节检测内存是否包含非零值
  - `memory_is_nonzero()`：高效检测大块内存是否包含非零值

- **主检查接口**：
  - `check_region_inline()`：内联内存区域检查函数
  - `kasan_check_range()`：对外暴露的内存范围检查接口
  - `kasan_byte_accessible()`：检查单个字节是否可访问

- **全局变量处理**：
  - `register_global()`：注册全局变量并设置红区
  - `__asan_register_globals()` / `__asan_unregister_globals()`：全局变量注册/注销接口

- **编译器插桩接口**：
  - `__asan_load{1,2,4,8,16,N}()`：各种大小的加载操作检查
  - `__asan_store{1,2,4,8,16,N}()`：各种大小的存储操作检查
  - `__asan_handle_no_return()`：空实现占位符
  - `__asan_alloca_poison()`：栈上分配对象的中毒处理

- **SLAB 缓存管理**：
  - `kasan_cache_shrink()`：缓存收缩时的 KASAN 处理
  - `kasan_cache_shutdown()`：缓存关闭时的 KASAN 处理

## 3. 关键实现

### 影子内存映射机制
- 使用 `kasan_mem_to_shadow()` 将实际内存地址转换为对应的影子内存地址
- 每个影子字节对应 `KASAN_GRANULE_SIZE`（通常为8字节）的实际内存
- 影子字节值的含义：
  - 0：全部8字节都可访问
  - 正数（1-7）：前N字节可访问，其余不可访问
  - 负数：整个8字节区域都不可访问（中毒）

### 跨粒度边界处理
- 对于跨越8字节边界的内存访问，需要检查多个影子字节
- `memory_is_poisoned_2_4_8()` 和 `memory_is_poisoned_16()` 特别处理了对齐和跨边界情况
- 未对齐的16字节访问可能映射到3个影子字节

### 编译时优化
- 使用 `__builtin_constant_p()` 在编译时判断访问大小
- 针对常量大小的访问使用专门优化的函数
- 所有核心函数都标记为 `__always_inline` 以确保编译器优化

### 栈分配对象处理
- `__asan_alloca_poison()` 为栈上分配的对象设置左右红区
- 左红区大小为 `KASAN_ALLOCA_REDZONE_SIZE`
- 右红区包括填充区域和固定大小的红区
- 要求分配地址按红区大小对齐

### 全局变量初始化
- 全局变量的有效数据区域被标记为可访问
- 末尾的填充区域（对齐到粒度边界）被标记为全局红区
- 确保全局变量的越界访问能够被检测到

## 4. 依赖关系

### 头文件依赖
- `<linux/kasan.h>`：KASAN 核心接口定义
- `"kasan.h"`：内部 KASAN 实现头文件
- `../slab.h`：SLAB 分配器相关功能
- 其他标准内核头文件（mm、slab、vmalloc 等）

### 功能依赖
- **架构特定代码**：通过 `kasan_arch_is_ready()` 和 `addr_has_metadata()` 依赖架构特定实现
- **内存管理子系统**：依赖 `kasan_mem_to_shadow()` 的内存映射实现
- **错误报告机制**：调用 `kasan_report()` 进行违规访问报告
- **隔离区（Quarantine）**：通过 `kasan_quarantine_remove_cache()` 管理延迟释放的对象
- **KFENCE**：与 KFENCE 内存调试工具共存（头文件包含但无直接调用）

### 导出符号
- 多个 `__asan_*` 函数通过 `EXPORT_SYMBOL` 导出，供编译器生成的插桩代码调用
- 支持模块加载时的动态链接

## 5. 使用场景

### 编译器插桩
- GCC/Clang 在启用 `-fsanitize=kernel-address` 时自动插入对 `__asan_load*`/`__asan_store*` 函数的调用
- 每次内存访问前都会执行相应的检查函数

### 栈对象检测
- 函数内的局部变量（特别是变长数组）通过 `__asan_alloca_poison()` 设置红区保护
- 函数返回时通过 `__asan_allocas_unpoison()` 清理（文件截断，但存在对应实现）

### 全局变量检测
- 编译器为每个全局变量生成 `kasan_global` 结构
- 通过 `__asan_register_globals()` 在模块初始化时注册全局变量信息

### 动态内存检测
- SLAB/SLOB/SLUB 分配器集成 KASAN，在分配/释放时调用相应的中毒/解毒函数
- 缓存管理操作（shrink/shutdown）触发隔离区清理

### 运行时验证
- 所有内核代码路径中的内存访问都会经过 KASAN 检查（如果启用）
- 检测到违规访问时立即报告详细的错误信息，包括访问地址、大小、调用栈等

### 调试和开发
- 主要用于内核开发阶段的内存安全问题调试
- 在生产环境中通常禁用以避免性能开销