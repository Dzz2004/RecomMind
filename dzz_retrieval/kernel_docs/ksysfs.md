# ksysfs.c

> 自动生成时间: 2025-10-25 14:29:36
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `ksysfs.c`

---

# ksysfs.c 技术文档

## 文件概述

`ksysfs.c` 是 Linux 内核中负责在 `/sys/kernel/` 目录下创建与内核核心功能相关的 sysfs 属性文件的实现文件。这些属性不隶属于任何特定子系统，而是提供对内核全局状态、配置和元数据的只读或可写访问接口。该文件通过 sysfs 向用户空间暴露内核运行时信息，便于调试、监控和动态配置。

## 核心功能

### 主要 sysfs 属性（文件）

| 属性名 | 类型 | 说明 |
|--------|------|------|
| `uevent_seqnum` | 只读 | 当前 uevent 事件的序列号 |
| `cpu_byteorder` | 只读 | CPU 字节序（"little" 或 "big"） |
| `address_bits` | 只读 | 指针宽度对应的地址位数（如 64） |
| `uevent_helper` | 读写（需 `CONFIG_UEVENT_HELPER`）| uevent 辅助程序路径 |
| `profiling` | 读写（需 `CONFIG_PROFILING`）| 内核性能分析开关 |
| `kexec_loaded` | 只读（需 `CONFIG_KEXEC_CORE`）| 是否已加载 kexec 内核镜像 |
| `kexec_crash_loaded` | 只读（需 `CONFIG_CRASH_DUMP`）| 是否已加载崩溃转储内核 |
| `kexec_crash_size` | 读写（需 `CONFIG_CRASH_DUMP`）| 崩溃转储保留内存大小 |
| `vmcoreinfo` | 只读（需 `CONFIG_VMCORE_INFO`）| vmcoreinfo 的物理地址和大小 |
| `crash_elfcorehdr_size` | 只读（需 `CONFIG_CRASH_HOTPLUG`）| ELF core header 大小 |
| `fscaps` | 只读 | 文件能力（file capabilities）是否启用 |
| `rcu_expedited` | 读写（非 `CONFIG_TINY_RCU`）| 是否启用快速 RCU 回调 |
| `rcu_normal` | 读写（非 `CONFIG_TINY_RCU`）| 是否恢复标准 RCU 行为 |
| `notes` | 二进制只读 | 内核 `.notes` 段的原始内容 |

### 关键数据结构

- `kernel_kobj`：指向 `/sys/kernel/` 目录的 `kobject`，全局导出供其他模块使用。
- `kernel_attrs[]`：包含所有 sysfs 属性的数组。
- `notes_attr`：用于暴露内核 `.notes` 段的二进制属性。

### 核心函数

- `ksysfs_init()`：模块初始化函数，创建 `/sys/kernel/` 目录并注册所有属性。
- 各属性的 `show`/`store` 回调函数（如 `uevent_seqnum_show`、`profiling_store` 等）。

## 关键实现

### 宏定义简化属性声明
使用 `KERNEL_ATTR_RO` 和 `KERNEL_ATTR_RW` 宏自动生成 `kobj_attribute` 实例，减少样板代码。

### 字节序检测
通过预处理器宏 `__LITTLE_ENDIAN` / `__BIG_ENDIAN` 在编译期确定 `cpu_byteorder` 的值，避免运行时开销。

### 安全与同步机制
- **`profiling_store`**：使用互斥锁 (`mutex`) 防止并发初始化，确保 `prof_on` 状态和 `prof_buffer` 分配的一致性。
- **RCU 属性**：使用 `READ_ONCE()` 保证对 `rcu_expedited`/`rcu_normal` 的无锁读取符合内存模型要求。

### 条件编译
大量使用 `#ifdef CONFIG_XXX` 控制功能编译，确保仅在启用对应内核配置时暴露相关属性，减小内核体积。

### 二进制属性处理
`notes_read()` 直接从内核符号 `__start_notes` 到 `__stop_notes` 之间拷贝数据，暴露 ELF note 段内容，用于调试器或崩溃分析工具。

### 用户输入处理
- `uevent_helper_store`：截断换行符并确保字符串以 `\0` 结尾。
- `kexec_crash_size_store` 和 RCU 属性：使用 `kstrtoul`/`kstrtoint` 安全解析用户输入。

## 依赖关系

### 头文件依赖
- `<linux/sysfs.h>`：sysfs 核心 API。
- `<linux/kobject.h>`：kobject 机制。
- `<linux/kexec.h>`：kexec 和崩溃转储相关接口。
- `<linux/profile.h>`：内核性能分析支持。
- `<linux/rcupdate.h>`：RCU 配置变量。
- `<asm/byteorder.h>`：字节序定义。

### 内核配置依赖
- `CONFIG_UEVENT_HELPER`：控制 `uevent_helper` 属性。
- `CONFIG_PROFILING`：启用 profiling 支持。
- `CONFIG_KEXEC_CORE` / `CONFIG_CRASH_DUMP`：kexec 和崩溃转储功能。
- `CONFIG_VMCORE_INFO` / `CONFIG_CRASH_HOTPLUG`：vmcore 信息暴露。
- `CONFIG_TINY_RCU`：决定是否编译 RCU 调优属性。

### 全局符号依赖
- `uevent_seqnum`（来自 `drivers/base/core.c`）
- `uevent_helper`（来自 `drivers/base/uevent.c`）
- `prof_on`, `profile_setup()`, `profile_init()`（来自 `kernel/profile.c`）
- `kexec_image`, `kexec_crash_loaded()`（来自 `kernel/kexec.c`）
- `paddr_vmcoreinfo_note()`（来自 `kernel/kexec_core.c`）
- `__start_notes` / `__stop_notes`（链接器脚本定义）

## 使用场景

1. **系统监控与调试**
   - 通过 `uevent_seqnum` 跟踪 uevent 事件流。
   - 读取 `cpu_byteorder` 和 `address_bits` 获取架构信息。
   - 访问 `notes` 文件获取内核构建信息（如版本、编译器等）。

2. **动态内核配置**
   - 修改 `uevent_helper` 设置用户空间热插拔处理程序（已废弃但兼容）。
   - 通过 `profiling` 启用/禁用内核性能分析。
   - 调整 `kexec_crash_size` 动态修改崩溃转储保留内存大小。
   - 设置 `rcu_expedited=1` 加速 RCU 回调（用于测试或低延迟场景）。

3. **崩溃转储与恢复**
   - `kexec_loaded` 和 `kexec_crash_loaded` 指示 kexec 状态。
   - `vmcoreinfo` 提供崩溃分析所需的关键内核结构信息。
   - `crash_elfcorehdr_size` 支持热插拔场景下的崩溃头大小查询。

4. **安全审计**
   - `fscaps` 显示文件能力是否启用，影响系统安全策略。

5. **内核模块集成**
   - 其他子系统可通过 `kernel_kobj` 在 `/sys/kernel/` 下创建自己的属性（如 `ftrace`、`debug` 等）。