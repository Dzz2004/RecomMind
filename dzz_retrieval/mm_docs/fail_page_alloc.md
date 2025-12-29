# fail_page_alloc.c

> 自动生成时间: 2025-12-07 15:59:52
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `fail_page_alloc.c`

---

# `fail_page_alloc.c` 技术文档

## 1. 文件概述

`fail_page_alloc.c` 是 Linux 内核中用于实现内存页分配故障注入（fault injection）机制的模块。该文件通过模拟 `alloc_pages()` 等内存分配函数失败的情形，帮助开发者测试内核在内存分配失败时的错误处理路径和健壮性。它基于通用的故障注入框架（`fault-inject.h`），并提供了运行时可配置的控制参数。

## 2. 核心功能

### 数据结构
- **`fail_page_alloc`**：全局静态结构体，包含：
  - `attr`：标准的 `fault_attr` 故障属性，用于控制故障注入的概率、间隔等行为。
  - `ignore_gfp_highmem`：布尔值，若为 `true`，则忽略带有 `__GFP_HIGHMEM` 标志的分配请求。
  - `ignore_gfp_reclaim`：布尔值，若为 `true`，则忽略带有 `__GFP_DIRECT_RECLAIM` 标志的分配请求。
  - `min_order`：无符号 32 位整数，指定只对大于等于此阶数（order）的页分配进行故障注入。

### 主要函数
- **`setup_fail_page_alloc(char *str)`**：内核启动参数解析函数，用于通过 `fail_page_alloc=` 内核命令行参数初始化故障属性。
- **`should_fail_alloc_page(gfp_t gfp_mask, unsigned int order)`**：核心判断函数，根据当前分配请求的 `gfp_mask` 和 `order` 决定是否注入分配失败。
- **`fail_page_alloc_debugfs(void)`**（条件编译）：在启用了 `CONFIG_FAULT_INJECTION_DEBUG_FS` 时，创建 debugfs 接口以动态调整故障注入参数。

### 宏与注解
- **`__setup("fail_page_alloc=", setup_fail_page_alloc)`**：注册内核启动参数处理函数。
- **`ALLOW_ERROR_INJECTION(should_fail_alloc_page, TRUE)`**：声明该函数可被错误注入框架拦截，支持动态启用/禁用。

## 3. 关键实现

- **故障注入条件判断**：
  - 仅当请求的 `order >= min_order` 时才考虑注入失败。
  - 若分配标志包含 `__GFP_NOFAIL`（表示分配必须成功），则跳过注入。
  - 可选择性忽略高内存（`__GFP_HIGHMEM`）或直接回收（`__GFP_DIRECT_RECLAIM`）类型的分配请求。
  - 若分配请求设置了 `__GFP_NOWARN`，则传递 `FAULT_NOWARN` 标志给底层故障注入逻辑，避免打印警告信息。

- **debugfs 接口**（当 `CONFIG_FAULT_INJECTION_DEBUG_FS` 启用时）：
  - 在 `/sys/kernel/debug/fail_page_alloc/` 目录下创建以下可调参数：
    - `ignore-gfp-wait`：对应 `ignore_gfp_reclaim`（注：变量名与 debugfs 名称存在历史命名差异，实际控制 `__GFP_DIRECT_RECLAIM`）。
    - `ignore-gfp-highmem`：控制是否忽略高内存分配。
    - `min-order`：设置最小注入阶数。

- **故障决策**：最终调用 `should_fail_ex()`，传入按 `order` 缩放的权重（`1 << order`），使得大块内存分配更容易被注入失败，更贴近真实场景。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/fault-inject.h>`：提供通用故障注入框架（如 `fault_attr`, `should_fail_ex`, `setup_fault_attr` 等）。
  - `<linux/error-injection.h>`：提供 `ALLOW_ERROR_INJECTION` 宏，用于支持动态错误注入。
  - `<linux/mm.h>`：提供内存管理相关定义，如 `gfp_t`、`__GFP_*` 标志等。

- **内核配置依赖**：
  - 必须启用 `CONFIG_FAULT_INJECTION` 才能使用基础故障注入功能。
  - `CONFIG_FAULT_INJECTION_DEBUG_FS` 控制是否生成 debugfs 接口。

- **调用关系**：
  - `should_fail_alloc_page()` 被内存分配路径（如 `__alloc_pages()`）调用，通常通过 `__alloc_pages_nodemask()` 中的 `should_fail_alloc_page()` 检查点触发。

## 5. 使用场景

- **内核开发与测试**：
  - 开发者可通过内核启动参数（如 `fail_page_alloc=10`）或 debugfs 接口动态开启页分配失败模拟，验证内核路径在内存不足时的行为。
  - 用于测试文件系统、网络子系统、设备驱动等模块在 `kmalloc`/`alloc_pages` 失败时的错误恢复能力。

- **压力测试与稳定性验证**：
  - 结合 `failslab` 等其他故障注入模块，构建全面的内存压力测试环境。
  - 验证 `__GFP_NOFAIL` 等关键分配是否被正确处理，防止死锁或崩溃。

- **调试特定问题**：
  - 当怀疑某段代码未正确处理内存分配失败时，可针对性地启用该模块，复现并定位问题。