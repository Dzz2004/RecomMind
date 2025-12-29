# kallsyms_selftest.c

> 自动生成时间: 2025-10-25 14:14:43
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kallsyms_selftest.c`

---

# kallsyms_selftest.c 技术文档

## 文件概述

`kallsyms_selftest.c` 是 Linux 内核中用于对 `kallsyms`（内核符号表）子系统进行功能验证和性能测试的自检模块。该文件通过一系列测试用例，验证 `kallsyms_lookup_name()`、`kallsyms_on_each_symbol()` 和 `kallsyms_on_each_match_symbol()` 等核心接口的正确性，并评估其性能表现。同时，该模块还计算内核符号表的压缩率，用于评估符号表存储效率。

## 核心功能

### 主要数据结构

- **`struct test_stat`**  
  用于记录测试过程中的统计信息，包括最小/最大耗时、调用次数、地址记录、累计时间等。

- **`struct test_item`**  
  定义测试项，包含符号名称和预期地址，用于验证符号解析的准确性。

- **`test_items[]`**  
  预定义的测试符号数组，涵盖静态函数、全局函数、弱符号以及（在 `CONFIG_KALLSYMS_ALL` 启用时）全局和静态变量。

### 主要函数

- **`test_kallsyms_basic_function()`**  
  核心功能测试函数，验证三种符号查找接口对预定义符号的解析是否准确。

- **`test_kallsyms_compression_ratio()`**  
  计算并输出内核符号表的压缩率，包括原始符号名总长度与压缩后实际占用内存的对比。

- **`test_perf_kallsyms_lookup_name()`**  
  性能测试：遍历所有符号，测量 `kallsyms_lookup_name()` 的单次调用耗时（最小值、最大值、平均值）。

- **`test_perf_kallsyms_on_each_symbol()`**  
  性能测试：使用一个不可能匹配的“桩”符号名，遍历整个符号表，测量 `kallsyms_on_each_symbol()` 的总耗时。

- **`test_perf_kallsyms_on_each_match_symbol()`**  
  性能测试：使用桩符号名调用 `kallsyms_on_each_match_symbol()`，测量其遍历耗时。

- **`lookup_name()` / `find_symbol()` / `match_symbol()`**  
  回调函数，分别用于上述性能测试和功能验证中，收集统计信息。

- **`match_cleanup_name()`**  
  辅助函数，用于处理 Clang LTO（Link Time Optimization）编译时生成的带 `.llvm.` 后缀的符号名，确保测试兼容性。

## 关键实现

1. **测试符号设计**  
   模块内部定义了多种类型的符号（静态函数、全局函数、弱函数、BSS/DATA 段变量），覆盖 `kallsyms` 支持的不同符号类别。变量测试仅在 `CONFIG_KALLSYMS_ALL` 配置启用时进行。

2. **桩符号（Stub Symbol）生成**  
   为避免在性能测试中因匹配成功而提前退出，模块构造一个由数字 `'4'` 组成的符号名（符号名不能以数字开头，确保无匹配）。其长度设为所有符号名的平均长度，使测试更贴近真实场景。

3. **压缩率计算逻辑**  
   - 通过 `kallsyms_on_each_symbol()` 累加所有符号名长度得到原始大小（`total_len`）。
   - 手动解析 `kallsyms_names[]` 数组的压缩格式（支持 7/15 位长度编码），计算压缩后数据区大小（`off - num`，排除长度字段）。
   - 加上 `kallsyms_token_table[]` 和 `kallsyms_token_index[]` 的内存开销，得到总压缩大小（`total_size`）。
   - 最终计算压缩率：`ratio = (total_size * 10000) / total_len`，以百分比形式输出（保留两位小数）。

4. **LTO 符号兼容性处理**  
   在启用 Clang LTO 时，编译器会为符号添加 `.llvm.<hash>` 后缀。`match_cleanup_name()` 函数通过检查前缀是否匹配原始符号名，确保测试能正确识别这类符号。

5. **性能测量方法**  
   使用 `ktime_get_ns()` 获取纳秒级高精度时间戳，在每次符号查找前后采样，计算单次或整体操作耗时。

## 依赖关系

- **头文件依赖**：
  - `<linux/kallsyms.h>`：提供 `kallsyms_lookup_name()`、`kallsyms_on_each_symbol()` 等公共接口。
  - `"kallsyms_internal.h"`：访问 `kallsyms` 内部数据结构（如 `kallsyms_names`、`kallsyms_token_table`、`kallsyms_num_syms`），用于压缩率计算。
  - `"kallsyms_selftest.h"`：可能包含测试相关的辅助定义（本文件未展示其内容）。
  - 其他通用内核头文件（`init.h`, `module.h`, `random.h`, `sched/clock.h`, `kthread.h`, `vmalloc.h`）。

- **配置依赖**：
  - `CONFIG_KALLSYMS`：必须启用，否则 `kallsyms` 功能不可用。
  - `CONFIG_KALLSYMS_ALL`：控制是否测试变量符号。
  - `CONFIG_LTO_CLANG`：影响符号名后缀处理逻辑。

- **函数依赖**：
  - 依赖 `vmalloc_noprof` 和 `vfree` 作为已知内核函数符号进行测试。
  - 使用 `is_ksym_addr()` 判断地址是否属于内核符号范围（代码片段末尾未完整展示）。

## 使用场景

- **内核开发与调试**：在开发或修改 `kallsyms` 相关代码后，加载此模块可快速验证符号解析功能是否正常。
- **性能基准测试**：评估不同内核版本或配置下 `kallsyms` 接口的性能变化，特别是在符号表规模较大时的查找效率。
- **压缩算法验证**：监控符号表压缩率，帮助优化内核镜像大小（尤其在嵌入式或资源受限环境中）。
- **CI/CD 自动化测试**：可集成到内核持续集成流程中，作为 `kallsyms` 子系统的回归测试用例。
- **LTO 编译兼容性验证**：确保在使用 Clang LTO 编译内核时，`kallsyms` 仍能正确处理修饰后的符号名。