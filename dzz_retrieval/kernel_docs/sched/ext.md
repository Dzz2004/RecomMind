# sched\ext.c

> 自动生成时间: 2025-10-25 16:08:15
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\ext.c`

---

# `sched/ext.c` 技术文档

## 文件概述

`sched/ext.c` 是 Linux 内核中 **BPF 可扩展调度器（sched_ext）** 的核心实现文件之一，定义了调度器与 BPF 程序交互所需的数据结构、常量和操作接口。该文件为用户空间通过 BPF 实现自定义调度策略提供了内核侧的框架支持，允许将任务调度逻辑完全委托给加载的 BPF 程序，同时保留与内核调度子系统的安全集成。

## 核心功能

### 主要数据结构

- **`struct sched_ext_ops`**  
  BPF 调度器的操作函数表，包含调度器必须或可选实现的回调函数，如 `select_cpu`、`enqueue`、`dequeue`、`dispatch` 等，用于控制任务的 CPU 选择、入队、出队和分发逻辑。

- **`struct scx_exit_info`**  
  描述 BPF 调度器退出原因的结构体，包含退出类型（`kind`）、退出码（`exit_code`）、错误信息（`reason`、`msg`）、回溯栈（`bt`）和调试转储（`dump`）。

- **`struct scx_init_task_args` / `scx_exit_task_args`**  
  分别用于 `ops.init_task()` 和 `ops.exit_task()` 回调的参数容器，传递任务初始化/退出上下文（如是否由 fork 触发、所属 cgroup 等）。

- **`struct scx_cpu_acquire_args` / `scx_cpu_release_args`**  
  用于 CPU 获取/释放回调的参数结构，其中 `cpu_release` 包含抢占原因（如 RT/DL 任务抢占）和即将运行的任务。

- **`struct scx_dump_ctx`**  
  为调度器转储（dump）操作提供上下文信息，包括退出类型、时间戳等。

### 关键枚举与常量

- **`enum scx_exit_kind`**  
  定义调度器退出的类别，如正常退出（`SCX_EXIT_DONE`）、用户/BPF/内核主动注销（`SCX_EXIT_UNREG*`）、系统请求（`SCX_EXIT_SYSRQ`）或运行时错误（`SCX_EXIT_ERROR*`）。

- **`enum scx_exit_code`**  
  定义 64 位退出码的位域格式，支持系统原因（如 `SCX_ECODE_RSN_HOTPLUG`）和系统动作（如 `SCX_ECODE_ACT_RESTART`），允许用户自定义退出上下文。

- **`enum scx_ops_flags`**  
  调度器操作标志，控制调度行为：
  - `SCX_OPS_KEEP_BUILTIN_IDLE`：保留内建空闲跟踪
  - `SCX_OPS_ENQ_LAST`：切片到期后仍无任务时重新入队
  - `SCX_OPS_ENQ_EXITING`：由 BPF 处理退出中任务
  - `SCX_OPS_SWITCH_PARTIAL`：仅调度 `SCHED_EXT` 策略任务
  - `SCX_OPS_HAS_CGROUP_WEIGHT`：支持 cgroup cpu.weight

- **调度器常量**  
  如 `SCX_DSP_DFL_MAX_BATCH`（默认分发批大小）、`SCX_WATCHDOG_MAX_TIMEOUT`（看门狗超时）、`SCX_OPS_TASK_ITER_BATCH`（任务迭代锁释放批次）等，用于控制调度器内部行为。

## 关键实现

- **BPF 调度器生命周期管理**  
  通过 `scx_exit_info` 和退出码机制，支持多种退出路径（用户、BPF、内核、SysRq、错误），并提供详细的诊断信息（回溯、消息、转储）。

- **任务入队优化**  
  在 `select_cpu` 中允许直接插入 DSQ（如本地 DSQ），跳过后续 `enqueue` 调用，减少调度开销；同时通过 `SCX_OPS_ENQ_EXITING` 标志处理退出中任务的调度问题，避免 RCU 停顿。

- **CPU 抢占通知**  
  通过 `scx_cpu_release_args` 向 BPF 调度器传递 CPU 被高优先级调度类（RT/DL/Stop）抢占的原因，便于调度器做出相应调整。

- **cgroup 集成**  
  支持 cgroup 调度（`CONFIG_EXT_GROUP_SCHED`），在任务加入 cgroup 时传递权重信息（`scx_cgroup_init_args`），并通过 `SCX_OPS_HAS_CGROUP_WEIGHT` 标志启用。

- **安全与鲁棒性**  
  内核侧跟踪 BPF 是否拥有任务，可忽略无效分发；任务迭代时定期释放锁（`SCX_OPS_TASK_ITER_BATCH`），防止 RCU/CSD 停顿；看门狗机制（`SCX_WATCHDOG_MAX_TIMEOUT`）检测任务卡死。

## 依赖关系

- **BPF 子系统**：通过 `#include <linux/bpf.h>` 依赖 BPF 基础设施，用于加载和验证调度器 BPF 程序。
- **调度核心**：与 `kernel/sched/` 下的核心调度代码（如 `core.c`、`rt.c`、`dl.c`）交互，处理任务入队、CPU 选择和抢占。
- **cgroup 子系统**：当启用 `CONFIG_EXT_GROUP_SCHED` 时，依赖 cgroup CPU 控制器获取任务权重和层级信息。
- **RCU 与锁机制**：使用 `scx_tasks_lock` 保护任务迭代，需与 RCU 同步机制协调。

## 使用场景

- **自定义调度策略开发**：用户通过 BPF 实现特定工作负载的调度逻辑（如延迟敏感型、批处理优化、NUMA 感知等），并注册到 `sched_ext`。
- **系统调试与监控**：利用 `ops.dump()` 和退出信息结构体，在调度器异常退出时收集诊断数据。
- **混合调度部署**：通过 `SCX_OPS_SWITCH_PARTIAL` 标志，仅对部分任务（`SCHED_EXT`）启用 BPF 调度，其余任务仍由 CFS 处理。
- **资源隔离与 QoS**：结合 cgroup 支持，为不同 cgroup 配置不同的调度行为和资源权重。
- **内核调度实验平台**：作为安全的沙箱环境，测试新型调度算法而无需修改核心调度代码。