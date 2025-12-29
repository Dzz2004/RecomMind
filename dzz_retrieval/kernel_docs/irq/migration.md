# irq\migration.c

> 自动生成时间: 2025-10-25 14:03:53
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\migration.c`

---

# `irq/migration.c` 技术文档

## 1. 文件概述

`irq/migration.c` 是 Linux 内核中断子系统中用于处理中断亲和性（IRQ affinity）迁移的核心实现文件。该文件主要负责在 CPU 热插拔（如 CPU offline）或显式调用 `irq_set_affinity()` 时，安全、正确地将中断从一个或多个 CPU 迁移到新的目标 CPU 集合。其关键职责包括：

- 清理因 CPU 下线而无法完成的中断迁移状态；
- 执行实际的中断亲和性重定向操作；
- 确保在迁移过程中中断行为的正确性，尤其对边沿触发（edge-triggered）中断避免硬件异常。

## 2. 核心功能

### 主要函数

| 函数名 | 功能简述 |
|--------|---------|
| `irq_fixup_move_pending()` | 在 CPU 即将离线时，清理中断描述符中未完成的迁移状态（`move pending`），根据参数决定是否强制清除。 |
| `irq_move_masked_irq()` | 执行已标记为“待迁移”的中断的实际亲和性设置操作，调用底层 `irq_chip` 的 `irq_set_affinity` 回调。 |
| `__irq_move_irq()` | 对未被禁用的中断执行完整的迁移流程：临时屏蔽 → 执行迁移 → 恢复屏蔽状态。 |

### 关键数据结构（间接使用）

- `struct irq_desc`：中断描述符，包含中断状态、锁、pending_mask 等。
- `struct irq_data`：中断数据结构，包含芯片操作回调、亲和性掩码、状态标志（如 `IRQD_SETAFFINITY_PENDING`）。
- `cpumask_t pending_mask`：记录待迁移的目标 CPU 掩码。

## 3. 关键实现

### 中断迁移状态管理

- **`IRQD_SETAFFINITY_PENDING` 标志**：当调用 `irq_set_affinity()` 但无法立即执行（如中断正在处理中），内核会设置此标志，并将目标 CPU 掩码存入 `desc->pending_mask`。
- **迁移触发时机**：通常在中断处理结束（EOI）或显式调用迁移函数时，检查该标志并执行实际迁移。

### `irq_fixup_move_pending()` 的逻辑

- 若未设置 `move pending`，直接返回 `false`。
- 检查 `pending_mask` 中是否还有**在线 CPU**：
  - 若无（即所有目标 CPU 都已离线），则清除 `move pending` 标志，返回 `false`。
  - 若有，且 `force_clear == true`，则强制清除标志，但仍返回 `true`（表示存在有效目标）。
- 返回值用于判断是否仍需将中断迁移到其他在线 CPU。

### `irq_move_masked_irq()` 的安全迁移机制

- **前提条件**：调用者必须已持有 `desc->lock`，且中断已被屏蔽（由 `__irq_move_irq` 保证）。
- **关键步骤**：
  1. 清除 `move pending` 标志；
  2. 跳过 per-CPU 中断（不应迁移）；
  3. 若 `pending_mask` 为空或芯片不支持 `irq_set_affinity`，直接退出；
  4. 调用 `irq_do_set_affinity()` 执行底层亲和性设置；
  5. 若返回 `-EBUSY`（如向量资源繁忙），重新设置 `move pending`，保留 `pending_mask`，推迟迁移；
  6. 成功则清空 `pending_mask`。

### `__irq_move_irq()` 的屏蔽保护

- 对非屏蔽中断，**临时屏蔽** → 执行迁移 → **恢复原状态**。
- 防止在迁移过程中（尤其是边沿触发中断）因硬件寄存器重编程导致中断丢失或重复触发。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/irq.h>`、`<linux/interrupt.h>`：提供中断核心 API 和数据结构定义。
  - `"internals.h"`：包含中断子系统内部函数和宏（如 `irq_do_set_affinity`、状态操作宏）。
- **功能依赖**：
  - **中断域（IRQ Domain）层次结构**：通过 `irq_desc_get_irq_data()` 自动处理层次化中断控制器（如级联 GIC）。
  - **CPU 热插拔子系统**：`cpu_online_mask` 用于判断目标 CPU 是否在线。
  - **底层中断控制器驱动**：依赖 `struct irq_chip` 的 `irq_mask`/`irq_unmask`/`irq_set_affinity` 回调实现。

## 5. 使用场景

1. **CPU 热插拔（Offline）**：
   - 当 CPU 被关闭时，内核调用 `irq_fixup_move_pending()` 清理分配给该 CPU 但尚未迁移的中断。
   - 若存在其他在线目标 CPU，则后续通过 `__irq_move_irq()` 完成实际迁移。

2. **用户空间或内核动态设置亲和性**：
   - 通过 `/proc/irq/<N>/smp_affinity` 或 `irq_set_affinity()` API 修改中断目标 CPU。
   - 若中断处于活跃状态，设置 `move pending` 标志，待安全时机（如中断处理结束）由 `__irq_move_irq()` 执行迁移。

3. **中断负载均衡**：
   - 内核调度器或中断均衡器（如 `irqbalance`）调整中断分布时，触发亲和性迁移流程。

4. **虚拟化与容器环境**：
   - 在 vCPU 热插拔或 NUMA 拓扑变化时，确保设备中断正确绑定到新拓扑中的在线 CPU。