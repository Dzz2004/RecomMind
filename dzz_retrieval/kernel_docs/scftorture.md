# scftorture.c

> 自动生成时间: 2025-10-25 15:55:14
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `scftorture.c`

---

# scftorture.c 技术文档

## 文件概述

`scftorture.c` 是 Linux 内核中的一个压力测试（torture test）模块，专门用于对 `smp_call_function()` 及其相关函数族（如 `smp_call_function_single()`、`resched_cpu()` 等）进行高强度、长时间的功能正确性和稳定性验证。该模块通过多线程并发调用各种 SMP（对称多处理）函数接口，结合 CPU 热插拔、随机延迟、权重控制等机制，检测潜在的竞态条件、死锁、内存泄漏或调用失败等问题。

## 核心功能

### 主要数据结构

- **`struct scf_statistics`**  
  每个测试线程的统计信息结构，记录各类 SMP 调用的执行次数，包括：
  - `resched_cpu()` 调用次数
  - 单 CPU 无等待/等待调用次数（含离线 CPU 情况）
  - 多 CPU / 全 CPU 调用次数
  - RPC（远程过程调用）形式的单 CPU 调用

- **`struct scf_selector`**  
  用于随机选择测试原语（primitive）的权重配置结构，包含：
  - 权重值（`scfs_weight`）
  - 原语类型（如 `SCF_PRIM_SINGLE`）
  - 是否等待完成（`scfs_wait`）

- **`struct scf_check`**  
  用于在调用者与目标 CPU 处理函数之间传递状态和同步信息，包含完成量（`completion`）和 CPU 标识等。

### 主要函数

- **`scf_torture_stats_print()`**  
  汇总并打印所有线程的统计信息，包括调用次数、错误计数（如内存屏障错误、分配失败等），并在检测到错误时添加 `!!!` 警告前缀。

- **`scf_torture_stats()`**  
  后台内核线程，按 `stat_interval` 参数周期性调用 `scf_torture_stats_print()` 输出统计信息。

- **`scf_sel_add()`**  
  向测试原语选择数组 `scf_sel_array` 中添加一个带权重的测试项，用于后续的随机调度。

- **`scf_sel_dump()`**  
  打印各测试原语的权重百分比分布，便于调试和验证配置。

### 模块参数（通过 `torture_param` 定义）

- `holdoff`：启动测试前的延迟时间（秒）
- `nthreads`：测试线程数（默认为 CPU 数）
- `onoff_holdoff` / `onoff_interval`：CPU 热插拔控制
- `weight_*`：各类 SMP 调用的测试权重（如 `weight_single_wait`）
- `verbose`：启用详细调试日志
- `use_cpus_read_lock`：是否使用 `cpus_read_lock()` 排除热插拔干扰
- `shutdown`：测试结束后是否触发内核关机（内置模块默认启用）

## 关键实现

### 随机原语选择机制

模块定义了 5 种基本 SMP 调用原语（`resched_cpu`、`single`、`single_rpc`、`many`、`all`），每种支持“等待”和“非等待”两种模式（`resched_cpu` 和 `single_rpc` 除外）。通过 `scf_sel_add()` 根据用户配置的 `weight_*` 参数构建加权选择数组 `scf_sel_array`，测试线程在运行时根据随机数按权重选择具体调用方式，实现覆盖全面的压力测试。

### 错误检测与统计

- 使用 `atomic_t` 变量（如 `n_errs`、`n_mb_in_errs`）记录各类错误。
- 通过 `per_cpu(scf_invoked_count, cpu)` 统计每个 CPU 被调用的总次数。
- 在统计输出中，若存在错误且未启用 KASAN，则将 `bangstr` 设为 `"!!! "` 以高亮警告。
- 支持内存分配失败（`n_alloc_errs`）和内存屏障顺序错误（`n_mb_in_errs`/`n_mb_out_errs`）的检测。

### 同步与生命周期管理

- 使用 `completion` 机制确保单 CPU 等待型调用能正确同步。
- 通过 `torture_must_stop()` 和 `torture_shutdown_absorb()` 集成内核 torture 测试框架的标准停止流程。
- 利用 `cpus_read_lock()`（可选）避免在 CPU 热插拔期间执行关键 SMP 调用，提高测试稳定性。

### 权重归一化与溢出防护

在 `scf_sel_add()` 中，通过 `WARN_ON_ONCE` 检查：
- 权重总和是否会导致百分比计算溢出（使用 `100000 * weight` 进行定点数计算）
- 数组边界是否越界
- 原语索引是否有效

确保配置安全可靠。

## 依赖关系

- **内核核心子系统**：
  - `smp.h`：提供 `smp_call_function*()` 系列函数
  - `cpu.h` / `notifier.h`：支持 CPU 热插拔（`onoff` 功能）
  - `rcupdate.h` / `srcu.h`：可能用于内部同步（虽未直接使用，但 torture 框架依赖）
  - `torture.h`：集成标准 torture 测试框架（线程管理、停止机制、统计等）

- **内存与调度**：
  - `slab.h`：用于动态内存分配
  - `sched.h` / `kthread.h`：创建和管理测试线程

- **调试支持**：
  - `KASAN`：影响错误计数逻辑（分配错误在 KASAN 下不计入）
  - `verbose` 模式依赖 `pr_alert` 输出详细日志

## 使用场景

- **内核开发与回归测试**：在修改 SMP 相关代码（如 IPI 处理、CPU 热插拔、调度器交互）后运行此模块，验证功能正确性。
- **稳定性压力测试**：在真实或虚拟多核系统上长时间运行，暴露低概率并发 bug。
- **新平台验证**：在新硬件架构上启用此模块，确保 `smp_call_function` 实现符合预期。
- **CI/CD 集成**：作为内核持续集成测试的一部分，自动检测 SMP 调用路径的回归问题。

该模块通常通过内核配置 `CONFIG_SCF_TORTURE_TEST` 启用，并可通过模块参数精细控制测试行为，适用于开发、测试和生产前验证阶段。