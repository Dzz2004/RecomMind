# hwpoison-inject.c

> 自动生成时间: 2025-12-07 16:08:30
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `hwpoison-inject.c`

---

# hwpoison-inject.c 技术文档

## 1. 文件概述

`hwpoison-inject.c` 是 Linux 内核中用于**软件模拟硬件内存故障（Hardware Poison）注入与清除**的调试模块。该模块通过 debugfs 接口，允许具有 `CAP_SYS_ADMIN` 权限的用户空间程序向指定物理页帧号（PFN）注入或清除“坏页”标记（`PG_hwpoison`），主要用于测试内核内存错误处理机制（如 `memory_failure()` 路径）在无真实硬件故障情况下的行为。

## 2. 核心功能

### 主要函数
- **`hwpoison_inject(void *data, u64 val)`**  
  向指定 PFN 注入硬件内存故障。执行权限检查、页有效性验证、过滤器判断后调用 `memory_failure()`。
  
- **`hwpoison_unpoison(void *data, u64 val)`**  
  清除指定 PFN 的硬件内存故障标记，调用 `unpoison_memory()`。

- **`pfn_inject_init(void)`**  
  模块初始化函数，创建 debugfs 目录及控制文件。

- **`pfn_inject_exit(void)`**  
  模块退出函数，清理 debugfs 条目并禁用过滤器。

### 主要数据结构/全局变量
- **`hwpoison_dir`**：debugfs 目录入口（`/sys/kernel/debug/hwpoison/`）。
- **`hwpoison_fops` / `unpoison_fops`**：debugfs 文件操作接口，分别用于写入 corrupt/unpoison 请求。
- **`hwpoison_filter_enable` 等全局变量**：控制 hwpoison 过滤器的行为参数（通过 debugfs 可配置）。

## 3. 关键实现

### 故障注入流程 (`hwpoison_inject`)
1. **权限与有效性校验**：仅允许 `CAP_SYS_ADMIN` 用户操作，并确保输入 PFN 有效（`pfn_valid()`）。
2. **页类型过滤**：
   - 若 `hwpoison_filter_enable=0`，跳过过滤直接注入。
   - 否则，仅对 **LRU 页**、**HugeTLB 页** 或 **空闲 Buddy 页** 允许注入，其他非 LRU 页（如 slab、匿名映射未加入 LRU 的页）被忽略。
3. **过滤器检查**：调用 `hwpoison_filter()` 执行基于设备号、页标志、memcg 等条件的精细过滤（racy check，最终由 `memory_failure()` 在持锁下确认）。
4. **触发内存故障处理**：调用 `memory_failure(pfn, MF_SW_SIMULATED)`，其中 `MF_SW_SIMULATED` 表示软件模拟故障。

### 故障清除流程 (`hwpoison_unpoison`)
- 直接调用通用接口 `unpoison_memory()` 清除 `PG_hwpoison` 标记，适用于已标记为坏页的页面。

### DebugFS 接口设计
- **`corrupt-pfn`**：写入 PFN 触发注入（权限 `0200`，仅写）。
- **`unpoison-pfn`**：写入 PFN 触发清除（权限 `0200`，仅写）。
- **过滤器控制参数**：提供 `corrupt-filter-*` 系列文件动态配置过滤条件（如设备号、页标志掩码、memcg ID）。

## 4. 依赖关系

- **核心内存管理子系统**：
  - `<linux/mm.h>`、`<linux/pagemap.h>`：页结构、PFN 转换、LRU 状态检查。
  - `<linux/hugetlb.h>`：HugeTLB 页支持。
  - `"internal.h"`：内核 MM 内部接口（如 `shake_folio()`、`hwpoison_filter()`）。
- **内存故障处理框架**：
  - `memory_failure()` 和 `unpoison_memory()`：定义于 `mm/memory-failure.c`，负责实际坏页处理逻辑。
- **DebugFS 基础设施**：依赖 `<linux/debugfs.h>` 提供用户态交互接口。
- **可选依赖**：
  - `CONFIG_MEMCG`：若启用内存控制组，则支持基于 memcg 的过滤。

## 5. 使用场景

- **内核开发与测试**：
  - 验证 `memory_failure()` 路径对不同类型页面（匿名页、文件页、HugeTLB 页等）的处理正确性。
  - 测试 hwpoison 过滤器逻辑（如基于设备、memcg 的隔离策略）。
- **系统可靠性验证**：
  - 模拟硬件内存故障，评估应用程序和内核在坏页注入下的恢复能力（如进程终止、页面迁移）。
- **故障注入工具集成**：
  - 作为底层接口被用户态工具（如 `mce-inject` 或自定义脚本）调用，实现可控的内存错误注入实验。