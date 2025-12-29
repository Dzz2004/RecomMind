# ksyms_common.c

> 自动生成时间: 2025-10-25 14:28:41
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `ksyms_common.c`

---

# ksyms_common.c 技术文档

## 1. 文件概述

`ksyms_common.c` 是 Linux 内核中 `kernel/kallsyms.c` 的拆分文件，用于存放与内核符号表（kallsyms）相关的通用函数实现。该文件中的代码不依赖于 `CONFIG_KALLSYMS` 配置选项，主要提供判断是否允许向用户空间暴露内核符号地址值的安全策略逻辑，用于在不同安全级别下控制对内核指针值的访问权限。

## 2. 核心功能

- **`kallsyms_for_perf(void)`**  
  静态内联函数，用于判断当前系统是否因性能监控（perf）需求而放宽对内核符号地址的访问限制。

- **`kallsyms_show_value(const struct cred *cred)`**  
  公共函数，根据系统安全策略（如 `kptr_restrict` 和 `sysctl_perf_event_paranoid`）以及调用者的凭证（credentials），决定是否允许显示内核符号的实际地址值。

## 3. 关键实现

- **安全策略分级控制**：  
  函数 `kallsyms_show_value()` 依据全局变量 `kptr_restrict` 的值实施三级访问控制：
  - **`kptr_restrict == 0`**：默认允许显示地址，但若启用了 `CONFIG_PERF_EVENTS` 且 `sysctl_perf_event_paranoid <= 1`，则直接返回 `true`；否则继续检查。
  - **`kptr_restrict == 1`**：仅当调用者具备 `CAP_SYSLOG` 能力（且不触发审计）时允许显示。
  - **`kptr_restrict >= 2`**：一律禁止显示内核地址，返回 `false`。

- **perf 事件集成**：  
  `kallsyms_for_perf()` 函数通过检查 `sysctl_perf_event_paranoid` 内核参数（仅在 `CONFIG_PERF_EVENTS` 启用时有效）判断是否因性能分析需求而临时放宽限制。当该值 ≤ 1 时，允许非特权用户访问符号地址，以支持 perf 工具正常工作。

- **能力检查优化**：  
  使用 `security_capable(..., CAP_OPT_NOAUDIT)` 进行能力检查，避免在审计日志中记录此类常规权限查询，提升性能并减少日志噪音。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/kallsyms.h>`：提供 `kallsyms_show_value()` 的函数声明及 `kptr_restrict` 定义。
  - `<linux/security.h>`：提供 `security_capable()` 安全能力检查接口。

- **配置依赖**：
  - 可选依赖 `CONFIG_PERF_EVENTS`：仅当该配置启用时，才会编译 perf 相关的权限判断逻辑。

- **全局变量依赖**：
  - `kptr_restrict`：控制系统是否限制内核指针暴露的全局安全参数。
  - `sysctl_perf_event_paranoid`（仅在 `CONFIG_PERF_EVENTS` 下）：控制系统对 perf 事件的严格程度。

## 5. 使用场景

- **`/proc/kallsyms` 访问控制**：  
  当用户读取 `/proc/kallsyms` 文件时，内核调用 `kallsyms_show_value()` 判断是否应显示符号的实际地址（否则显示为 `0000000000000000`），以防止信息泄露。

- **性能分析工具支持**：  
  在使用 `perf` 等性能分析工具时，若系统配置允许（`perf_event_paranoid <= 1`），即使普通用户也可获取内核符号地址，便于进行准确的性能剖析。

- **安全加固环境**：  
  在高安全要求的系统中（如 `kptr_restrict=2`），彻底屏蔽内核地址暴露，防止攻击者利用地址信息绕过 ASLR 等防护机制。