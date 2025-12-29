# livepatch\transition.c

> 自动生成时间: 2025-10-25 14:34:51
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `livepatch\transition.c`

---

# livepatch/transition.c 技术文档

## 1. 文件概述

`livepatch/transition.c` 是 Linux 内核实时补丁（Kernel Live Patching）子系统的核心组件之一，负责管理补丁状态转换过程。该文件实现了从旧代码到新补丁代码（或反向）的安全过渡机制，确保所有正在运行的任务（包括内核线程、用户态进程和 idle 线程）都能安全地切换到目标补丁状态，避免在函数栈中仍存在待替换函数时进行切换，从而防止系统崩溃或行为异常。

## 2. 核心功能

### 主要全局变量
- `klp_transition_patch`：指向当前正在进行状态转换的补丁对象。
- `klp_target_state`：目标补丁状态（`KLP_PATCHED` 或 `KLP_UNPATCHED`），初始为 `KLP_UNDEFINED`。
- `klp_signals_cnt`：用于统计信号处理相关计数（当前未在代码片段中完整使用）。
- `klp_stack_entries`：每 CPU 栈追踪缓冲区，用于保存任务调用栈。

### 主要函数
- `klp_transition_work_fn()`：延迟工作队列回调，用于重试未能完成转换的“滞留”任务。
- `klp_synchronize_transition()`：强制在所有 CPU 上执行调度同步，确保 RCU 不可见区域也能完成同步。
- `klp_complete_transition()`：完成整个补丁状态转换，清理数据结构并调用回调。
- `klp_cancel_transition()`：在转换开始前取消补丁操作。
- `klp_update_patch_state()`：更新指定任务的补丁状态。
- `klp_check_stack_func()`：检查给定函数是否出现在栈追踪中。
- `klp_check_stack()`：检查任务栈中是否存在待替换/待移除的函数（代码片段中被截断）。

### 静态键与调度集成
- 在支持 `CONFIG_PREEMPT_DYNAMIC` 的系统上，通过 `sched_dynamic_klp_enable/disable()` 启用/禁用 cond_resched 中的栈检查。
- 否则使用静态键 `klp_sched_try_switch_key` 控制是否在 `cond_resched()` 中进行补丁栈检查，以帮助 CPU 密集型内核线程完成补丁切换。

## 3. 关键实现

### 补丁状态转换流程
1. **初始化阶段**：设置 `klp_transition_patch` 和 `klp_target_state`。
2. **任务状态更新**：通过 `TIF_PATCH_PENDING` 标志标记需要更新状态的任务。
3. **栈安全检查**：使用 `stack_trace_save_tsk_reliable()` 获取可靠栈追踪，检查是否存在待替换函数。
4. **同步机制**：
   - 使用 `klp_synchronize_transition()` 调用 `schedule_on_each_cpu(klp_sync)`，强制所有 CPU（包括 idle 和用户态）参与同步。
   - 此机制绕过标准 RCU，适用于 RCU 不活跃的上下文（如 `user_exit()` 前）。
5. **完成清理**：
   - 清除所有任务的 `patch_state` 为 `KLP_UNDEFINED`。
   - 调用对象级的 `post_patch` 或 `post_unpatch` 回调。
   - 重置全局状态变量。

### 栈检查逻辑
- **打补丁时（KLP_PATCHED）**：检查栈中是否包含**旧函数**（原始函数或上一个补丁版本的函数）。
- **卸补丁时（KLP_UNPATCHED）**：检查栈中是否包含**新函数**（当前补丁中的函数）。
- 若发现相关函数在栈中，则返回 `-EAGAIN`，推迟该任务的状态切换。

### 内存屏障与并发控制
- `test_and_clear_tsk_thread_flag()` 不仅清除 `TIF_PATCH_PENDING`，还充当读屏障（`smp_rmb`），确保：
  1. `klp_target_state` 的读取顺序正确。
  2. 后续 `klp_ftrace_handler()` 能看到一致的 `func->transition` 状态。

### 滞留任务处理
- 通过 `DECLARE_DELAYED_WORK(klp_transition_work, ...)` 定期重试未能完成转换的任务，提高转换成功率。

## 4. 依赖关系

- **内部依赖**：
  - `core.h`：提供 `klp_mutex`、`klp_for_each_object/func` 等核心宏和函数。
  - `patch.h`：定义 `klp_func`、`klp_object`、`klp_patch` 等数据结构及操作函数（如 `klp_unpatch_objects`）。
  - `transition.h`：声明本文件导出的接口（如 `klp_cancel_transition`）。
- **内核子系统**：
  - **RCU**：用于常规同步，但在 RCU 不活跃区域使用自定义同步。
  - **调度器**：通过 `cond_resched()` 集成补丁检查，依赖 `CONFIG_PREEMPT_DYNAMIC` 或静态键。
  - **栈追踪**：使用 `stack_trace_save_tsk_reliable()` 获取可靠调用栈。
  - **CPU 热插拔**：通过 `for_each_possible_cpu` 处理所有可能的 CPU（包括离线 CPU 的 idle 任务）。

## 5. 使用场景

- **应用实时补丁**：当管理员通过 sysfs 启用一个 livepatch 模块时，内核调用此文件中的函数将所有任务从旧代码切换到新补丁代码。
- **卸载实时补丁**：当禁用补丁时，安全地将所有任务切换回旧函数，并清理补丁数据结构。
- **处理滞留任务**：对于因长时间运行或处于不可中断状态而未能及时切换的任务，通过延迟工作队列周期性重试。
- **支持特殊上下文**：确保在 RCU 不活跃的上下文（如系统调用入口/出口、idle 循环）中也能安全完成补丁切换。
- **错误恢复**：在补丁初始化后、实际切换前发生错误时，调用 `klp_cancel_transition()` 安全回滚。