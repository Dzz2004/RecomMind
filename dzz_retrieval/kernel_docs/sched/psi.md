# sched\psi.c

> 自动生成时间: 2025-10-25 16:14:11
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sched\psi.c`

---

# `sched/psi.c` 技术文档

## 1. 文件概述

`sched/psi.c` 实现了 **压力失速信息**（Pressure Stall Information, PSI）机制，用于监控和量化系统在 CPU、内存和 I/O 资源上的争用压力。该机制通过测量任务因资源不足而延迟执行的时间比例，提供两类关键指标：

- **SOME**：表示至少有一个任务因资源争用而延迟，反映工作负载性能下降。
- **FULL**：表示所有非空闲任务均被阻塞，导致 CPU 完全无法推进工作，反映资源利用率损失。

PSI 为系统管理员和容器运行时（如 cgroup）提供细粒度的资源压力感知能力，用于负载调度、自动扩缩容和性能调优。

## 2. 核心功能

### 主要数据结构

- `struct psi_group`  
  表示一个 PSI 监控组（如系统级或 cgroup 级），包含：
  - 每 CPU 的状态统计（`pcpu`）
  - 压力平均值（10s/60s/300s）
  - 触发器列表（用于通知用户空间）
  - 定时器与工作队列（用于周期性更新）

- `struct psi_group_cpu`  
  每 CPU 的 PSI 状态快照，记录：
  - 延迟任务数（`nr_delayed`）
  - 有效任务数（`nr_productive`）
  - 非空闲任务数（`nr_nonidle`）
  - 各状态的累计时间（`tstamp`、`state_start` 等）

- `psi_system`  
  全局系统级 PSI 组实例。

### 主要函数与机制

- `psi_write_begin()` / `psi_write_end()`  
  使用 `seqcount_t` 保护每 CPU PSI 状态写入，确保读取一致性。

- `psi_read_begin()` / `psi_read_retry()`  
  提供无锁读取接口，配合 seqcount 实现安全的跨 CPU 状态聚合。

- `group_init()`  
  初始化 PSI 组，包括锁、触发器链表、延迟工作队列等。

- `psi_avgs_work()`  
  延迟工作函数，用于计算并更新滑动窗口下的压力平均值（10s/60s/300s）。

- `poll_timer_fn()`  
  轮询定时器回调，支持用户空间通过轮询方式获取 PSI 更新。

- `setup_psi()`  
  内核启动参数 `psi=` 的解析函数，用于动态启用/禁用 PSI。

### 全局变量

- `psi_disabled` / `psi_cgroups_enabled`  
  静态分支预测键，用于在编译时或运行时优化 PSI 路径。

- `psi_enable`  
  控制 PSI 是否默认启用（受 `CONFIG_PSI_DEFAULT_DISABLED` 影响）。

- `psi_period`  
  PSI 采样周期（单位：纳秒），默认为 2 秒（`PSI_FREQ = 2*HZ+1`）。

- `EXP_10s` / `EXP_60s` / `EXP_300s`  
  指数加权移动平均（EWMA）的衰减系数，用于计算不同时间窗口的压力均值。

## 3. 关键实现

### 压力模型

PSI 基于 **执行潜力损失** 模型：
- **SOME** = `min(nr_delayed / threads, 1)`  
- **FULL** = `(threads - min(nr_productive, threads)) / threads`  
其中 `threads = min(nr_nonidle_tasks, nr_cpus)`，反映系统实际可并行执行的线程数。

### 多 CPU 聚合策略

为避免全局锁开销，PSI 采用 **每 CPU 局部统计 + 周期性聚合** 策略：
- 每个 runqueue 独立记录 `tSOME[cpu]`、`tFULL[cpu]` 和 `tNONIDLE[cpu]`
- 聚合时加权平均：  
  `tSOME = Σ(tSOME[i] * tNONIDLE[i]) / Σ(tNONIDLE[i])`  
  该方法在低开销下逼近真实全局压力。

### 无锁读取与一致性

使用 `seqcount_t` 机制：
- 写入时调用 `write_seqcount_begin/end()`
- 读取时通过 `read_seqcount_begin/retry()` 检测写冲突，必要时重试
- 避免读写锁，提升高并发下的性能

### 平均值计算

采用 **指数加权移动平均**（EWMA）计算 10s/60s/300s 压力均值：
- 每 2 秒更新一次（`PSI_FREQ`）
- 衰减因子预计算为定点整数（如 `EXP_10s = 1677` 对应 `1/exp(2/10)`）

### 触发器支持

支持两类触发器：
- **平均值触发器**（`avg_triggers`）：当某窗口平均压力超过阈值时通知
- **实时轮询触发器**（`rtpoll_triggers`）：支持用户空间高效轮询

## 4. 依赖关系

- **调度器核心**（`kernel/sched/`）  
  PSI 深度集成于 CFS 调度器，在任务入队/出队、睡眠/唤醒等路径调用 PSI 接口更新状态。

- **cgroup 子系统**  
  PSI 为每个支持的 cgroup（如 cpu、memory）创建独立的 `psi_group`，实现容器级资源压力监控。

- **时间子系统**  
  依赖 `sched_clock()` 获取高精度时间戳，用于状态持续时间计算。

- **工作队列与定时器**  
  使用 `delayed_work` 和 `timer_list` 实现异步平均值更新和轮询通知。

- **配置选项**  
  由 `CONFIG_PSI` 控制编译，`CONFIG_PSI_DEFAULT_DISABLED` 控制默认启用状态。

## 5. 使用场景

- **系统监控工具**（如 `pressure` 文件）  
  用户可通过 `/proc/pressure/{cpu,memory,io}` 读取系统级 PSI 数据。

- **容器运行时**（如 Docker、Kubernetes）  
  通过 cgroup v2 的 `memory.pressure`、`cpu.pressure` 等接口获取容器内压力指标，用于弹性伸缩或驱逐决策。

- **内核自适应调度**  
  PSI 数据可被其他子系统（如内存回收、负载均衡）用作反馈信号，优化资源分配。

- **性能分析与调优**  
  开发者利用 PSI 识别资源瓶颈（如内存回收导致的 FULL stall），定位性能下降根因。