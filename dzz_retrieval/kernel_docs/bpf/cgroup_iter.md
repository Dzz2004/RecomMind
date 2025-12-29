# bpf\cgroup_iter.c

> 自动生成时间: 2025-10-25 12:04:56
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\cgroup_iter.c`

---

# `bpf/cgroup_iter.c` 技术文档

## 1. 文件概述

`bpf/cgroup_iter.c` 实现了 BPF 迭代器（BPF iterator）对 cgroup 层级结构的遍历功能。该模块允许用户空间通过 BPF 程序以四种不同模式遍历 cgroup 层级：前序遍历后代、后序遍历后代、向上遍历祖先，或仅显示指定 cgroup。该迭代器基于内核的 seq_file 机制实现，并在 `cgroup_mutex` 保护下执行，确保遍历过程的一致性和安全性。此功能主要用于内核态向用户态高效导出 cgroup 相关信息，适用于监控、调试和资源分析等场景。

## 2. 核心功能

### 数据结构

- **`struct bpf_iter__cgroup`**  
  BPF 程序的上下文结构，包含元数据指针和当前遍历的 `cgroup` 指针。

- **`struct cgroup_iter_priv`**  
  迭代器私有状态，包含：
  - `start_css`：起始 cgroup 的子系统状态（css）
  - `visited_all`：是否已完成全部遍历
  - `terminate`：是否由 BPF 程序请求提前终止
  - `order`：遍历模式（如 `BPF_CGROUP_ITER_DESCENDANTS_PRE` 等）

### 主要函数

- **`cgroup_iter_seq_start`**  
  初始化遍历，根据指定模式返回首个遍历元素；不支持跨会话读取。

- **`cgroup_iter_seq_next`**  
  返回下一个遍历元素，依据遍历模式调用相应的 cgroup 遍历辅助函数（如 `css_next_descendant_pre`）。

- **`cgroup_iter_seq_show` / `__cgroup_iter_seq_show`**  
  调用用户提供的 BPF 程序处理当前 cgroup；若传入 `NULL` 表示遍历结束，用于后处理。

- **`cgroup_iter_seq_stop`**  
  释放 `cgroup_mutex`，并在遍历结束时调用 BPF 程序进行后处理。

- **`cgroup_iter_seq_init` / `cgroup_iter_seq_fini`**  
  初始化和清理迭代器私有数据，管理起始 cgroup 的引用计数。

- **`bpf_iter_attach_cgroup`**  
  从用户提供的 cgroup 文件描述符（fd）或 cgroup ID 解析起始 cgroup，并验证遍历模式合法性。

- **`bpf_iter_detach_cgroup`**  
  释放对起始 cgroup 的引用。

- **`bpf_iter_cgroup_show_fdinfo`**  
  在 `/proc/pid/fdinfo/` 中显示该 BPF 迭代器关联的 cgroup 路径和遍历顺序。

- **`bpf_iter_cgroup_fill_link_info`**  
  填充 BPF link 信息，包括遍历顺序和 cgroup ID。

- **`DEFINE_BPF_ITER_FUNC(cgroup, ...)`**  
  注册 cgroup BPF 迭代器类型。

## 3. 关键实现

- **遍历模式支持**  
  支持四种遍历策略：
  - **Descendants Pre-order**：先访问父节点，再递归访问子节点。
  - **Descendants Post-order**：先递归访问子节点，再访问父节点。
  - **Ancestors Up**：从指定 cgroup 向上遍历至根。
  - **Self Only**：仅访问指定 cgroup。

- **单会话限制**  
  由于依赖 `cgroup_mutex` 全局锁，遍历必须在单次 `read()` 系统调用中完成。若用户缓冲区不足导致需多次读取，后续 `read()` 将返回 `-EOPNOTSUPP`，提示用户优化 BPF 程序以减少输出量。

- **BPF 程序交互**  
  BPF 程序通过 `ctx.cgroup` 获取当前 cgroup，通过 `seq->num == 0` 判断是否为首元素。程序返回 `1` 可提前终止遍历；传入 `NULL` cgroup 表示遍历结束，可用于输出尾部信息。

- **死 cgroup 过滤**  
  在 `__cgroup_iter_seq_show` 中检查 `cgroup_is_dead()`，跳过已销毁的 cgroup，避免访问无效内存。

- **引用计数管理**  
  `bpf_iter_attach_cgroup` 获取起始 cgroup 引用，`cgroup_iter_seq_init` 再次获取 css 引用，确保遍历期间对象不被释放；`fini` 函数负责释放。

## 4. 依赖关系

- **`<linux/cgroup.h>` / `cgroup-internal.h`**  
  依赖 cgroup 核心接口，包括 `cgroup_lock/unlock`、`cgroup_is_dead`、`css_next_descendant_*` 等内部函数。

- **`<linux/bpf.h>` / BPF 迭代器框架**  
  依赖 BPF 迭代器基础设施，如 `bpf_iter_get_info`、`bpf_iter_run_prog`、`bpf_iter_aux_info` 等。

- **`<linux/seq_file.h>`**  
  基于 seq_file 机制实现迭代器的 `start/next/stop/show` 回调。

- **BTF 支持**  
  通过 `BTF_ID_LIST_GLOBAL_SINGLE` 导出 `struct cgroup` 的 BTF ID，供 BPF verifier 使用。

## 5. 使用场景

- **系统监控工具**  
  用户空间工具（如 `bpftool`）可通过该迭代器高效遍历整个 cgroup 层级，收集资源使用情况（如 CPU、内存、IO 统计）。

- **安全与策略审计**  
  BPF 程序可检查 cgroup 配置是否符合安全策略，并在遍历时动态生成报告。

- **调试与诊断**  
  开发者可编写 BPF 程序遍历 cgroup 结构，输出拓扑关系或状态信息，辅助内核调试。

- **资源分析**  
  在容器化环境中，快速导出所有容器（对应 cgroup）的层级和属性，用于性能分析或容量规划。

> **注意**：由于遍历过程持有全局 `cgroup_mutex`，长时间运行的 BPF 程序可能阻塞其他 cgroup 操作，应尽量减少在 BPF 程序中的处理逻辑。