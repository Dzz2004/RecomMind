# locking\spinlock.c

> 自动生成时间: 2025-10-25 14:53:30
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `locking\spinlock.c`

---

# `locking/spinlock.c` 技术文档

## 1. 文件概述

`locking/spinlock.c` 是 Linux 内核中实现自旋锁（spinlock）和读写锁（rwlock）通用逻辑的核心源文件。该文件主要为对称多处理器（SMP）系统以及启用了锁调试（如 `DEBUG_SPINLOCK` 或 `DEBUG_LOCK_ALLOC`）的配置提供锁操作的通用实现。在单处理器（UP）且未启用调试的配置下，相关操作通常以内联函数形式直接展开，不依赖此文件。

该文件通过宏生成机制构建了多种锁操作函数，包括普通加锁、中断屏蔽加锁、软中断屏蔽加锁等变体，并支持可抢占内核（`CONFIG_PREEMPT`）下的友好调度行为。此外，文件还处理了与内存映射 I/O 写屏障（`CONFIG_MMIOWB`）相关的每 CPU 状态管理。

## 2. 核心功能

### 数据结构
- `struct mmiowb_state`（条件定义）：用于跟踪每 CPU 的内存映射 I/O 写屏障状态，仅在 `CONFIG_MMIOWB` 启用且架构未提供自有实现时定义。
  - 全局符号：`DEFINE_PER_CPU(struct mmiowb_state, __mmiowb_state)`，并通过 `EXPORT_PER_CPU_SYMBOL` 导出。

### 主要函数（通过宏生成或显式定义）
- **自旋锁（spinlock）操作**：
  - `_raw_spin_lock` / `__raw_spin_lock`
  - `_raw_spin_lock_irq` / `__raw_spin_lock_irq`
  - `_raw_spin_lock_irqsave` / `__raw_spin_lock_irqsave`
  - `_raw_spin_lock_bh` / `__raw_spin_lock_bh`
  - `_raw_spin_trylock` / `__raw_spin_trylock`
  - 对应的解锁函数（如 `_raw_spin_unlock` 等）

- **读写锁（rwlock）操作**（非 `PREEMPT_RT` 配置下）：
  - `_raw_read_lock` / `__raw_read_lock` 等读操作
  - `_raw_write_lock` / `__raw_write_lock` 等写操作
  - `_raw_write_lock_nested`：支持锁类嵌套的写锁获取

- **架构相关松弛函数（默认回退）**：
  - `arch_read_relax`, `arch_write_relax`, `arch_spin_relax`：默认定义为 `cpu_relax()`，允许架构提供特定优化。

## 3. 关键实现

### 锁操作的通用构建机制
- 使用 `BUILD_LOCK_OPS(op, locktype)` 宏统一生成加锁函数族（`_lock`, `_lock_irqsave`, `_lock_irq`, `_lock_bh`）。
- 每个加锁函数采用 **“尝试-失败-松弛-重试”** 循环：
  1. 禁用抢占（`preempt_disable()`）
  2. 尝试原子获取锁（调用 `do_raw_##op##_trylock`）
  3. 若成功则退出；否则恢复抢占（`preempt_enable()`）
  4. 调用架构特定的 `arch_##op##_relax()`（默认为 `cpu_relax()`）以降低 CPU 占用
- 在 `_irqsave` 和 `_bh` 变体中，正确处理中断和软中断的屏蔽与恢复。

### 可抢占性与调试兼容性
- 当启用 `CONFIG_DEBUG_LOCK_ALLOC` 或未定义 `CONFIG_GENERIC_LOCKBREAK` 时，**不使用**上述通用构建逻辑，而是依赖头文件（`spinlock_api_smp.h` / `rwlock_api_smp.h`）中的内联实现，以满足锁依赖验证器（lockdep）对中断状态的假设。
- 在通用构建路径中，循环内显式启用/禁用抢占，使得长时间自旋时当前 CPU 可被抢占，提升系统响应性。

### 函数导出与内联控制
- 所有 `_raw_*` 函数均通过条件编译（如 `#ifndef CONFIG_INLINE_SPIN_LOCK`）决定是否以内联或 `noinline` 形式定义。
- 非内联版本使用 `EXPORT_SYMBOL` 导出，供模块或其他编译单元调用。
- 解锁函数同样受 `CONFIG_UNINLINE_SPIN_UNLOCK` 等配置项控制。

### 嵌套写锁支持
- `_raw_write_lock_nested` 函数在非调试模式下退化为普通写锁；在调试模式下保留子类参数以支持锁类验证。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/spinlock.h>`：核心锁类型和 API 声明
  - `<linux/preempt.h>`：抢占控制原语（`preempt_disable/enable`）
  - `<linux/interrupt.h>`：中断控制（`local_irq_save/restore`, `local_bh_disable`）
  - `<linux/debug_locks.h>`：调试锁相关宏
  - `<linux/export.h>`：符号导出宏
  - `<linux/linkage.h>`：链接属性定义

- **架构依赖**：
  - 依赖架构层提供底层原子操作（如 `do_raw_spin_trylock` 的实际实现通常在 `arch/*/include/asm/spinlock.h` 中）
  - 架构可覆盖 `arch_*_relax` 宏以优化自旋行为
  - 某些架构的性能分析工具（如 `profile_pc`）依赖此文件中函数的栈帧结构稳定性

- **配置依赖**：
  - `CONFIG_SMP`：SMP 支持是此文件生效的前提
  - `CONFIG_PREEMPT` / `CONFIG_PREEMPT_RT`：影响锁实现路径选择
  - `CONFIG_DEBUG_LOCK_ALLOC`：决定是否使用通用构建逻辑
  - `CONFIG_MMIOWB`：控制每 CPU `mmiowb_state` 的定义

## 5. 使用场景

- **内核同步原语实现**：作为自旋锁和读写锁的通用后端，被内核各子系统（如内存管理、文件系统、设备驱动、网络栈等）广泛用于保护临界区。
- **中断上下文同步**：通过 `_irq` / `_irqsave` 变体，在中断处理程序与进程上下文之间提供同步。
- **软中断同步**：通过 `_bh` 变体，防止软中断与进程上下文同时访问共享数据。
- **实时内核适配**：在 `PREEMPT_RT` 补丁集下，读写锁实现被替换，但自旋锁仍由此文件提供（部分路径被绕过）。
- **锁调试与验证**：配合 `lockdep` 子系统，在开发和调试阶段检测死锁、锁顺序违规等问题。
- **性能关键路径**：通过可配置的内联/非内联策略，在代码大小与性能之间取得平衡。