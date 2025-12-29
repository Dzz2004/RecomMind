# irq\resend.c

> 自动生成时间: 2025-10-25 14:07:32
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\resend.c`

---

# `irq/resend.c` 技术文档

## 1. 文件概述

`irq/resend.c` 实现了 Linux 内核中断子系统中的 **中断重发（IRQ resend）机制**。该机制用于在中断未能被及时处理或需要重新触发时，尝试通过硬件重触发（retrigger）或软件任务（tasklet）方式重新投递中断。此功能主要用于支持那些无法通过硬件自动重发中断的中断控制器，以及用于调试和错误注入场景。

## 2. 核心功能

### 主要函数

| 函数名 | 功能说明 |
|--------|--------|
| `check_irq_resend(struct irq_desc *desc, bool inject)` | 检查是否需要重发中断，并尝试通过硬件重触发或软件重发机制重新投递中断。 |
| `irq_sw_resend(struct irq_desc *desc)` | 在不支持硬件重触发时，将中断描述符加入软件重发队列，并调度 tasklet 处理。 |
| `resend_irqs(struct tasklet_struct *unused)` | tasklet 回调函数，遍历软件重发队列并调用对应中断的 `handle_irq` 处理函数。 |
| `clear_irq_resend(struct irq_desc *desc)` | 从软件重发队列中移除指定中断描述符。 |
| `irq_resend_init(struct irq_desc *desc)` | 初始化中断描述符的重发链表节点。 |
| `irq_inject_interrupt(unsigned int irq)`（仅当 `CONFIG_GENERIC_IRQ_INJECTION` 启用） | 用于调试目的，主动注入指定中断。 |

### 主要数据结构

- `irq_resend_list`：全局哈希链表头，用于维护待软件重发的中断描述符。
- `irq_resend_lock`：保护 `irq_resend_list` 的原始自旋锁（raw spinlock）。
- `resend_tasklet`：用于异步执行软件重发逻辑的 tasklet。
- `desc->resend_node`：`struct irq_desc` 中用于链入 `irq_resend_list` 的节点。

## 3. 关键实现

### 中断重发条件判断

- **仅边沿触发中断支持重发**：`check_irq_resend()` 会跳过电平触发中断（`irq_settings_is_level()`），因为这类中断在电平有效期间会由硬件自动保持。
- **避免重复重发**：若中断已处于 `IRQS_REPLAY` 状态，则返回 `-EBUSY`，防止重复处理。
- **注入模式支持**：当 `inject == true`（如 `irq_inject_interrupt` 调用）时，即使 `IRQS_PENDING` 未置位也会尝试重发。

### 硬件 vs 软件重发

- **优先尝试硬件重触发**：调用 `try_retrigger()`，先检查中断芯片是否提供 `irq_retrigger` 回调；若无，则尝试层级中断域的 `irq_chip_retrigger_hierarchy`。
- **回退到软件重发**：若硬件重触发不可用且 `CONFIG_HARDIRQS_SW_RESEND` 已启用，则调用 `irq_sw_resend()` 将中断加入软件队列。

### 软件重发机制

- 使用 **tasklet** 在软中断上下文中执行重发，避免在硬中断或原子上下文中直接调用 `handle_irq`。
- 通过 `hlist` 管理待重发的 `irq_desc`，并用 `raw_spinlock` 保证并发安全。
- 支持嵌套线程中断（nested threaded IRQ）：若目标中断是嵌套线程类型，则重发其父中断。

### 安全性检查

- `handle_enforce_irqctx()` 确保中断可在非中断上下文中安全注入。
- 对嵌套线程中断，验证 `parent_irq` 有效性，防止空指针解引用。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/irq.h>`、`<linux/interrupt.h>`：提供中断核心 API 和数据结构。
  - `"internals.h"`：内核中断子系统内部头文件，包含 `irq_desc` 等私有定义。
- **配置依赖**：
  - `CONFIG_HARDIRQS_SW_RESEND`：启用软件重发机制。
  - `CONFIG_IRQ_DOMAIN_HIERARCHY`：支持层级中断域的重触发。
  - `CONFIG_GENERIC_IRQ_INJECTION`：启用 `irq_inject_interrupt()` 调试接口。
- **与其他模块交互**：
  - 依赖中断控制器驱动实现的 `irq_retrigger` 回调。
  - 与通用中断处理框架（如 `handle_irq`）紧密集成。

## 5. 使用场景

1. **中断丢失恢复**：在某些硬件平台或虚拟化环境中，中断可能因竞争条件或延迟而丢失，重发机制可提高可靠性。
2. **调试与测试**：通过 `irq_inject_interrupt()` 主动注入中断，用于测试中断处理路径、驱动健壮性或错误恢复逻辑。
3. **不支持硬件重触发的平台**：如部分 ARM SoC 或旧式 x86 芯片组，依赖软件 tasklet 机制模拟中断重发。
4. **电源管理（suspend/resume）**：在系统恢复过程中，可能需要重放挂起期间未处理的边沿中断。
5. **嵌套中断处理**：在 threaded IRQ 架构中，确保子中断能通过父中断正确重发。