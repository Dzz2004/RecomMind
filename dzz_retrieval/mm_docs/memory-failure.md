# memory-failure.c

> 自动生成时间: 2025-12-07 16:40:57
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `memory-failure.c`

---

# memory-failure.c 技术文档

## 1. 文件概述

`memory-failure.c` 是 Linux 内核中用于处理硬件报告的内存故障（如多比特 ECC 错误）的核心模块。该文件实现了对已损坏物理页的检测、隔离和恢复机制，支持两种主要操作模式：
- **硬离线（Hard Offline）**：处理已被硬件标记为损坏的页面，通常会导致使用该页的进程被终止
- **软离线（Soft Offline）**：主动隔离可疑但尚未损坏的页面，避免潜在故障而不杀死进程

该模块需要在不违反虚拟内存子系统正常锁定规则的前提下，异步安全地处理内存错误，确保系统稳定性。

## 2. 核心功能

### 主要全局变量
- `sysctl_memory_failure_early_kill`：控制是否立即杀死使用损坏页面的进程（0=延迟处理，1=立即杀死）
- `sysctl_memory_failure_recovery`：启用/禁用内存故障恢复功能（默认启用）
- `num_poisoned_pages`：原子计数器，记录已标记为有毒（poisoned）的页面数量
- `hw_memory_failure`：标识是否由硬件直接报告的内存故障
- `mf_mutex`：保护内存故障处理操作的互斥锁

### 主要函数
- `num_poisoned_pages_inc()` / `num_poisoned_pages_sub()`：管理有毒页面计数
- `__page_handle_poison()`：处理大页或空闲页的溶解和从伙伴系统移除
- `page_handle_poison()`：通用页面毒化处理函数，设置 HWPoison 标志并更新计数
- `hwpoison_filter_dev()`：基于设备号过滤硬件毒化页面（用于测试）
- `hwpoison_filter_flags()`：基于页面标志过滤硬件毒化页面（用于测试）

### Sysfs 接口
通过 `MF_ATTR_RO` 宏定义的只读属性，提供每个 NUMA 节点的内存故障统计信息：
- `total`：总处理的内存故障数
- `ignored`：被忽略的故障数
- `failed`：处理失败的故障数  
- `delayed`：延迟处理的故障数
- `recovered`：成功恢复的故障数

## 3. 关键实现

### 页面毒化处理流程
1. **页面状态识别**：区分大页（hugepage）、空闲页（freepage）和其他类型页面
2. **大页处理**：调用 `dissolve_free_huge_page()` 溶解大页，然后通过 `drain_all_pages()` 和 `take_page_off_buddy()` 确保页面从伙伴系统移除
3. **标志设置**：使用 `SetPageHWPoison()` 标记页面为硬件毒化状态
4. **引用计数管理**：增加页面引用计数并更新全局有毒页面计数器

### 锁定策略
- 避免使用 `zone_pcp_disable()` 以防止与 CPU 热插拔锁产生死锁
- 采用标准 VM 锁定规则，即使这意味着错误处理可能耗时较长
- 使用 `mf_mutex` 保护关键的内存故障处理路径

### 复杂度考量
- 由于 VM 数据结构的限制，某些操作（如通过 RMAP 反向映射查找进程）具有非线性时间复杂度
- 基于内存故障的稀有性，接受这种性能开销以避免影响核心 VM 性能

### 开发约束
新增处理逻辑必须满足：
- 具备可测试性
- 能够集成到 mce-test 测试套件
- 在真实工作负载中属于常见页面状态（page-types 工具 top 10）

## 4. 依赖关系

### 内核头文件依赖
- **内存管理**：`<linux/mm.h>`, `<linux/page-flags.h>`, `<linux/pagemap.h>`, `<linux/swap.h>`
- **进程管理**：`<linux/sched/signal.h>`, `<linux/sched/task.h>`
- **特殊内存类型**：`<linux/hugetlb.h>`, `<linux/dax.h>`, `<linux/ksm.h>`, `<linux/shmem_fs.h>`
- **系统架构**：`<linux/ras/ras_event.h>`, `<linux/memremap.h>`
- **内核内部**：`"swap.h"`, `"internal.h"`

### 功能依赖
- **RAS（Reliability, Availability, Serviceability）**：通过 ras_event 提供事件通知
- **内存热插拔**：`memblk_nr_poison_inc/sub` 用于内存块级统计
- **cgroup 内存控制**：CONFIG_MEMCG 支持基于 memcg 的故障页面过滤
- **硬件毒化注入**：CONFIG_HWPOISON_INJECT 提供测试框架

## 5. 使用场景

### 硬件内存故障处理
- 当硬件检测到多比特 ECC 内存错误时，通过 Machine Check Exception (MCE) 机制调用此模块
- 自动隔离损坏页面，防止数据损坏扩散

### 主动内存维护
- 系统管理员可通过 `/sys` 接口触发软离线操作，主动替换可疑内存页
- 用于内存压力测试和预防性维护

### 故障注入测试
- 通过 `hwpoison_inject` 模块模拟硬件内存故障
- 支持基于设备号、页面标志和 memcg 的精细过滤，用于针对性测试

### 系统监控和诊断
- 通过 sysfs 接口提供详细的内存故障统计信息
- 便于系统管理员监控内存健康状况和故障恢复效果

### 企业级可靠性保障
- 在高可用服务器环境中，确保单个内存故障不会导致整个系统崩溃
- 通过可配置的策略（early_kill, recovery）平衡服务连续性和数据完整性