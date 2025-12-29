# swap_slots.c

> 自动生成时间: 2025-12-07 17:27:07
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `swap_slots.c`

---

# swap_slots.c 技术文档

## 1. 文件概述

`swap_slots.c` 实现了 Linux 内核中用于管理交换槽（swap slots）的本地 CPU 缓存机制。该机制通过为每个 CPU 维护一个交换槽缓存，避免在每次分配或释放交换槽时频繁获取全局 `swap_info` 锁，从而提升性能。同时，它支持将回收的交换槽批量归还到全局池中，以减少内存碎片。

## 2. 核心功能

### 主要数据结构
- `struct swap_slots_cache`：每个 CPU 的交换槽缓存结构，包含两个数组：
  - `slots`：用于分配的交换槽缓存
  - `slots_ret`：用于暂存待回收的交换槽
- 全局 per-CPU 变量 `swp_slots`：存储各 CPU 的交换槽缓存实例

### 主要函数
- `alloc_swap_slot_cache()`：为指定 CPU 分配交换槽缓存内存
- `free_slot_cache()`：释放指定 CPU 的交换槽缓存
- `refill_swap_slots_cache()`：从全局交换池填充本地缓存
- `free_swap_slot()`：将交换槽返回到本地缓存或直接释放
- `__drain_swap_slots_cache()`：将所有在线 CPU 的缓存中的交换槽归还到全局池
- `drain_slots_cache_cpu()`：清空指定 CPU 的交换槽缓存
- `enable_swap_slots_cache()`：启用交换槽缓存机制
- `disable_swap_slots_cache_lock()` / `reenable_swap_slots_cache_unlock()`：禁用/重新启用缓存
- `check_cache_active()`：根据系统交换页数量动态激活/停用缓存

### 全局变量
- `swap_slot_cache_active`：指示缓存是否当前处于活跃状态
- `swap_slot_cache_enabled`：指示缓存功能是否已启用
- `swap_slot_cache_initialized`：指示缓存子系统是否已完成初始化
- `swap_slots_cache_mutex`：保护缓存操作的互斥锁
- `swap_slots_cache_enable_mutex`：序列化缓存启用/禁用操作的互斥锁

## 3. 关键实现

### 本地缓存设计
- 每个 CPU 拥有两个交换槽数组：
  - `slots`：用于快速分配交换槽（受 `alloc_lock` 互斥锁保护）
  - `slots_ret`：用于暂存待释放的交换槽（受 `free_lock` 自旋锁保护）
- 分配时优先从本地 `slots` 数组获取；若为空，则批量从全局池获取 `SWAP_SLOTS_CACHE_SIZE` 个槽位填充
- 释放时先放入 `slots_ret`，当其满时才批量归还到全局池，有助于减少锁竞争和内存碎片

### 动态启停机制
- 通过 `check_cache_active()` 根据可用交换页数量动态控制缓存活跃状态：
  - 当可用交换页 > `num_online_cpus() * THRESHOLD_ACTIVATE_SWAP_SLOTS_CACHE` 时激活缓存
  - 当可用交换页 < `num_online_cpus() * THRESHOLD_DEACTIVATE_SWAP_SLOTS_CACHE` 时停用缓存
- 停用时会立即清空所有 CPU 缓存中的交换槽并归还到全局池

### CPU 热插拔支持
- 使用 `cpuhp_setup_state()` 注册 CPU 热插拔回调：
  - CPU 上线时调用 `alloc_swap_slot_cache()` 分配缓存
  - CPU 下线时调用 `free_slot_cache()` 释放缓存
- 在清空缓存时使用 `for_each_online_cpu()` 遍历，避免与 CPU 热插拔操作死锁

### 锁设计
- 使用互斥锁（mutex）而非自旋锁，因为分配交换槽可能触发内存回收而睡眠
- 分离分配锁（`alloc_lock`）和释放锁（`free_lock`），提高并发性
- 全局操作使用 `swap_slots_cache_mutex` 保护，启用/禁用操作使用独立的 `swap_slots_cache_enable_mutex`

### 安全标记
- 从全局池分配的交换槽会被标记 `SWAP_HAS_CACHE`，防止被重复分配

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/swap_slots.h>`：定义交换槽缓存接口和数据结构
  - `<linux/cpu.h>`、`<linux/cpumask.h>`：CPU 热插拔和掩码操作
  - `<linux/slab.h>`、`<linux/vmalloc.h>`：内存分配
  - `<linux/mutex.h>`、`<linux/spinlock.h>`：同步原语
  - `<linux/mm.h>`：内存管理相关函数

- **外部函数依赖**：
  - `get_swap_pages()`：从全局交换池批量获取交换槽
  - `swapcache_free_entries()`：将交换槽归还到全局池
  - `has_usable_swap()`：检查是否存在可用交换设备
  - `get_nr_swap_pages()`：获取当前可用交换页数量
  - `zswap_invalidate()`：通知 zswap 无效化交换条目

- **被调用方**：
  - `folio_alloc_swap()`：在页面分配交换槽时使用此缓存机制
  - 交换子系统其他组件通过 `free_swap_slot()` 释放交换槽

## 5. 使用场景

1. **页面交换分配**：当内核需要为匿名页分配交换槽时，优先从本地 CPU 缓存获取，避免全局锁竞争
2. **页面交换释放**：当交换页被换入内存后，其交换槽通过 `free_swap_slot()` 返回到本地缓存
3. **内存压力场景**：在低内存情况下，系统可能停用交换槽缓存以释放更多交换空间
4. **交换设备管理**：
   - `swapon` 时通过 `enable_swap_slots_cache()` 启用缓存
   - `swapoff` 时通过 `__drain_swap_slots_cache()` 确保所有缓存槽位归还
5. **CPU 热插拔**：动态为新上线 CPU 分配缓存，为下线 CPU 释放缓存资源
6. **系统休眠/恢复**：在休眠前确保交换槽缓存被正确清空，避免状态不一致