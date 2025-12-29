# printk\internal.h

> 自动生成时间: 2025-10-25 15:31:50
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `printk\internal.h`

---

# `printk/internal.h` 技术文档

## 1. 文件概述

`printk/internal.h` 是 Linux 内核中 `printk` 子系统的内部头文件，定义了 `printk` 实现所需的内部数据结构、宏、函数声明和配置选项。该文件主要用于协调日志记录、控制台输出、环形缓冲区管理以及新旧控制台（legacy 与 nbcon）之间的调度逻辑，尤其在支持实时内核（`CONFIG_PREEMPT_RT`）和新型非阻塞控制台（`CONFIG_NBCON`）的场景下起关键作用。

## 2. 核心功能

### 宏定义
- `con_printk(lvl, con, fmt, ...)`：为特定控制台生成带上下文信息（如类型、名称、索引）的日志前缀。
- `force_legacy_kthread()`：在 `PREEMPT_RT` 下强制使用专用 legacy 打印线程。
- `printk_safe_enter_irqsave(flags)` / `printk_safe_exit_irqrestore(flags)`：提供 IRQ 安全的 printk 上下文入口/出口。
- `PRINTK_PREFIX_MAX`、`PRINTK_MESSAGE_MAX`、`PRINTKRB_RECORD_MAX`：定义日志记录格式和缓冲区大小限制。

### 枚举与标志
- `enum printk_info_flags`：
  - `LOG_NEWLINE`：表示日志行以换行符结尾。
  - `LOG_CONT`：表示该日志是连续行的片段。
- `enum nbcon_prio`：控制台优先级（如 `NBCON_PRIO_NORMAL`、`NBCON_PRIO_EMERGENCY`）。

### 数据结构
- `struct console_flush_type`：描述当前上下文可用的控制台刷新策略，包含四种方式：
  - `nbcon_atomic`：使用原子写回调直接刷新。
  - `nbcon_offload`：将刷新任务卸载到 nbcon 打印线程。
  - `legacy_direct`：在当前上下文中执行 legacy 控制台循环。
  - `legacy_offload`：将 legacy 循环卸载到中断或专用线程。

### 关键函数声明（仅在 `CONFIG_PRINTK` 启用时有效）
- **日志存储**：
  - `vprintk_store()`：将格式化日志存入 printk 环形缓冲区。
  - `vprintk_default()` / `vprintk_deferred()`：默认和延迟的 printk 后端。
- **安全上下文管理**：
  - `__printk_safe_enter()` / `__printk_safe_exit()`：进入/退出安全打印上下文。
- **控制台管理**：
  - `console_is_usable()`：判断控制台在当前上下文是否可用。
  - `defer_console_output()`：触发控制台输出延迟处理。
  - `is_printk_legacy_deferred()`：检查 legacy 输出是否被延迟。
- **nbcon（Non-Blocking Console）支持**：
  - `nbcon_alloc()` / `nbcon_free()`：分配/释放 nbcon 资源。
  - `nbcon_seq_read()` / `nbcon_seq_force()`：管理控制台序列号。
  - `nbcon_kthread_create()` / `nbcon_kthread_stop()` / `nbcon_kthread_wake()`：管理 nbcon 打印线程。
  - `nbcon_legacy_emit_next_record()`：在 legacy 模式下发射下一条记录。
- **系统控制**（需 `CONFIG_SYSCTL`）：
  - `printk_sysctl_init()`：初始化 printk 相关 sysctl。
  - `devkmsg_sysctl_set_loglvl()`：通过 sysctl 设置日志级别。

### 全局变量
- `prb`：指向 printk 环形缓冲区的指针。
- `printk_kthreads_running`：指示 printk 打印线程是否已启动。
- `have_boot_console` / `have_nbcon_console` / `have_legacy_console`：标识系统中存在的控制台类型。
- `legacy_allow_panic_sync`：允许在 panic 时同步执行 legacy 控制台输出。

## 3. 关键实现

### 控制台可用性判断
`console_is_usable()` 综合考虑控制台状态标志（如 `CON_ENABLED`、`CON_SUSPENDED`）、回调函数存在性（`write` 或 `write_atomic`）、CPU 在线状态及 `CON_ANYTIME` 标志，决定控制台是否可在当前上下文使用。

### nbcon 与 legacy 协同
- 在非 panic 场景下，若启用 `CONFIG_PREEMPT_RT`，则强制使用 legacy 打印线程以避免延迟。
- nbcon 控制台支持两种输出模式：原子上下文（`write_atomic`）和线程上下文（`write_thread`）。
- `printk_get_console_flush_type()` 根据当前 nbcon 优先级、控制台类型和线程运行状态，动态选择最优刷新策略。

### 安全打印上下文
通过 `printk_safe_enter_irqsave()` 和 `printk_safe_exit_irqrestore()` 封装本地中断屏蔽与 printk 安全状态切换，确保在中断或 NMI 等敏感上下文中安全记录日志。

### 条件编译支持
- 当 `CONFIG_PRINTK` 未启用时，所有 printk 相关函数退化为空操作或返回常量，但保留 `console_sem` 和基础控制台函数以维持兼容性。
- sysctl 支持仅在 `CONFIG_PRINTK && CONFIG_SYSCTL` 同时启用时编译。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/console.h>`：定义 `struct console` 及控制台标志。
  - `<linux/percpu.h>`：支持 per-CPU 数据访问。
  - `<linux/types.h>`：基础类型定义。
- **配置依赖**：
  - `CONFIG_PRINTK`：启用完整 printk 功能。
  - `CONFIG_NBCON`：启用非阻塞控制台支持（隐含在 nbcon 函数中）。
  - `CONFIG_PREEMPT_RT`：影响 legacy 打印线程行为。
  - `CONFIG_SYSCTL`：启用 printk sysctl 接口。
- **模块交互**：
  - 与 `printk.c`、`printk_ringbuffer.c` 紧密协作，实现日志存储与输出。
  - 与控制台驱动（如 `tty`, `earlycon`）通过 `console` 结构体交互。
  - 依赖 RCU 机制（`rcuwait`）实现 nbcon 线程唤醒同步。

## 5. 使用场景

- **内核日志记录**：所有 `printk()` 调用最终通过此文件定义的后端函数（如 `vprintk_store`）写入环形缓冲区。
- **控制台输出调度**：在 `console_unlock()` 等路径中，根据 `printk_get_console_flush_type()` 决定如何刷新日志到控制台。
- **实时系统支持**：在 `PREEMPT_RT` 内核中，确保 printk 不阻塞关键路径，通过专用线程处理 legacy 输出。
- **panic 处理**：在系统崩溃时，优先使用 nbcon 原子输出，必要时 fallback 到 legacy 同步输出。
- **动态日志级别调整**：通过 `/proc/sys/kernel/printk` 等接口，调用 `devkmsg_sysctl_set_loglvl()` 修改运行时日志级别。
- **引导阶段日志**：区分 `boot console` 与常规控制台，确保早期日志正确路由。