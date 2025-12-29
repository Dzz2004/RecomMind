# usercopy.c

> 自动生成时间: 2025-12-07 17:30:09
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `usercopy.c`

---

# usercopy.c 技术文档

## 1. 文件概述

`usercopy.c` 实现了 Linux 内核中 `CONFIG_HARDENED_USERCOPY*` 系列安全机制的核心检查逻辑，旨在防止内核内存在用户空间与内核空间之间进行数据拷贝（如 `copy_from_user()` 和 `copy_to_user()`）时发生**非预期的暴露（exposure）或覆写（overwrite）**。该机制源自 PaX 的 `PAX_USERCOPY` 安全特性，通过严格验证待拷贝缓冲区的合法性，阻止攻击者利用内核漏洞读取或篡改敏感内核数据。

## 2. 核心功能

### 主要函数

- **`__check_object_size(const void *ptr, unsigned long n, bool to_user)`**  
  入口函数，对指定内存区域 `[ptr, ptr+n)` 执行完整的安全性检查。
  
- **`usercopy_abort(const char *name, const char *detail, bool to_user, unsigned long offset, unsigned long len)`**  
  安全违规处理函数，打印详细错误信息并触发内核 `BUG()` 崩溃。

- **`check_stack_object(const void *obj, unsigned long len)`**  
  检查对象是否位于当前任务的合法栈范围内，并进一步判断是否处于有效栈帧内。

- **`check_heap_object(const void *ptr, unsigned long n, bool to_user)`**  
  验证堆分配对象（包括 slab、vmalloc、高端内存映射等）的边界和合法性。

- **`check_kernel_text_object(unsigned long ptr, unsigned long n, bool to_user)`**  
  检测访问是否涉及内核代码段（`.text`），防止内核指令被意外读取或修改。

- **`check_bogus_address(unsigned long ptr, unsigned long n, bool to_user)`**  
  检查地址是否为非法值（如空指针、地址回绕等）。

- **`overlaps(unsigned long ptr, unsigned long n, unsigned long low, unsigned long high)`**  
  辅助函数，判断两个内存区间是否重叠。

### 关键数据结构/宏

- **`bypass_usercopy_checks`**  
  静态跳转键（static key），用于在运行时动态关闭所有用户拷贝检查（通常仅用于调试）。

- **`parse_hardened_usercopy(char *str)`**  
  内核启动参数解析函数（未完整显示），用于通过 `hardened_usercopy=` 参数控制是否启用检查。

- **返回码枚举（隐式定义）**：
  - `NOT_STACK`：对象不在栈上
  - `GOOD_FRAME`：对象完全位于有效栈帧内
  - `GOOD_STACK`：对象在栈上但无法精确验证帧
  - `BAD_STACK`：栈位置非法或跨越栈边界

## 3. 关键实现

### 多层次内存区域验证
`__check_object_size()` 按顺序执行以下检查：

1. **地址有效性检查**  
   使用 `check_bogus_address()` 排除空指针、零长度及地址算术溢出（回绕）情况。

2. **栈内存检查**  
   调用 `check_stack_object()`：
   - 首先确认对象完全位于当前任务的栈页（`[stack, stack + THREAD_SIZE)`）内；
   - 若架构支持（`arch_within_stack_frames`），进一步验证是否处于合法调用帧中；
   - 若支持当前栈指针（`current_stack_pointer`），还会检查对象是否位于当前栈指针的有效方向内（考虑栈增长方向）。

3. **堆内存检查**  
   `check_heap_object()` 区分多种分配类型：
   - **kmap 地址**：限制单页内偏移不超过页边界；
   - **vmalloc 地址**：通过 `find_vmap_area()` 获取虚拟内存区域，验证不越界；
   - **物理页分配（folio）**：
     - 若为 slab 对象，调用 `__check_heap_object()`（定义于 `slab.h`）检查是否在缓存的 `useroffset/usersize` 白名单范围内；
     - 若为大页（`folio_test_large`），验证不超出 folio 范围。

4. **内核文本段保护**  
   `check_kernel_text_object()` 检查是否与 `_stext` 到 `_etext` 区间重叠，并额外处理某些架构存在的线性映射别名（通过 `lm_alias()`）。

### 安全违规响应
一旦任一检查失败，立即调用 `usercopy_abort()`：
- 打印包含操作方向（to/from user）、对象类型、偏移、长度等详细信息；
- 调用 `BUG()` 触发内核崩溃，防止继续执行可能被利用的路径。

### 性能优化
- 使用 `static_branch_unlikely(&bypass_usercopy_checks)` 实现检查开关，正常启用时几乎无性能开销；
- 栈帧检查使用 `noinline` 避免内联膨胀；
- 零长度拷贝直接跳过所有检查。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/mm.h>`, `<linux/slab.h>`, `"slab.h"`：内存管理及 slab 分配器接口
  - `<linux/vmalloc.h>`：vmalloc 区域查询
  - `<linux/highmem.h>`：高端内存映射（kmap）判断
  - `<asm/sections.h>`：内核符号 `_stext`/`_etext`
  - `<linux/jump_label.h>`：静态跳转键支持

- **架构依赖**：
  - `arch_within_stack_frames()`：由各架构提供栈帧验证实现
  - `current_stack_pointer`：需 `CONFIG_ARCH_HAS_CURRENT_STACK_POINTER`
  - `lm_alias()`：处理内核线性映射别名（如 x86 的 `__va()`/`__pa()` 非对称映射）

- **导出符号**：
  - `EXPORT_SYMBOL(__check_object_size)`：供其他模块（如驱动、文件系统）在自定义用户拷贝路径中调用

## 5. 使用场景

- **内核用户拷贝入口点**  
  在 `copy_from_user()` / `copy_to_user()` 等函数内部（通常通过 `might_fault()` 或特定配置选项）调用 `__check_object_size()`，确保传入的内核缓冲区安全。

- **Slab 缓存白名单验证**  
  当使用 `kmem_cache_create_usercopy()` 创建允许部分暴露给用户的 slab 缓存时，此文件验证访问是否严格限制在声明的 `useroffset` 和 `usersize` 范围内。

- **安全加固默认行为**  
  启用 `CONFIG_HARDENED_USERCOPY` 后，所有未显式绕过检查的内核-用户数据传输均受保护，有效缓解因缓冲区溢出、Use-After-Free 等漏洞导致的内核信息泄露或提权攻击。

- **调试与禁用**  
  通过内核启动参数 `hardened_usercopy=0` 可临时禁用检查（需 `parse_hardened_usercopy` 完整实现），用于调试或兼容特殊硬件驱动。