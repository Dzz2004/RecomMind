# kfence\core.c

> 自动生成时间: 2025-12-07 16:23:33
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kfence\core.c`

---

# `kfence/core.c` 技术文档

## 1. 文件概述

`kfence/core.c` 是 Linux 内核中 **KFENCE（Kernel Electric Fence）** 动态内存错误检测机制的核心实现文件。KFENCE 是一种低开销的运行时内存安全检测器，用于捕获堆内存中的越界访问、释放后使用（Use-After-Free）、重复释放等常见内存错误。

该文件实现了 KFENCE 的对象分配器、故障处理逻辑、元数据管理、统计计数、参数控制以及与内核其他子系统的集成（如 debugfs、panic notifier 等）。其设计目标是在极低性能开销（通常 <1%）的前提下提供接近 100% 的内存错误检出能力。

## 2. 核心功能

### 主要全局变量
- `kfence_enabled`：KFENCE 是否启用的全局开关。
- `__kfence_pool`：KFENCE 使用的专用内存池，包含交错排列的保护页（guard pages）和实际对象页。
- `kfence_metadata` / `kfence_metadata_init`：每个 KFENCE 对象对应的元数据数组，记录分配状态、地址、栈追踪等信息。
- `kfence_freelist`：空闲 KFENCE 对象链表，受 `kfence_freelist_lock` 自旋锁保护。
- `kfence_allocation_key`：静态键（static key），用于在 KFENCE 禁用时快速跳过分配路径。
- `kfence_allocation_gate`：原子变量，用于控制采样周期内仅允许一次 KFENCE 分配。
- `alloc_covered[]`：基于 Counting Bloom Filter 的分配覆盖跟踪结构，避免相同调用栈过度占用池资源。
- `counters[]`：各类统计计数器（已分配数、总分配/释放次数、bug 数等）。

### 主要模块参数（可通过 `/sys/module/kfence/parameters/` 调整）
- `sample_interval`：采样间隔（纳秒），控制 KFENCE 分配频率；设为 0 可动态禁用 KFENCE。
- `skip_covered_thresh`：当池使用率超过此百分比（默认 75%）时，跳过已覆盖（重复栈）的分配。
- `burst`：每次采样允许的超额分配数量（用于应对突发分配）。
- `deferrable`：是否使用可延迟定时器（降低功耗）。
- `check_on_panic`：在内核 panic 时是否检查所有对象的 canary 值。

### 关键辅助函数
- `should_skip_covered()`：判断当前是否应跳过“已覆盖”的分配请求。
- `get_alloc_stack_hash()`：获取分配调用栈的哈希值（用于唯一性识别）。
- `alloc_covered_add()` / `alloc_covered_contains()`：操作 Counting Bloom Filter，记录或查询某调用栈是否已被覆盖。

### 宏定义
- `KFENCE_WARN_ON(cond)`：增强版 `WARN_ON`，触发警告时自动禁用 KFENCE 并标记 `disabled_by_warn`。

## 3. 关键实现

### 内存布局与保护机制
KFENCE 内存池 (`__kfence_pool`) 由交替的 **保护页（不可访问）** 和 **对象页（可分配）** 组成。每个对象页前后均有保护页隔离。任何对保护页的访问都会触发页错误，由 KFENCE 的页错误处理程序捕获并报告越界访问。

### 元数据初始化安全
通过分离 `kfence_metadata_init`（初始化阶段使用）和 `kfence_metadata`（初始化完成后赋值），确保在 `kfence_shutdown_cache()` 等路径中不会访问未完全初始化的元数据，防止 UAF 或未定义行为。

### 分配去重（Coverage Skipping）
采用 **Counting Bloom Filter** 跟踪已分配对象的调用栈哈希：
- 使用双哈希函数（`ALLOC_COVERED_HNUM=2`）减少冲突。
- 当池使用率超过 `kfence_skip_covered_thresh`（默认 75%）时，若新分配的调用栈已在 Bloom Filter 中存在，则跳过此次 KFENCE 分配，转而使用普通分配器，避免池被重复模式占满。

### 动态启停与采样控制
- 通过 `sample_interval` 模块参数支持运行时启用/禁用。
- 使用 `kfence_allocation_gate` 原子变量配合高精度定时器实现基于时间的采样，确保分配稀疏性。
- 若因严重错误（如元数据损坏）触发 `KFENCE_WARN_ON`，则永久禁用 KFENCE。

### 统计与调试支持
- 提供 8 类原子计数器，通过 debugfs 导出（通常位于 `/sys/kernel/debug/kfence/`）。
- 支持 panic 时全量 canary 检查（`kfence_check_on_panic`），辅助诊断延迟暴露的内存破坏。

## 4. 依赖关系

- **架构相关代码**：依赖 `<asm/kfence.h>` 提供的架构特定实现（如页错误处理、内存属性设置）。
- **内存管理子系统**：使用 `memblock` 在启动早期预留内存池；与 SLAB/SLUB 分配器集成，在 `kmalloc` 路径中插入 KFENCE 分配逻辑。
- **调试基础设施**：集成 `debugfs` 导出统计信息；使用 `panic_notifier` 实现 panic 时检查；依赖 `kcsan-checks.h` 确保与 KCSAN 兼容。
- **同步原语**：使用 `raw_spinlock_t` 保护空闲链表；利用 `static_key` 优化热路径性能。
- **随机数与哈希**：使用 `jhash` 和启动时随机种子 `stack_hash_seed` 生成调用栈哈希，增强跨重启的检测多样性。

## 5. 使用场景

- **开发与测试阶段**：作为内核内存错误检测工具，替代或补充 KASAN（尤其适用于资源受限或无法承受 KASAN 开销的场景）。
- **生产环境监控**：因其极低开销（默认采样率下 <1% CPU），可用于长期运行的生产系统中捕获偶发内存错误。
- **安全漏洞挖掘**：帮助发现内核驱动或子系统中的堆溢出、UAF 等安全漏洞。
- **内核稳定性分析**：通过 debugfs 统计数据评估系统内存分配行为及潜在风险点。
- **panic 事后分析**：结合 `check_on_panic` 选项，在系统崩溃时验证 KFENCE 对象完整性，辅助根因定位。