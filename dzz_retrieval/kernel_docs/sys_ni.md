# sys_ni.c

> 自动生成时间: 2025-10-25 16:31:37
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `sys_ni.c`

---

# sys_ni.c 技术文档

## 1. 文件概述

`sys_ni.c` 是 Linux 内核中用于处理**未实现系统调用（Not Implemented Syscall）**的核心文件。当某个系统调用在当前架构或配置下未被实现时，内核会将其重定向到 `sys_ni_syscall()` 函数，该函数统一返回 `-ENOSYS` 错误码（表示“Function not implemented”）。此机制确保了即使某些系统调用未被支持，用户空间程序调用它们时也不会导致内核崩溃，而是获得标准错误响应。

此外，该文件通过宏 `COND_SYSCALL` 和 `COND_SYSCALL_COMPAT` 为大量系统调用提供**弱符号（weak symbol）定义**，使得链接器在找不到具体实现时自动链接到 `sys_ni_syscall`，从而实现“按需启用、默认未实现”的灵活架构。

## 2. 核心功能

### 主要函数
- **`sys_ni_syscall(void)`**  
  所有未实现系统调用的默认入口点，返回 `-ENOSYS`。

### 关键宏定义
- **`COND_SYSCALL(name)`**  
  展开为 `cond_syscall(sys_##name)`，为指定系统调用名生成弱符号引用。
- **`COND_SYSCALL_COMPAT(name)`**  
  展开为 `cond_syscall(compat_sys_##name)`，为 32 位兼容模式下的系统调用生成弱符号引用。
- **`cond_syscall()`**（由链接器脚本或汇编支持）  
  实际由链接器处理，将未定义的系统调用符号指向 `sys_ni_syscall`。

## 3. 关键实现

### 未实现系统调用的统一处理
- 所有未在内核中实际实现的系统调用最终都会跳转到 `sys_ni_syscall()`，该函数仅返回 `-ENOSYS`，实现简洁且安全。
- 通过 `asmlinkage` 修饰符确保函数使用正确的调用约定（通常为栈传参），与系统调用入口一致。

### 弱符号机制
- 使用 `COND_SYSCALL(name)` 宏为每个可能未实现的系统调用生成一个弱符号声明。
- 在链接阶段，若某系统调用（如 `sys_io_setup`）有实际实现，则链接器使用其实现；若无，则自动绑定到 `sys_ni_syscall`。
- 此机制避免了为每个架构手动维护大量空 stub 函数，提高了代码可维护性。

### 兼容性支持
- `COND_SYSCALL_COMPAT` 专门处理 32 位兼容层（如 x86_64 上运行 32 位程序）的系统调用，确保兼容模式下未实现的调用同样返回 `-ENOSYS`。
- 支持架构特定的 syscall wrapper（通过 `CONFIG_ARCH_HAS_SYSCALL_WRAPPER`），允许某些架构自定义 `COND_SYSCALL` 行为。

### 系统调用列表组织
- 列表严格遵循 `include/uapi/asm-generic/unistd.h` 中的顺序，便于维护一致性。
- 包含：
  - 通用系统调用（如 `io_uring_*`, `epoll_*`, `timerfd_*`）
  - 架构特定调用（如 x86 的 `vm86`、s390 的 `s390_ipc`）
  - 已废弃但仍被某些架构需要的调用（如 `epoll_create`, `inotify_init`）
  - 条件编译调用（如 `__ARCH_WANT_SYS_CLONE3` 控制的 `clone3`）

## 4. 依赖关系

### 头文件依赖
- `<linux/linkage.h>`：提供 `asmlinkage` 宏定义
- `<linux/errno.h>`：提供 `-ENOSYS` 错误码
- `<asm/unistd.h>`：包含架构相关的系统调用编号定义
- `<asm/syscall_wrapper.h>`（条件包含）：允许架构覆盖 `COND_SYSCALL` 宏

### 内核构建系统依赖
- 依赖链接器脚本（如 `vmlinux.lds`）中的 `__cond_syscall` 段处理弱符号
- 与 `arch/*/kernel/syscall_table.c` 或等效文件协同工作，后者提供实际系统调用表

### 配置选项依赖
- `CONFIG_ARCH_HAS_SYSCALL_WRAPPER`：控制是否使用架构自定义 syscall wrapper
- 各种 `CONFIG_*` 选项（如 `CONFIG_MMU`、`CONFIG_FANOTIFY`）间接影响哪些 `COND_SYSCALL` 条目生效

## 5. 使用场景

### 内核构建时
- 在编译内核时，若某系统调用未被任何源文件实现（例如因配置选项关闭或架构不支持），链接器自动将其绑定到 `sys_ni_syscall`。
- 避免链接错误，同时保证系统调用表完整性。

### 用户空间调用未实现 syscall 时
- 用户程序调用未实现的系统调用（如在不支持 `landlock` 的内核上调用 `landlock_create_ruleset`）。
- 内核安全返回 `-ENOSYS`，程序可据此进行功能检测或降级处理。

### 架构移植与兼容层
- 新架构移植时，无需立即实现所有系统调用，未实现部分自动返回 `-ENOSYS`。
- 32/64 位兼容层（如 x86_64 的 compat 模式）中，未实现的 32 位专用 syscall 同样得到正确处理。

### 废弃 syscall 的平滑过渡
- 对于已废弃但仍保留在 uAPI 中的系统调用（如 `epoll_create`），通过此机制确保旧程序在新内核上仍能获得明确错误而非崩溃。