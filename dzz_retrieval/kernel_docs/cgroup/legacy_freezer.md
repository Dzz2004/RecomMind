# cgroup\legacy_freezer.c

> 自动生成时间: 2025-10-25 12:47:19
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `cgroup\legacy_freezer.c`

---

# cgroup/legacy_freezer.c 技术文档

## 文件概述

`cgroup/legacy_freezer.c` 实现了 Linux 内核中 cgroup v1 的 freezer 子系统（legacy freezer），用于冻结和解冻指定控制组（cgroup）中的所有进程。该机制允许用户空间通过向 `freezer.state` 文件写入 `"FROZEN"` 或 `"THAWED"` 来暂停或恢复整个 cgroup 中的任务执行，常用于系统快照、检查点/恢复（CRIU）和资源管理等场景。

## 核心功能

### 主要数据结构

- **`enum freezer_state_flags`**  
  定义 freezer 的状态标志：
  - `CGROUP_FREEZER_ONLINE`：freezer 已完全上线
  - `CGROUP_FREEZING_SELF`：当前 cgroup 自身处于冻结过程中
  - `CGROUP_FREEZING_PARENT`：祖先 cgroup 正在冻结，导致本 cgroup 被冻结
  - `CGROUP_FROZEN`：当前 cgroup 及其所有后代已完全冻结
  - `CGROUP_FREEZING`：`FREEZING_SELF` 与 `FREEZING_PARENT` 的组合掩码

- **`struct freezer`**  
  freezer 子系统的 cgroup 状态结构体，包含：
  - `css`：嵌入的 `cgroup_subsys_state`
  - `state`：当前 freezer 状态（使用上述标志位）

### 主要函数

- **`cgroup_freezing()`**  
  判断指定任务是否处于冻结状态（即其 freezer 的 state 包含 `CGROUP_FREEZING`）

- **`freezer_css_alloc()`**  
  分配新的 freezer 结构体

- **`freezer_css_online()`**  
  在 cgroup 创建完成时调用，标记 freezer 为在线，并继承父 freezer 的冻结状态

- **`freezer_css_offline()`**  
  在 cgroup 销毁前调用，清除状态并更新全局 `freezer_active` 静态分支计数

- **`freezer_attach()`**  
  将任务迁移到新 cgroup 时调用，确保任务状态与目标 freezer 的当前状态一致

- **`freezer_fork()`**  
  新进程 fork 后调用，使其符合所属 cgroup 的冻结状态

- **`update_if_frozen()`**  
  检查当前 cgroup 及其所有子 cgroup 和任务是否均已冻结，若是则设置 `CGROUP_FROZEN` 标志

- **`freezer_state_strs()`**  
  将内部状态转换为用户可见的字符串（"FROZEN" / "FREEZING" / "THAWED"）

## 关键实现

### 状态继承与传播机制

- **冻结状态继承**：当父 cgroup 被冻结时，所有子 cgroup 自动继承 `CGROUP_FREEZING_PARENT` 标志，从而被冻结。
- **状态同步**：`freezer_attach()` 在任务迁移时强制同步任务状态；若目标 cgroup 处于 `FROZEN` 状态，则先将其降级为 `FREEZING`，再调用 `freeze_task()`，后续由 `update_if_frozen()` 确认是否真正冻结完成。
- **懒更新机制**：`CGROUP_FROZEN` 标志不会在冻结开始时立即设置，而是通过 `update_if_frozen()` 懒惰地检查所有子 cgroup 和任务是否都已冻结后才设置。

### 并发控制

- 使用全局 `freezer_mutex` 互斥锁保护所有状态变更操作，确保 freezer 状态修改的原子性。
- 在修改涉及 CPU 热插拔敏感的 `freezer_active` 静态分支计数时，配合 `cpus_read_lock()` 防止 CPU 离线导致的竞态。

### 任务冻结流程

1. 用户写入 `"FROZEN"` 到 `freezer.state`，设置 `CGROUP_FREEZING_SELF`
2. 所有现有任务被调用 `freeze_task()`
3. 新 fork 的任务或迁移进来的任务在 `freezer_fork()` 或 `freezer_attach()` 中被冻结
4. 定期调用 `update_if_frozen()` 检查是否所有任务和子 cgroup 都已冻结
5. 若全部冻结完成，设置 `CGROUP_FROZEN` 标志

### 解冻处理

- 写入 `"THAWED"` 会清除 `CGROUP_FREEZING_SELF`
- `freezer_attach()` 和 `freezer_fork()` 会调用 `__thaw_task()` 解冻任务
- 父 freezer 解冻时，子 freezer 的 `CGROUP_FREEZING_PARENT` 被清除，可能触发解冻

## 依赖关系

- **`<linux/cgroup.h>`**：cgroup 核心框架，提供 `cgroup_subsys_state`、`task_css()` 等接口
- **`<linux/freezer.h>`**：内核任务冻结机制，提供 `freeze_task()`、`__thaw_task()`、`frozen()` 等函数
- **`<linux/cpu.h>`**：用于 `cpus_read_lock()` 保护 CPU 热插拔期间的静态分支操作
- **`freezer_active` 静态分支**：由其他内核模块（如 PM core）使用，用于快速判断系统是否存在活跃的 freezer cgroup

## 使用场景

- **系统休眠/挂起**：在 suspend 前冻结用户空间进程，防止干扰 suspend 流程
- **容器检查点/恢复（CRIU）**：冻结容器内所有进程以创建一致的内存快照
- **调试与测试**：临时暂停特定服务或应用组以进行故障分析
- **资源隔离**：在资源紧张时冻结低优先级任务组以释放 CPU 资源
- **cgroup v1 兼容性**：为仍使用 cgroup v1 的系统提供进程冻结功能（cgroup v2 使用统一的 cgroup.freeze 接口）