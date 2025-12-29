# vmstat.c

> 自动生成时间: 2025-12-07 17:34:18
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `vmstat.c`

---

# vmstat.c 技术文档

## 1. 文件概述

`vmstat.c` 是 Linux 内核内存管理子系统（MM）中的核心统计模块，负责维护和管理虚拟内存相关的各类计数器。该文件实现了以下三类主要统计信息：

- **全局/区域级内存统计**（zone/node 级别）
- **NUMA 架构下的内存访问统计**
- **虚拟内存事件计数器**（如页面分配、回收、交换等）

这些统计数据通过 `/proc/vmstat`、`/sys/kernel/debug/` 等接口暴露给用户空间，用于性能监控、调优和故障诊断。

## 2. 核心功能

### 主要数据结构
- `vm_zone_stat[NR_VM_ZONE_STAT_ITEMS]`：全局区域级内存统计计数器（如空闲页、活跃页等）
- `vm_node_stat[NR_VM_NODE_STAT_ITEMS]`：NUMA 节点级内存统计计数器
- `vm_numa_event[NR_VM_NUMA_EVENT_ITEMS]`：NUMA 相关事件计数器（如本地/远程页面分配）
- `vm_event_states`（per-CPU）：每个 CPU 的虚拟内存事件状态
- `per_cpu_zonestats` / `per_cpu_nodestats`：每个 CPU 对应的区域/节点统计结构

### 主要函数
- **NUMA 统计控制**：
  - `sysctl_vm_numa_stat_handler()`：通过 sysctl 接口动态启用/禁用 NUMA 统计
  - `invalid_numa_statistics()`：清除所有 NUMA 计数器
  - `fold_vm_numa_events()`：将 per-CPU NUMA 事件聚合到全局计数器

- **VM 事件管理**（需 CONFIG_VM_EVENT_COUNTERS）：
  - `all_vm_events()`：汇总所有 CPU 的 VM 事件计数
  - `vm_events_fold_cpu()`：将指定 CPU 的事件折叠到全局计数器

- **阈值计算与刷新**（SMP 系统）：
  - `calculate_normal_threshold()`：基于 CPU 数量和内存大小计算正常统计更新阈值
  - `calculate_pressure_threshold()`：计算内存压力下的保守阈值
  - `refresh_zone_stat_thresholds()`：为所有区域和节点刷新 per-CPU 统计阈值

## 3. 关键实现

### Per-CPU 统计与延迟更新机制
为避免频繁原子操作带来的性能开销，内核采用 **per-CPU 缓存 + 延迟批量更新** 策略：
- 每个 CPU 维护自己的统计副本（如 `per_cpu_zonestats`）
- 当本地计数器超过预设阈值（`stat_threshold`）时，才将增量同步到全局原子变量
- 阈值通过 `calculate_normal_threshold()` 动态调整，平衡精度与性能

### NUMA 统计动态开关
通过静态分支（`static_branch_enable/disable`）实现零开销切换：
- 启用时：记录本地/远程页面分配等 NUMA 行为
- 禁用时：立即清零所有相关计数器，避免无效统计

### 内存水位线与漂移容忍
在 `refresh_zone_stat_thresholds()` 中考虑了统计延迟导致的“漂移”问题：
- 计算最大可能漂移量：`max_drift = num_online_cpus() * threshold`
- 若漂移可能掩盖 min watermark 违规，则设置 `percpu_drift_mark` 作为更严格的警戒线

### 高效聚合算法
- 使用 `xchg()` 原子交换清零 per-CPU 计数器，避免读-改-写竞争
- 全局聚合时加 `cpus_read_lock()` 防止 CPU 热插拔导致的数据不一致

## 4. 依赖关系

### 头文件依赖
- `<linux/mm.h>`：内存管理核心定义
- `<linux/vmstat.h>`：VM 统计相关的宏和类型
- `<linux/percpu.h>`（隐含）：Per-CPU 变量支持
- `"internal.h"`：MM 子系统内部接口

### 配置选项依赖
- `CONFIG_NUMA`：启用 NUMA 统计相关代码
- `CONFIG_VM_EVENT_COUNTERS`：启用详细的 VM 事件计数
- `CONFIG_SMP`：多处理器阈值计算逻辑

### 符号导出
- `EXPORT_SYMBOL(vm_zone_stat)` / `vm_node_stat`：供其他模块（如 compaction、vmscan）读取统计
- `EXPORT_SYMBOL_GPL(all_vm_events)`：供 tracing 或 debug 模块使用

## 5. 使用场景

### 内核内部使用
- **内存回收**（kswapd）：根据 `NR_FREE_PAGES` 等统计决定回收时机
- **页面分配器**：更新分配路径的统计（如 `alloc_pages` 调用 `count_vm_event`）
- **内存压缩**（compaction）：监控迁移成功率等指标
- **OOM Killer**：评估系统内存压力

### 用户空间监控
- **`/proc/vmstat`**：提供全局 VM 统计（由 `fs/proc/proc_misc.c` 调用 `all_vm_events` 生成）
- **`/sys/kernel/debug/`**：debugfs 接口暴露详细 per-zone 统计
- **性能分析工具**：如 `sar -r`, `vmstat`, `perf` 依赖这些计数器
- **NUMA 调优**：通过 `numastat` 工具分析跨节点访问开销

### 动态调优
- 管理员可通过 `sysctl vm.numa_stat=0/1` 动态关闭 NUMA 统计以降低开销
- 内核根据系统规模自动调整统计更新频率，适应从嵌入式设备到大型服务器的不同场景