# page_counter.c

> 自动生成时间: 2025-12-07 17:00:45
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `page_counter.c`

---

# page_counter.c 技术文档

## 1. 文件概述

`page_counter.c` 实现了一个无锁（lockless）的分层页面计数与限制机制，用于在 Linux 内核中对内存资源进行层级化计量、保护和限制。该机制主要用于 cgroup 内存控制器（如 memcg）中，支持对内存使用量进行精确跟踪，并提供 `memory.min` 和 `memory.low` 两种级别的内存保护策略，同时支持设置硬性上限（`memory.max`）。所有操作均基于原子操作实现，避免了传统锁带来的性能开销。

## 2. 核心功能

### 主要数据结构
- `struct page_counter`：核心计数器结构体，包含以下关键字段：
  - `usage`：当前已使用的页面数（原子变量）
  - `max`：硬性内存上限（可配置）
  - `min` / `low`：内存保护阈值（软性保障）
  - `min_usage` / `low_usage`：实际受保护的内存量
  - `children_min_usage` / `children_low_usage`：子节点受保护内存总量
  - `watermark`：历史最大使用量（用于统计）
  - `failcnt`：因超出限制而失败的尝试次数
  - `parent`：指向父级计数器的指针，构成层级树
  - `protection_support`：是否启用保护机制的标志

### 主要函数
| 函数 | 功能说明 |
|------|--------|
| `page_counter_charge()` | 无条件地向计数器及其所有祖先层级增加指定页数 |
| `page_counter_uncharge()` | 向计数器及其祖先层级减少指定页数（调用 `cancel`） |
| `page_counter_try_charge()` | 尝试充电，若任一层级超过 `max` 则回滚并返回失败 |
| `page_counter_cancel()` | 从本地计数器减去页数，处理下溢并更新保护用量 |
| `page_counter_set_max()` | 设置硬性内存上限，若当前用量已超限则返回 `-EBUSY` |
| `page_counter_set_min()` / `page_counter_set_low()` | 设置内存保护阈值，并触发保护用量传播 |
| `page_counter_memparse()` | 解析用户输入的字符串（如 "1G"）为页数，支持 "max" 关键字 |
| `propagate_protected_usage()` | （内部）根据当前用量和 min/low 阈值，向上更新受保护内存量 |

## 3. 关键实现

### 无锁层级更新
- 所有计数操作（charge/uncharge）通过 `atomic_long_add_return()` 和 `atomic_long_sub_return()` 实现，确保线程安全。
- 在 `page_counter_try_charge()` 中采用“先加后检”策略：先原子增加用量，再检查是否超过 `max`。若超限则回退。此方法虽存在短暂超限窗口，但避免了昂贵的 CAS 循环，适用于 THP（透明大页）等场景。

### 内存保护机制
- 引入 `min` 和 `low` 两级软保护：
  - `min`：强保障，通常用于关键服务
  - `low`：弱保障，用于优先级稍低的内存预留
- `propagate_protected_usage()` 计算每个节点的实际受保护量：`protected = min(usage, threshold)`，并通过 `min_usage`/`low_usage` 原子变量记录，并累加到父节点的 `children_*_usage` 中，供上层决策（如内存回收）使用。

### 水位线与失败计数
- `watermark` 记录历史峰值用量，用于监控和调优。
- `failcnt` 统计因超限导致的充电失败次数，仅用于统计信息，允许轻微不一致。

### 安全的 max 更新
- `page_counter_set_max()` 使用 `xchg()` 原子交换新旧上限，并通过循环验证：若在设置过程中用量增长导致新上限仍不足，则恢复旧值并重试，确保不会将上限设为低于当前用量的值。

### 字符串解析
- `page_counter_memparse()` 封装 `memparse()`，将用户空间传入的字符串（如 "512M"）转换为页数，并支持特殊值 "max" 表示 `PAGE_COUNTER_MAX`（即 `ULONG_MAX`）。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/page_counter.h>`：定义 `struct page_counter` 及函数声明
  - `<linux/atomic.h>`：提供原子操作原语
  - `<asm/page.h>`：提供 `PAGE_SIZE` 定义
  - `<linux/kernel.h>`、`<linux/string.h>` 等基础内核头文件
- **配置依赖**：
  - 主要服务于 `CONFIG_MEMCG`（内存 cgroup）和 `CONFIG_CGROUP_DMEM`（设备内存 cgroup）
  - 文件末尾的 `#if IS_ENABLED(...)` 表明其设计初衷是为 cgroup 内存控制器提供底层支持
- **运行时依赖**：
  - 依赖内核的原子操作和内存屏障语义保证正确性
  - 与内存回收（reclaim）逻辑紧密配合，保护用量信息用于决定回收顺序

## 5. 使用场景

- **cgroup v2 内存控制器**：作为 `memory.max`、`memory.min`、`memory.low` 等接口的底层实现，管理容器或进程组的内存限额与保障。
- **内存服务质量（QoS）**：通过 `min`/`low` 机制为关键应用提供内存预留，防止被普通任务挤占。
- **内存超售（Overcommit）管理**：在云环境或虚拟化平台中，精确控制各租户的内存使用边界。
- **透明大页（THP）分配**：`try_charge` 的投机性设计特别优化了 THP（2MB/1GB 页）与普通页（4KB）并发分配时的性能。
- **系统监控与调优**：通过 `watermark` 和 `failcnt` 提供内存使用峰值和限制冲突的统计信息，辅助系统管理员进行容量规划。