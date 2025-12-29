# damon\lru_sort.c

> 自动生成时间: 2025-12-07 15:47:42
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `damon\lru_sort.c`

---

# `damon/lru_sort.c` 技术文档

## 1. 文件概述

`damon/lru_sort.c` 是 Linux 内核中基于 DAMON（Data Access MONitor）框架实现的一个内核模块，用于根据内存访问模式动态调整页面在 LRU（Least Recently Used）列表中的优先级。该模块通过监控内存区域的访问频率和空闲时间，将“热”页面标记为高优先级（防止被回收），将“冷”页面标记为低优先级（优先回收），从而优化内存回收效率。模块行为受水位线（watermarks）机制控制，仅在系统空闲内存低于特定阈值时激活。

## 2. 核心功能

### 主要数据结构
- **`enabled`**: 控制模块是否启用的布尔标志。
- **`commit_inputs`**: 触发运行时参数重载的布尔标志。
- **`hot_thres_access_freq`**: 热内存区域的访问频率阈值（单位：千分比，默认 500，即 50%）。
- **`cold_min_age`**: 冷内存区域的最小未访问时间（单位：微秒，默认 120,000,000，即 120 秒）。
- **`damon_lru_sort_quota`**: 操作配额限制，控制 DAMON 操作消耗的 CPU 时间（默认每秒最多 10 毫秒）。
- **`damon_lru_sort_wmarks`**: 水位线配置，基于空闲内存率决定模块是否激活（高/中/低阈值分别为 20%/15%/5%）。
- **`damon_lru_sort_mon_attrs`**: DAMON 监控属性，包括采样间隔、聚合间隔等。
- **`monitor_region_start/monitor_region_end`**: 监控的物理内存区域范围（默认为最大 System RAM 区域）。
- **`kdamond_pid`**: DAMON 工作线程的 PID（启用时有效，否则为 -1）。
- **`damon_lru_sort_hot_stat` / `damon_lru_sort_cold_stat`**: 热/冷页面操作的统计信息。
- **`damon_lru_sort_stub_pattern`**: 基础访问模式模板，用于构建热/冷识别规则。

### 主要函数
- **`damon_lru_sort_new_scheme()`**: 创建通用的 DAMOS（DAMON Operation Scheme）方案。
- **`damon_lru_sort_new_hot_scheme()`**: 创建用于识别并提升热页面优先级的方案（`DAMOS_LRU_PRIO`）。
- **`damon_lru_sort_new_cold_scheme()`**: 创建用于识别并降低冷页面优先级的方案（`DAMOS_LRU_DEPRIO`）。
- **`damon_lru_sort_copy_quota_status()`**: 复制配额使用状态，用于方案更新时保留历史配额信息。
- **`damon_lru_sort_apply_parameters()`**: 应用当前模块参数到 DAMON 上下文，包括监控属性、操作方案和监控区域。
- **`damon_lru_sort_turn()`**: 启用或禁用 DAMON LRU 排序功能。
- **`damon_lru_sort_enabled_store()`**: 处理 `enabled` 参数的写入（代码片段截断，但功能为切换模块状态）。

## 3. 关键实现

- **热/冷页面识别**：
  - **热页面**：在聚合间隔内访问次数 ≥ `hot_thres_access_freq`（转换为 DAMON 访问计数阈值）。
  - **冷页面**：未被访问的时间 ≥ `cold_min_age`（转换为以聚合间隔为单位的年龄阈值）。
  
- **LRU 优先级调整**：
  - 热页面通过 `DAMOS_LRU_PRIO` 动作标记为已访问，提升其在 LRU 列表中的位置。
  - 冷页面通过 `DAMOS_LRU_DEPRIO` 动作标记为未访问，降低其优先级以便优先回收。

- **资源控制**：
  - 使用 `damos_quota` 限制操作开销（默认每秒最多 10ms CPU 时间），热/冷方案各分配一半配额。
  - 配额状态在方案更新时保留，避免因参数重载导致配额重置。

- **条件激活**：
  - 通过 `damos_watermarks` 实现基于空闲内存率的自动启停：
    - 空闲内存率 ≤ 低水位（5%）时激活；
    - ≥ 高水位（20%）时停用；
    - 在中/低水位间保持当前状态。

- **参数动态更新**：
  - 除 `enabled` 外的参数修改后，需设置 `commit_inputs=Y` 触发重载。
  - 重载失败（如参数无效）将导致模块自动禁用。

## 4. 依赖关系

- **核心依赖**：
  - `linux/damon.h`：DAMON 框架核心 API。
  - `modules-common.h`：DAMON 模块通用宏和辅助函数（如 `DEFINE_DAMON_MODULES_*` 宏）。
- **内核子系统**：
  - 内存管理子系统（LRU 列表操作）。
  - 进程调度（DAMON 工作线程 `kdamond`）。
- **配置接口**：
  - 通过 `module_param` 提供 `/sys/module/damon_lru_sort/parameters/` 下的运行时配置。

## 5. 使用场景

- **内存压力下的页面回收优化**：在系统内存紧张时，自动将长期未使用的冷页面置于 LRU 列表前端，加速其回收；同时保护频繁访问的热页面不被误回收。
- **透明大页（THP）友好**：通过基于访问模式的 LRU 调整，减少对 THP 的干扰。
- **低开销内存监控**：利用 DAMON 的自适应区域拆分/合并机制，在有限 CPU 开销（默认 ≤10ms/s）下实现高效监控。
- **容器/虚拟化环境**：适用于多租户场景，动态优化各 workload 的内存使用效率。
- **嵌入式/实时系统**：通过严格配额控制，确保内存优化操作不影响关键任务实时性。