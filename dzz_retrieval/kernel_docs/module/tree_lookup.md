# module\tree_lookup.c

> 自动生成时间: 2025-10-25 15:09:32
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `module\tree_lookup.c`

---

# module/tree_lookup.c 技术文档

## 1. 文件概述

`module/tree_lookup.c` 实现了一个基于**锁存红黑树（latched RB-tree）** 的模块地址查找机制，用于高效地根据内存地址定位所属的内核模块。该机制专为高性能、低延迟的地址查询场景设计，特别适用于性能事件（perf events）和跟踪（tracing）子系统在任意上下文（包括 NMI）中频繁调用 `__module_address()` 的情况。通过使用 RCU-sched 语义，该实现支持无锁读取，同时保证写操作（模块加载/卸载）的安全性。

## 2. 核心功能

### 主要函数

- `mod_tree_insert(struct module *mod)`  
  将模块的所有内存区域（按类型）插入全局模块树 `mod_tree`。

- `mod_tree_remove_init(struct module *mod)`  
  仅移除模块的初始化内存区域（如 `.init.text`、`.init.data` 等）。

- `mod_tree_remove(struct module *mod)`  
  移除模块的所有内存区域。

- `mod_find(unsigned long addr, struct mod_tree_root *tree)`  
  在指定模块树中查找包含给定地址 `addr` 的模块，返回对应的 `struct module *`。

- `__mod_tree_insert()` / `__mod_tree_remove()`  
  内部辅助函数，封装对 `latch_tree_insert()` 和 `latch_tree_erase()` 的调用。

### 关键数据结构

- `struct latch_tree_ops mod_tree_ops`  
  定义模块树的比较和排序逻辑，包含：
  - `.less`：节点间大小比较函数
  - `.comp`：键值与节点的范围比较函数

- `struct mod_tree_node`（隐含在 `struct module_memory` 中）  
  模块内存区域在红黑树中的节点表示，包含指向所属模块的指针。

## 3. 关键实现

### 锁存红黑树（Latched RB-tree）机制
- 使用 `latch_tree` 数据结构，支持**双版本（double-buffered）** 更新，允许读者在不加锁的情况下通过 RCU-sched 安全遍历。
- 写操作（插入/删除）由 `module_mutex` 串行化，确保树结构修改的原子性。
- 读操作（`mod_find`）可在任意上下文（包括中断、NMI）中执行，无需获取锁。

### 地址范围比较逻辑
- 每个模块内存区域由基地址（`base`）和大小（`size`）定义。
- `mod_tree_comp()` 函数实现**区间包含判断**：
  - 若查询地址 `< base`，返回 `-1`（在左侧）
  - 若查询地址 `>= base + size`，返回 `1`（在右侧）
  - 否则返回 `0`（命中该区域）

### 内存区域类型遍历
- 使用宏 `for_each_mod_mem_type()` 和 `for_class_mod_mem_type()` 遍历模块的所有内存段类型（如代码段、数据段、初始化段等）。
- 仅当内存区域大小非零时才插入/移除树节点，避免无效条目。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/module.h>`：提供 `struct module` 等核心模块定义
  - `<linux/rbtree_latch.h>`：提供锁存红黑树实现
  - `"internal.h"`：包含模块子系统内部数据结构（如 `mod_tree` 全局变量、`module_memory` 定义等）

- **全局变量依赖**：
  - `mod_tree`：全局 `struct mod_tree_root` 实例，定义在 `internal.h` 中
  - `module_mutex`：序列化模块树修改操作的互斥锁

- **条件编译**：  
  该文件功能仅在 `CONFIG_PERF_EVENTS || CONFIG_TRACING` 启用时编译，因其主要服务于性能分析和跟踪场景。

## 5. 使用场景

- **性能分析（perf）**：  
  在 perf 采样中断或 NMI 中，通过 `__module_address()` 快速确定程序计数器（PC）是否位于某个内核模块内，用于符号解析和调用栈展开。

- **内核跟踪（ftrace/kprobes）**：  
  跟踪点触发时需识别当前执行地址所属模块，以提供模块上下文信息。

- **模块卸载安全检查**：  
  在模块移除前，通过地址查询验证无活跃引用（如 kprobe、ftrace 等）。

- **内核 Oops/panic 诊断**：  
  在内核崩溃时，快速定位错误地址所属模块，辅助调试。

该实现通过无锁读取和高效区间查询，显著提升了高频率地址查找场景下的系统性能和实时性。