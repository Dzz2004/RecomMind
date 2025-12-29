# percpu-stats.c

> 自动生成时间: 2025-12-07 17:09:48
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `percpu-stats.c`

---

# percpu-stats.c 技术文档

## 1. 文件概述

`percpu-stats.c` 是 Linux 内核中用于收集和展示 per-CPU（每 CPU）内存分配器运行时统计信息的调试模块。该文件通过 debugfs 接口 `/sys/kernel/debug/percpu_stats` 向用户空间暴露详细的 per-CPU 内存分配状态，包括全局统计、分配参数以及每个内存块（chunk）的碎片、分配大小分布等信息，主要用于性能分析和内存调试。

## 2. 核心功能

### 主要数据结构
- `struct percpu_stats pcpu_stats`：全局 per-CPU 分配器统计信息，记录分配/释放次数、当前/最大分配数、最小/最大分配大小等。
- `struct pcpu_alloc_info pcpu_stats_ai`：per-CPU 内存布局配置信息，如单元大小、静态区大小、动态区大小等。
- `int *buffer`：临时缓冲区，用于在 `chunk_map_stats()` 中存储每个 chunk 的分配/空闲片段大小。

### 主要函数
- `find_max_nr_alloc(void)`：遍历所有 per-CPU 内存块（chunks），找出具有最多分配项（`nr_alloc`）的块，用于预分配临时缓冲区。
- `chunk_map_stats(struct seq_file *m, struct pcpu_chunk *chunk, int *buffer)`：分析并打印单个 chunk 的详细状态，包括碎片情况、分配大小分布（最小、中位数、最大）等。
- `percpu_stats_show(struct seq_file *m, void *v)`：debugfs 文件的读取回调函数，汇总并输出全局统计、分配配置及所有 chunk 的详细信息。
- `init_percpu_stats_debugfs(void)`：模块初始化函数，在 debugfs 中创建 `percpu_stats` 文件。

## 3. 关键实现

### Chunk 状态分析算法
`chunk_map_stats()` 函数通过遍历 `alloc_map` 和 `bound_map` 位图来重建 chunk 的内存布局：
- `alloc_map` 标记已分配的最小单位（`PCPU_MIN_ALLOC_SIZE`）；
- `bound_map` 标记每个分配区域的结束边界；
- 通过交替查找 `alloc_map` 和 `bound_map` 中的下一个置位位，将连续区域划分为“已分配”或“空闲”片段；
- 已分配片段记录为正数，空闲片段记录为负数，并统一转换为字节数；
- 对片段数组排序后，负值（空闲）在前且按绝对值降序排列，便于计算总碎片（`sum_frag`）和最大连续空闲块（`max_frag`）；
- 从第一个非负值开始，提取当前最小、中位数和最大分配大小。

### 并发安全与重试机制
由于 per-CPU 分配器状态可能在缓冲区分配前后发生变化，`percpu_stats_show()` 采用以下策略确保一致性：
1. 先在 `pcpu_lock` 保护下获取当前最大 `nr_alloc`；
2. 按此值分配足够大的临时缓冲区；
3. 再次加锁检查 `nr_alloc` 是否增长，若增长则释放缓冲区并重试；
4. 整个统计过程在 `pcpu_lock` 临界区内完成，避免并发修改导致的数据不一致。

### 输出格式
使用宏 `P(X, Y)`、`PL(X)`、`PU(X)` 统一格式化输出，字段对齐，数值右对齐，便于阅读和脚本解析。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/debugfs.h>`：提供 debugfs 文件系统接口；
  - `<linux/percpu.h>` 和 `"percpu-internal.h"`：访问 per-CPU 分配器内部数据结构（如 `pcpu_chunk`、`pcpu_chunk_lists`、`pcpu_lock` 等）；
  - `<linux/seq_file.h>`：支持顺序文件输出；
  - `<linux/sort.h>`：用于对分配/空闲片段数组排序；
  - `<linux/vmalloc.h>`：使用 `vmalloc_array()` 分配大块临时内存。

- **内核子系统**：
  - 依赖 per-CPU 内存管理子系统（`mm/percpu.c`）提供的全局变量和内部结构；
  - 通过 `late_initcall` 在内核初始化后期注册 debugfs 接口。

## 5. 使用场景

- **内核开发者调试**：当怀疑 per-CPU 内存分配存在碎片化、性能下降或内存泄漏时，可通过读取 `/sys/kernel/debug/percpu_stats` 获取详细分配状态。
- **系统性能分析**：运维人员或性能工程师可监控 `nr_cur_alloc`、`free_bytes`、`sum_frag` 等指标，评估 per-CPU 内存使用效率。
- **内存优化参考**：通过观察 `cur_min_alloc`、`cur_med_alloc`、`cur_max_alloc` 等分配大小分布，指导内核模块调整 per-CPU 变量的大小或对齐方式。
- **验证内存布局**：检查 `unit_size`、`static_size`、`dyn_size` 等配置是否符合预期，特别是在自定义内核配置或架构移植时。