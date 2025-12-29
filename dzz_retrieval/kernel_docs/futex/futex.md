# futex\futex.h

> 自动生成时间: 2025-10-25 13:32:59
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `futex\futex.h`

---

# `futex/futex.h` 技术文档

## 1. 文件概述

`futex/futex.h` 是 Linux 内核中快速用户空间互斥锁（Fast Userspace muTEX，简称 futex）子系统的核心头文件之一。该文件定义了 futex 机制所依赖的关键数据结构、宏、标志位以及内部函数接口，用于支持用户空间的高效同步原语（如互斥锁、条件变量等）。它为 futex 的等待、唤醒、优先级继承（PI）、超时处理、NUMA 感知等高级功能提供底层抽象和操作接口。

## 2. 核心功能

### 主要数据结构

- **`struct futex_hash_bucket`**  
  表示 futex 哈希桶，用于组织等待同一 futex 地址的多个等待者。包含自旋锁、等待者计数器和优先级链表（`plist_head`）。

- **`struct futex_pi_state`**  
  用于实现优先级继承（Priority Inheritance）机制的状态结构，包含 RT 互斥锁、所有者任务、引用计数和关联的 futex 键。

- **`struct futex_q`**  
  表示一个等待 futex 的任务队列项，包含任务指针、哈希桶锁、futex 键、PI 状态、RT 等待器、位掩码唤醒参数等字段。

- **`union futex_key`**  
  抽象表示 futex 的唯一标识（由地址、映射对象和偏移组成），用于哈希和匹配。

### 关键宏与标志

- **大小标志**：`FLAGS_SIZE_8/16/32/64`，用于指定 futex 操作的数据宽度。
- **共享标志**：`FLAGS_SHARED`，区分进程私有与共享内存中的 futex。
- **时钟标志**：`FLAGS_CLOCKRT`，表示使用 `CLOCK_REALTIME` 而非 `CLOCK_MONOTONIC`。
- **其他标志**：`FLAGS_HAS_TIMEOUT`、`FLAGS_NUMA`、`FLAGS_STRICT` 等用于控制行为。

### 核心函数接口

- **标志转换函数**：
  - `futex_to_flags()`：将传统 futex 操作码（如 `FUTEX_WAIT`）转换为内部标志。
  - `futex2_to_flags()`：将新式 futex2 标志转换为内部标志。
- **验证函数**：
  - `futex_flags_valid()`：验证 futex 大小标志是否合法（目前仅支持 32 位）。
  - `futex_validate_input()`：检查用户传入的值是否超出 futex 数据宽度。
- **哈希与匹配**：
  - `futex_hash()`：根据 `futex_key` 计算哈希桶。
  - `futex_match()`：比较两个 `futex_key` 是否相等。
- **队列操作**：
  - `futex_queue()` / `futex_unqueue()`：将等待项加入/移出哈希桶。
  - `__futex_queue()` / `__futex_unqueue()`：底层无锁版本。
- **PI 相关**：
  - `futex_lock_pi_atomic()`：原子地尝试获取 PI futex。
  - `get_pi_state()` / `put_pi_state()`：管理 `futex_pi_state` 引用计数。
- **辅助函数**：
  - `get_futex_key()`：从用户地址解析出内核可识别的 `futex_key`。
  - `futex_setup_timer()`：设置高精度定时器用于超时等待。
  - `fault_in_user_writeable()`：确保用户地址可写（用于写前预检）。

## 3. 关键实现

### Futex 标志系统
通过位掩码统一处理传统 futex（`FUTEX_*`）和新式 futex2（`FUTEX2_*`）的选项，将操作语义（如私有/共享、时钟类型、数据大小）编码为内部 `flags`，便于跨系统调用重启时保留上下文。

### 哈希桶与等待队列
- 所有 futex 等待项按 `futex_key` 哈希到全局哈希表中的桶（`futex_hash_bucket`）。
- 每个桶使用自旋锁保护，内部用优先级链表（`plist`）维护等待任务，支持优先级继承调度。
- `futex_q` 结构体替代标准等待队列项，支持按 key 精确唤醒。

### 优先级继承（PI）支持
- `futex_pi_state` 封装 RT 互斥锁，当高优先级任务阻塞于低优先级任务持有的 PI futex 时，临时提升持有者优先级。
- `futex_unqueue_pi()` 在唤醒 PI futex 时特殊处理，避免竞争。

### 内存与架构适配
- 通过 `CONFIG_MMU` 条件编译，NOMMU 系统忽略 `FLAGS_SHARED`（无进程地址空间隔离）。
- `in_compat_syscall()` 与 `CONFIG_64BIT` 联合限制 64 位 futex 在 32 位兼容模式下不可用。
- `__randomize_layout` 用于结构体布局随机化，增强安全性。

### 实时内核（PREEMPT_RT）支持
- 在 `CONFIG_PREEMPT_RT` 下引入 `rcuwait` 机制（`requeue_wait` 字段），用于 `futex_requeue_pi` 的安全同步。
- 包含 `<linux/rcuwait.h>` 以支持 RCU 等待原语。

### 故障注入
- `CONFIG_FAIL_FUTEX` 支持 futex 故障注入测试，通过 `should_fail_futex()` 模拟失败路径。

## 4. 依赖关系

- **内核子系统**：
  - `<linux/rtmutex.h>`：提供 RT 互斥锁实现，用于 PI futex。
  - `<linux/sched/wake_q.h>`：提供批量唤醒队列（`wake_q_head`）。
  - `<linux/compat.h>`：处理 32/64 位兼容性。
  - `<linux/hrtimer.h>`（间接）：通过 `futex_setup_timer` 使用高精度定时器。
- **架构相关**：
  - `<asm/futex.h>`：包含架构特定的 futex 原子操作（如 `futex_atomic_cmpxchg_inatomic`）。
- **配置选项**：
  - `CONFIG_PREEMPT_RT`：启用实时内核特定逻辑。
  - `CONFIG_FAIL_FUTEX`：启用故障注入。
  - `CONFIG_MMU`：影响共享标志定义。
  - `CONFIG_SMP`：影响等待者计数器的原子操作和内存屏障。

## 5. 使用场景

- **用户空间同步原语实现**：glibc 的 `pthread_mutex_t`、`pthread_cond_t` 等基于 futex 构建，通过 `futex()` 系统调用进入内核。
- **PI 互斥锁**：实时应用使用 `FUTEX_LOCK_PI` 避免优先级反转。
- **带超时的等待**：如 `pthread_mutex_timedlock()` 调用 `futex_wait` 并设置 `hrtimer`。
- **Requeue 操作**：`FUTEX_CMP_REQUEUE` 用于条件变量广播，将等待者从一个 futex 迁移到另一个。
- **NUMA 感知调度**：`FUTEX2_NUMA` 标志用于优化多 NUMA 节点系统的唤醒局部性。
- **内核自检与测试**：通过故障注入（`CONFIG_FAIL_FUTEX`）验证 futex 错误处理路径。