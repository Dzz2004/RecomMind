# capability.c

> 自动生成时间: 2025-10-25 12:39:00
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `capability.c`

---

# capability.c 技术文档

## 1. 文件概述

`capability.c` 是 Linux 内核中实现 POSIX 能力（Capabilities）机制的核心文件，位于 `kernel/` 目录下。该文件主要负责提供用户空间与内核之间进行能力获取（`capget`）和设置（`capset`）的系统调用接口，并维护能力模型的版本兼容性、安全策略检查以及与 LSM（Linux Security Module）框架的集成。能力机制允许将传统超级用户权限细分为多个独立的特权单元，从而实现最小权限原则。

## 2. 核心功能

### 主要全局变量
- `file_caps_enabled`：控制是否启用文件能力（File Capabilities）功能的全局开关，默认启用。可通过内核启动参数 `no_file_caps` 禁用。

### 主要函数
- **`cap_validate_magic()`**：验证用户传入的能力结构体版本号，支持 v1、v2、v3 版本，并对旧版本发出警告。
- **`cap_get_target_pid()`**：安全地获取指定进程（通过 PID）的有效（Effective）、可继承（Inheritable）和允许（Permitted）能力集。
- **`sys_capget()`**：`capget(2)` 系统调用的实现，用于查询指定进程的能力集。
- **`sys_capset()`**：`capset(2)` 系统调用的实现，用于设置当前进程的能力集（仅限自身）。
- **`mk_kernel_cap()`**：将用户空间传入的高低 32 位能力值组合成内核内部的 `kernel_cap_t` 类型。
- **`has_ns_capability()`**（截断）：检查指定任务在给定用户命名空间中是否拥有某项能力（函数体在提供的代码中被截断）。

### 辅助函数
- `warn_legacy_capability_use()`：对使用 v1（32 位）能力接口的应用程序发出一次性警告。
- `warn_deprecated_v2()`：对使用已弃用的 v2 能力接口的应用程序发出一次性警告。

## 3. 关键实现

### 能力版本兼容性处理
- 支持三种能力结构版本：
  - **v1 (`_LINUX_CAPABILITY_VERSION_1`)**：仅支持 32 位能力（旧版），调用时触发 `warn_legacy_capability_use()`。
  - **v2 (`_LINUX_CAPABILITY_VERSION_2`)**：支持 64 位能力但存在安全风险，调用时触发 `warn_deprecated_v2()`。
  - **v3 (`_LINUX_CAPABILITY_VERSION_3`)**：当前推荐版本，功能等同于 v2 但通过头文件变更避免误用。
- 对于无效版本，内核会尝试将当前支持的版本号写回用户空间并返回 `-EINVAL`。

### 能力数据传输格式
- 用户空间使用两个 `__user_cap_data_struct` 结构体（`kdata[2]`）来表示 64 位能力值：
  - `kdata[0]` 存储低 32 位
  - `kdata[1]` 存储高 32 位
- 在 `capget` 中，内核能力值被拆分为高低 32 位写入用户缓冲区；在 `capset` 中则反向组合。
- **向后兼容策略**：当用户空间请求的版本只支持 32 位（`tocopy = 1`）时，内核会静默丢弃高 32 位能力，避免旧版 `libcap` 应用崩溃。

### 安全限制
- **`capset` 限制**：仅允许进程修改自身能力（`pid` 必须为 0 或当前进程 PID），修改其他进程能力的功能已被移除。
- **能力设置规则**（由 LSM 实现，如 `security_capset`）：
  - 新的 **可继承集（I）** 和 **允许集（P）** 只能是旧允许集的子集。
  - 新的 **有效集（E）** 必须是新允许集的子集。
- 使用 `prepare_creds()` / `commit_creds()` 机制安全地更新进程凭证（credentials），并在失败时通过 `abort_creds()` 回滚。

### 并发与锁机制
- 获取**其他进程**能力时，使用 `rcu_read_lock()` 保护对进程链表的访问（通过 `find_task_by_vpid()`）。
- 获取**当前进程**能力时无需加锁，因为能力修改是原子的（通过凭证替换）。

### 审计与日志
- `capset` 成功时调用 `audit_log_capset()` 记录能力变更事件，用于安全审计。
- 对旧版能力接口的使用通过 `pr_info_once()` 发出一次性内核日志警告。

## 4. 依赖关系

- **LSM 框架**：通过 `security_capget()` 和 `security_capset()` 钩子与安全模块（如 SELinux、AppArmor）交互，实际的能力检查和设置策略由 LSM 实现。
- **凭证子系统**：依赖 `cred` 结构体管理进程权限，使用 `prepare_creds()`、`commit_creds()` 等函数安全更新。
- **命名空间**：支持用户命名空间（`user_namespace.h`），能力检查与命名空间隔离相关（体现在 `has_ns_capability` 等函数中）。
- **审计子系统**：通过 `audit.h` 提供能力变更的审计日志。
- **系统调用接口**：通过 `SYSCALL_DEFINE2` 定义 `capget` 和 `capset` 系统调用。
- **用户空间访问**：使用 `uaccess.h` 中的 `copy_to_user()` 和 `copy_from_user()` 安全传输数据。

## 5. 使用场景

- **容器与沙箱**：容器运行时（如 Docker、runc）通过 `capset` 限制容器内进程的能力集，实现权限隔离。
- **特权程序降权**：需要临时提升权限的程序（如 `ping` 使用 `CAP_NET_RAW`）可在执行关键操作后通过 `capset` 丢弃多余能力。
- **安全策略实施**：系统管理员或安全模块通过限制进程能力，遵循最小权限原则，减少攻击面。
- **调试与监控**：安全工具（如 `getpcaps`）通过 `capget` 查询进程当前能力状态，用于诊断或合规检查。
- **文件能力加载**：虽然本文件不直接处理文件能力，但 `file_caps_enabled` 开关控制是否启用基于文件扩展属性（xattr）的能力加载机制（由 `fs/` 子系统实现）。