# livepatch\core.c

> 自动生成时间: 2025-10-25 14:31:53
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `livepatch\core.c`

---

# livepatch/core.c 技术文档

## 文件概述

`livepatch/core.c` 是 Linux 内核实时补丁（Kernel Live Patching, KLP）子系统的核心实现文件。该文件提供了实时补丁机制的基础框架，包括补丁注册、符号解析、模块对象管理以及与内核其他子系统的集成。其主要职责是安全、可靠地将运行时补丁应用到正在执行的内核或内核模块中，而无需重启系统。

该文件根据是否启用 `CONFIG_LIVEPATCH_FTRACE` 配置选项，采用不同的底层打补丁机制：基于 ftrace 的轻量级方案或基于 stop_machine 的强一致性方案。

## 核心功能

### 主要全局变量
- `klp_mutex`：粗粒度互斥锁，用于串行化所有对 livepatch 相关数据结构的访问（少数特殊函数除外）。
- `klp_patches`：链表，维护当前处于启用状态或正在过渡状态的补丁对象。
- `klp_root_kobj`：sysfs 中 livepatch 根目录的 kobject，用于暴露补丁信息到用户空间。

### 关键函数
- `klp_is_module()`：判断给定的 `klp_object` 是否代表一个内核模块（而非 vmlinux）。
- `klp_find_object_module()`：根据模块名查找并关联对应的 `struct module` 实例（仅在 `CONFIG_LIVEPATCH_FTRACE` 下实现）。
- `klp_find_object_symbol()`：在指定对象（vmlinux 或模块）的符号表中查找符号地址，支持通过 `sympos` 处理重载符号。
- `klp_resolve_symbols()`：解析 livepatch 模块中的特殊重定位节（`.klp.rela.*`），将 `.klp.sym.*` 格式的符号引用转换为实际内核地址。
- `klp_match_callback()` / `klp_find_callback()`：用于遍历符号表的回调函数，支持按名称和位置匹配符号。

### 条件编译功能
- **启用 `CONFIG_LIVEPATCH_FTRACE`**：
  - 提供 `klp_find_func()` 和 `klp_find_object()` 用于在补丁结构中查找对应函数和对象。
  - 使用 ftrace 机制实现函数替换，性能开销小。
- **禁用 `CONFIG_LIVEPATCH_FTRACE`**：
  - 依赖 `stop_machine()` 机制进行全局同步打补丁，确保强一致性。
  - 包含对 kprobes 和 static_call 的额外支持。

## 关键实现

### 符号解析机制
- Livepatch 模块使用特殊的符号命名格式：`.klp.sym.<objname>.<symname>,<sympos>`。
- `klp_resolve_symbols()` 函数解析这些符号，调用 `klp_find_object_symbol()` 在目标对象（vmlinux 或模块）中定位实际地址。
- 支持通过 `sympos`（符号位置）区分同名符号（如内联函数），`sympos=0` 表示符号必须唯一。
- 严格限制模块专属的 livepatch 重定位节不得引用 vmlinux 符号，避免初始化顺序问题。

### 模块生命周期管理
- 在 `CONFIG_LIVEPATCH_FTRACE` 模式下，`klp_find_object_module()` 使用 RCU 读锁安全地查找模块，但不增加模块引用计数。
- 依赖 `mod->klp_alive` 标志判断模块是否仍可被补丁作用，确保在模块退出过程中（`GOING` 状态）仍能正确处理函数调用。

### 并发控制
- 全局 `klp_mutex` 保护所有补丁操作（注册、启用、禁用等）。
- 少数关键路径（如 ftrace 处理函数、状态更新函数）通过无锁设计或 RCU 机制避免持有该锁，以减少性能影响。

### 安全性保障
- 符号解析时进行严格格式校验（`sscanf` 字段宽度限制），防止缓冲区溢出。
- 使用 `BUILD_BUG_ON()` 静态检查 `MODULE_NAME_LEN` 和 `KSYM_NAME_LEN` 的预期大小。
- 对非 livepatch 标记的符号（`st_shndx != SHN_LIVEPATCH`）拒绝处理，确保重定位安全性。

## 依赖关系

- **核心依赖**：
  - `<linux/module.h>`：模块加载和符号解析基础。
  - `<linux/kallsyms.h>`：内核符号表访问。
  - `<linux/livepatch.h>`：Livepatch 核心数据结构定义。
  - `<linux/elf.h>`：ELF 重定位处理。
- **条件依赖**：
  - `CONFIG_LIVEPATCH_FTRACE`：依赖 `ftrace` 子系统（通过 `patch.h`, `state.h`, `transition.h`）。
  - 非 FTRACE 模式：依赖 `stop_machine()`、`kprobes`（若启用 `CONFIG_LIVEPATCH_RESTRICT_KPROBE`）和 `static_call`。
- **架构相关**：包含 `<asm/cacheflush.h>` 用于指令缓存刷新，确保补丁代码立即生效。

## 使用场景

1. **内核热修复**：系统管理员在不重启服务器的情况下应用关键安全补丁或 bug 修复。
2. **动态功能增强**：在运行时注入新功能或修改现有内核行为（如调试、性能监控）。
3. **模块兼容性维护**：当内核升级后，通过 livepatch 保持旧模块的兼容性。
4. **高可用系统**：在电信、金融等要求 99.999% 可用性的场景中，避免因补丁导致的服务中断。

该文件作为 livepatch 子系统的中枢，协调符号解析、补丁应用、模块交互等关键流程，确保补丁操作的安全性和可靠性。