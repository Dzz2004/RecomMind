# vmpressure.c

> 自动生成时间: 2025-12-07 17:33:01
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `vmpressure.c`

---

# vmpressure.c 技术文档

## 1. 文件概述

`vmpressure.c` 实现了 Linux 内核中的虚拟内存压力（VM pressure）监控机制。该机制通过跟踪页面扫描（scanned）与回收（reclaimed）的比率，评估系统或特定内存控制组（memcg）所面临的内存压力程度，并在达到预设阈值时向用户空间发送通知。此功能主要用于支持 cgroup v2 的 memory.pressure 接口，使用户空间程序（如容器运行时）能够感知内存紧张状况并作出响应（如释放缓存、限制内存使用等），从而避免系统进入 OOM（Out-Of-Memory）状态。

## 2. 核心功能

### 主要数据结构

- **`struct vmpressure`**  
  表示一个内存控制组的 VM 压力状态，包含：
  - `tree_scanned` / `tree_reclaimed`：累积的扫描和回收页数（用于子树模式）
  - `sr_lock`：保护上述计数器的自旋锁
  - `events_lock`：保护事件监听列表的互斥锁
  - `events`：注册的事件监听器链表（`struct vmpressure_event`）
  - `work`：延迟处理工作项（`struct work_struct`）

- **`struct vmpressure_event`**  
  表示一个用户空间注册的压力事件监听器，包含：
  - `efd`：关联的 eventfd 上下文，用于通知
  - `level`：触发通知的最低压力等级（low/medium/critical）
  - `mode`：通知模式（default/hierarchy/local）
  - `node`：链表节点

### 主要函数

- **`vmpressure()`**  
  核心接口函数，由内存回收路径（vmscan）调用，传入当前扫描和回收的页数，更新压力统计并可能调度异步处理。

- **`vmpressure_work_fn()`**  
  工作队列回调函数，负责计算压力等级、触发事件通知，并向上遍历内存控制组层级（支持层次化通知）。

- **`vmpressure_calc_level()`**  
  根据 `scanned` 和 `reclaimed` 计算压力百分比，并映射到离散的压力等级（low/medium/critical）。

- **`vmpressure_event()`**  
  遍历当前 memcg 注册的所有事件监听器，根据压力等级、通知模式和层级关系决定是否触发 eventfd 信号。

- **辅助函数**  
  - `vmpressure_parent()`：获取父级 memcg 对应的 `vmpressure` 结构
  - `vmpressure_level()`：将压力百分比映射为枚举等级
  - `work_to_vmpressure()`：从 work_struct 转换为 vmpressure 指针

### 关键常量

- **`vmpressure_win`**：压力计算窗口大小（512 页），用于速率限制和平均
- **`vmpressure_level_med`**（60）和 **`vmpressure_level_critical`**（95）：中等和严重压力的百分比阈值
- **`vmpressure_level_critical_prio`**：基于扫描优先级判断严重压力的备用机制

## 3. 关键实现

### 压力等级计算
压力通过公式 `pressure = (scanned - reclaimed) * 100 / scanned` 计算（实际实现考虑了 `reclaimed > scanned` 的边界情况）。该值反映回收效率：值越高表示回收越困难，内存压力越大。

### 异步处理机制
`vmpressure()` 函数仅累加计数器并调度 `vmpressure_work_fn` 工作项，避免在内存回收关键路径上执行复杂逻辑。工作项在后台执行压力计算和通知。

### 层级化通知（Hierarchy）
支持三种通知模式：
- **`local`**：仅当前 memcg 触发
- **`hierarchy`**：当前及所有祖先 memcg 均可触发
- **`default`（no passthrough）**：当前 memcg 触发后，阻止向祖先传递（避免重复通知）

### 窗口与速率限制
使用固定窗口（`vmpressure_win`）累积扫描/回收页数，确保压力评估具有时间局部性，同时防止高频通知。

### 与 vmscan 集成
直接接收 vmscan 传递的 `scanned` 和 `reclaimed` 参数，紧密耦合内存回收行为，提供实时压力反馈。

## 4. 依赖关系

- **内存控制组（memcg）**：通过 `mem_cgroup` 结构关联 `vmpressure` 实例，依赖 cgroup 子系统（`memory_cgrp_subsys`）
- **内存管理核心（mm）**：依赖 `vmscan` 回收路径调用 `vmpressure()`，使用 `SWAP_CLUSTER_MAX` 常量
- **事件通知机制**：使用 `eventfd` 向用户空间发送信号
- **内核同步原语**：使用 `spinlock`（`sr_lock`）和 `mutex`（`events_lock`）保护数据
- **通用内核组件**：依赖 `workqueue`（延迟处理）、`slab`（内存分配）、`printk`（调试）

## 5. 使用场景

1. **容器内存管理**  
   容器运行时（如 Docker、systemd-nspawn）通过监听 cgroup v2 的 `memory.pressure` 文件，在内存压力升高时主动释放缓存或限制应用内存使用，避免被 OOM killer 终止。

2. **系统级内存优化**  
   用户空间守护进程（如 earlyoom、nohang）利用压力事件提前干预，例如在 `critical` 压力下终止低优先级进程。

3. **内核子系统集成**  
   其他内核模块可通过注册 `vmpressure` 事件监听器，在内存紧张时调整自身行为（如降低缓存占用）。

4. **传统 cgroup v1 支持**  
   通过 `tree` 参数兼容旧版 subtree 压力报告模式（尽管主要面向 cgroup v2 设计）。