# task_work.c

> 自动生成时间: 2025-10-25 16:33:42
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `task_work.c`

---

# task_work.c 技术文档

## 文件概述

`task_work.c` 实现了 Linux 内核中的 **任务工作（task work）机制**，允许内核在特定时机（如任务返回用户态、收到信号或处于 NMI 上下文）异步执行回调函数。该机制主要用于在不阻塞当前执行路径的前提下，将工作延迟到目标任务的合适上下文中执行，常用于安全模块（如 seccomp）、用户态通知、延迟清理等场景。

任务工作队列是 **LIFO（后进先出）** 的，且不保证多个工作项之间的执行顺序。该机制支持多种通知模式，以适应不同的延迟和中断需求。

## 核心功能

### 主要函数

| 函数 | 功能描述 |
|------|--------|
| `task_work_add()` | 向指定任务添加一个回调工作项，并根据通知模式触发相应通知 |
| `task_work_run()` | 执行当前任务的所有挂起工作项，通常在返回用户态或任务退出前调用 |
| `task_work_cancel_match()` | 根据自定义匹配函数取消队列中的某个工作项 |
| `task_work_cancel_func()` | 取消队列中第一个函数指针匹配指定函数的工作项 |
| `task_work_cancel()` | 取消队列中指定的回调结构体（精确匹配指针） |

### 主要数据结构

- `struct callback_head`：通用回调结构体，包含 `next` 指针和 `func` 回调函数指针。
- `enum task_work_notify_mode`：通知模式枚举，包括：
  - `TWA_NONE`：不通知
  - `TWA_RESUME`：在任务返回用户态或进入 guest 模式前执行
  - `TWA_SIGNAL`：类似信号，可中断内核态任务并立即调度执行
  - `TWA_SIGNAL_NO_IPI`：类似 `TWA_SIGNAL`，但不发送 IPI 强制重调度
  - `TWA_NMI_CURRENT`：仅用于当前任务且在 NMI 上下文中，通过 IRQ work 触发

### 全局变量

- `work_exited`：特殊标记，表示任务已退出，不能再接受新工作。
- `irq_work_NMI_resume`（per-CPU）：用于 `TWA_NMI_CURRENT` 模式下触发 `TIF_NOTIFY_RESUME` 标志。

## 关键实现

### 1. 无锁队列插入（LIFO）

`task_work_add()` 使用 `try_cmpxchg()` 原子操作将新工作项插入到 `task->task_works` 链表头部，实现无锁并发插入。若发现 `task_works == &work_exited`，说明任务正在退出，返回 `-ESRCH`。

### 2. 多种通知机制

- **`TWA_RESUME`**：调用 `set_notify_resume(task)`，设置 `TIF_NOTIFY_RESUME` 标志，确保任务在 `exit_to_user_mode()` 路径中调用 `task_work_run()`。
- **`TWA_SIGNAL` / `TWA_SIGNAL_NO_IPI`**：分别调用 `set_notify_signal()` 和 `__set_notify_signal()`，设置 `TIF_NOTIFY_SIGNAL` 标志，并可能发送 IPI 强制目标 CPU 重调度。
- **`TWA_NMI_CURRENT`**：在 NMI 上下文中，通过 per-CPU 的 `irq_work` 触发软中断，在 IRQ 上下文中设置 `TIF_NOTIFY_RESUME`。

### 3. 安全退出处理

`task_work_run()` 在循环中：
- 原子地将 `task_works` 置为 `NULL`（或 `&work_exited`，若任务正在退出）。
- 若任务正在退出（`PF_EXITING`），则标记为 `work_exited`，防止后续 `task_work_add()` 成功。
- 执行所有取出的工作项，每个 `work->func(work)` 可能再次调用 `task_work_add()`，因此需循环处理。

### 4. 并发取消机制

`task_work_cancel_match()` 使用 `task->pi_lock` 保护遍历和删除操作：
- 遍历链表查找匹配项。
- 使用 `try_cmpxchg()` 原子地移除节点，避免与 `task_work_add()` 或 `task_work_run()` 冲突。
- 特别地，`task_work_run()` 在执行前会短暂获取 `pi_lock`，确保取消操作不会在执行过程中移除正在运行的工作项。

### 5. KASAN 辅助栈记录

在 `task_work_add()` 中，根据 `TWAF_NO_ALLOC` 标志调用 `kasan_record_aux_stack()` 或 `kasan_record_aux_stack_noalloc()`，用于在 KASAN 报告中显示工作项的分配调用栈。

## 依赖关系

- **`<linux/irq_work.h>`**：提供 `irq_work` 机制，用于 `TWA_NMI_CURRENT` 模式。
- **`<linux/resume_user_mode.h>`**：提供 `set_notify_resume()` 等接口，用于在返回用户态时触发回调。
- **`<linux/spinlock.h>`**：使用 `raw_spinlock_t`（`pi_lock`）保护取消操作。
- **`<linux/task_work.h>`**：定义 `task_work_notify_mode`、`callback_head` 等核心类型。
- **调度子系统**：依赖 `TIF_NOTIFY_RESUME` / `TIF_NOTIFY_SIGNAL` 标志位，在调度路径中调用 `task_work_run()`。
- **KASAN**：集成内存错误检测的调用栈记录功能。

## 使用场景

1. **Seccomp 通知**：当 seccomp 策略需要异步通知用户态代理时，通过 `task_work_add()` 添加回调。
2. **用户态延迟操作**：内核模块需要在任务下次返回用户态时执行清理或通知，使用 `TWA_RESUME`。
3. **NMI 上下文延迟处理**：在不可睡眠的 NMI 处理程序中，通过 `TWA_NMI_CURRENT` 安全地安排后续工作。
4. **信号式中断执行**：需要立即中断目标任务（即使在内核态）以执行高优先级工作，使用 `TWA_SIGNAL`。
5. **资源回收**：在任务退出路径中，确保所有挂起工作被执行或清理。
6. **动态取消机制**：如 seccomp 可能需要在条件变化时取消之前安排的工作，使用 `task_work_cancel_func()`。