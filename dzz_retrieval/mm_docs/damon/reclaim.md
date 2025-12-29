# damon\reclaim.c

> 自动生成时间: 2025-12-07 15:50:20
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `damon\reclaim.c`

---

# `damon/reclaim.c` 技术文档

## 1. 文件概述

`damon/reclaim.c` 是 Linux 内核中基于 **DAMON（Data Access MONitor）** 框架实现的**自动内存回收模块**。该模块通过监控物理内存区域的访问模式，识别长时间未被访问的“冷”内存页，并主动将其回收（page-out），从而释放系统内存资源。其核心目标是在不影响系统性能的前提下，智能地回收低价值内存，提升内存利用率。

该模块以可加载内核模块（LKM）形式存在，通过一组可调参数控制其行为，并支持基于水位线（watermarks）的条件激活机制，避免在内存充足时进行不必要的回收操作。

## 2. 核心功能

### 主要数据结构

- **`enabled`**: 全局开关，控制 DAMON_RECLAIM 功能是否启用。
- **`commit_inputs`**: 触发参数重载的标志位，用于运行时动态更新配置（除 `enabled` 外）。
- **`min_age`**: 冷内存判定阈值（微秒），默认 120 秒。
- **`damon_reclaim_quota`**: 回收配额控制结构，限制单位时间内的最大回收量（默认每秒最多 128 MiB）和 CPU 时间开销（默认最多 10 ms）。
- **`damon_reclaim_wmarks`**: 水位线配置，基于空闲内存比率决定是否激活回收（高/中/低水位分别为 50%/40%/20%）。
- **`damon_reclaim_mon_attrs`**: DAMON 监控属性，定义采样间隔（5ms）、聚合间隔（100ms）等。
- **`monitor_region_start/end`**: 目标监控内存区域的物理地址范围，默认为系统最大连续 RAM 区域。
- **`skip_anon`**: 布尔标志，若为真则跳过匿名页（anonymous pages）的回收。
- **`kdamond_pid`**: DAMON 工作线程的 PID，未启用时为 -1。
- **`damon_reclaim_stat`**: 统计信息结构，记录尝试回收区域数、成功回收区域数及配额超限次数。

### 主要函数

- **`damon_reclaim_new_scheme()`**: 创建 DAMOS（DAMON Operation Scheme）策略，定义“冷内存”模式（大小 ≥ PAGE_SIZE、访问次数为 0、年龄 ≥ `min_age`）并指定操作为 `DAMOS_PAGEOUT`。
- **`damon_reclaim_apply_parameters()`**: 应用所有用户配置参数到 DAMON 上下文（`ctx`），包括监控属性、回收策略、过滤器（如 `skip_anon`）和监控区域。
- **`damon_reclaim_turn()`**: 启动或停止 DAMON_RECLAIM 的核心监控与回收逻辑。
- **`damon_reclaim_enabled_store()`**: `enabled` 参数的 setter 回调，处理启用/禁用逻辑。
- **`damon_reclaim_handle_commit_inputs()`**: 处理 `commit_inputs` 标志，触发运行时参数重载。
- **`damon_reclaim_after_aggregation()` / `damon_reclaim_after_wmarks_check()`**: DAMON 回调函数，在聚合后和水位检查后更新统计信息并处理参数提交。
- **`damon_reclaim_init()`**: 模块初始化函数，创建 DAMON 上下文和目标，注册回调，并根据初始 `enabled` 状态决定是否启动。

## 3. 关键实现

### 冷内存识别与回收策略
- 通过 `damon_reclaim_new_scheme()` 定义 DAMOS 策略：
  - **访问模式匹配**：区域大小 ≥ `PAGE_SIZE`、访问次数 = 0、年龄 ≥ `min_age / aggr_interval`（转换为聚合周期单位）。
  - **操作类型**：`DAMOS_PAGEOUT`，即对匹配区域执行页面回收。
  - **配额控制**：使用 `damon_reclaim_quota` 限制回收速度和 CPU 开销，确保系统稳定性。
  - **水位激活**：仅当空闲内存比率低于 `high` 水位（50%）时激活策略，高于 `low` 水位（20%）时停用。

### 动态参数更新机制
- 用户可通过写入 `commit_inputs=Y` 触发运行时参数重载（`min_age`、配额、水位、监控区域等）。
- `damon_reclaim_handle_commit_inputs()` 在 DAMON 的聚合后或水位检查后回调中执行重载，确保线程安全。
- 重载时保留旧策略的配额状态（如已消耗的配额），避免统计中断。

### 匿名页过滤
- 若 `skip_anon=Y`，通过 `DAMOS_FILTER_TYPE_ANON` 过滤器排除匿名页（如进程堆栈、堆内存），仅回收文件缓存等页面。

### 监控区域自动配置
- 默认使用 `damon_set_region_biggest_system_ram_default()` 自动选择系统中最大的连续物理 RAM 区域作为监控目标，用户也可通过 `monitor_region_start/end` 手动指定。

## 4. 依赖关系

- **DAMON 核心框架** (`<linux/damon.h>`): 依赖 DAMON 提供的内存访问监控、策略引擎（DAMOS）、配额管理、水位控制等基础设施。
- **内核模块通用接口** (`modules-common.h`): 使用 `DEFINE_DAMON_MODULES_*` 宏简化参数声明和统计暴露。
- **内存管理子系统**: 通过 `DAMOS_PAGEOUT` 操作与 MM 子系统交互，实际执行页面回收。
- **参数解析工具** (`<linux/kstrtox.h>`): 用于解析用户输入的布尔值和数值参数。

## 5. 使用场景

- **内存压力缓解**: 在内存紧张但尚未触发传统 LRU 回收或 OOM Killer 之前，提前回收长期未使用的冷内存，延缓内存压力。
- **容器/虚拟机内存优化**: 在容器或 VM 中部署，自动回收应用未使用的缓存内存，提高宿主机内存密度。
- **大内存系统调优**: 在 TB 级内存服务器上，减少因缓存膨胀导致的内存浪费，提升整体内存效率。
- **低延迟敏感场景**: 通过配额限制（`ms=10`）确保回收操作不会显著影响关键任务的延迟。
- **调试与监控**: 通过 `kdamond_pid` 和统计参数（`reclaim_tried_regions` 等）监控 DAMON_RECLAIM 的运行状态和效果。