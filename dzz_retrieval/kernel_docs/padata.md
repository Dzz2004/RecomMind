# padata.c

> 自动生成时间: 2025-10-25 15:13:27
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `padata.c`

---

# padata.c 技术文档

## 文件概述

`padata.c` 实现了 Linux 内核中的 **padata**（parallel data）框架，提供了一个通用接口，用于在多个 CPU 上并行处理数据流，同时保证结果按照原始顺序串行化输出。该机制常用于需要高吞吐量并行计算但又要求结果有序的场景（如加密、压缩等）。padata 框架通过将任务分发到多个 CPU 并行执行，并在专用的串行化 CPU 上按序回调，实现了并行与有序的统一。

## 核心功能

### 主要数据结构

- `struct padata_work`：封装工作项，用于将并行任务提交到工作队列。
- `struct padata_mt_job_state`：用于多线程作业（multi-threaded job）的状态管理，包含完成通知、工作计数和数据块大小。
- `struct parallel_data`：并行数据上下文，包含 CPU 掩码、序列号、重排序队列等关键状态。
- `struct padata_priv`：用户传递的任务私有数据结构，必须包含 `.parallel` 和 `.serial` 回调函数。

### 主要函数

- `padata_do_parallel()`：核心入口函数，将任务分发到并行工作队列。
- `padata_parallel_worker()`：并行工作线程执行函数，调用用户提供的 `.parallel` 回调。
- `padata_find_next()`：在重排序队列中查找下一个应被串行化的任务。
- `padata_cpu_hash()`：根据序列号将任务哈希到特定的并行 CPU。
- `padata_index_to_cpu()`：将逻辑 CPU 索引映射到实际的 CPU ID。
- `padata_work_alloc()` / `padata_work_free()`：管理工作项的分配与回收。
- `padata_work_alloc_mt()` / `padata_works_free()`：用于多线程作业的批量工作项管理。

## 关键实现

### 1. 并行-串行模型
padata 采用“并行执行 + 有序串行化”模型：
- **并行阶段**：任务通过 `padata_do_parallel()` 分发到 `parallel_wq` 工作队列，在 `pd->cpumask.pcpu` 指定的 CPU 上并行执行（BH 关闭）。
- **串行阶段**：任务完成后进入 per-CPU 重排序队列，由 `padata_reorder()` 机制按 `seq_nr` 顺序触发 `.serial` 回调，回调在 `pd->cpumask.cbcpu` 指定的 CPU 上执行。

### 2. 顺序保证机制
- 每个任务分配唯一递增的 `seq_nr`。
- 任务完成后按 `seq_nr % weight(pcpu_mask)` 哈希到特定 CPU 的重排序队列。
- `padata_find_next()` 仅当 `seq_nr == pd->processed` 时才取出任务，确保严格 FIFO 顺序。

### 3. 工作项管理
- 全局预分配 `padata_work` 对象池（`padata_free_works` 链表），避免运行时内存分配。
- 使用自旋锁 `padata_works_lock` 保护工作项分配/回收，支持 BH 上下文安全。

### 4. CPU 掩码处理
- 支持动态 CPU 掩码（`pcpu` 用于并行，`cbcpu` 用于串行回调）。
- 若用户指定的 `cb_cpu` 不在 `cbcpu` 掩码中，自动选择回退 CPU（通过模运算和 `cpumask_next`）。

### 5. 引用计数与生命周期
- `parallel_data` 使用 `refcount_t` 管理生命周期，`padata_get_pd()` / `padata_put_pd()` 控制引用。
- RCU 保护 `pd` 指针的读取（`rcu_dereference_bh`），确保并发安全。

## 依赖关系

- **内核子系统**：
  - `workqueue`：依赖内核工作队列机制执行并行任务。
  - `RCU`：用于 `parallel_data` 结构的并发读取保护。
  - `percpu`：使用 per-CPU 变量存储重排序队列（`reorder_list`）。
  - `sysfs`：支持通过 sysfs 接口配置 padata 实例（未在片段中体现，但头文件包含）。
- **头文件依赖**：
  - `<linux/padata.h>`：定义用户接口和核心结构。
  - `<linux/completion.h>`、`<linux/cpumask.h>`、`<linux/rcupdate.h>` 等提供基础功能。

## 使用场景

1. **加密子系统**：如 IPsec 或 dm-crypt 使用 padata 并行处理多个数据块的加密/解密，同时保证输出顺序。
2. **压缩/解压缩**：在需要高吞吐量的压缩场景中并行处理数据流。
3. **批量数据处理**：任何需要将大数据集分片并行处理，但要求结果按输入顺序交付的内核模块。
4. **多线程作业辅助**：通过 `padata_work_alloc_mt()` 接口，辅助实现内核态多线程任务分发（如大内存初始化）。

> **注意**：所有通过 `padata_do_parallel()` 提交的任务**必须**调用 `padata_do_serial()` 完成串行化阶段，否则会导致资源泄漏和顺序错乱。