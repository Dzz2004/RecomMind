# bpf\cgroup.c

> 自动生成时间: 2025-10-25 12:04:23
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\cgroup.c`

---

# bpf/cgroup.c 技术文档

## 文件概述

`bpf/cgroup.c` 是 Linux 内核中用于管理附加到 cgroup（控制组）的 eBPF 程序的核心实现文件。该文件提供了 cgroup 与 eBPF 集成的基础设施，包括程序执行、生命周期管理、存储分配以及与 LSM（Linux Security Module）挂钩的机制。通过将 eBPF 程序绑定到 cgroup，内核可以在进程或套接字进入特定资源控制组时动态执行安全策略、网络过滤或资源监控逻辑。

## 核心功能

### 主要数据结构

- `cgroup_bpf_enabled_key`：静态键数组，用于快速判断特定类型的 cgroup BPF 程序是否启用（基于 `static_key` 优化）。
- `cgroup_bpf_destroy_wq`：专用工作队列，用于异步销毁 cgroup BPF 相关资源，避免阻塞系统工作队列。
- `cgroup_lsm_atype[]`（仅当 `CONFIG_BPF_LSM` 启用）：用于映射 BPF LSM cgroup 附件类型到内部索引，支持动态 BTF ID 注册。
- `bpf_cg_run_ctx`：BPF 程序执行上下文，用于在运行时传递返回值和程序项信息。

### 主要函数

- `bpf_prog_run_array_cg()`：核心执行函数，遍历并运行指定 cgroup 上某类型的所有有效 BPF 程序。
- `__cgroup_bpf_run_lsm_sock()` / `__cgroup_bpf_run_lsm_socket()` / `__cgroup_bpf_run_lsm_current()`：LSM 钩子入口函数，分别用于套接字、socket 结构和当前任务的 cgroup BPF 执行。
- `bpf_cgroup_atype_find()`：根据 BPF 附件类型和 BTF ID 查找或分配对应的 cgroup BPF 附件类型。
- `bpf_cgroup_atype_get()` / `bpf_cgroup_atype_put()`：管理 LSM cgroup 附件类型的引用计数。
- `cgroup_bpf_offline()`：标记 cgroup BPF 子系统为离线状态，触发引用计数关闭。
- `bpf_cgroup_storages_*()` 系列函数：管理 per-cgroup、per-attach-type 的 BPF map 存储（如 per-cgroup counters）。
- `cgroup_bpf_release()`：异步释放 cgroup BPF 资源的工作项处理函数（代码截断，但功能明确）。

## 关键实现

### BPF 程序执行机制

`bpf_prog_run_array_cg()` 是执行引擎的核心：
- 使用 RCU 保护读取 `cgrp->bpf.effective[atype]` 程序数组，确保并发安全。
- 通过 `bpf_set_run_ctx()` 设置运行时上下文 `bpf_cg_run_ctx`，用于传递初始返回值和收集程序执行结果。
- 程序按顺序执行，若任一程序返回 0（拒绝），且当前返回值非错误，则最终返回 `-EPERM`。
- 使用 `migrate_disable()` 禁用 CPU 迁移，保证执行上下文一致性。
- 支持通过 `ret_flags` 收集高 31 位的返回标志（低 1 位为允许/拒绝决策）。

### LSM 与 cgroup BPF 集成

当启用 `CONFIG_BPF_LSM` 时：
- 通过 `cgroup_lsm_atype` 数组动态注册 LSM 钩子对应的 BTF ID。
- `bpf_cgroup_atype_find()` 在首次附加时分配空闲槽位，实现最多 `CGROUP_LSM_NUM` 个动态 LSM 钩子。
- 引用计数机制确保 BTF ID 映射在无程序使用时可复用。

### 资源管理与异步销毁

- 专用工作队列 `cgroup_bpf_destroy_wq` 避免大量 cgroup 销毁时阻塞 `system_wq`，防止死锁。
- `cgroup_bpf_offline()` 触发 `percpu_ref_kill()`，确保所有 BPF 执行路径完成后才释放资源。
- cgroup BPF 存储（`bpf_cgroup_storage`）按类型（local/global）分配、链接和释放，支持程序访问 per-cgroup 数据。

### 上下文恢复技巧

LSM 钩子函数（如 `__cgroup_bpf_run_lsm_sock`）通过 `insn` 指针反推 `struct bpf_prog` 地址：
```c
shim_prog = (const struct bpf_prog *)((void *)insn - offsetof(struct bpf_prog, insnsi));
```
这是 BPF trampoline 机制的标准做法，用于在无显式 prog 指针的 LSM 回调中获取程序元数据。

## 依赖关系

- **cgroup 子系统**：依赖 `cgroup.h` 和 `cgroup-internal.h`，使用 `cgroup_mutex`、`task_dfl_cgroup()`、`sock_cgroup_ptr()` 等接口。
- **BPF 核心**：依赖 `bpf.h`、`filter.h`、`bpf_verifier.h`，使用 `bpf_prog`、`bpf_prog_array`、`bpf_map` 等核心结构。
- **网络子系统**：通过 `net/sock.h` 和 `net/bpf_sk_storage.h` 集成套接字级别的 cgroup BPF。
- **LSM 框架**：当 `CONFIG_BPF_LSM` 启用时，与 LSM 钩子集成，实现基于 cgroup 的安全策略。
- **RCU 与内存管理**：大量使用 RCU 保护数据结构，依赖 `slab.h` 进行内存分配。

## 使用场景

1. **网络策略控制**：在 `sock_create`、`connect`、`sendmsg` 等路径上，通过 `BPF_CGROUP_INET_*` 类型程序实施基于 cgroup 的网络访问控制。
2. **资源监控与限制**：使用 `BPF_CGROUP_DEVICE` 或 `BPF_CGROUP_SOCK_OPS` 监控或限制 cgroup 内进程的设备访问或套接字行为。
3. **安全增强（LSM）**：通过 `BPF_LSM_CGROUP` 类型程序，在 LSM 钩子（如 `socket_create`、`task_alloc`）中执行基于 cgroup 的安全策略。
4. **性能分析**：附加 `BPF_CGROUP_SYSCTL` 等程序跟踪 cgroup 内的系统调用或参数变更。
5. **服务网格与容器网络**：在 Kubernetes 等容器平台中，利用 cgroup BPF 实现细粒度的网络策略和可观测性。