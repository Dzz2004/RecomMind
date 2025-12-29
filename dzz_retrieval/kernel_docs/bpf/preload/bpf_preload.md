# bpf\preload\bpf_preload.h

> 自动生成时间: 2025-10-25 12:23:37
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\preload\bpf_preload.h`

---

# bpf_preload.h 技术文档

## 1. 文件概述

`bpf_preload.h` 是 Linux 内核中用于支持 BPF（Berkeley Packet Filter）预加载机制的头文件。该文件定义了 BPF 预加载所需的核心数据结构和接口，允许内核模块在系统启动早期阶段注册并自动加载预定义的 BPF 程序和链接（links），从而实现无需用户空间干预的 BPF 功能初始化。

## 2. 核心功能

### 数据结构

- **`struct bpf_preload_info`**  
  表示单个 BPF 预加载项的信息：
  - `char link_name[16]`：BPF 链接的名称（最多 15 个字符 + 1 个终止符）
  - `struct bpf_link *link`：指向已创建的 BPF 链接对象的指针

- **`struct bpf_preload_ops`**  
  定义 BPF 预加载操作的回调接口：
  - `int (*preload)(struct bpf_preload_info *)`：预加载回调函数，用于初始化并填充 `bpf_preload_info`
  - `struct module *owner`：拥有该操作集的内核模块指针，用于引用计数管理

### 全局变量与宏

- **`extern struct bpf_preload_ops *bpf_preload_ops;`**  
  全局指针，指向当前注册的 BPF 预加载操作集。由支持预加载的模块在初始化时设置。

- **`#define BPF_PRELOAD_LINKS 2`**  
  定义系统支持的最大预加载 BPF 链接数量（当前为 2）。

## 3. 关键实现

- 该头文件本身不包含具体实现逻辑，而是提供接口规范。
- 预加载机制依赖于外部模块（如 `bpf_preload.ko`）实现 `bpf_preload_ops` 中的 `preload` 回调。
- 在内核初始化阶段，BPF 子系统会调用 `bpf_preload_ops->preload()`，传入一个 `bpf_preload_info` 数组（大小为 `BPF_PRELOAD_LINKS`），由回调函数负责创建 BPF 程序、附加到相应 hook 点，并填充对应的 `link` 字段。
- `link_name` 字段用于在 `/sys/fs/bpf/` 或其他调试接口中标识该预加载链接，便于用户空间识别和管理。
- `owner` 字段确保在模块卸载时能正确释放相关资源，防止悬空指针。

## 4. 依赖关系

- 依赖 **BPF 核心子系统**（`kernel/bpf/`）提供的 `struct bpf_link` 定义及链接管理 API。
- 依赖 **内核模块系统**（`include/linux/module.h`），用于模块引用计数和生命周期管理。
- 通常由 **`bpf_preload` 内核模块**（位于 `kernel/bpf/preload/`）实现并注册 `bpf_preload_ops`。
- 可能与 **LSM（Linux Security Module）**、**Tracing** 或 **Networking** 子系统交互，具体取决于预加载的 BPF 程序类型。

## 5. 使用场景

- **系统启动早期自动加载关键 BPF 程序**：例如安全策略（如 Landlock）、性能监控或网络策略，无需等待用户空间初始化。
- **嵌入式或安全敏感环境**：在用户空间不可信或尚未启动时，通过内核内置机制确保关键 BPF 功能可用。
- **简化部署**：将常用 BPF 程序打包进内核模块，实现“开箱即用”的 BPF 功能，避免复杂的用户空间加载逻辑。
- **内核自检与调试**：预加载用于内核自检或调试的 BPF 程序，辅助开发和故障排查。