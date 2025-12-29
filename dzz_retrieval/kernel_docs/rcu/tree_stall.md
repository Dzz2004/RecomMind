# rcu\tree_stall.h

> 自动生成时间: 2025-10-25 15:49:46
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `rcu\tree_stall.h`

---

# `rcu/tree_stall.h` 技术文档

## 1. 文件概述

`rcu/tree_stall.h` 是 Linux 内核 RCU（Read-Copy-Update）子系统中用于检测和处理 **RCU 宽限期（grace period）停滞（stall）** 的核心头文件。该文件定义了与 RCU CPU 停滞警告相关的控制逻辑、超时计算、状态重置机制以及与系统其他组件（如 sysrq、panic、sysfs）的交互接口。其主要目标是在 RCU 宽限期异常延迟时发出警告，甚至触发内核 panic，以帮助开发者诊断死锁、长时间关中断或调度器问题等严重系统异常。

## 2. 核心功能

### 全局变量
- `sysctl_panic_on_rcu_stall`：控制是否在 RCU 停滞时触发 `panic()`。
- `sysctl_max_rcu_stall_to_panic`：指定在触发 panic 前允许的最大停滞警告次数。
- `rcu_cpu_stall_suppress`：全局标志，用于在特定场景（如 sysrq、panic）下抑制 RCU 停滞警告。
- `rcu_stall_count`（仅 CONFIG_SYSFS）：记录 RCU 停滞警告发生的总次数。

### 主要函数
- `rcu_jiffies_till_stall_check()`：计算普通 RCU 宽限期的停滞检测超时时间（单位：jiffies）。
- `rcu_exp_jiffies_till_stall_check()`：计算**紧急（expedited）RCU 宽限期**的停滞检测超时时间。
- `rcu_gp_might_be_stalled()`：判断当前宽限期是否可能已停滞，用于优化内存回收策略。
- `rcu_cpu_stall_reset()`：重置停滞检测计时器，通常在宽限期开始或强制宽限期（fqs）循环中调用。
- `rcu_sysrq_start()` / `rcu_sysrq_end()`：在 sysrq 打印期间临时抑制 RCU 停滞警告。
- `record_gp_stall_check_time()`：在新宽限期开始时记录起始时间和超时阈值。
- `zero_cpu_stall_ticks()`：重置指定 CPU 的停滞检测计数器。
- `rcu_stall_kick_kthreads()`：在配置启用时，超时后唤醒 RCU 宽限期内核线程。
- `rcu_iw_handler()`：处理用于检测长时间关中断的 `irq_work` 回调。

### Sysfs 接口（仅 CONFIG_SYSFS）
- `/sys/kernel/rcu_stall_count`：只读属性，暴露 `rcu_stall_count` 的值。

## 3. 关键实现

### 停滞超时计算
- **基础超时**：由 `rcu_cpu_stall_timeout`（单位：秒）控制，默认范围为 3–300 秒，通过 `rcu_jiffies_till_stall_check()` 转换为 jiffies。
- **PROVE_RCU 扩展**：若启用 `CONFIG_PROVE_RCU`，会额外增加约 25% 的延迟（`RCU_STALL_DELAY_DELTA = 5 * HZ`），以适应锁验证带来的开销。
- **紧急宽限期**：`rcu_exp_jiffies_till_stall_check()` 使用独立的 `rcu_exp_cpu_stall_timeout`（单位：毫秒），并同样支持 `PROVE_RCU` 扩展。

### 停滞检测逻辑
- **宽限期进度跟踪**：通过 `rcu_state.gp_start`（宽限期开始时间）和 `rcu_state.jiffies_stall`（超时阈值）判断是否超时。
- **早期停滞判断**：`rcu_gp_might_be_stalled()` 使用缩短的阈值（`RCU_STALL_MIGHT_DIV = 8`，最小 `RCU_STALL_MIGHT_MIN = 2 * HZ`）快速判断宽限期是否可能停滞，用于优化 `synchronize_rcu()` 的调用策略。
- **内存屏障**：在读取 `jiffies` 和 RCU 状态字段（如 `.gp_seq`、`.gp_start`）之间使用 `smp_mb()`，防止因编译器或 CPU 重排序导致误报。

### 特殊场景处理
- **SysRq 抑制**：`rcu_sysrq_start()` 将 `rcu_cpu_stall_suppress` 设为 2，在 sysrq 打印期间禁止警告；`rcu_sysrq_end()` 恢复。
- **Panic 抑制**：通过 `panic_notifier_list` 注册回调，在内核 panic 时设置 `rcu_cpu_stall_suppress = 1`。
- **自动 Panic**：若 `sysctl_panic_on_rcu_stall` 启用且停滞次数超过 `sysctl_max_rcu_stall_to_panic`，则触发 `panic("RCU Stall\n")`。

### 中断与线程唤醒
- **长时间关中断检测**：通过 `irq_work` 机制（`rcu_iw_handler`）在宽限期中途检查中断是否被长时间关闭。
- **Kthread 唤醒**：若 `rcu_kick_kthreads` 启用且超时，会唤醒 RCU 宽限期线程（`rcu_state.gp_kthread`）并触发 ftrace dump。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/console.h>`：用于 sysrq 相关功能。
  - `<linux/kvm_para.h>`：可能用于虚拟化环境下的特殊处理（代码中未直接使用，但为历史依赖）。
  - `<linux/rcu_notifier.h>`：提供 RCU 通知链支持。
- **RCU 核心结构**：
  - 依赖 `rcu_state` 全局状态结构（定义于 `tree.c`）。
  - 依赖 `rcu_data` 和 `rcu_node` 结构（定义于 `tree_plugin.h`）。
- **配置选项**：
  - `CONFIG_SYSFS`：启用 sysfs 计数接口。
  - `CONFIG_PROVE_RCU`：启用额外的停滞延迟。
  - `CONFIG_PREEMPT_RCU`：影响任务阻塞信息的打印逻辑（文件末尾未完成的函数）。

## 5. 使用场景

- **系统调试**：当系统出现 RCU 宽限期无法完成的情况（如 CPU 死循环、长时间关中断、死锁），该模块会输出详细警告信息，帮助定位问题。
- **生产环境监控**：通过 sysfs 的 `rcu_stall_count` 可监控系统稳定性；通过 sysctl 可配置 panic 行为以实现自动恢复。
- **内核测试**：`CONFIG_PROVE_RCU` 下的扩展超时用于 lockdep 等验证工具，避免误报。
- **资源优化**：`rcu_gp_might_be_stalled()` 被内存回收子系统调用，决定是否绕过 RCU 延迟释放而直接同步等待。
- **紧急恢复**：在 sysrq 或 panic 等关键路径中抑制警告，避免干扰诊断信息输出。