# kcmp.c

> 自动生成时间: 2025-10-25 14:15:38
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kcmp.c`

---

# kcmp.c 技术文档

## 1. 文件概述

`kcmp.c` 实现了 Linux 内核中的 `kcmp()` 系统调用，用于安全地比较两个进程（或任务）内部内核对象的相等性与相对顺序。该机制主要用于用户空间调试器、容器运行时或安全工具在不暴露真实内核指针的前提下，判断两个进程是否共享某些内核资源（如文件描述符表、内存空间、信号处理结构等）。为防止信息泄露，所有内核指针在比较前都会经过随机化混淆处理。

## 2. 核心功能

### 主要函数

- **`kcmp_ptr(void *v1, void *v2, enum kcmp_type type)`**  
  对两个内核对象指针进行混淆后比较，返回其相对顺序（0=相等，1=v1<v2，2=v1>v2）。

- **`kptr_obfuscate(long v, int type)`**  
  使用预生成的随机“cookie”对指针值进行混淆，确保用户空间无法推断真实内核地址。

- **`get_file_raw_ptr(struct task_struct *task, unsigned int idx)`**  
  在指定任务的文件描述符表中查找并返回对应索引的 `struct file*` 指针（不增加引用计数）。

- **`kcmp_lock()` / `kcmp_unlock()`**  
  安全地获取两个任务的 `exec_update_lock` 读锁，避免死锁（通过地址排序加锁）。

- **`kcmp_epoll_target()`**  
  特殊处理 `epoll` 目标文件的比较，支持通过 `kcmp_epoll_slot` 结构指定 epoll 实例中的目标文件。

- **`SYSCALL_DEFINE5(kcmp, ...)`**  
  `kcmp` 系统调用入口，根据传入的类型参数比较两个进程的指定内核对象。

- **`kcmp_cookies_init()`**  
  初始化阶段生成用于指针混淆的随机数（每个 `kcmp_type` 类型对应一组 cookie）。

### 主要数据结构

- **`cookies[KCMP_TYPES][2]`**  
  全局只读数组，存储每种比较类型对应的两个随机值：  
  - `cookies[type][0]`：用于 XOR 混淆  
  - `cookies[type][1]`：用于乘法混淆（强制为奇数，保证可逆性）

- **`enum kcmp_type`**（定义于 `<linux/kcmp.h>`）  
  定义支持的比较类型，包括：
  - `KCMP_FILE`：文件描述符指向的文件对象
  - `KCMP_VM`：内存描述符（mm_struct）
  - `KCMP_FILES`：文件描述符表（files_struct）
  - `KCMP_FS`：文件系统信息（fs_struct）
  - `KCMP_SIGHAND`：信号处理结构（sighand_struct）
  - `KCMP_IO`：I/O 上下文
  - `KCMP_SYSVSEM`：System V 信号量 undo 列表
  - `KCMP_EPOLL_TFD`：epoll 目标文件

## 3. 关键实现

### 指针混淆机制

为防止内核地址泄露，所有比较均不使用原始指针值，而是通过以下两步混淆：

1. **XOR 混淆**：`v ^ cookies[type][0]`  
   将指针映射到随机偏移的新地址空间。

2. **乘法混淆**：结果 × `cookies[type][1]`  
   其中乘数被强制设为奇数（`| 1` 且最高位为1），确保在模 2^64 下为可逆操作（因奇数与 2^n 互质），从而保证混淆后的值仍保持全序性，可用于安全排序。

### 安全访问控制

- 通过 `ptrace_may_access(..., PTRACE_MODE_READ_REALCREDS)` 检查调用者是否有权限读取目标进程信息。
- 使用 `exec_update_lock` 读锁保护进程关键结构（如 `mm`, `files` 等）在比较期间不被 `execve` 替换。
- 加锁时采用地址排序（`if (l2 > l1) swap(l1, l2)`）避免 AB-BA 死锁。

### epoll 特殊处理

`KCMP_EPOLL_TFD` 类型允许比较一个普通文件描述符与另一个进程 epoll 实例中注册的目标文件。通过 `kcmp_epoll_slot` 用户结构传入 epoll fd、目标 fd 和偏移，内核调用 `get_epoll_tfile_raw_ptr()` 获取 epoll 内部注册的文件指针进行比较。

### 错误处理

- 无效 PID：返回 `-ESRCH`
- 无权限：返回 `-EPERM`
- 无效 fd：返回 `-EBADF`
- 不支持的功能（如未配置 `CONFIG_EPOLL` 或 `CONFIG_SYSVIPC`）：返回 `-EOPNOTSUPP`
- 无效类型：返回 `-EINVAL`

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/kcmp.h>`：定义 `kcmp_type` 枚举和用户空间结构
  - `<linux/eventpoll.h>`：提供 `get_epoll_tfile_raw_ptr()`（需 `CONFIG_EPOLL`）
  - `<linux/fdtable.h>`、`<linux/file.h>`：文件描述符操作
  - `<linux/ptrace.h>`：权限检查
  - `<linux/random.h>`：初始化随机 cookie

- **配置依赖**：
  - `CONFIG_EPOLL`：启用 epoll 目标文件比较支持
  - `CONFIG_SYSVIPC`：启用 System V 信号量比较支持

- **内核子系统**：
  - 进程管理（`task_struct`, `mm_struct` 等）
  - 文件系统（`struct file`, fdtable）
  - 安全模块（ptrace 权限模型）

## 5. 使用场景

- **进程资源共享检测**：  
  容器运行时或安全沙箱可使用 `kcmp` 判断两个进程是否共享内存空间（`KCMP_VM`）、文件表（`KCMP_FILES`）等，用于隔离性验证。

- **调试器与分析工具**：  
  用户态调试器可通过比较文件描述符（`KCMP_FILE`）判断两个进程是否打开同一文件，或通过 `KCMP_EPOLL_TFD` 分析 epoll 事件源。

- **内核对象生命周期追踪**：  
  在不泄露内核地址的前提下，对内核对象进行唯一性标识和排序，用于性能分析或资源泄漏检测。

- **安全审计**：  
  验证进程间是否意外共享敏感资源（如信号处理结构、I/O 上下文），辅助安全策略实施。

> **注意**：由于指针混淆的存在，`kcmp` 的比较结果仅在同一系统启动周期内有效，且不能用于推断内核地址布局。