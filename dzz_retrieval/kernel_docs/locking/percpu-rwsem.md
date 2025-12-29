# locking\percpu-rwsem.c

> 自动生成时间: 2025-10-25 14:44:20
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `locking\percpu-rwsem.c`

---

# `locking/percpu-rwsem.c` 技术文档

## 1. 文件概述

`percpu-rwsem.c` 实现了一种高性能的**每 CPU 读写信号量**（per-CPU read-write semaphore），专为读多写少场景优化。该机制允许多个读者在无写者时并发执行（无需全局同步），而写者则需等待所有活跃读者退出后才能获得独占访问权。其核心思想是利用 per-CPU 计数器记录读者数量，避免读者之间的原子操作竞争，从而显著提升可扩展性。

## 2. 核心功能

### 主要数据结构
- **`struct percpu_rw_semaphore`**：每 CPU 读写信号量控制结构，包含：
  - `read_count`：per-CPU 整型变量，记录各 CPU 上的活跃读者数量
  - `rss`：`rcu_sync` 结构，用于协调 RCU 与写者临界区
  - `writer`：`rcuwait` 结构，供写者等待读者退出
  - `waiters`：等待队列头，管理阻塞的读者/写者
  - `block`：原子变量，标志写者是否已请求独占（1=阻塞新读者）
  - `dep_map`：Lockdep 调试用的依赖映射

### 主要函数
| 函数 | 功能 |
|------|------|
| `__percpu_init_rwsem()` | 初始化 per-CPU 读写信号量 |
| `percpu_free_rwsem()` | 释放信号量资源 |
| `__percpu_down_read()` | 获取读者锁（支持尝试模式） |
| `percpu_down_write()` | 获取写者锁（阻塞式） |
| `percpu_up_write()` | 释放写者锁 |
| `percpu_is_read_locked()` | 检查是否存在活跃读者 |
| `__percpu_down_read_trylock()` | 尝试快速获取读者锁 |
| `__percpu_down_write_trylock()` | 尝试快速获取写者锁 |
| `readers_active_check()` | 检查所有读者是否已退出 |

## 3. 关键实现

### 3.1 读者快速路径（Fast Path）
- **无锁计数**：读者通过 `this_cpu_inc(*sem->read_count)` 原子增加本 CPU 计数（禁用抢占保证 CPU 亲和性）
- **内存屏障**：`smp_mb()` 确保 `block` 标志的读取顺序
- **乐观检查**：若 `block==0` 则直接进入临界区；否则回退并唤醒写者

### 3.2 写者同步机制
1. **阻塞新读者**：通过 `rcu_sync_enter()` 通知读者走慢路径，并设置 `block=1`
2. **等待活跃读者**：使用 `rcuwait_wait_event()` 轮询 `readers_active_check()` 直到所有 per-CPU 计数归零
3. **释放写锁**：
   - 清除 `block` 标志（`atomic_set_release` 保证临界区内存可见性）
   - 唤醒等待队列中的一个任务（FIFO 顺序）
   - 调用 `rcu_sync_exit()` 允许读者恢复快速路径

### 3.3 等待队列管理
- **自定义唤醒函数** `percpu_rwsem_wake_function()`：
  - 使用 `WQ_FLAG_EXCLUSIVE` 保证 FIFO
  - 通过 `WQ_FLAG_CUSTOM` 区分读者/写者
  - 返回值控制唤醒数量：读者可批量唤醒，写者仅唤醒一个

### 3.4 内存序保障
- **读者-写者同步**：通过四组内存屏障配对（代码注释 A/B/C/D）确保：
  - 读者增量操作与写者 `block` 检查的顺序性
  - 写者释放锁后读者能观察到临界区修改

## 4. 依赖关系

| 依赖模块 | 用途 |
|----------|------|
| `linux/percpu.h` | 提供 per-CPU 变量分配/访问接口 |
| `linux/rcupdate.h` | 通过 `rcu_sync` 协调 RCU 与写者临界区 |
| `linux/rcuwait.h` | 实现写者等待读者退出的睡眠机制 |
| `linux/lockdep.h` | 提供锁依赖验证（DEBUG_LOCK_ALLOC） |
| `linux/atomic.h` | 原子操作（`block` 标志管理） |
| `trace/events/lock.h` | 锁竞争事件追踪 |

## 5. 使用场景

- **文件系统**：如 `alloc_super()` 中用于保护超级块操作
- **内存管理**：需要频繁读取但偶尔修改的全局状态（如内存策略）
- **网络子系统**：路由表等读多写少的数据结构保护
- **性能关键路径**：替代传统读写锁以消除读者间的原子操作开销

> **典型工作流**：  
> 1. 读者通过 `__percpu_down_read()` 快速进入（无全局锁）  
> 2. 写者调用 `percpu_down_write()` 阻塞新读者并等待现存读者退出  
> 3. 写者完成操作后 `percpu_up_write()` 恢复读者快速路径  
> 4. 所有操作通过 RCU 机制保证内存一致性