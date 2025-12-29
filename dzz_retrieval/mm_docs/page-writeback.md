# page-writeback.c

> 自动生成时间: 2025-12-07 16:59:09
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `page-writeback.c`

---

# page-writeback.c 技术文档

## 1. 文件概述

`page-writeback.c` 是 Linux 内核内存管理子系统（MM）中的核心文件，负责实现**脏页回写（dirty page writeback）机制**。该机制用于控制和协调将修改过的页面（即“脏页”）从内存写回到持久化存储（如磁盘）的过程，以确保数据一致性、防止内存耗尽，并在系统负载与 I/O 带宽之间取得平衡。

该文件主要提供以下功能：
- 脏页数量的全局与每 BDI（Backing Device Info）级别的阈值管理
- 脏页生成速率的动态限流（throttling）
- 后台回写线程（如 `writeback` 线程）的触发逻辑
- 支持基于 cgroup 的内存回写控制（当启用 `CONFIG_CGROUP_WRITEBACK` 时）
- 与 `/proc/sys/vm` 中可调参数的交互接口

## 2. 核心功能

### 主要全局变量（可通过 sysctl 调整）
| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `dirty_background_ratio` | 10 | 当脏页占可用内存比例达到此值时，启动后台回写 |
| `vm_dirty_ratio` | 20 | 脏页比例硬上限，超过则阻塞写进程进行同步回写 |
| `dirty_background_bytes` | 0 | 以字节为单位指定后台回写阈值（优先级高于 ratio） |
| `vm_dirty_bytes` | 0 | 以字节为单位指定脏页硬上限（优先级高于 ratio） |
| `dirty_writeback_interval` | 500 (5秒) | 后台回写线程的唤醒间隔（单位：厘秒） |
| `dirty_expire_interval` | 3000 (30秒) | 脏页最大存活时间，超时强制回写 |
| `laptop_mode` | 0 | 笔记本模式开关，减少磁盘活动以省电 |
| `ratelimit_pages` | 32 | 每 CPU 脏页速率限制阈值 |

### 关键数据结构
- **`struct wb_domain`**  
  回写域（writeback domain），用于聚合多个 BDI 的回写状态，支持全局或 per-memcg 的回写控制。
  
- **`struct dirty_throttle_control` (dtc)**  
  脏页限流控制上下文，包含：
  - `avail`：当前可脏化的内存总量
  - `dirty`：当前脏页数量
  - `thresh` / `bg_thresh`：硬/软回写阈值
  - `wb_dirty` / `wb_thresh` / `wb_bg_thresh`：per-BDI 级别的对应值
  - `pos_ratio`：用于计算回写速率的比例因子

- **条件编译支持**  
  通过 `CONFIG_CGROUP_WRITEBACK` 区分是否支持 memcg 级别的回写控制，提供 `GDTC_INIT`、`MDTC_INIT` 等宏及辅助函数（如 `mdtc_valid()`、`wb_min_max_ratio()`）。

### 核心辅助函数（部分在截断代码中未完整显示）
- `node_dirtyable_memory()`：计算指定 NUMA 节点中可用于脏页缓存的内存总量（包括空闲页 + 文件缓存页 - 保留页）。
- `balance_dirty_pages()`：主限流函数，在进程写入时被调用，根据当前脏页水位决定是否休眠或触发回写。
- `balance_dirty_pages_ratelimited()`：带速率限制的脏页平衡入口，避免频繁调用开销。

## 3. 关键实现

### 脏页阈值计算逻辑
- 脏页上限基于 **“dirtyable memory”** 计算，即 `(free pages + file cache pages - kernel reserves)`。
- 支持两种配置方式：**百分比（ratio）** 或 **绝对字节数（bytes）**，后者优先。
- 当启用 `vm_highmem_is_dirtyable` 时，highmem 区域的空闲页也计入 dirtyable memory。

### 动态限流机制
- 使用 **`MAX_PAUSE`（最大 200ms）** 限制单次 `balance_dirty_pages()` 的休眠时间。
- 引入 **`DIRTY_POLL_THRESH`（128KB）** 作为调用间隔优化阈值：若脏页增长过快，则提升休眠时间至最大值。
- 通过 **`BANDWIDTH_INTERVAL`（200ms）** 动态估算存储设备的写入带宽，用于调整回写速率。

### cgroup writeback 支持
- 在 `CONFIG_CGROUP_WRITEBACK` 启用时：
  - 每个 memcg 有独立的 `wb_domain`
  - `dirty_throttle_control` 可关联全局（gdtc）或 memcg（mdtc）上下文
  - BDI 的 min/max_ratio 根据其实际带宽动态缩放，实现公平分配

### 老化与完成计数
- 使用 `fprop_local_percpu` 结构跟踪每个 BDI 的回写完成情况。
- `VM_COMPLETIONS_PERIOD_LEN`（3 秒）定义了回写完成率的老化周期，影响带宽估算的响应速度。

## 4. 依赖关系

- **内存管理核心**：依赖 `<linux/mm.h>`、`<linux/swap.h>`、`<linux/pagevec.h>` 等，与页分配、回收机制紧密集成。
- **VFS 层**：通过 `<linux/fs.h>`、`<linux/pagemap.h>` 与 address_space 和 inode 交互。
- **块设备层**：通过 `<linux/blkdev.h>`、`<linux/backing-dev.h>` 获取 BDI 信息和 I/O 能力。
- **调度与同步**：使用 `<linux/sched.h>`、`<linux/spinlock.h>`、`<linux/timer.h>` 实现休眠、锁和定时器。
- **追踪系统**：集成 `<trace/events/writeback.h>` 提供回写事件追踪点。
- **内部头文件**：包含 `"internal.h"` 获取 MM 子系统内部接口。

## 5. 使用场景

1. **用户空间写入文件**  
   当进程通过 `write()` 修改文件页时，页被标记为脏，随后调用 `balance_dirty_pages_ratelimited()` 触发脏页控制。

2. **内存压力下的页面回收**  
   kswapd 或直接回收路径在需要释放内存时，可能调用回写逻辑清理脏页。

3. **定期后台回写**  
   `writeback` 内核线程按 `dirty_writeback_interval` 周期唤醒，检查并回写超过 `dirty_expire_interval` 的脏页。

4. **系统关闭或 sync 调用**  
   虽然主要同步逻辑在其他文件，但本文件提供的阈值和状态是决策基础。

5. **容器环境中的资源隔离**  
   启用 cgroup writeback 后，不同 memcg 的脏页回写相互隔离，避免一个容器的大量写入影响其他容器性能。

6. **笔记本省电模式**  
   当 `laptop_mode` 启用时，延迟回写以减少磁盘旋转时间，延长电池寿命。