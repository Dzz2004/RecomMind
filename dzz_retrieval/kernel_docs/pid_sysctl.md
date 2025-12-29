# pid_sysctl.h

> 自动生成时间: 2025-10-25 15:17:36
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `pid_sysctl.h`

---

# `pid_sysctl.h` 技术文档

## 1. 文件概述

`pid_sysctl.h` 是 Linux 内核中用于定义与 PID 命名空间（`pid_namespace`）相关的系统控制（sysctl）接口的头文件。其核心功能是提供对 `memfd_noexec` 系统策略的运行时配置支持，该策略用于控制通过 `memfd_create()` 创建的内存文件是否允许执行代码。该配置具有层级继承语义：子 PID 命名空间的策略不能比其父命名空间更宽松，以确保安全策略的向下兼容性和强制性。

## 2. 核心功能

### 函数

- **`pid_mfd_noexec_dointvec_minmax`**  
  自定义的 sysctl 处理函数，用于读写 `memfd_noexec` 策略值。在写入时执行权限检查和策略继承约束验证。

- **`register_pid_ns_sysctl_table_vm`**  
  内联函数，用于向内核 sysctl 子系统注册 `vm.memfd_noexec` 控制项（仅在 `CONFIG_SYSCTL` 和 `CONFIG_MEMFD_CREATE` 同时启用时有效）。

### 数据结构

- **`pid_ns_ctl_table_vm`**  
  `ctl_table` 类型的静态数组，定义了 `vm.memfd_noexec` sysctl 条目，包括其名称、数据指针、访问权限、处理函数及取值范围（0 到 2）。

## 3. 关键实现

- **权限控制**：  
  在写入 `memfd_noexec` 值时，调用 `ns_capable(ns->user_ns, CAP_SYS_ADMIN)` 检查当前任务是否在对应用户命名空间中拥有 `CAP_SYS_ADMIN` 能力，防止非特权用户修改安全策略。

- **策略继承约束**：  
  通过 `pidns_memfd_noexec_scope(ns->parent)` 获取父 PID 命名空间的策略值 `parent_scope`，并确保当前命名空间的策略值 `scope` 不小于父策略（即不能更宽松）。实际写入前使用 `max(READ_ONCE(ns->memfd_noexec_scope), parent_scope)` 保证该约束。

- **原子读写**：  
  使用 `READ_ONCE()` 和 `WRITE_ONCE()` 对 `ns->memfd_noexec_scope` 进行访问，确保在并发环境下内存访问的可见性和顺序性。

- **sysctl 注册**：  
  通过 `register_sysctl("vm", pid_ns_ctl_table_vm)` 将控制项注册到 `/proc/sys/vm/memfd_noexec` 路径下，供用户空间通过标准 sysctl 接口访问。

- **条件编译**：  
  整个功能仅在 `CONFIG_SYSCTL`（启用 sysctl 支持）和 `CONFIG_MEMFD_CREATE`（启用 memfd_create 系统调用）同时配置时编译，否则 `register_pid_ns_sysctl_table_vm` 为空内联函数，避免代码膨胀。

## 4. 依赖关系

- **`<linux/pid_namespace.h>`**：  
  提供 `struct pid_namespace` 定义及辅助函数如 `task_active_pid_ns()` 和 `pidns_memfd_noexec_scope()`。

- **`CONFIG_SYSCTL`**：  
  内核配置选项，启用 sysctl 框架支持，提供 `register_sysctl`、`proc_dointvec_minmax` 等接口。

- **`CONFIG_MEMFD_CREATE`**：  
  内核配置选项，启用 `memfd_create()` 系统调用及相关功能（如 `memfd_noexec_scope` 字段）。

- **能力子系统（Capabilities）**：  
  依赖 `ns_capable()` 进行命名空间感知的权限检查。

## 5. 使用场景

- **安全策略配置**：  
  系统管理员或容器运行时可通过写入 `/proc/sys/vm/memfd_noexec` 设置当前 PID 命名空间中 `memfd` 文件的执行限制级别（0=允许执行，1=禁止执行但可覆盖，2=严格禁止执行），用于防御基于内存文件的代码注入攻击。

- **容器隔离**：  
  在容器化环境中，不同容器运行在独立的 PID 命名空间中。父命名空间（如宿主机）可设置较严格的 `memfd_noexec` 策略，子容器无法降低该策略级别，从而实现自上而下的安全策略强制。

- **运行时动态调整**：  
  允许在系统运行期间动态调整 `memfd` 执行策略，无需重启或重新加载内核模块，提升系统灵活性与安全性。