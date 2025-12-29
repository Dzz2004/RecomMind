# entry\syscall_user_dispatch.c

> 自动生成时间: 2025-10-25 13:20:47
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `entry\syscall_user_dispatch.c`

---

# entry/syscall_user_dispatch.c 技术文档

## 1. 文件概述

`entry/syscall_user_dispatch.c` 实现了 **系统调用用户分发（Syscall User Dispatch, SUD）** 机制，该机制允许用户空间程序通过 `prctl()` 系统调用配置一个“选择器”（selector），用于在特定条件下拦截或允许系统调用的执行。当系统调用指令指针位于指定区域之外且选择器状态为“阻塞”时，内核会回滚该系统调用并向进程发送 `SIGSYS` 信号，从而实现对系统调用的细粒度控制。此功能常用于沙箱、安全监控或调试场景。

## 2. 核心功能

### 主要函数

- `trigger_sigsys(struct pt_regs *regs)`  
  构造并强制发送 `SIGSYS` 信号，携带被拦截系统调用的详细信息（如地址、系统调用号、架构等）。

- `syscall_user_dispatch(struct pt_regs *regs)`  
  系统调用入口处的分发判断逻辑。根据当前指令指针位置和用户选择器状态决定是否拦截系统调用。

- `task_set_syscall_user_dispatch(struct task_struct *task, ...)`  
  为指定任务设置系统调用用户分发配置（开启/关闭、偏移、长度、选择器地址）。

- `set_syscall_user_dispatch(...)`  
  为当前任务设置系统调用用户分发配置的封装接口，供 `prctl()` 调用。

- `syscall_user_dispatch_get_config(...)`  
  通过 `ptrace` 获取指定任务的 SUD 配置。

- `syscall_user_dispatch_set_config(...)`  
  通过 `ptrace` 设置指定任务的 SUD 配置。

### 关键数据结构

- `struct syscall_user_dispatch`（定义在 `<linux/syscall_user_dispatch.h>`）  
  存储每个任务的 SUD 配置：
  - `selector`：指向用户空间选择器字节的指针
  - `offset` / `len`：允许直接执行系统调用的代码区域（[offset, offset+len)）
  - `on_dispatch`：标志位，表示当前是否处于分发拦截状态

- `struct ptrace_sud_config`  
  用于 `ptrace` 接口传递 SUD 配置的结构体，包含 `mode`、`offset`、`len` 和 `selector`。

## 3. 关键实现

### 系统调用拦截逻辑

1. **区域检查**：若当前指令指针（`instruction_pointer(regs)`）落在 `[offset, offset + len)` 范围内，则**允许**系统调用直接执行，不进行拦截。
2. **vdso 例外**：若系统调用来自 vDSO 中的 `sigreturn`（如 `arch_syscall_is_vdso_sigreturn()` 返回 true），则跳过拦截，避免干扰信号返回路径。
3. **选择器读取**：若配置了 `selector`，则从用户空间读取一个字节的状态值：
   - `SYSCALL_DISPATCH_FILTER_ALLOW`（0）：允许系统调用
   - `SYSCALL_DISPATCH_FILTER_BLOCK`（1）：触发拦截
   - 其他值：视为非法，发送 `SIGSYS`
4. **拦截处理**：
   - 设置 `on_dispatch = true`
   - 调用 `syscall_rollback()` 回滚系统调用（恢复寄存器状态）
   - 调用 `trigger_sigsys()` 发送 `SIGSYS` 信号

### 安全与健壮性设计

- **地址合法性校验**：在设置 `selector` 时使用 `access_ok(untagged_addr(selector), ...)`，确保地址可访问，并处理内存标记（如 ARM MTE）场景下调试器（tracer）与被调试进程（tracee）地址标记不一致的问题。
- **溢出防护**：检查 `offset + len <= offset` 防止整数溢出导致无效区域。
- **权限隔离**：`ptrace` 接口允许调试器配置其他进程的 SUD，但需具备相应权限。

### 信号信息构造

`trigger_sigsys()` 构造的 `siginfo_t` 包含：
- `si_signo = SIGSYS`
- `si_code = SYS_USER_DISPATCH`
- `si_call_addr`：触发系统调用的用户空间地址
- `si_syscall`：系统调用号
- `si_arch`：系统调用架构（如 x86_64、AArch64）

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/prctl.h>`：定义 `PR_SYS_DISPATCH_*` 常量
  - `<linux/syscall_user_dispatch.h>`：定义 `struct syscall_user_dispatch` 和相关常量
  - `<asm/syscall.h>`：提供 `syscall_get_arch()`、`syscall_get_nr()` 等架构相关接口
  - `"common.h"`：可能包含内核入口通用辅助函数
- **内核子系统**：
  - **调度器（sched）**：访问 `current` 任务结构
  - **信号子系统（signal）**：发送 `SIGSYS` 信号
  - **内存管理（uaccess）**：用户空间内存访问（`__get_user`, `access_ok`）
  - **ptrace**：支持调试器配置 SUD
  - **ELF**：可能用于架构识别（间接依赖）

## 5. 使用场景

- **沙箱环境**：限制应用只能在特定代码段发起系统调用，防止恶意代码绕过安全策略。
- **动态二进制插桩（DBI）**：工具（如 Valgrind、Intel Pin）可拦截系统调用进行分析或重定向。
- **安全监控**：监控程序可配置选择器为“阻塞”，在 `SIGSYS` 信号处理程序中记录或审查系统调用。
- **调试与测试**：通过 `ptrace` 动态启用/禁用 SUD，用于测试系统调用拦截逻辑。
- **W^X 策略增强**：结合代码段只读与 SUD，确保只有可信代码路径可发起系统调用。