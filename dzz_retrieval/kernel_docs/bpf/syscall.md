# bpf\syscall.c

> 自动生成时间: 2025-10-25 12:31:40
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\syscall.c`

---

# `bpf/syscall.c` 技术文档

## 1. 文件概述

`bpf/syscall.c` 是 Linux 内核中 BPF（Berkeley Packet Filter）子系统的核心实现文件之一，主要负责处理与 BPF 相关的系统调用逻辑。该文件实现了 BPF 程序、映射（map）和链接（link）对象的创建、更新、查询、删除等操作的底层支持，并管理这些对象的生命周期、权限控制、内存布局以及与用户空间的交互。此外，它还包含对 BPF 对象中用户指针（uptr）的内存固定（pinning）机制，确保内核安全访问用户空间内存。

## 2. 核心功能

### 主要数据结构
- `bpf_map_ops`：定义各类 BPF 映射的操作函数集，通过 `bpf_map_types[]` 数组按类型索引。
- `bpf_map`：BPF 映射的通用抽象结构，包含类型、键/值大小、操作函数指针等。
- IDR（Integer ID Allocator）结构：
  - `prog_idr` / `map_idr` / `link_idr`：分别用于分配和管理 BPF 程序、映射和链接的全局唯一 ID。
- `btf_record` 与 `btf_field`：用于描述 BPF 对象中包含的 BTF（BPF Type Format）元数据字段，特别是 `BPF_UPTR` 类型字段。

### 主要函数
- `bpf_check_uarg_tail_zero()`：验证用户传入的结构体尾部未使用字节是否为零，用于向前兼容。
- `bpf_map_value_size()`：根据映射类型计算实际存储值的大小（如 per-CPU 映射需乘以 CPU 数）。
- `bpf_map_update_value()`：统一入口，根据映射类型分发到对应的更新实现。
- `bpf_obj_pin_uptrs()` / `bpf_obj_unpin_uptrs()`：对 BPF 对象中 `BPF_UPTR` 字段指向的用户空间内存进行长期固定（pin）或释放。
- `maybe_wait_bpf_programs()`：在更新某些映射（如 map-in-map）后同步等待正在运行的 BPF 程序完成。
- `bpf_map_write_active*()`：提供映射写入活跃状态的原子计数机制。

### 全局变量
- `sysctl_unprivileged_bpf_disabled`：控制非特权用户是否可使用 BPF 的运行时开关。
- `bpf_prog_active`（per-CPU）：跟踪当前 CPU 上是否正在执行 BPF 程序。
- `bpf_map_offload_ops`：用于硬件卸载（offload）场景的映射操作集。

### 宏定义
- `IS_FD_*` 系列宏：用于快速判断映射是否存储文件描述符（如程序、其他映射等）。
- `BPF_OBJ_FLAG_MASK`：定义 BPF 对象创建时允许的标志位掩码。

## 3. 关键实现

### 用户参数兼容性检查
`bpf_check_uarg_tail_zero()` 函数确保当用户空间传递比内核预期更大的结构体时，超出部分必须全为零。这防止新版本用户空间依赖尚未实现的内核特性，保障 ABI 的向前兼容性。该函数区分内核指针和用户指针，分别使用 `memchr_inv()` 和 `check_zeroed_user()` 进行检查。

### BPF 映射值大小计算
`bpf_map_value_size()` 根据映射类型动态计算实际存储开销：
- 对于 per-CPU 类型（如 `PERCPU_HASH`、`PERCPU_ARRAY`），值大小需对齐到 8 字节并乘以可能的 CPU 数量。
- 对于存储文件描述符的映射（如 `PROG_ARRAY`、`ARRAY_OF_MAPS`），值大小固定为 `sizeof(u32)`。
- 其他类型直接使用 `map->value_size`。

### 用户指针（uptr）内存固定机制
BPF 支持在映射值或程序上下文中包含指向用户空间内存的指针（`BPF_UPTR`）。为确保内核安全访问：
1. `bpf_obj_pin_uptrs()` 使用 `pin_user_pages_fast()` 将用户页长期固定（`FOLL_LONGTERM`），防止被换出。
2. 要求目标结构体不能跨页（避免复杂性），且不支持高端内存（`PageHighMem`）。
3. 固定成功后，将用户虚拟地址转换为内核线性映射地址存储。
4. 出错时通过 `__bpf_obj_unpin_uptrs()` 回滚已固定的页。

### 映射更新分发逻辑
`bpf_map_update_value()` 是映射更新的核心分发函数：
- 硬件卸载映射调用 `bpf_map_offload_update_elem()`。
- 特殊映射（如 `CPUMAP`、`SOCKMAP`）调用其专属更新函数。
- 文件描述符类映射（`PROG_ARRAY`、`ARRAY_OF_MAPS` 等）在 RCU 读锁保护下更新，确保并发安全。
- per-CPU 映射调用对应的 per-CPU 更新函数。
- 更新前调用 `bpf_disable_instrumentation()` 避免追踪干扰。

### 同步机制
- 对于 `HASH_OF_MAPS` 和 `ARRAY_OF_MAPS`，更新后调用 `synchronize_rcu()` 确保所有 CPU 上正在运行的 BPF 程序看到新值。
- per-CPU 计数器 `bpf_prog_active` 用于检测 BPF 程序递归调用或死锁。

## 4. 依赖关系

- **BPF 子系统内部**：
  - 依赖 `bpf_map_types.h` 自动生成的映射操作函数表。
  - 与 `bpf_verifier.c`（验证器）、`bpf_helpers.c`（辅助函数）、各类映射实现（如 `arraymap.c`、`hashtab.c`）紧密协作。
- **内存管理**：
  - 使用 `pin_user_pages_fast()` / `unpin_user_page()` 管理用户页固定。
  - 依赖 `mm/` 子系统的页表和内存分配机制。
- **RCU 机制**：
  - 在更新共享映射时使用 RCU 保证并发安全。
- **BTF（BPF Type Format）**：
  - 依赖 `btf.c` 提供的类型信息解析 `BPF_UPTR` 字段。
- **网络子系统**：
  - 包含 `netfilter/nf_bpf_link.h`、`netkit.h`、`tcx.h` 等头文件，支持网络相关的 BPF 链接类型。
- **安全模块**：
  - 与 LSM（`bpf_lsm.h`）、审计（`audit.h`）集成，实施权限检查。

## 5. 使用场景

- **系统调用处理**：作为 `bpf(2)` 系统调用的后端实现，处理 `BPF_MAP_CREATE`、`BPF_MAP_UPDATE_ELEM`、`BPF_PROG_LOAD` 等命令。
- **eBPF 程序执行**：为运行中的 BPF 程序提供映射访问、程序调用（通过 `PROG_ARRAY`）等运行时支持。
- **容器与 cgroup 集成**：通过 `CGROUP_ARRAY` 等映射类型实现资源控制策略。
- **性能监控**：`PERF_EVENT_ARRAY` 映射用于将 BPF 程序与 perf 事件关联。
- **网络数据平面**：`SOCKMAP`、`XSKMAP` 等用于加速 socket 和 AF_XDP 数据路径。
- **内核追踪**：与 ftrace、kprobe 等子系统结合，实现动态追踪。
- **安全策略实施**：通过 BPF LSM 钩子执行自定义安全策略。
- **用户空间内存安全访问**：在需要内核直接访问用户缓冲区的场景（如某些高级 BPF 程序）中，通过 `BPF_UPTR` 机制安全固定内存。