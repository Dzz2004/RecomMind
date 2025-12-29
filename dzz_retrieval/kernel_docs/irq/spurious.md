# irq\spurious.c

> 自动生成时间: 2025-10-25 14:09:47
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\spurious.c`

---

# `irq/spurious.c` 技术文档

## 1. 文件概述

`irq/spurious.c` 是 Linux 内核中断子系统中的一个关键组件，负责处理**伪中断**（spurious interrupts）和**错误路由中断**（misrouted interrupts）。当硬件中断未被任何中断处理程序正确处理（返回 `IRQ_NONE`）时，内核会怀疑该中断是伪中断或被错误路由到当前 IRQ 线。该文件实现了检测、诊断和恢复机制，包括：

- 统计未处理中断次数并判断是否为“卡住”的 IRQ
- 在启用 `irqfixup` 选项时尝试在其他 IRQ 线上查找真正的中断源（中断错位恢复）
- 定期轮询被禁用的伪中断线以尝试恢复共享中断设备
- 提供诊断信息（如调用栈和注册的处理函数列表）

该机制对于提高系统在硬件或固件存在缺陷时的鲁棒性至关重要。

## 2. 核心功能

### 主要全局变量
- `irqfixup`：模块参数，控制伪中断修复行为（0=禁用，1=仅对未处理中断尝试修复，2=对标记为 `IRQF_IRQPOLL` 的中断也尝试修复）
- `poll_spurious_irq_timer`：定时器，用于定期轮询被标记为 `IRQS_SPURIOUS_DISABLED` 的中断线
- `irq_poll_cpu`：记录当前正在执行轮询任务的 CPU ID
- `irq_poll_active`：原子变量，防止多个 CPU 同时执行轮询

### 主要函数
- `irq_wait_for_poll(struct irq_desc *desc)`  
  等待轮询操作完成，避免与轮询线程竞争。在 SMP 系统中自旋等待 `IRQS_POLL_INPROGRESS` 标志清除。
  
- `try_one_irq(struct irq_desc *desc, bool force)`  
  尝试在指定中断描述符上执行中断处理。跳过 PER_CPU、嵌套线程和显式标记为轮询的中断。若中断被禁用，则仅在 `force=true` 时处理。支持共享中断的 `IRQS_PENDING` 重试机制。

- `misrouted_irq(int irq)`  
  遍历所有 IRQ（除 0 和当前 IRQ），调用 `try_one_irq()` 尝试在其他线上找到真正的中断源。用于中断错位恢复。

- `poll_spurious_irqs(struct timer_list *unused)`  
  定时器回调函数，轮询所有被标记为 `IRQS_SPURIOUS_DISABLED` 的中断线，强制尝试处理（`force=true`）。

- `__report_bad_irq()` / `report_bad_irq()`  
  打印伪中断诊断信息，包括中断号、错误返回值、调用栈及所有注册的处理函数。

- `try_misrouted_irq()`  
  根据 `irqfixup` 级别判断是否应尝试中断错位恢复。

- `note_interrupt(struct irq_desc *desc, irqreturn_t action_ret)`  
  中断处理结果分析入口。统计未处理中断，触发伪中断检测、诊断和恢复逻辑。

## 3. 关键实现

### 伪中断检测机制
- 当 `note_interrupt()` 收到 `IRQ_NONE` 时，会递增中断描述符的未处理计数。
- 若在 100,000 次中断中有 99,900 次未处理，则判定该 IRQ “卡住”，打印诊断信息并建议使用 `irqpoll` 启动参数。
- 诊断信息包含所有注册的处理函数地址及符号名，便于调试。

### 中断错位恢复（Misrouted IRQ Recovery）
- 通过 `irqfixup` 内核参数启用（启动时传入 `irqfixup=1` 或 `2`）。
- 当当前 IRQ 未被处理时，遍历其他所有 IRQ 线，尝试调用其处理函数（`try_one_irq()`）。
- 仅适用于共享中断（`IRQF_SHARED`）且非 PER_CPU/嵌套线程类型。
- 使用 `IRQS_POLL_INPROGRESS` 标志防止与正常中断处理冲突。

### 轮询恢复机制
- 被判定为伪中断的 IRQ 会被标记 `IRQS_SPURIOUS_DISABLED` 并禁用。
- 启用 `irqfixup` 时，启动定时器 `poll_spurious_irq_timer`（间隔 100ms）。
- 定时器回调 `poll_spurious_irqs()` 遍历所有 `IRQS_SPURIOUS_DISABLED` 的 IRQ，强制尝试处理（即使已禁用）。
- 通过 `local_irq_disable/enable()` 保证轮询期间本地中断关闭，避免嵌套。

### SMP 安全性
- 使用 `irq_poll_active` 原子变量确保同一时间仅一个 CPU 执行轮询。
- `irq_wait_for_poll()` 在 SMP 下自旋等待轮询完成，防止死锁。
- 所有关键操作均在 `desc->lock` 保护下进行。

### 线程化中断处理支持
- 若主处理函数返回 `IRQ_WAKE_THREAD`，则延迟伪中断判断至下一次硬件中断，以等待线程处理结果。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/irq.h>`、`<linux/interrupt.h>`：中断核心数据结构和 API
  - `<linux/timer.h>`：定时器支持（用于轮询）
  - `"internals.h"`：中断子系统内部接口

- **内核配置依赖**：
  - `CONFIG_SMP`：影响 `irq_wait_for_poll()` 的实现
  - `irqfixup` 模块参数：控制恢复行为

- **与其他模块交互**：
  - 被通用中断处理流程（如 `handle_irq_event()`）调用
  - 与中断描述符管理（`irq_desc`）紧密集成
  - 依赖内核打印和栈回溯机制（`dump_stack()`）

## 5. 使用场景

1. **硬件/固件缺陷处理**：  
   当 BIOS 或硬件错误地将设备中断路由到错误的 IRQ 线时，通过 `irqfixup` 机制尝试在其他线上找到真正的处理函数。

2. **共享中断线故障恢复**：  
   在多个设备共享同一 IRQ 线时，若其中一个设备故障产生持续中断但无处理函数响应，内核可禁用该线并定期轮询，避免系统被中断风暴拖垮。

3. **系统调试与诊断**：  
   当出现“nobody cared”中断错误时，自动打印详细的处理函数列表和调用栈，帮助开发者定位问题设备或驱动。

4. **高可用性系统**：  
   在无法立即修复硬件问题的生产环境中，通过 `irqpoll` 启动参数启用轮询机制，维持系统基本运行。

5. **传统 PC 兼容性**：  
   特别处理 IRQ 0（系统定时器），因其在传统 PC 架构中的特殊地位，即使在 `irqfixup=2` 模式下也始终尝试恢复。