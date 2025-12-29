# trace\trace_mmiotrace.c

> 自动生成时间: 2025-10-25 17:28:55
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `trace\trace_mmiotrace.c`

---

# `trace/trace_mmiotrace.c` 技术文档

## 1. 文件概述

`trace_mmiotrace.c` 是 Linux 内核中用于实现 **Memory-Mapped I/O (MMIO) 跟踪（mmiotrace）** 功能的核心文件。该功能可记录对内存映射 I/O 区域的所有读写操作以及映射/解除映射事件，主要用于硬件驱动调试、PCI 设备行为分析和系统底层 I/O 行为监控。该 tracer 通过 ftrace 框架集成，支持通过 `/sys/kernel/debug/tracing/` 接口启用和读取跟踪数据。

## 2. 核心功能

### 主要数据结构

- **`struct header_iter`**  
  用于在读取跟踪数据时遍历 PCI 设备列表的迭代器结构，包含当前遍历的 `pci_dev` 指针。

- **全局变量**  
  - `mmio_trace_array`：指向当前激活的 `mmiotrace` tracer 实例。
  - `overrun_detected` / `prev_overruns` / `dropped_count`：用于检测和报告跟踪缓冲区溢出（事件丢失）状态。

### 主要函数

- **Tracer 生命周期管理**
  - `mmio_trace_init()`：初始化 mmiotrace，启用底层跟踪机制。
  - `mmio_trace_reset()`：禁用跟踪并清理状态。
  - `mmio_trace_start()`：每次启动跟踪时重置数据。

- **跟踪事件记录**
  - `mmio_trace_rw()`：记录一次 MMIO 读或写操作。
  - `__trace_mmiotrace_rw()` / `__trace_mmiotrace_map()`：内部封装，将事件写入 ring buffer。

- **输出格式化**
  - `mmio_print_rw()`：格式化 MMIO 读写事件（`R`/`W`/`UNKNOWN`）。
  - `mmio_print_map()`：格式化映射（`MAP`）和解除映射（`UNMAP`）事件。
  - `mmio_print_mark()`：格式化通用标记事件（`MARK`）。
  - `mmio_print_pcidev()`：输出 PCI 设备详细信息（总线号、设备号、资源、驱动名等）。

- **用户接口**
  - `mmio_pipe_open()`：打开跟踪管道时输出版本号并初始化 PCI 设备迭代器。
  - `mmio_close()`：释放迭代器资源（注释指出此函数在 pipe 关闭时可能未被调用）。
  - `mmio_read()`：处理用户空间读取请求，输出 PCI 设备信息或丢失事件警告。

- **辅助函数**
  - `count_overruns()`：统计并汇总 ring buffer 和内部计数器中的事件丢失数量。
  - `mmio_reset_data()`：重置跟踪状态和缓冲区。

### Tracer 注册

- `mmio_tracer`：`struct tracer` 实例，定义了 tracer 的名称（`"mmiotrace"`）及所有回调函数。
- `init_mmio_trace()`：通过 `device_initcall` 在内核初始化阶段注册该 tracer。

## 3. 关键实现

### 跟踪事件类型

- **`TRACE_MMIO_RW`**：记录单次 MMIO 访问，包含操作类型（读/写/未知）、宽度、物理地址、值、程序计数器（PC）等。
- **`TRACE_MMIO_MAP`**：记录内存映射（`MMIO_PROBE`）和解除映射（`MMIO_UNPROBE`）事件，包含映射 ID、物理地址、虚拟地址、长度等。
- **`TRACE_PRINT`**：用于输出自定义标记信息（如事件丢失提示）。

### 输出格式

- **时间戳**：以 `秒.微秒` 格式表示（基于 `ns2usecs` 转换）。
- **PCI 设备信息**：在跟踪开始时输出所有 PCI 设备的详细信息，包括：
  - 总线号、设备功能号
  - 厂商 ID、设备 ID、IRQ
  - 7 个资源区域的起始地址（含标志位）和长度
  - 关联的驱动名称
- **事件丢失处理**：通过 `atomic_t dropped_count` 和 ring buffer 溢出计数检测事件丢失，并在输出中插入 `MARK` 行提示。

### 缓冲区管理

- 使用 ftrace 的 `ring_buffer` 机制存储事件。
- 当缓冲区满或分配失败时，递增 `dropped_count` 并可能触发警告。
- 通过 `tracing_reset_online_cpus()` 在每次启动时清空缓冲区。

### PCI 设备遍历

- 在 `mmio_read()` 中通过 `pci_get_device()` 迭代所有 PCI 设备，每次读取返回一个设备信息，直到遍历完成。

## 4. 依赖关系

- **内核子系统**
  - **ftrace 框架**：依赖 `trace.h`、`trace_output.h` 提供的 tracer 注册、ring buffer、序列化输出等基础设施。
  - **PCI 子系统**：通过 `linux/pci.h` 访问 PCI 设备信息和资源。
  - **MMIO 跟踪核心**：依赖 `linux/mmiotrace.h` 定义的 `mmiotrace_rw`、`mmiotrace_map` 等数据结构及 `enable_mmiotrace()`/`disable_mmiotrace()` 控制函数。
  - **内存管理**：使用 `kzalloc`/`kfree` 分配迭代器内存。
  - **时间子系统**：使用 `ns2usecs` 转换时间戳。

- **事件定义**
  - 依赖外部定义的 `event_mmiotrace_rw` 和 `event_mmiotrace_map`（通常在 `trace_events` 相关文件中定义）。

## 5. 使用场景

- **硬件驱动调试**：跟踪驱动对 MMIO 寄存器的访问序列，验证读写时序和值是否正确。
- **PCI 设备行为分析**：结合 PCI 设备信息，分析特定设备的 I/O 模式。
- **系统性能分析**：识别频繁的 MMIO 操作或异常访问模式。
- **内核开发与测试**：在开发新驱动或修改现有驱动时，验证 MMIO 行为是否符合预期。
- **故障诊断**：当系统出现硬件相关崩溃或挂起时，通过 mmiotrace 日志定位问题操作。

> **启用方式**：  
> ```bash
> echo mmiotrace > /sys/kernel/debug/tracing/current_tracer
> cat /sys/kernel/debug/tracing/trace_pipe
> ```