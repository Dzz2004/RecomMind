# trace\preemptirq_delay_test.c

> 自动生成时间: 2025-10-25 17:06:05
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\preemptirq_delay_test.c`

---

# `trace/preemptirq_delay_test.c` 技术文档

## 1. 文件概述

`preemptirq_delay_test.c` 是一个用于测试 Linux 内核延迟追踪器（latency tracers）的内核模块。该模块通过在内核线程中主动禁用中断（IRQ）或抢占（preemption）并执行指定时长的忙等待（busy-wait），人为制造延迟场景，从而验证延迟追踪机制（如 `irqsoff`、`preemptoff` 等 tracer）是否能正确捕获和记录此类延迟事件。模块支持通过 sysfs 接口触发测试，并可通过模块参数灵活配置测试模式、延迟时间、突发次数及 CPU 亲和性。

## 2. 核心功能

### 模块参数（可配置）
- `delay`（`ulong`）：忙等待时长，单位为微秒，默认 100 μs。
- `test_mode`（`char[12]`）：测试模式，可选 `"irq"`（禁用中断）、`"preempt"`（禁用抢占）或 `"alternate"`（交替执行两种模式），默认为 `"irq"`。
- `burst_size`（`uint`）：单次测试中连续执行延迟操作的次数，默认为 1。
- `cpu_affinity`（`int`）：指定测试线程运行的 CPU 编号，-1 表示不限制。

### 主要函数
- `busy_wait(ulong time)`：使用高精度 `trace_clock_local()` 实现指定微秒级的忙等待。
- `irqoff_test(void)`：保存本地中断状态，禁用中断，执行 `busy_wait`，然后恢复中断。
- `preemptoff_test(void)`：禁用内核抢占，执行 `busy_wait`，然后重新启用抢占。
- `execute_preemptirqtest(int idx)`：根据 `test_mode` 选择执行 IRQ 禁用、抢占禁用或交替模式。
- `preemptirq_delay_run(void *data)`：内核线程主函数，设置 CPU 亲和性，按 `burst_size` 调用测试函数，并等待停止信号。
- `preemptirq_run_test(void)`：创建并启动测试线程，等待其完成。
- `trigger_store(...)`：sysfs 写回调函数，用于手动触发测试。
- `preemptirq_delay_init/exit`：模块初始化与退出函数。

### 数据结构
- `testfuncs[]`：包含 10 个不同命名的测试函数指针（`preemptirqtest_0` 到 `preemptirqtest_9`），用于生成不同的调用栈，便于追踪器区分。
- `done`：`completion` 对象，用于同步主线程与测试线程。
- `attr_group` 与 `trigger_attribute`：sysfs 属性组，暴露 `/sys/kernel/preemptirq_delay_test/trigger` 接口。

## 3. 关键实现

### 多函数生成机制
通过宏 `DECLARE_TESTFN(POSTFIX)` 自动生成 10 个内容相同但符号名不同的函数（`preemptirqtest_0` ~ `preemptirqtest_9`）。此举确保每次调用产生唯一的调用栈回溯（backtrace），便于延迟追踪器准确识别和记录不同实例的延迟事件，避免因函数内联或符号重复导致追踪信息混淆。

### 高精度忙等待
`busy_wait()` 使用 `trace_clock_local()`（一种快速、单调、适用于追踪的时钟源）进行时间测量，循环检查已过去时间是否达到目标延迟（微秒转纳秒）。循环中检查 `kthread_should_stop()` 以支持线程优雅退出。

### 模式切换逻辑
`execute_preemptirqtest()` 根据 `test_mode` 字符串动态选择延迟类型：
- `"irq"`：调用 `irqoff_test()`，使用 `local_irq_save/restore` 禁用本地 CPU 中断。
- `"preempt"`：调用 `preemptoff_test()`，使用 `preempt_disable/enable` 禁用内核抢占。
- `"alternate"`：根据调用索引奇偶性交替执行上述两种模式。

### CPU 亲和性控制
若 `cpu_affinity` 参数有效（≥0），测试线程会通过 `set_cpus_allowed_ptr()` 绑定到指定 CPU，确保延迟测试在目标处理器上执行，便于针对性分析。

### sysfs 触发接口
模块在 `/sys/kernel/` 下创建 `preemptirq_delay_test` 目录，并提供 `trigger` 文件（权限 0200）。向该文件写入任意内容即可触发一次完整的延迟测试流程。

### 模块自动测试
模块加载时（`preemptirq_delay_init`）会自动执行一次默认配置的测试，用于快速验证功能。

## 4. 依赖关系

- **内核追踪子系统**：依赖 `trace_clock_local()`（来自 `kernel/trace/trace_clock.c`）提供高精度时间戳。
- **内核线程机制**：使用 `kthread_run()` 和 `kthread_stop()` 创建和管理内核线程。
- **中断与抢占控制**：依赖 `local_irq_save/restore` 和 `preempt_disable/enable` 等底层调度与中断管理原语。
- **sysfs 接口**：依赖 `kobject`、`kobj_attribute` 和 `sysfs_create_group` 实现用户空间交互。
- **CPU 掩码操作**：使用 `cpumask_var_t` 及相关 API 设置线程 CPU 亲和性。

## 5. 使用场景

- **延迟追踪器验证**：开发或调试 `ftrace` 中的 `irqsoff`、`preemptoff`、`preemptirqsoff` 等延迟追踪器时，用于生成可控的延迟事件，验证追踪器能否正确捕获延迟路径、持续时间和调用栈。
- **实时性分析**：在实时系统（如 PREEMPT_RT 补丁集）开发中，用于测试和量化中断/抢占禁用对系统响应时间的影响。
- **性能回归测试**：作为自动化测试用例的一部分，监控内核变更是否引入不可接受的延迟增长。
- **教学与演示**：展示 Linux 内核中中断禁用和抢占禁用对系统行为的影响，以及如何通过追踪工具进行观测。