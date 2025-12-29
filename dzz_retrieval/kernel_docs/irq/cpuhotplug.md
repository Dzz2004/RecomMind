# irq\cpuhotplug.c

> 自动生成时间: 2025-10-25 13:49:28
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `irq\cpuhotplug.c`

---

# `irq/cpuhotplug.c` 技术文档

## 1. 文件概述

`irq/cpuhotplug.c` 实现了通用的 CPU 热插拔（hotplug）过程中中断迁移（IRQ migration）的核心逻辑。当某个 CPU 被下线（offline）时，该文件负责将原本绑定到该 CPU 的中断迁移到其他在线 CPU 上；当 CPU 重新上线（online）时，则恢复受管理中断（managed IRQs）的亲和性设置。此机制确保系统在 CPU 动态增删过程中中断仍能被正确处理，避免中断丢失或服务中断。

该代码最初从 ARM 架构实现中抽象而来，现已成为通用中断子系统的一部分，适用于支持 CPU 热插拔的多种架构。

## 2. 核心功能

### 主要函数

- **`irq_needs_fixup(struct irq_data *d)`**  
  判断当前中断是否需要在 CPU 下线时进行迁移。依据有效亲和性掩码（effective affinity mask）是否包含当前正在下线的 CPU。

- **`migrate_one_irq(struct irq_desc *desc)`**  
  执行单个中断描述符的迁移操作：检查是否可迁移、处理挂起的亲和性变更、必要时强制迁移到在线 CPU，并调用底层芯片驱动设置新亲和性。

- **`irq_migrate_all_off_this_cpu(void)`**  
  遍历所有活跃中断，对每个中断调用 `migrate_one_irq()`，完成当前 CPU 下线前的中断迁移工作。

- **`hk_should_isolate(struct irq_data *data, unsigned int cpu)`**  
  判断是否应因 housekeeping 隔离策略将中断迁移到指定 CPU。用于支持受管理中断的 CPU 隔离场景。

- **`irq_restore_affinity_of_irq(struct irq_desc *desc, unsigned int cpu)`**  
  在 CPU 上线时，为受管理中断恢复其原始亲和性设置，必要时重新启动中断。

- **`irq_affinity_online_cpu(unsigned int cpu)`**  
  在指定 CPU 上线时，遍历所有中断并调用 `irq_restore_affinity_of_irq()`，恢复受管理中断的亲和性。

### 关键数据结构依赖

- `struct irq_desc`：中断描述符，包含中断状态、操作函数、亲和性等信息。
- `struct irq_data`：中断数据结构，封装芯片相关数据和亲和性掩码。
- `cpumask`：CPU 位掩码，用于表示中断亲和性及在线 CPU 集合。

## 3. 关键实现

### 中断迁移触发条件

中断仅在满足以下条件时才需要迁移：
- 非 per-CPU 中断；
- 中断已启动（`irqd_is_started`）；
- 当前 CPU 包含在中断的有效亲和性掩码中（通过 `irq_needs_fixup` 判断）。

### 亲和性掩码处理

- 若架构支持 `CONFIG_GENERIC_IRQ_EFFECTIVE_AFF_MASK`，优先使用有效亲和性掩码；若为空（某些芯片未实现），则回退到通用亲和性掩码。
- 若亲和性掩码中除当前下线 CPU 外无其他在线 CPU，则强制将中断迁移到任意在线 CPU（`cpu_online_mask`）。
- 对于**受管理中断**（managed IRQ），若无法找到有效目标 CPU，则直接关闭中断（`irq_shutdown_and_deactivate`）并标记为“管理关闭”。

### 中断上下文安全处理

- 对于不能在进程上下文迁移的中断（`!irq_can_move_pcntxt`），在设置新亲和性前先调用 `irq_mask` 屏蔽中断，设置完成后再 `irq_unmask`，避免迁移过程中中断丢失。
- 调用 `irq_force_complete_move` 确保之前在硬中断上下文中发起的迁移操作完成清理。

### Housekeeping 隔离支持

当启用 `HK_TYPE_MANAGED_IRQ`（通过内核启动参数如 `isolcpus=domain,managed_irq`），系统会尝试将受管理中断限制在 housekeeping CPU 上。`hk_should_isolate` 用于判断是否应将中断迁移到即将上线的 housekeeping CPU。

### 错误处理与回退

- 若 `irq_do_set_affinity` 返回 `-ENOSPC`（如向量资源不足），尝试将中断亲和性扩展至所有在线 CPU。
- 使用 `pr_warn_ratelimited` 避免因频繁失败导致日志泛滥。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/interrupt.h>`、`<linux/irq.h>`：提供中断子系统核心 API。
  - `<linux/sched/isolation.h>`：提供 housekeeping 和 CPU 隔离相关接口。
  - `"internals.h"`：中断子系统内部头文件，包含描述符锁、迁移辅助函数等。

- **内核子系统依赖**：
  - **通用中断子系统（Generic IRQ）**：依赖 `irq_set_affinity`、`irq_data` 管理、亲和性掩码机制。
  - **CPU 热插拔框架**：本文件函数由 CPU 热插拔通知链（如 `CPU_DEAD`、`CPU_ONLINE`）调用。
  - **调度器隔离机制**：通过 `housekeeping_cpumask()` 获取隔离 CPU 集合。

- **配置选项依赖**：
  - `CONFIG_GENERIC_IRQ_EFFECTIVE_AFF_MASK`：决定是否使用有效亲和性掩码。
  - `CONFIG_GENERIC_IRQ_CHIP` / 架构特定 IRQ 芯片实现：提供 `irq_set_affinity` 回调。

## 5. 使用场景

1. **CPU 下线（Offline）**  
   当系统通过 `echo 0 > /sys/devices/system/cpu/cpuX/online` 或内核主动下线 CPU 时，调用 `irq_migrate_all_off_this_cpu()`，将所有绑定到该 CPU 的中断迁移到其他在线 CPU。

2. **CPU 上线（Online）**  
   当 CPU 重新上线时，调用 `irq_affinity_online_cpu()`，恢复受管理中断的原始亲和性，确保中断负载均衡或符合隔离策略。

3. **实时/低延迟系统中的 CPU 隔离**  
   在使用 `isolcpus=domain,managed_irq` 的系统中，非 housekeeping CPU 上的受管理中断会在 CPU 上线时被自动迁移到 housekeeping CPU，减少对隔离 CPU 的干扰。

4. **系统从 S3 休眠恢复**  
   虽然休眠恢复主要通过 `resume_device_irqs()` 处理，但本文件逻辑会跳过 `IRQS_SUSPENDED` 状态的中断，避免重复操作。

5. **中断亲和性动态调整失败后的恢复**  
   当因资源不足（如 MSI 向量耗尽）导致亲和性设置失败时，自动回退到全在线 CPU 掩码，保证中断可投递。