# module\stats.c

> 自动生成时间: 2025-10-25 15:06:48
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `module\stats.c`

---

# `module/stats.c` 技术文档

## 1. 文件概述

`module/stats.c` 是 Linux 内核模块子系统中用于收集和跟踪模块加载失败相关调试统计信息的实现文件。当启用 `CONFIG_MODULE_STATS` 配置选项时，该文件提供对模块加载过程中因各种原因失败所导致的虚拟内存浪费情况的监控能力。其主要目标是帮助开发者和系统维护人员识别和优化模块加载过程中的资源浪费问题，特别是在系统启动阶段因重复加载或竞争条件导致的无效内存分配。

## 2. 核心功能

### 主要数据结构

- **`dup_failed_modules`**  
  全局静态链表（`LIST_HEAD`），用于记录因模块名称重复（已加载或正在处理）而加载失败的模块实例。该链表帮助追踪因用户空间竞争或内核并发加载导致的无效加载尝试。

### 调试统计计数器（通过 debugfs 暴露）

- **`total_mod_size`**：系统处理过的所有模块占用的总字节数。
- **`total_text_size`**：所有模块的 `.text` 和 `.init.text` ELF 节区大小总和。
- **`invalid_kread_bytes`**：因 `kernel_read_file_from_fd()` 阶段失败而浪费的 `vmalloc()` 分配字节数。
- **`invalid_decompress_bytes`**：模块解压过程中因失败而浪费的 `vmap()` 分配字节数。
- **`invalid_becoming_bytes`**：在 `early_mod_check()` 之后、`layout_and_allocate()` 之前失败所浪费的内存总量（含解压和读取阶段）。
- **`invalid_mod_bytes`**：在 `layout_and_allocate()` 之后（即模块已分配最终内存布局）因失败而释放的内存总量。

> 注：文档片段在 `invalid_mod_bytes` 处截断，但根据上下文可推断其用于统计最晚阶段（模块结构体已分配）的失败内存开销。

## 3. 关键实现

### 模块加载失败的三阶段内存模型

模块加载过程中的内存分配分为三个关键阶段，每个阶段失败对应不同的统计计数器：

1. **阶段 a**：`kernel_read_file_from_fd()` 使用 `vmalloc()` 读取模块文件。
2. **阶段 b**（可选）：若模块为压缩格式，解压后通过 `vmap()` 映射解压内容，原始读取缓冲区随即释放。
3. **阶段 c**：`layout_and_allocate()` 为模块分配最终运行时内存布局（可能使用 `vzalloc()` 或架构特定的 `vmalloc` 变体）。

失败统计遵循“最晚失败点”原则：仅在导致失败的最晚阶段对应的计数器中累加**该次加载尝试中所有已分配并最终释放的内存总量**。

### 重复模块加载失败分类

针对因模块名重复导致的失败，细分为两类：

- **`FAIL_DUP_MOD_BECOMING`**：在 `early_mod_check()` 末尾检测到重复（尚未调用 `layout_and_allocate()`）。
  - 有解压：浪费 2 次分配（`kread` + `vmap`）
  - 无解压：浪费 1 次分配（`kread`）
- **`FAIL_DUP_MOD_LOAD`**：在 `add_unformed_module()` 阶段检测到重复（已执行 `layout_and_allocate()`）。
  - 有解压：浪费 3 次分配
  - 无解压：浪费 2 次分配

### 原子计数与性能考量

所有统计计数器均使用**原子操作**更新，以避免锁竞争、死锁及性能开销，确保在高并发模块加载场景下的低延迟。

### debugfs 集成

统计信息通过 **debugfs** 文件系统暴露，便于用户空间工具（如 `cat /sys/kernel/debug/...`）实时监控模块加载效率和内存浪费情况。

## 4. 依赖关系

- **内核头文件依赖**：
  - `<linux/module.h>`：模块核心接口
  - `<linux/debugfs.h>`：调试文件系统支持
  - `<linux/vmalloc.h>` 相关（通过 `slab.h`, `math.h` 等间接依赖）：虚拟内存分配
  - `<linux/rculist.h>`：RCU 安全链表操作
- **内部依赖**：
  - `"internal.h"`：模块子系统内部头文件，包含未公开的模块管理结构和函数
- **配置依赖**：
  - 仅在 `CONFIG_MODULE_STATS=y` 时编译生效

## 5. 使用场景

- **系统启动优化**：分析启动过程中因用户空间并发调用 `modprobe` 或 `request_module()` 导致的重复模块加载，减少不必要的 `vmalloc` 压力。
- **内存压力诊断**：在虚拟地址空间受限的架构（如 x86 默认 128 MiB vmalloc 空间）上，定位模块加载失败是否加剧内存碎片或耗尽问题。
- **内核/用户空间协同改进**：通过 `dup_failed_modules` 链表识别用户空间加载逻辑缺陷（如未检查 `/sys/module` 即重复加载），推动工具链优化。
- **安全与验证调试**：监控因签名验证（`module_sig_check`）、ELF 格式错误或黑名单策略导致的早期失败，评估安全机制开销。