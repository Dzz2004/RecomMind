# bpf\token.c

> 自动生成时间: 2025-10-25 12:36:08
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\token.c`

---

# `bpf/token.c` 技术文档

## 1. 文件概述

`bpf/token.c` 实现了 BPF（Berkeley Packet Filter）令牌（token）机制，用于在受限环境中安全地委托 BPF 操作权限。该机制允许用户空间程序通过文件描述符形式的令牌，将特定的 BPF 命令、映射类型、程序类型和附加类型权限委托给其他进程，同时结合用户命名空间（user namespace）和 LSM（Linux Security Module）安全策略进行细粒度访问控制。

## 2. 核心功能

### 主要函数

- `bpf_ns_capable()`：检查用户命名空间是否具备指定能力，或具备 `CAP_SYS_ADMIN`（除 `CAP_SYS_ADMIN` 自身外）。
- `bpf_token_capable()`：结合用户命名空间能力和 LSM 安全钩子，判断令牌是否具备指定能力。
- `bpf_token_inc()` / `bpf_token_put()`：引用计数管理，支持延迟释放。
- `bpf_token_free()`：释放令牌资源，包括用户命名空间引用和安全模块数据。
- `bpf_token_create()`：创建 BPF 令牌文件描述符，基于挂载在 BPF 文件系统上的委托配置。
- `bpf_token_get_from_fd()`：从文件描述符获取并增加引用计数的 `bpf_token` 结构。
- `bpf_token_allow_cmd()` / `bpf_token_allow_map_type()` / `bpf_token_allow_prog_type()`：检查令牌是否允许执行特定 BPF 操作。

### 关键数据结构

- `struct bpf_token`：表示 BPF 令牌，包含：
  - `refcnt`：引用计数（`atomic64_t`）
  - `userns`：关联的用户命名空间
  - `allowed_cmds` / `allowed_maps` / `allowed_progs` / `allowed_attachs`：位掩码，分别表示允许的 BPF 命令、映射类型、程序类型和附加类型
  - `work`：用于延迟释放的工作队列项

### 文件操作接口

- `bpf_token_fops`：定义了 `release` 和 `show_fdinfo` 回调，用于文件关闭和 `/proc/pid/fdinfo/` 信息展示。

## 3. 关键实现

### 令牌创建流程 (`bpf_token_create`)

1. **验证输入**：检查传入的 `bpffs_fd` 是否指向 BPF 文件系统的根目录。
2. **权限校验**：
   - 要求调用者与 BPF 文件系统实例处于同一用户命名空间。
   - 必须具备 `CAP_BPF` 能力。
   - 禁止在 `init_user_ns` 中创建令牌。
3. **委托配置检查**：确保 BPF 文件系统挂载时已通过挂载选项设置了至少一项委托权限（`delegate_*` 字段非零）。
4. **资源分配**：
   - 创建匿名 inode 和文件。
   - 分配 `bpf_token` 结构并初始化引用计数为 1。
   - 复制挂载选项中的委托位掩码到令牌。
5. **安全模块集成**：调用 `security_bpf_token_create()` 允许 LSM 进行额外策略检查。
6. **返回文件描述符**：安装文件到进程 fd 表并返回。

### 安全能力检查 (`bpf_token_capable`)

- 默认允许 `CAP_SYS_ADMIN` 作为“超级能力”覆盖其他能力检查（但 `CAP_SYS_ADMIN` 本身仍需显式授权）。
- 调用 `security_bpf_token_capable()` 允许 LSM 对令牌能力进行二次验证。

### 引用计数与延迟释放

- 使用 `atomic64_t refcnt` 管理生命周期。
- 当引用计数归零时，通过 `schedule_work()` 将释放操作推迟到工作队列执行，避免在中断或原子上下文中调用可能睡眠的 `put_user_ns()` 和 `kfree()`。

### `/proc/pid/fdinfo/` 支持

- `bpf_token_show_fdinfo()` 将令牌的委托权限以十六进制或 "any" 形式输出，便于调试和审计。

### 权限位掩码设计

- 所有委托权限（命令、映射、程序、附加类型）均使用 64 位无符号整数位掩码表示。
- 通过 `BUILD_BUG_ON()` 确保枚举类型数量不超过 64，防止位移溢出。
- 若掩码全为 1，则显示为 "any"，表示无限制。

## 4. 依赖关系

- **BPF 子系统**：依赖 `bpf_super_ops`、`bpf_get_inode()` 等 BPF 文件系统接口。
- **用户命名空间**：通过 `user_namespace` 和 `ns_capable()` 实现能力隔离。
- **安全模块 (LSM)**：集成 `security_bpf_token_*` 钩子，支持 SELinux、AppArmor 等策略扩展。
- **VFS 层**：使用 `inode`、`file`、`path`、`fdtable` 等通用文件系统抽象。
- **内存管理**：使用 `kzalloc()`/`kfree()` 和 `vmalloc.h`（虽未直接使用，但为潜在扩展预留）。
- **工作队列**：通过 `schedule_work()` 实现延迟释放。

## 5. 使用场景

- **容器化环境中的 BPF 权限委托**：在用户命名空间隔离的容器中，特权进程可创建 BPF 令牌并传递给非特权子进程，使其在受限范围内使用 BPF 功能（如 eBPF 程序加载、映射操作）。
- **安全沙箱**：应用程序可通过令牌机制将特定 BPF 操作权限委托给插件或子模块，避免授予完整 `CAP_BPF` 或 `CAP_SYS_ADMIN`。
- **审计与调试**：通过 `/proc/pid/fdinfo/` 查看进程持有的 BPF 令牌权限，辅助安全分析。
- **LSM 策略集成**：安全模块可基于令牌内容实施更细粒度的访问控制，例如限制特定程序类型只能在特定挂载点使用。