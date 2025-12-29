# bpf\preload\iterators\iterators.lskel-little-endian.h

> 自动生成时间: 2025-10-25 12:26:51
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\preload\iterators\iterators.lskel-little-endian.h`

---

# `bpf/preload/iterators/iterators.lskel-little-endian.h` 技术文档

## 文件概述

该文件是 **BPF skeleton 头文件**，由 `bpftool` 工具自动生成，用于在用户空间加载和管理一组与 BPF 迭代器（BPF iterators）相关的 eBPF 程序。文件专为小端（little-endian）架构生成，封装了两个 BPF 迭代器程序：`dump_bpf_map` 和 `dump_bpf_prog`，分别用于遍历内核中的 BPF map 和 BPF program 对象。该 skeleton 提供了统一的接口用于打开、加载、挂载（attach）、卸载（detach）和销毁 BPF 资源，是用户空间程序与内核 BPF 迭代器交互的桥梁。

## 核心功能

### 数据结构

- **`struct iterators_bpf`**  
  主 skeleton 结构体，包含以下成员：
  - `ctx`：BPF 加载器上下文（`bpf_loader_ctx`）
  - `maps`：包含只读数据段（`rodata`）的 map 描述符
  - `progs`：包含两个 BPF 程序描述符：
    - `dump_bpf_map`：用于遍历 BPF maps 的迭代器程序
    - `dump_bpf_prog`：用于遍历 BPF programs 的迭代器程序
  - `links`：存储已创建的 BPF trace link 文件描述符（FD）：
    - `dump_bpf_map_fd`
    - `dump_bpf_prog_fd`

### 主要函数

- **`iterators_bpf__open()`**  
  分配并初始化 `iterators_bpf` 结构体内存，设置 loader 上下文大小。

- **`iterators_bpf__load()`**  
  将内嵌的 BPF 字节码（ELF 内容以字符串形式硬编码）加载到内核，并创建对应的 maps 和 programs。

- **`iterators_bpf__dump_bpf_map__attach()`**  
  为 `dump_bpf_map` 程序创建 `BPF_TRACE_ITER` 类型的 trace link，使其可被 `/sys/kernel/debug/tracing/trace_pipe` 或 `bpf_iter` 文件系统接口调用。

- **`iterators_bpf__dump_bpf_prog__attach()`**  
  为 `dump_bpf_prog` 程序创建 `BPF_TRACE_ITER` 类型的 trace link。

- **`iterators_bpf__attach()`**  
  批量挂载所有 BPF 迭代器程序。

- **`iterators_bpf__detach()`**  
  关闭所有已创建的 trace link FD。

- **`iterators_bpf__destroy()`**  
  安全释放所有资源（links、programs、maps）并释放 skeleton 内存。

## 关键实现

- **自动生成与硬编码字节码**  
  文件中包含一个长度为 6208 字节的字符串字面量（`opts.data`），其中嵌入了完整的 BPF ELF 二进制数据（以小端格式编码）。该数据由 `bpftool gen skeleton` 在编译时生成并内联至此头文件，避免运行时依赖外部文件。

- **BPF 迭代器挂载机制**  
  通过 `skel_link_create(prog_fd, 0, BPF_TRACE_ITER)` 创建 `BPF_LINK_TYPE_TRACE_ITER` 类型的链接。该链接使 BPF 程序注册为内核迭代器，用户可通过打开 `/sys/fs/bpf/` 下的对应迭代器文件或使用 `bpf_iter_create()` 系统调用触发遍历。

- **资源管理与错误处理**  
  所有资源（FD）使用 `skel_closenz()` 安全关闭（检查非负值），`__attach` 函数采用“短路求值”逻辑：任一 attach 失败即返回错误码，后续 attach 不再执行。

- **内存布局计算**  
  `skel->ctx.sz` 通过指针算术 `&skel->links - (void *)skel` 动态计算 loader 上下文所需大小，确保 `bpf_loader_ctx` 能正确覆盖到 `links` 成员起始位置。

## 依赖关系

- **内核依赖**：
  - `CONFIG_BPF`、`CONFIG_BPF_SYSCALL`：启用 BPF 子系统
  - `CONFIG_BPF_ITER`：支持 BPF 迭代器功能
  - `BPF_TRACE_ITER` 程序类型支持（v5.8+）

- **用户空间依赖**：
  - `libbpf` 库（提供 `skel_internal.h` 及底层 `bpf()` 系统调用封装）
  - `bpftool`（用于生成此 skeleton 文件）
  - 内核头文件中的 BPF 相关定义（如 `bpf.h`）

- **内部依赖**：
  - 依赖同目录下对应的 BPF 源文件（如 `iterators.bpf.c`）编译生成的 ELF 对象
  - 依赖 `bpf/preload/iterators/` 中的 BPF 程序逻辑

## 使用场景

- **BPF 资源内省（Introspection）**  
  用户空间工具（如 `bpftool map show` / `bpftool prog show` 的底层实现）通过此 skeleton 加载迭代器程序，安全遍历内核中所有 BPF maps 和 programs，获取其元数据（如类型、大小、引用计数等）。

- **系统监控与调试**  
  开发者或运维人员可利用此接口构建自定义监控工具，实时审计系统中运行的 BPF 程序和数据结构，用于性能分析或安全审计。

- **BPF 预加载（Preload）机制**  
  作为 `bpf/preload/` 子系统的一部分，该 skeleton 可在系统启动早期或特定服务初始化时预加载 BPF 迭代器，为后续诊断功能提供基础设施。

- **容器与沙箱环境**  
  在容器运行时中，通过受限的 BPF 迭代器接口，实现对容器内 BPF 资源的隔离查看，而无需全局权限。