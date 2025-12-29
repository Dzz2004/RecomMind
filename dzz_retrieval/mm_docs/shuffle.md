# shuffle.c

> 自动生成时间: 2025-12-07 17:21:18
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `shuffle.c`

---

# shuffle.c 技术文档

## 1. 文件概述

`shuffle.c` 实现了 Linux 内核内存管理子系统中的**页面分配随机化（Page Allocation Shuffling）**功能。该机制通过在内存初始化阶段对空闲页面链表进行 Fisher-Yates 洗牌操作，降低物理页帧分配的可预测性，从而增强系统安全性，抵御基于内存布局预测的攻击（如堆喷射、地址泄露等）。该功能默认关闭，可通过内核启动参数 `shuffle=1` 启用。

## 2. 核心功能

### 数据结构与全局变量
- `page_alloc_shuffle_key`：静态分支键（static key），用于运行时启用/禁用洗牌逻辑，减少未启用时的性能开销。
- `shuffle_param`：模块参数布尔值，控制是否启用洗牌功能。
- `shuffle_param_ops`：自定义模块参数操作集，用于处理 `shuffle` 参数的设置和读取。

### 主要函数
- `shuffle_param_set()`：解析并设置 `shuffle` 内核参数，若启用则激活 `page_alloc_shuffle_key`。
- `shuffle_valid_page()`：验证指定 PFN 的页面是否满足洗牌条件（属于 buddy 系统、同 zone、空闲、相同 order 和 migratetype）。
- `__shuffle_zone()`：对指定内存区域（zone）执行 Fisher-Yates 洗牌算法，随机交换同阶空闲页面。
- `__shuffle_free_memory()`：遍历节点（pgdat）中所有 zone，依次调用 `shuffle_zone()` 进行洗牌。
- `shuffle_pick_tail()`：提供轻量级随机位生成器，用于在分配时决定从链表头部还是尾部取页（增强运行时随机性）。

## 3. 关键实现

### 洗牌算法（Fisher-Yates）
- **粒度**：以 `SHUFFLE_ORDER`（通常为 0，即单页）为单位进行洗牌。
- **范围**：遍历 zone 内所有按 order 对齐的 PFN，对每个有效页面 `page_i` 随机选择另一个有效页面 `page_j` 进行交换。
- **有效性校验**：通过 `shuffle_valid_page()` 确保交换双方均为 buddy 系统管理的空闲页，且具有相同的迁移类型（migratetype）。
- **重试机制**：最多尝试 `SHUFFLE_RETRY`（10 次）寻找有效的随机目标页，避免因内存空洞导致失败。
- **锁优化**：每处理 100 个页面后释放 zone 自旋锁并调度，防止长时间持锁影响系统响应。

### 随机性来源
- 使用 `get_random_long()` 获取高质量伪随机数作为洗牌索引。
- `shuffle_pick_tail()` 使用无锁的 64 位随机状态生成器，每次返回最低位并右移，用于运行时分配策略的微调。

### 安全性权衡
- 明确承认不消除模运算偏差（modulo bias）或 PRNG 偏差，目标是“提高攻击门槛”而非完美随机。
- 仅在内存初始化阶段（`__meminit`）执行一次洗牌，不影响运行时分配性能。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/mm.h>`、`<linux/mmzone.h>`：内存管理核心数据结构（`struct zone`, `struct page`）。
  - `<linux/random.h>`：提供 `get_random_long()` 和 `get_random_u64()`。
  - `"internal.h"`、`"shuffle.h"`：内核 MM 子系统内部接口及洗牌功能声明。
- **功能依赖**：
  - Buddy 分配器：依赖 `PageBuddy()`、`buddy_order()` 等接口判断页面状态。
  - 页面迁移类型（Migratetype）：确保洗牌不破坏不同迁移类型页面的隔离。
  - 静态分支（Static Keys）：通过 `static_branch_enable()` 动态启用洗牌路径。

## 5. 使用场景

- **安全加固**：在需要防范物理地址预测攻击的场景（如虚拟化宿主机、安全敏感设备）中启用，增加攻击者利用内存布局漏洞的难度。
- **内核初始化**：在 `free_area_init_core()` 等内存子系统初始化流程中调用 `__shuffle_free_memory()`，对初始空闲内存进行一次性洗牌。
- **运行时分配辅助**：`shuffle_pick_tail()` 被页面分配器调用，决定从空闲链表头/尾取页，进一步增加分配时序的不可预测性。
- **调试支持**：通过 `pr_debug()` 输出洗牌失败或迁移类型不匹配的日志，便于问题诊断（需开启 `DEBUG_SHUFFLE`）。