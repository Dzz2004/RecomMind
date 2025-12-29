# failslab.c

> 自动生成时间: 2025-12-07 16:00:26
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `failslab.c`

---

# failslab.c 技术文档

## 1. 文件概述

`failslab.c` 是 Linux 内核中用于实现 slab 分配器故障注入（fault injection）机制的核心文件。该机制允许在内存分配过程中人为地模拟分配失败，主要用于测试内核代码在内存不足或分配失败情况下的健壮性和错误处理路径。通过此功能，开发者可以验证内核子系统对 `ENOMEM` 等错误的响应是否正确，从而提升系统稳定性。

## 2. 核心功能

### 主要数据结构
- **`failslab` 全局结构体**  
  包含：
  - `attr`：`struct fault_attr` 类型，用于配置故障注入的行为（如概率、间隔、堆栈跟踪等）
  - `ignore_gfp_reclaim`：布尔值，控制是否忽略带有 `__GFP_DIRECT_RECLAIM` 标志的分配请求
  - `cache_filter`：布尔值，启用后仅对设置了 `SLAB_FAILSLAB` 标志的 slab 缓存进行故障注入

### 主要函数
- **`should_failslab(struct kmem_cache *s, gfp_t gfpflags)`**  
  判断当前 slab 分配请求是否应被强制失败。若满足注入条件，返回 `-ENOMEM`；否则返回 `0`。
  
- **`setup_failslab(char *str)`**  
  内核启动参数解析函数，用于通过 `failslab=` 命令行参数初始化故障注入属性。

- **`failslab_debugfs_init(void)`**（条件编译）  
  在启用了 `CONFIG_FAULT_INJECTION_DEBUG_FS` 时，创建 debugfs 接口，允许运行时动态配置故障注入行为。

### 宏与注解
- **`ALLOW_ERROR_INJECTION(should_failslab, ERRNO)`**  
  注册 `should_failslab` 函数为可被 error-injection 框架拦截的函数，支持通过 ftrace 或其他机制动态修改其返回值。

## 3. 关键实现

- **故障注入条件判断逻辑**：
  1. **跳过 bootstrap cache**：若分配请求来自 `kmem_cache`（即 slab 自身的元数据缓存），则永不注入故障，防止系统初始化失败。
  2. **跳过 `__GFP_NOFAIL` 请求**：该标志表示分配必须成功，因此不进行故障注入。
  3. **可选跳过 reclaim 路径**：若 `ignore_gfp_reclaim` 为真且分配请求包含 `__GFP_DIRECT_RECLAIM`（即允许直接回收内存），则跳过注入，避免干扰内存回收关键路径。
  4. **缓存过滤机制**：若启用 `cache_filter`，仅当目标 slab 缓存设置了 `SLAB_FAILSLAB` 标志时才进行注入，实现细粒度控制。
  5. **静默模式支持**：若分配请求包含 `__GFP_NOWARN`，则传递 `FAULT_NOWARN` 标志给底层故障注入框架，避免打印警告信息（防止死锁，参考 commit 6b9dbedbe349）。

- **debugfs 接口**：
  - 创建 `/sys/kernel/debug/failslab/` 目录
  - 提供 `ignore-gfp-wait`（实际对应 `ignore_gfp_reclaim`）和 `cache-filter` 两个可读写布尔文件，用于运行时调整行为

- **启动参数支持**：  
  通过 `failslab=<attributes>` 内核命令行参数（如 `failslab=probability:10,interval:100`）初始化故障注入策略。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/fault-inject.h>`：提供通用故障注入框架（`struct fault_attr`, `should_fail_ex()` 等）
  - `<linux/error-injection.h>`：提供 `ALLOW_ERROR_INJECTION` 宏
  - `<linux/slab.h>` 和 `"slab.h"`：提供 slab 分配器相关定义（`kmem_cache`, `SLAB_FAILSLAB` 等）
  - `<linux/mm.h>`：提供 GFP 标志定义（如 `__GFP_NOFAIL`, `__GFP_DIRECT_RECLAIM`）

- **内核配置依赖**：
  - `CONFIG_FAULT_INJECTION`：必须启用才能使用故障注入功能
  - `CONFIG_FAULT_INJECTION_DEBUG_FS`：启用 debugfs 接口（可选）

- **与其他模块交互**：
  - 被 slab/slub/slob 分配器调用（通过 `should_failslab()`）
  - 与内核错误注入框架（error-injection）集成，支持动态返回值修改

## 5. 使用场景

- **内核开发与测试**：
  - 验证内核子系统在内存分配失败时的错误处理逻辑（如驱动、文件系统、网络协议栈等）
  - 模拟极端内存压力场景，测试 OOM（Out-Of-Memory）路径的正确性

- **运行时调试**：
  - 通过 debugfs 动态开启/关闭故障注入，无需重启系统
  - 结合 `cache-filter` 精准针对特定 slab 缓存（如 `kmalloc-64`）进行测试

- **自动化测试框架集成**：
  - 作为 LTP（Linux Test Project）、KASAN、KFENCE 等测试工具的底层支持组件
  - 用于 CI/CD 流水线中的健壮性回归测试

- **安全与可靠性研究**：
  - 分析内核在资源受限条件下的行为，发现潜在的内存泄漏或未处理错误路径