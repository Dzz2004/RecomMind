# bpf\preload\bpf_preload_kern.c

> 自动生成时间: 2025-10-25 12:24:17
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\preload\bpf_preload_kern.c`

---

# bpf_preload_kern.c 技术文档

## 文件概述

`bpf_preload_kern.c` 是 Linux 内核中 BPF（Berkeley Packet Filter）预加载机制的核心实现文件之一。该文件负责在内核初始化阶段自动加载一组预定义的 BPF 程序和映射（maps），主要用于提供内核级的 BPF 调试和内省能力（如 `bpf_iter` 迭代器）。通过 `bpf_preload` 框架，该模块将 BPF 程序与内核生命周期绑定，使得用户空间工具（如 bpftool）能够直接访问预加载的 BPF 资源，而无需手动加载。

## 核心功能

### 主要数据结构

- `struct bpf_link *maps_link, *progs_link`：分别指向用于调试 BPF maps 和 BPF programs 的 BPF 链接对象。
- `struct iterators_bpf *skel`：由 `libbpf` 生成的 skeleton 结构体，封装了 BPF 程序、映射及链接的元数据。
- `struct bpf_preload_ops ops`：实现 `bpf_preload` 框架的回调接口，包含 `preload` 函数指针和模块所有者信息。

### 主要函数

- `free_links_and_skel(void)`：安全释放 BPF 链接和 skeleton 资源。
- `preload(struct bpf_preload_info *obj)`：向 BPF 预加载框架注册已加载的 BPF 链接。
- `load_skel(void)`：打开、加载并挂载 BPF skeleton，获取对应的 BPF 链接。
- `load(void)`：模块初始化入口，调用 `load_skel` 并注册预加载操作。
- `fini(void)`：模块卸载清理函数，注销预加载操作并释放资源。

## 关键实现

1. **BPF Skeleton 加载**：
   - 使用 `iterators_bpf__open()`、`iterators_bpf__load()` 和 `iterators_bpf__attach()` 三步完成 BPF 程序的加载与挂载。
   - 根据编译时字节序（小端或大端）包含对应的 skeleton 头文件（`iterators.lskel-little-endian.h` 或 `iterators.lskel-big-endian.h`）。

2. **BPF 链接获取与管理**：
   - 通过 `bpf_link_get_from_fd()` 从 skeleton 中的文件描述符获取持久化的 `bpf_link` 对象，确保即使原始 FD 关闭，链接仍有效。
   - 显式关闭原始 FD（`dump_bpf_map_fd` 和 `dump_bpf_prog_fd`）并置零，防止 `iterators_bpf__destroy()` 尝试关闭已释放的 FD，避免干扰 init 进程的标准文件描述符。

3. **预加载注册机制**：
   - 实现 `bpf_preload_ops::preload` 回调，将两个 BPF 链接分别命名为 `"maps.debug"` 和 `"progs.debug"`，供用户空间通过 `/sys/kernel/bpf/` 虚拟文件系统访问。
   - 在 `late_initcall` 阶段注册 `bpf_preload_ops`，确保在大多数子系统初始化完成后才暴露 BPF 资源。

4. **错误处理与资源清理**：
   - 所有资源分配均配对 `free_links_and_skel()` 清理路径，使用 `IS_ERR_OR_NULL()` 安全判断指针有效性。
   - 加载失败时自动回滚已分配资源，保证内核状态一致性。

## 依赖关系

- **内核子系统**：
  - 依赖 BPF 子系统（`CONFIG_BPF`、`CONFIG_BPF_SYSCALL`）提供的 `bpf_link`、`bpf_preload` 等核心 API。
  - 依赖 `libbpf` 生成的 skeleton 机制（通过 `bpftool gen skeleton` 生成 `iterators.lskel-*.h`）。
- **头文件**：
  - `<linux/init.h>`、`<linux/module.h>`：模块初始化与退出支持。
  - `"bpf_preload.h"`：定义 `bpf_preload_ops` 和 `bpf_preload_info` 接口。
  - `iterators/iterators.lskel-*.h`：BPF 程序的 skeleton 定义，由构建系统根据字节序自动生成。
- **构建依赖**：
  - 需要预先编译 `iterators.bpf.o` 并生成对应的 skeleton 头文件。

## 使用场景

- **内核调试与内省**：为 `bpftool prog show`、`bpftool map show` 等命令提供底层支持，允许直接遍历所有 BPF 程序和映射。
- **系统监控工具**：用户空间监控工具（如 BCC、bpftrace）可利用预加载的迭代器高效获取 BPF 资源状态。
- **安全审计**：安全模块可通过预加载的 BPF 迭代器检查系统中是否存在恶意或异常的 BPF 程序。
- **开发与测试**：内核开发者可借助该机制快速验证 BPF 程序行为，无需手动加载调试程序。