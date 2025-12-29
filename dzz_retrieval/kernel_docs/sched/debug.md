# sched\debug.c

> 自动生成时间: 2025-10-25 16:07:26
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\debug.c`

---

# `sched/debug.c` 技术文档

## 1. 文件概述

`sched/debug.c` 是 Linux 内核调度子系统中的调试支持模块，主要提供以下功能：

- 通过 debugfs 接口暴露调度器内部状态（如 CFS 红黑树结构）
- 允许动态启用/禁用调度器特性（sched features）
- 支持配置调度器可调参数的缩放策略（SMP 环境下）
- 提供抢占模式的动态切换接口（CONFIG_PREEMPT_DYNAMIC）
- 控制调度域（sched domain）的详细调试输出
- 支持公平服务器（fair server）运行时参数的动态调整（实验性功能）

该文件为内核开发者和系统调优人员提供运行时诊断和调优能力。

## 2. 核心功能

### 主要函数

- **`SEQ_printf` 宏**：统一向 seq_file 或控制台输出调试信息
- **`nsec_high` / `nsec_low`**：将纳秒值拆分为高/低部分，便于格式化输出
- **`sched_feat_show` / `sched_feat_write`**：读取/设置调度器特性开关
- **`sched_scaling_show` / `sched_scaling_write`**（SMP）：配置调度参数缩放策略
- **`sched_dynamic_show` / `sched_dynamic_write`**（PREEMPT_DYNAMIC）：动态切换抢占模式
- **`sched_verbose_write`**：控制详细调试输出开关，并管理调度域 debugfs 条目
- **`sched_debug_open`**：打开主调度调试接口（`/sys/kernel/debug/sched/debug`）
- **`sched_fair_server_write`**：动态设置公平服务器的运行时和周期参数

### 主要数据结构

- **`sched_feat_names[]`**：调度器特性名称字符串数组
- **`sched_feat_keys[]`**（CONFIG_JUMP_LABEL）：每个特性的静态跳转键（static_key），用于性能优化
- **`sched_feat_fops`**：调度特性 debugfs 文件操作结构
- **`sched_scaling_fops`**（SMP）：调度缩放策略文件操作结构
- **`sched_dynamic_fops`**（PREEMPT_DYNAMIC）：抢占模式动态切换文件操作结构
- **`sched_verbose_fops`**：详细调试开关文件操作结构
- **`sched_debug_fops`**：主调度调试接口文件操作结构

### 全局变量

- **`sched_debug_verbose`**：控制是否启用详细调度调试输出
- **`sd_dentry`**（SMP）：调度域 debugfs 目录入口
- **`fair_server_period_max/min`**：公平服务器周期参数的上下限

## 3. 关键实现

### 调度器特性动态开关

- 通过 `sysctl_sched_features` 位图跟踪各特性的启用状态
- 在支持 `CONFIG_JUMP_LABEL` 时，使用 `static_key` 机制实现零开销条件分支：
  - 启用特性：`static_key_enable_cpuslocked()`
  - 禁用特性：`static_key_disable_cpuslocked()`
- 特性名称通过 `features.h` 自动生成，确保与定义一致

### 安全并发控制

- 在修改调度特性时使用 `cpus_read_lock()` + `inode_lock()` 保证一致性
- 调度域调试开关使用 `sched_domains_mutex` 互斥锁保护
- 公平服务器参数修改时使用 `rq_lock_irqsave` 保护运行队列

### 时间值格式化

- `SPLIT_NS(x)` 宏将 64 位纳秒值拆分为秒和微秒部分
- 通过 `do_div()` 安全处理 64 位除法（兼容 32 位平台）

### 公平服务器参数验证

- 运行时不能超过周期（`runtime <= period`）
- 周期必须在 100μs ~ 4s 范围内
- 修改时若 CFS 队列非空，会临时停止/重启服务器以应用新参数

## 4. 依赖关系

### 头文件依赖
- `features.h`：定义调度器特性列表（通过宏展开生成）
- 调度核心头文件（隐式包含）：`sched.h`、`cpumask.h` 等

### 配置选项依赖
- **`CONFIG_JUMP_LABEL`**：启用静态跳转优化调度特性开关
- **`CONFIG_SMP`**：启用调度缩放策略和调度域调试功能
- **`CONFIG_PREEMPT_DYNAMIC`**：启用运行时抢占模式切换
- **`CONFIG_DEBUG_FS`**：提供 debugfs 接口基础支持

### 内核子系统依赖
- **调度核心**：访问 `rq`（运行队列）、`cfs_rq` 等核心数据结构
- **RCU/锁机制**：使用 `cpus_read_lock()`、`mutex` 等同步原语
- **debugfs**：通过 `single_open()`、`seq_read()` 等接口暴露调试信息

## 5. 使用场景

### 调试调度行为
- 通过 `/sys/kernel/debug/sched/debug` 查看 CFS 红黑树、运行队列状态等
- 启用 `sched_debug_verbose` 获取调度域拓扑详细信息

### 动态调优
- 通过 `/sys/kernel/debug/sched_features` 启用/禁用特定调度特性（如 `NO_GENTLE_FAIR_SLEEPERS`）
- 在 SMP 系统中通过 `/sys/kernel/debug/sched_scaling` 调整参数缩放策略（none/linear/log）

### 抢占模式切换
- 在支持动态抢占的内核中，通过 `/sys/kernel/debug/sched_dynamic` 切换 none/voluntary/full 抢占模式

### 实验性功能测试
- 通过 CPU 特定接口（如 `/sys/kernel/debug/sched/fair_server_runtime_0`）调整公平服务器参数，用于实时性测试

### 性能分析
- 结合 `perf`、`ftrace` 等工具，通过调度器调试接口验证调度决策和延迟表现