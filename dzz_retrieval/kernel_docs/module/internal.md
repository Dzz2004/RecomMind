# module\internal.h

> 自动生成时间: 2025-10-25 15:01:24
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `module\internal.h`

---

# `module/internal.h` 技术文档

## 1. 文件概述

`module/internal.h` 是 Linux 内核模块子系统的核心内部头文件，定义了模块加载、符号解析、内存布局、调试统计等关键内部数据结构和辅助函数。该文件仅供内核模块子系统内部使用，不对外暴露给模块开发者。它封装了模块加载过程中的中间状态、符号查找逻辑、内存管理细节以及与架构相关的重定位处理，并集成了模块压缩、热补丁（livepatch）、污点追踪（taint tracking）和调试统计等可选功能的支持。

## 2. 核心功能

### 主要数据结构

- **`struct kernel_symbol`**  
  内核符号的内部表示，支持两种模式：  
  - 普通模式：直接存储符号值（`value`）、名称（`name`）和命名空间（`namespace`）指针。  
  - `CONFIG_HAVE_ARCH_PREL32_RELOCATIONS` 模式：使用偏移量（`value_offset` 等）以节省内存并支持位置无关代码。

- **`struct load_info`**  
  模块加载过程中的临时信息容器，包含 ELF 头、节头表、字符串表、符号表、各节偏移、签名状态、解压页信息等，贯穿整个 `load_module()` 流程。

- **`struct find_symbol_arg`**  
  符号查找的输入/输出参数结构，用于 `find_symbol()` 函数，支持按名称、GPL 许可限制进行符号搜索。

- **`enum fail_dup_mod_reason`**  
  定义重复模块加载失败的两种场景：`FAIL_DUP_MOD_BECOMING`（早期检查阶段发现重复）和 `FAIL_DUP_MOD_LOAD`（分配内存后发现重复）。

- **`struct mod_fail_load`**（仅当 `CONFIG_MODULE_STATS` 启用）  
  用于统计重复加载失败的模块信息。

- **`struct mod_unload_taint`**（仅当 `CONFIG_MODULE_UNLOAD_TAINT_TRACKING` 启用）  
  记录卸载时带有污点（taint）的模块信息。

### 主要函数

- **符号管理**  
  - `find_symbol()`：在全局符号表中查找指定名称的符号。  
  - `kernel_symbol_value()`：获取 `kernel_symbol` 结构中符号的实际地址。

- **模块加载辅助**  
  - `mod_verify_sig()`：验证模块签名。  
  - `try_to_force_load()`：在特定条件下强制加载被拒绝的模块（如 taint 原因）。  
  - `module_get_offset_and_type()`：计算模块节在目标内存布局中的偏移和内存类型。  
  - `module_flags()` / `module_flags_taint()`：生成模块状态或污点标志的字符串表示。

- **模块信息解析**  
  - `module_next_tag_pair()`：解析模块信息（modinfo）中的键值对。  
  - `for_each_modinfo_entry`：遍历指定名称的 modinfo 条目。

- **热补丁支持**（`CONFIG_LIVEPATCH`）  
  - `copy_module_elf()` / `free_module_elf()`：复制或释放模块的 ELF 原始数据，供 livepatch 使用。  
  - `set_livepatch_module()`：标记模块为 livepatch 模块。

- **统计与调试**（条件编译）  
  - `try_add_failed_module()`：记录重复加载失败事件。  
  - `mod_stat_bump_invalid()` / `mod_stat_bump_becoming()`：更新无效或正在加载的模块统计。  
  - `try_add_tainted_module()` / `print_unloaded_tainted_modules()`：跟踪并打印卸载时带污点的模块。  
  - `kmod_dup_request_exists_wait()` / `kmod_dup_request_announce()`：用于调试自动加载重复请求。

- **解压支持**（`CONFIG_MODULE_DECOMPRESS`）  
  - `module_decompress()` / `module_decompress_cleanup()`：解压压缩的模块镜像。

### 全局变量

- `module_mutex`：保护模块列表和状态的全局互斥锁。  
- `modules`：已加载模块的全局链表。  
- `modinfo_attrs[]` / `modinfo_attrs_count`：模块信息属性数组及其数量。  
- `__start___ksymtab[]` 等：链接器生成的内核符号表起止标记。  
- 各类统计计数器（如 `total_mod_size`, `modcount` 等，仅当 `CONFIG_MODULE_STATS` 启用）。

## 3. 关键实现

### 符号表与重定位优化
- 通过 `CONFIG_HAVE_ARCH_PREL32_RELOCATIONS` 支持使用 32 位相对偏移代替 64 位绝对指针，显著减少符号表内存占用，尤其在 64 位系统上。
- `kernel_symbol_value()` 宏根据配置自动选择解析方式，对上层透明。

### 节类型编码
- 利用 ELF 节头 `sh_entsize` 的高 4 位存储 `mod_mem_type`（内存类型），低 28/60 位存储偏移量。
- 定义了 `SH_ENTSIZE_TYPE_BITS`、`SH_ENTSIZE_TYPE_MASK` 等宏进行位操作，确保在 32/64 位系统上正确分离类型与偏移。

### 模块加载状态保护
- `module_assert_mutex_or_preempt()` 利用 `lockdep` 和 `rcu_read_lock_sched_held()` 确保关键操作在持有 `module_mutex` 或处于 RCU 读临界区中执行，防止并发错误。

### 重复模块检测
- `enum fail_dup_mod_reason` 精确区分重复模块在加载流程中被发现的两个关键点，有助于分析资源浪费（如 vmap 空间）和竞态条件。

### 条件编译功能集成
- 通过 `#ifdef CONFIG_XXX` 将模块统计、污点追踪、自动加载调试、解压、热补丁等功能模块化，保持核心逻辑简洁，按需启用。

## 4. 依赖关系

- **内核核心头文件**：  
  - `<linux/elf.h>`：ELF 格式定义。  
  - `<linux/module.h>`：模块公共接口。  
  - `<linux/mutex.h>`, `<linux/rculist.h>`, `<linux/rcupdate.h>`：同步原语。  
  - `<linux/mm.h>`：内存管理相关定义。

- **架构相关**：  
  - `ARCH_SHF_SMALL`：架构特定的节标志，用于小内存模型。

- **可选子系统**：  
  - `CONFIG_KALLSYMS`：内核符号表支持。  
  - `CONFIG_LIVEPATCH`：内核热补丁。  
  - `CONFIG_MODULE_DECOMPRESS`：模块解压。  
  - `CONFIG_MODULE_STATS` / `CONFIG_MODULE_DEBUGFS` / `CONFIG_MODULE_UNLOAD_TAINT_TRACKING` / `CONFIG_MODULE_DEBUG_AUTOLOAD_DUPS`：各类调试与统计功能。

- **链接器脚本**：  
  - 依赖链接器生成的 `__start___ksymtab`、`__stop___ksymtab_gpl` 等符号，用于遍历内建符号表。

## 5. 使用场景

- **模块加载流程**：`load_module()` 及其辅助函数使用 `struct load_info` 传递解析后的 ELF 信息，并调用 `mod_verify_sig()`、`module_decompress()` 等进行预处理。
- **符号解析**：`find_symbol()` 被 `kernel/module.c` 中的符号导出/导入机制调用，实现模块间及内核与模块间的符号链接。
- **内存布局**：`module_get_offset_and_type()` 在 `layout_and_allocate()` 阶段确定各节在模块内存映像中的位置。
- **调试与监控**：  
  - `module_flags()` 用于 `/sys/module/<name>/taint` 等接口显示模块状态。  
  - 统计功能（`CONFIG_MODULE_STATS`）帮助分析模块加载性能与失败原因。  
  - 污点追踪（`CONFIG_MODULE_UNLOAD_TAINT_TRACKING`）记录可能导致系统不稳定模块的卸载信息。
- **热补丁**：livepatch 子系统通过 `copy_module_elf()` 保留原始 ELF 用于补丁验证和回滚。
- **并发控制**：所有修改全局模块列表或状态的操作必须通过 `module_mutex` 保护，`module_assert_mutex_or_preempt()` 用于运行时检查。