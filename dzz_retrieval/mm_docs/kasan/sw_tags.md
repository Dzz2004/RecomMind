# kasan\sw_tags.c

> 自动生成时间: 2025-12-07 16:22:05
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kasan\sw_tags.c`

---

# kasan/sw_tags.c 技术文档

## 1. 文件概述

`kasan/sw_tags.c` 是 Linux 内核中软件实现的基于标签（Software Tag-based）的 KASAN（Kernel Address Sanitizer）核心代码文件。KASAN 是一种用于检测内核内存错误（如越界访问、释放后使用等）的动态检测工具。该文件实现了基于随机内存标签的检测机制，通过为每个内存分配赋予唯一的 8 位标签，并在每次内存访问时验证地址标签与影子内存（shadow memory）中存储的预期标签是否匹配，从而发现非法内存访问。

此实现适用于不支持硬件内存标签（如 ARM64 MTE）的架构，采用纯软件方式模拟标签检查逻辑，属于概率性调试特性，主要用于开发和测试阶段。

## 2. 核心功能

### 主要函数：

- `kasan_init_sw_tags(void)`  
  初始化软件标签 KASAN 子系统，包括为每个 CPU 初始化伪随机数生成器（PRNG）状态，并调用通用标签初始化函数。

- `kasan_random_tag(void)`  
  为新分配的内存对象生成一个随机的 8 位标签（范围为 `0x00` 到 `KASAN_TAG_MAX`），使用线性同余生成器（LCG）算法。

- `kasan_check_range(const void *addr, size_t size, bool write, unsigned long ret_ip)`  
  检查指定内存范围 `[addr, addr + size)` 的所有字节是否具有与地址标签一致的影子标签。若发现不匹配，则触发 KASAN 报告。

- `kasan_byte_accessible(const void *addr)`  
  快速判断单个地址是否可安全访问（即其标签与影子内存中的标签匹配，或为内核保留标签 `0xFF`）。

- `__hwasan_load{1/2/4/8/16}_noabort`, `__hwasan_store{1/2/4/8/16}_noabort`  
  由编译器插桩调用的固定大小内存读写检查函数（对应 1~16 字节访问）。

- `__hwasan_loadN_noabort`, `__hwasan_storeN_noabort`  
  可变长度内存访问的检查函数。

- `__hwasan_tag_memory(void *addr, u8 tag, ssize_t size)`  
  将指定内存区域的影子内存设置为给定标签（用于内存分配/释放时的“染毒”操作）。

- `kasan_tag_mismatch(void *addr, unsigned long access_info, unsigned long ret_ip)`  
  处理标签不匹配异常（通常由汇编 stub 调用），解析访问大小和读写类型后调用通用报告函数。

### 主要数据结构：

- `static DEFINE_PER_CPU(u32, prng_state)`  
  每个 CPU 私有的伪随机数生成器状态，用于生成内存对象标签。

## 3. 关键实现

### 标签生成机制
- 使用 **线性同余生成器**（LCG）：`state = 1664525 * state + 1013904223`，这是一种轻量级 PRNG。
- 每次调用 `kasan_random_tag()` 时更新当前 CPU 的 PRNG 状态并返回 `state % (KASAN_TAG_MAX + 1)` 作为新标签。
- 允许非原子读-改-写操作（因抢占可能导致少量标签重复），但设计上认为这对概率性检测影响可接受，且中断带来的随机扰动反而增强不可预测性。

### 标签检查逻辑
- 地址的高 8 位（Top Byte）存储标签（ARM64 TBI 支持），通过 `get_tag()` 提取。
- 若标签为 `KASAN_TAG_KERNEL`（`0xFF`），直接放行，用于兼容 `kmap`/`page_address` 等场景导致的标签丢失问题。
- 对未标记地址（如 vmalloc 区域）或无元数据区域，直接视为非法访问。
- 遍历访问范围对应的影子内存字节，逐个比对标签是否一致。

### 编译器插桩接口
- 定义了 HWASan（Hardware-assisted AddressSanitizer）ABI 兼容的符号（如 `__hwasan_load8_noabort`），使 Clang 编译器可对内核进行插桩。
- 所有插桩函数最终委托给 `kasan_check_range()` 进行实际检查。

### 内存染毒（Poisoning）
- `__hwasan_tag_memory` 调用 `kasan_poison()` 设置影子内存，用于在对象分配（设有效标签）或释放（设无效标签如 `0xFE`）时更新元数据。

## 4. 依赖关系

- **内部依赖**：
  - `kasan.h`：提供 KASAN 通用接口（如 `kasan_mem_to_shadow`, `kasan_report`, `kasan_poison`）。
  - `../slab.h`：与 SLAB/SLUB 分配器集成，用于对象级别的标签管理。
- **外部依赖**：
  - 内存管理子系统（`mm.h`, `slab.h`, `vmalloc.h`）：获取内存布局和分配信息。
  - 调试与日志（`printk.h`, `bug.h`）：输出初始化信息和错误报告。
  - 调度与 CPU 管理（`sched.h`, `percpu.h`）：支持 per-CPU PRNG 状态。
  - 堆栈追踪（`stacktrace.h`）：在报告中包含调用栈（若启用）。

## 5. 使用场景

- **内核开发与调试**：在启用 `CONFIG_KASAN_SW_TAGS` 配置选项后，该模块在内核启动时初始化，并对所有经编译器插桩的内存访问进行运行时检查。
- **内存错误检测**：捕获以下类型的 bug：
  - 堆/栈/全局变量的越界读写
  - 使用已释放内存（Use-After-Free）
  - 释放未分配或重复释放内存
- **与分配器协同工作**：SLAB/SLUB 在分配对象时调用 `kasan_random_tag()` 获取新标签，并通过 `__hwasan_tag_memory` 设置影子内存；释放时将其设为无效标签。
- **兼容性处理**：对 `kmap` 等传统高内存映射机制产生的 `0xFF` 标签地址豁免检查，避免误报。
- **性能权衡**：作为软件实现，相比硬件 MTE 版本性能开销较大，但可在无 MTE 支持的平台上提供类似检测能力。