# bpf\bpf_lsm.c

> 自动生成时间: 2025-10-25 12:01:09
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\bpf_lsm.c`

---

# `bpf/bpf_lsm.c` 技术文档

## 1. 文件概述

`bpf/bpf_lsm.c` 是 Linux 内核中实现 **BPF LSM（Linux Security Module）** 支持的核心文件。该文件为 BPF 程序提供了一种机制，使其能够挂载（attach）到 LSM 安全钩子上，在系统关键安全决策点执行自定义策略。通过将 BPF 程序与 LSM 钩子集成，用户可以在不修改内核代码或加载传统 LSM 模块的情况下，动态实现细粒度的安全控制（如访问控制、审计、完整性度量等）。

该文件主要完成以下任务：
- 自动生成所有可被 BPF 附加的 LSM 钩子桩函数（stub functions）
- 定义哪些 LSM 钩子被禁用（不可附加 BPF 程序）
- 实现 BPF 程序在 LSM 钩子上的验证逻辑
- 提供 LSM BPF 程序可调用的辅助函数（helpers）
- 支持基于 cgroup 的 LSM BPF 程序上下文查找

## 2. 核心功能

### 主要数据结构

- **`bpf_lsm_hooks`**：BTF ID 集合，包含所有允许 BPF 程序附加的 LSM 钩子对应的桩函数。
- **`bpf_lsm_disabled_hooks`**：BTF ID 集合，列出明确禁止 BPF 程序附加的 LSM 钩子（如涉及安全敏感或语义不兼容的钩子）。
- **`bpf_lsm_current_hooks`**：BTF ID 集合，标识那些应始终在 `current` 进程的 cgroup 上下文中执行的 LSM 钩子（即使函数签名不包含 cgroup 参数）。
- **`bpf_lsm_locked_sockopt_hooks` / `bpf_lsm_unlocked_sockopt_hooks`**：分别标识在 socket 已加锁或未加锁但处于初始化阶段时可安全调用 `bpf_{get,set}sockopt` 的网络 LSM 钩子。

### 主要函数

- **`bpf_lsm_verify_prog()`**：验证 BPF LSM 程序的合法性，包括许可证（必须为 GPL 兼容）、附加目标是否在允许列表中且不在禁用列表中。
- **`bpf_lsm_func_proto()`**：为 BPF LSM 程序提供可用的辅助函数原型（`bpf_func_proto`），根据程序类型和附加钩子动态返回支持的 helpers。
- **`bpf_lsm_find_cgroup_shim()`**（条件编译）：为 cgroup 类型的 LSM BPF 程序选择合适的运行时 shim 函数（`__cgroup_bpf_run_lsm_*`），依据附加钩子的第一个参数类型（如 socket、sock 或其他）决定执行上下文。
- **辅助函数实现**：
  - `bpf_bprm_opts_set()`：允许 LSM BPF 程序设置 `linux_binprm` 的 `secureexec` 标志。
  - `bpf_ima_inode_hash()` / `bpf_ima_file_hash()`：封装 IMA（Integrity Measurement Architecture）接口，用于获取 inode 或文件的哈希值（可能睡眠）。
  - `bpf_get_attach_cookie()`：获取附加到当前 LSM 钩子的 BPF 程序的 cookie 值。

## 3. 关键实现

### 自动生成 LSM 桩函数
通过两次包含 `linux/lsm_hook_defs.h` 宏定义文件，结合 `LSM_HOOK` 宏：
1. 第一次展开生成所有 `bpf_lsm_<hook_name>()` 桩函数，函数体仅返回默认值（如 0 或 -ENOSYS）。
2. 第二次展开生成 `bpf_lsm_hooks` BTF ID 集合，收集所有桩函数的 BTF ID，用于后续验证和查找。

### 钩子分类管理
使用 BTF ID 集合对 LSM 钩子进行精细分类：
- **禁用钩子**：如 `vm_enough_memory`、`inode_getsecurity` 等，因语义冲突、性能敏感或安全原因禁止 BPF 附加。
- **cgroup 上下文钩子**：如 `sk_alloc_security`，虽无 cgroup 参数，但需在 `current` cgroup 中执行。
- **socket 选项钩子**：区分 socket 是否已加锁，以决定是否允许调用 `bpf_{get,set}sockopt`。

### BPF 辅助函数支持
- **上下文感知**：`bpf_lsm_func_proto()` 根据 `prog->expected_attach_type`（如 `BPF_LSM_CGROUP`）和 `attach_btf_id` 动态启用特定 helpers。
- **安全限制**：如 `bpf_ima_*_hash` 仅允许在可睡眠的 LSM 钩子中使用（通过 `bpf_lsm_is_sleepable_hook()` 判断）。
- **网络支持**：条件编译下提供 socket 存储（`sk_storage`）和 socket 选项操作 helpers。

### 验证机制
`bpf_lsm_verify_prog()` 确保：
- 程序许可证为 GPL 兼容（LSM BPF 要求开源）。
- 附加目标 BTF ID 必须在 `bpf_lsm_hooks` 中且不在 `bpf_lsm_disabled_hooks` 中。

## 4. 依赖关系

- **LSM 框架**：依赖 `<linux/lsm_hooks.h>` 和 `lsm_hook_defs.h` 定义的 LSM 钩子接口。
- **BPF 核心**：依赖 `<linux/bpf.h>`、`<linux/filter.h>` 提供 BPF 程序模型、验证器和辅助函数机制。
- **BTF（BPF Type Format）**：使用 `<linux/btf.h>` 和 `BTF_ID` 宏进行类型安全的钩子标识和验证。
- **cgroup BPF**：条件依赖 `CONFIG_CGROUP_BPF`，用于 cgroup 上下文的 LSM BPF 支持。
- **网络子系统**：条件依赖 `CONFIG_SECURITY_NETWORK` 和 `CONFIG_NET`，提供 socket 相关的 LSM 钩子和 helpers。
- **IMA（完整性度量架构）**：依赖 `<linux/ima.h>`，为 BPF 程序提供文件/ inode 哈希计算能力。
- **BPF 存储**：依赖 `bpf_local_storage` 和 `bpf_sk_storage`，提供 inode 和 socket 的本地存储访问。

## 5. 使用场景

- **动态安全策略实施**：管理员或安全工具可加载 BPF LSM 程序，在文件访问、进程执行、网络连接等关键点实施自定义访问控制策略，无需重启或加载内核模块。
- **系统审计与监控**：通过附加到 LSM 钩子（如 `file_open`、`task_alloc`），BPF 程序可收集安全相关事件并上报。
- **容器安全隔离**：结合 cgroup BPF，可在容器边界（如 socket 创建、二进制执行）实施额外的安全检查。
- **完整性度量集成**：利用 `bpf_ima_*_hash` helpers，在 LSM 钩子中触发 IMA 度量，实现基于 BPF 的完整性策略。
- **安全研究与原型开发**：为安全研究人员提供灵活、安全的 LSM 扩展机制，快速验证新安全模型。