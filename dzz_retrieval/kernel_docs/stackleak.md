# stackleak.c

> 自动生成时间: 2025-10-25 16:27:07
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `stackleak.c`

---

# stackleak.c 技术文档

## 1. 文件概述

`stackleak.c` 是 Linux 内核中实现 **STACKLEAK** 安全特性的核心源文件。该特性源自 grsecurity/PaX 项目，主要功能是在内核返回用户空间前，将当前任务已使用的内核栈区域用特定“毒值”（poison value）填充。此举可显著降低内核栈信息泄露漏洞的危害，并有效防御部分基于未初始化栈变量的攻击。

## 2. 核心功能

### 主要函数

- **`stackleak_erase(void)`**  
  通用接口，自动判断当前是否运行在任务栈上，并调用 `__stackleak_erase()` 执行栈擦除。

- **`stackleak_erase_on_task_stack(void)`**  
  显式指定当前运行在任务栈上，调用 `__stackleak_erase(true)`。

- **`stackleak_erase_off_task_stack(void)`**  
  显式指定当前运行在非任务栈（如入口跳板栈）上，调用 `__stackleak_erase(false)`。

- **`stackleak_track_stack(void)`**  
  跟踪当前栈指针位置，动态更新 `current->lowest_stack`，记录本次系统调用期间栈使用的最低地址（即最深位置）。

- **`__stackleak_erase(bool on_task_stack)`**  
  核心擦除逻辑：根据 `on_task_stack` 参数确定擦除范围，并调用 `__stackleak_poison()` 填充毒值。

- **`__stackleak_poison(unsigned long erase_low, unsigned long erase_high, unsigned long poison)`**  
  内联函数，从 `erase_low` 到 `erase_high` 的内存区域以 `unsigned long` 为单位写入 `STACKLEAK_POISON`。

### 数据结构与变量

- **`stack_erasing_bypass`**  
  静态跳转键（`static_key`），用于在运行时动态启用/禁用栈擦除功能（仅当 `CONFIG_STACKLEAK_RUNTIME_DISABLE=y` 时存在）。

- **`current->lowest_stack`**  
  每个任务的 `task_struct` 中维护的字段，记录自上次擦除以来栈使用的最低地址。

- **`current->prev_lowest_stack`**（仅当 `CONFIG_STACKLEAK_METRICS=y`）  
  用于性能度量，保存上一次擦除的起始地址。

## 3. 关键实现

### 栈擦除范围确定
- **擦除起点 (`erase_low`)**：通过 `stackleak_find_top_of_poison()` 从 `task_stack_low` 向上搜索，找到第一个非毒值地址，即上次擦除后首次使用的栈位置。
- **擦除终点 (`erase_high`)**：
  - 若在任务栈上执行（`on_task_stack == true`），终点为当前栈指针 `current_stack_pointer`，避免覆盖当前函数栈帧。
  - 若在其他栈上执行（如中断/系统调用入口栈），终点为任务栈顶 `task_stack_high`，可安全擦除整个任务栈未使用区域。

### 运行时动态开关
- 当配置 `CONFIG_STACKLEAK_RUNTIME_DISABLE` 时，提供 `/proc/sys/kernel/stack_erasing` sysctl 接口。
- 通过 `static_branch_unlikely(&stack_erasing_bypass)` 实现零开销判断：默认编译为直接跳过擦除，仅在运行时启用时才执行。

### 栈使用跟踪机制
- `stackleak_track_stack()` 在编译器插桩（由 GCC plugin 实现）调用下，定期更新 `current->lowest_stack`。
- 要求 `CONFIG_STACKLEAK_TRACK_MIN_SIZE <= STACKLEAK_SEARCH_DEPTH`，确保毒值搜索不会越界。

### 安全与性能优化
- 所有擦除函数标记为 `noinstr`，禁止被 ftrace 等调试机制插桩，防止干扰关键路径。
- `stackleak_track_stack()` 使用 `__no_caller_saved_registers`，避免编译器生成额外寄存器保存/恢复代码，减少开销。

## 4. 依赖关系

- **编译依赖**：
  - 必须启用 `CONFIG_STACKLEAK`。
  - 依赖 GCC plugin（`stackleak_plugin.c`）在编译时插入 `stackleak_track_stack()` 调用。
- **头文件依赖**：
  - `<linux/stackleak.h>`：定义 `STACKLEAK_POISON`、栈边界宏及任务结构体扩展字段。
  - `<linux/kprobes.h>`：提供 `noinstr` 等属性定义。
- **可选依赖**：
  - `CONFIG_STACKLEAK_RUNTIME_DISABLE`：启用运行时开关功能。
  - `CONFIG_SYSCTL`：提供 sysctl 控制接口。
  - `CONFIG_STACKLEAK_METRICS`：启用栈使用深度度量。

## 5. 使用场景

- **系统调用返回路径**：在 `syscall_exit_to_user_mode()` 等路径中调用 `stackleak_erase()`，清理本次系统调用使用的内核栈。
- **中断/异常返回用户空间前**：当从中断上下文返回用户态时，若使用独立栈（如 entry trampoline stack），调用 `stackleak_erase_off_task_stack()`。
- **内核线程退出**：在切换回用户任务前擦除内核栈残留数据。
- **安全加固场景**：部署在高安全要求环境中，防止栈信息泄露（如通过侧信道或内存泄露漏洞）暴露内核地址、敏感数据或控制流信息。