# seccomp.c

> 自动生成时间: 2025-10-25 16:23:11
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `seccomp.c`

---

# seccomp.c 技术文档

## 文件概述

`seccomp.c` 是 Linux 内核中实现安全计算（Secure Computing，简称 seccomp）机制的核心文件。该机制用于限制进程可执行的系统调用，从而提升系统安全性。文件支持两种主要模式：

- **Mode 1（严格模式）**：仅允许 `read`、`write`、`exit` 和 `sigreturn` 四个系统调用。
- **Mode 2（过滤器模式）**：允许用户通过 Berkeley Packet Filter（BPF）形式定义自定义的系统调用过滤规则。

此外，该文件还实现了 **用户空间通知（user-space notification）** 功能，允许内核在遇到特定系统调用时暂停执行并通知用户态监听器进行处理。

## 核心功能

### 主要数据结构

- **`struct seccomp_filter`**  
  表示一个 seccomp BPF 过滤器实例，包含：
  - 引用计数（`refs` 和 `users`）
  - BPF 程序指针（`prog`）
  - 通知相关结构（`notif`、`notify_lock`、`wqh`）
  - 动作缓存（`cache`）
  - 指向前一个过滤器的指针（`prev`），构成过滤器链

- **`struct notification`**  
  管理用户空间通知的容器，包含请求计数器、标志位、下一个通知 ID 和通知链表。

- **`struct seccomp_knotif`**  
  表示一个待处理的用户通知请求，记录触发通知的任务、系统调用数据、状态（INIT/SENT/REPLIED）、返回值及完成信号量。

- **`struct seccomp_kaddfd`**  
  用于 `SECCOMP_IOCTL_NOTIF_ADDFD` 操作，允许监听器向目标进程注入文件描述符。

- **`struct action_cache`**（条件编译）  
  针对原生和兼容架构的系统调用动作缓存，用于快速判断是否允许某系统调用，避免重复执行 BPF 程序。

### 关键枚举与常量

- **`enum notify_state`**：通知状态机（INIT → SENT → REPLIED）
- **`SECCOMP_MODE_DEAD`**：内部使用的特殊模式，表示进程已进入不可恢复的 seccomp 状态
- **`MAX_INSNS_PER_PATH`**：限制 BPF 指令路径总长度不超过 256KB，防止资源耗尽

### 特殊兼容性处理

- **`SECCOMP_IOCTL_NOTIF_ID_VALID_WRONG_DIR`**：为兼容早期错误的 ioctl 命令方向而保留的旧定义

## 关键实现

### 过滤器生命周期管理

- 使用双重引用计数机制：
  - `refs`：控制对象内存释放（包括任务引用、依赖过滤器、通知监听器）
  - `users`：跟踪直接或间接使用该过滤器的任务数量，用于判断是否还能被新任务继承
- 过滤器一旦附加到任务，除引用计数外不可修改，确保并发安全

### 用户空间通知机制

- 当 BPF 程序返回 `SECCOMP_RET_USER_NOTIF` 时，内核创建 `seccomp_knotif` 并加入通知队列
- 用户态通过文件描述符读取通知，内核将状态置为 `SENT`
- 监听器通过 `ioctl` 回复结果，状态转为 `REPLIED`，触发 `completion` 使原任务继续执行
- 支持通过 `SECCOMP_IOCTL_NOTIF_ADDFD` 向目标进程注入文件描述符

### 动作缓存优化（`action_cache`）

- 在支持 `SECCOMP_ARCH_NATIVE` 的架构上，为每个系统调用编号维护一个“始终允许”位图
- 若缓存命中（即该系统调用在所有路径下均返回 `ALLOW`），可跳过 BPF 执行，提升性能
- 分别处理原生（native）和兼容（compat）系统调用空间

### 安全与资源限制

- 限制 BPF 指令总路径长度，防止深度嵌套或循环导致 DoS
- 通知机制使用互斥锁（`notify_lock`）和完成量（`completion`）保证状态一致性
- 支持 `wait_killable_recv` 选项，使等待通知回复的进程可被信号中断

## 依赖关系

- **BPF 子系统**：依赖 `linux/filter.h` 提供的 socket filter/BPF 执行引擎
- **进程管理**：与 `sched.h`、`task_struct` 紧密集成，管理 per-task seccomp 状态
- **文件系统与 fd 管理**：通过 `file.h`、`uaccess.h` 实现跨进程 fd 注入
- **审计与日志**：集成 `audit.h` 支持 seccomp 事件审计
- **架构相关代码**：通过 `asm/syscall.h` 获取系统调用号和参数
- **能力机制**：依赖 `capability.h` 检查特权操作权限
- **内存管理**：使用 `slab.h` 分配过滤器和通知结构

## 使用场景

1. **容器安全**：Docker、LXC 等容器运行时使用 seccomp 过滤器限制容器内进程的系统调用，防止逃逸
2. **沙箱应用**：Chromium、Firefox 等浏览器使用 seccomp 构建渲染进程沙箱
3. **最小权限原则**：特权服务（如 systemd、sshd）在初始化后启用 seccomp 以减少攻击面
4. **动态策略执行**：通过 `SECCOMP_RET_USER_NOTIF` 实现用户态代理系统调用（如 ptrace 替代方案）
5. **安全审计**：结合 `SECCOMP_RET_LOG` 记录所有被拦截或允许的系统调用行为
6. **系统加固**：在不可信环境中运行程序时，强制限制其系统调用能力