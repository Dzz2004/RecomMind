# bpf\preload\iterators\iterators.lskel-big-endian.h

> 自动生成时间: 2025-10-25 12:25:53
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\preload\iterators\iterators.lskel-big-endian.h`

---

# `bpf/preload/iterators/iterators.lskel-big-endian.h` 技术文档

## 1. 文件概述

该文件是 `bpftool` 自动生成的 BPF skeleton 头文件（针对大端序架构），用于封装和管理一组 BPF 迭代器程序（`dump_bpf_map` 和 `dump_bpf_prog`）。它提供了一套标准化的接口，用于打开、加载、附加、分离和销毁 BPF 程序及其关联资源，使得用户空间程序能够安全、便捷地使用 BPF 迭代器功能来遍历内核中的 BPF map 和 BPF program 对象。

## 2. 核心功能

### 主要数据结构

- **`struct iterators_bpf`**  
  BPF skeleton 主结构体，包含以下成员：
  - `ctx`：BPF 加载器上下文
  - `maps`：包含只读数据段（`rodata`）的 map 描述符
  - `progs`：包含两个 BPF 程序描述符：
    - `dump_bpf_map`：用于遍历 BPF maps 的迭代器程序
    - `dump_bpf_prog`：用于遍历 BPF programs 的迭代器程序
  - `links`：存储两个程序 attach 后返回的链接文件描述符（`dump_bpf_map_fd` 和 `dump_bpf_prog_fd`）

### 主要函数

- **`iterators_bpf__open(void)`**  
  分配并初始化 skeleton 结构体内存。

- **`iterators_bpf__load(struct iterators_bpf *skel)`**  
  将内嵌的 BPF 字节码（ELF 格式数据）加载到内核中，并创建对应的 maps 和 programs。

- **`iterators_bpf__dump_bpf_map__attach(struct iterators_bpf *skel)`**  
  将 `dump_bpf_map` 程序 attach 到 `BPF_TRACE_ITER` 类型的 tracepoint，返回链接 FD。

- **`iterators_bpf__dump_bpf_prog__attach(struct iterators_bpf *skel)`**  
  将 `dump_bpf_prog` 程序 attach 到 `BPF_TRACE_ITER` 类型的 tracepoint，返回链接 FD。

- **`iterators_bpf__attach(struct iterators_bpf *skel)`**  
  一次性 attach 所有 BPF 程序（两个迭代器）。

- **`iterators_bpf__detach(struct iterators_bpf *skel)`**  
  关闭所有已 attach 的链接 FD，解除程序与 tracepoint 的绑定。

- **`iterators_bpf__destroy(struct iterators_bpf *skel)`**  
  释放所有资源（FD、内存等），安全销毁 skeleton 实例。

## 3. 关键实现

- **自动生成与内嵌字节码**：  
  文件末尾包含一个长度为 6008 字节的内嵌字符串（`opts.data`），实际是编译好的 BPF ELF 二进制数据（以 `\0` 填充开头，后接有效字节码），由 `bpftool gen skeleton` 命令生成。该数据在 `iterators_bpf__load()` 中通过 `bpf_load_and_run_opts` 传递给内核加载器。

- **BPF 迭代器 Attach 机制**：  
  两个 `__attach` 函数均调用 `skel_link_create(prog_fd, 0, BPF_TRACE_ITER)`，表明这两个程序是 **BPF 迭代器（BPF iterator）** 类型，通过 `BPF_TRACE_ITER` attach 类型注册到内核。用户可通过 `/sys/kernel/debug/tracing/trace_pipe` 或 `bpf_iter_run()` 接口触发迭代。

- **资源管理与错误处理**：  
  - 使用 `skel_closenz()` 安全关闭文件描述符（自动处理无效 FD）
  - `__attach` 函数采用链式错误传播：任一 attach 失败即返回负错误码
  - `__destroy` 确保在释放内存前清理所有内核资源，防止泄漏

- **大端序兼容性**：  
  文件名含 `big-endian`，表明内嵌的 BPF 字节码和数据布局已针对大端序 CPU（如 PowerPC、SPARC）进行适配，确保跨架构正确性。

## 4. 依赖关系

- **内核依赖**：
  - `CONFIG_BPF`、`CONFIG_BPF_SYSCALL`：BPF 子系统支持
  - `CONFIG_BPF_ITER`：BPF 迭代器功能（Linux 5.8+）
  - `BPF_TRACE_ITER` attach 类型支持

- **用户空间库依赖**：
  - `libbpf`：提供 `skel_*` 系列辅助函数（如 `skel_alloc`, `skel_link_create`, `skel_closenz`）
  - `bpf/skel_internal.h`：skeleton 内部实现头文件

- **构建工具依赖**：
  - `bpftool`：用于生成此 skeleton 文件（`bpftool gen skeleton`）

## 5. 使用场景

- **BPF 调试与内省**：  
  用户空间工具（如 `bpftool map show` / `bpftool prog show`）通过此 skeleton 加载迭代器程序，安全遍历系统中所有 BPF maps 或 programs，获取其元数据（如类型、ID、引用计数等）。

- **监控与审计**：  
  安全或运维工具可定期 attach 这些迭代器，收集 BPF 对象状态，用于检测异常 BPF 程序或资源泄漏。

- **预加载（preload）机制**：  
  作为 `bpf/preload/` 子系统的一部分，该 skeleton 可被集成到系统初始化流程中，提前加载常用 BPF 迭代器，减少运行时开销。

- **跨架构支持**：  
  专为大端序系统生成，确保在非 x86 架构（如 IBM Power）上正确运行 BPF 迭代器功能。