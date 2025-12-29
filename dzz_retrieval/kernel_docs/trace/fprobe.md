# trace\fprobe.c

> 自动生成时间: 2025-10-25 17:02:19
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\fprobe.c`

---

# `trace/fprobe.c` 技术文档

## 1. 文件概述

`fprobe.c` 实现了 Linux 内核中 **fprobe**（Function Probe）机制，它是对 **ftrace** 框架的轻量级封装，用于在函数入口（entry）和/或出口（exit）处动态插入探针回调。  
fprobe 支持两种注册方式：基于符号名（支持通配符过滤）或直接基于函数地址。若配置了退出处理函数（`exit_handler`），则通过 `rethook` 机制自动在函数返回时触发回调。  
该模块特别适用于需要低开销、高灵活性的函数级动态追踪场景，并可与 kprobes 共享回调上下文。

---

## 2. 核心功能

### 主要数据结构

- **`struct fprobe`**  
  用户定义的探针控制结构，包含：
  - `entry_handler`：函数入口回调
  - `exit_handler`：函数出口回调（可选）
  - `rethook`：用于管理函数返回钩子的结构
  - `ops`：关联的 `ftrace_ops`，用于注册到 ftrace 框架
  - `nmissed`：因资源不足或递归等原因错过的探针调用计数
  - `nr_maxactive`：用户指定的最大并发返回钩子数量
  - `entry_data_size`：用户可在入口回调中分配的私有数据大小

- **`struct fprobe_rethook_node`**  
  为每个被探测函数调用实例分配的节点，用于在入口和出口之间传递上下文：
  - `node`：嵌入的 `rethook_node`
  - `entry_ip` / `entry_parent_ip`：记录入口时的指令指针和调用者地址
  - `data[]`：变长数组，用于存储用户自定义的入口数据

### 主要函数

- **`register_fprobe()`**  
  通过符号通配符模式注册 fprobe，支持正向过滤（`filter`）和反向排除（`notfilter`）。

- **`register_fprobe_ips()`**  
  通过一组已知的 ftrace 位置地址（通常是符号地址 + 架构偏移）直接注册 fprobe。

- **`register_fprobe_syms()`**（代码截断，但可推断）  
  通过符号名数组注册 fprobe，内部调用 `get_ftrace_locations()` 将符号转换为地址。

- **`fprobe_handler()` / `fprobe_kprobe_handler()`**  
  ftrace 入口回调函数。前者用于普通 fprobe，后者用于与 kprobes 共享上下文的场景，包含额外的 kprobe 递归检测。

- **`fprobe_exit_handler()`**  
  由 `rethook` 框架在函数返回时调用，执行用户定义的 `exit_handler`。

- **`fprobe_init()` / `fprobe_init_rethook()`**  
  初始化 fprobe 结构及其返回钩子资源池。

- **`get_ftrace_locations()`**  
  将符号名数组转换为对应的内核地址数组，供 `register_fprobe_ips()` 使用。

---

## 3. 关键实现

### 递归防护机制
- 所有入口和出口处理函数均使用 `ftrace_test_recursion_trylock()` / `unlock()` 防止在追踪路径中发生递归调用，避免死锁或栈溢出。
- 在与 kprobes 共享模式下，额外检查 `kprobe_running()`，若已有 kprobe 处理中则跳过本次 fprobe 调用，确保上下文一致性。

### 返回钩子（rethook）管理
- 若用户提供了 `exit_handler`，则在初始化时预分配 `rethook_node` 池：
  - 默认大小为 `num * num_possible_cpus() * 2`（`num` 为探测点数量）
  - 用户可通过 `nr_maxactive` 覆盖默认值
- 入口处理中，若 `entry_handler` 返回非零值，则立即回收 `rethook_node`（表示不追踪返回）；否则将其挂载到当前函数调用栈，等待返回时触发。

### 符号解析与地址转换
- `get_ftrace_locations()` 对符号名数组排序后调用 `ftrace_lookup_symbols()`，这是 ftrace 提供的标准符号解析接口。
- 要求符号必须对应有效的 ftrace 可追踪位置（通常是函数开头的 `mcount`/`fentry` 桩）。

### 错误处理与资源清理
- 任何初始化失败（如内存分配、ftrace 注册失败）都会调用 `fprobe_fail_cleanup()` 释放已分配资源，包括 `rethook` 池和 ftrace 过滤器。

---

## 4. 依赖关系

- **ftrace 核心框架**（`<linux/ftrace.h>`, `"trace.h"`）  
  依赖 ftrace 的函数追踪、过滤、递归检测等基础设施。

- **kprobes 子系统**（`<linux/kprobes.h>`）  
  在共享模式下依赖 kprobes 的运行状态检测（`kprobe_running()`）和忙状态标记（`kprobe_busy_begin/end()`）。

- **rethook 机制**（`<linux/rethook.h>`）  
  用于实现函数返回钩子，是 exit_handler 的底层支撑。

- **kallsyms**（`<linux/kallsyms.h>`）  
  用于符号名到地址的解析（通过 `ftrace_lookup_symbols` 间接使用）。

- **内存管理**（`<linux/slab.h>`）  
  动态分配 `fprobe_rethook_node` 和地址数组。

- **排序算法**（`<linux/sort.h>`）  
  对符号名数组排序以满足 `ftrace_lookup_symbols` 的输入要求。

---

## 5. 使用场景

- **动态函数追踪**：无需修改内核代码，即可在任意可追踪函数的入口/出口插入自定义逻辑（如性能分析、参数记录、行为监控）。
- **低开销探针**：相比 kprobes，fprobe 基于 ftrace，开销更小，适用于高频函数。
- **与 kprobes 协同工作**：通过 `fprobe_shared_with_kprobes()` 标志，允许 fprobe 与 kprobes 共享同一回调上下文，避免冲突。
- **符号级批量探测**：支持通配符（如 `"vfs_*"`）一次性探测多个相关函数。
- **精确地址探测**：适用于已知具体地址的场景（如 JIT 代码、模块符号解析后地址）。
- **函数调用链分析**：结合 entry/exit handler，可构建完整的函数调用图和执行时间统计。