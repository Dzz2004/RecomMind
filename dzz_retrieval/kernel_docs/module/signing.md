# module\signing.c

> 自动生成时间: 2025-10-25 15:06:05
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `module\signing.c`

---

# module/signing.c 技术文档

## 1. 文件概述

`module/signing.c` 是 Linux 内核中用于验证内核模块数字签名的核心实现文件。该文件提供了模块加载过程中对 PKCS#7 格式签名的解析、验证和策略控制功能，确保只有经过合法签名的模块才能被加载到内核中，从而增强系统的安全性和完整性。该机制是内核模块签名（Module Signature）子系统的关键组成部分，支持强制签名（`CONFIG_MODULE_SIG_FORCE`）和运行时策略控制。

## 2. 核心功能

### 主要函数

- **`is_module_sig_enforced(void)`**  
  返回当前是否强制要求模块必须具有有效签名。该函数导出为符号，供其他内核子系统使用。

- **`set_module_sig_enforced(void)`**  
  在运行时将模块签名强制策略设置为启用状态（`true`），通常由安全机制（如 Lockdown）调用。

- **`mod_verify_sig(const void *mod, struct load_info *info)`**  
  执行模块签名的实际验证逻辑：解析模块末尾的 `module_signature` 结构，提取签名数据，并调用通用 PKCS#7 验证接口进行验证。

- **`module_sig_check(struct load_info *info, int flags)`**  
  模块加载流程中的主入口函数，负责检测模块是否包含签名标记（`~Module signature appended~\n`），决定是否调用 `mod_verify_sig`，并根据验证结果和系统策略决定是否允许加载。

### 关键数据结构与变量

- **`sig_enforce`**  
  全局布尔变量，表示是否强制执行模块签名验证。初始值由 `CONFIG_MODULE_SIG_FORCE` 决定，可通过内核命令行参数 `module.sig_enforce=1` 或运行时调用 `set_module_sig_enforced()` 修改。

- **`module_signature`**  
  定义在 `<linux/module_signature.h>` 中的结构体，位于模块二进制末尾，包含签名元数据（如签名长度、哈希算法、密钥标识等）。

- **`MODULE_SIG_STRING`**  
  签名结束标记字符串 `"~Module signature appended~\n"`，用于识别模块是否包含签名。

## 3. 关键实现

### 签名验证流程

1. **签名检测**：  
   `module_sig_check` 检查模块末尾是否存在 `MODULE_SIG_STRING` 标记。若存在，则认为模块包含签名。

2. **签名解析**：  
   `mod_verify_sig` 从模块末尾读取 `struct module_signature`，调用 `mod_check_sig()` 验证其格式合法性。

3. **数据截断**：  
   从模块总长度中扣除签名数据和签名结构体的长度，得到实际代码/数据部分的长度（`info->len` 更新为此值）。

4. **PKCS#7 验证**：  
   调用 `verify_pkcs7_signature()`，使用内核的 `VERIFY_USE_SECONDARY_KEYRING`（通常为 `.module_signing` 密钥环）验证模块主体的完整性与签名有效性。

### 安全策略处理

- **强制模式（`sig_enforce == true`）**：  
  任何未签名、密钥不可用或加密算法不支持的模块均被拒绝加载，返回 `-EKEYREJECTED`。

- **非强制模式**：  
  允许加载未签名模块，但会检查系统是否处于 Lockdown 模式（通过 `security_locked_down(LOCKDOWN_MODULE_SIGNATURE)`）。若处于 Lockdown，则仍拒绝加载。

- **模块篡改防护**：  
  若加载标志包含 `MODULE_INIT_IGNORE_MODVERSIONS` 或 `MODULE_INIT_IGNORE_VERMAGIC`（即忽略版本魔数或模块版本），则视为“被篡改”的模块，即使有签名也不予验证，防止绕过签名保护。

### 错误分类

- **非致命错误**（仅在非强制模式下可忽略）：
  - `-ENODATA`：模块未签名
  - `-ENOPKG`：使用了内核不支持的加密算法
  - `-ENOKEY`：签名所用公钥不在信任密钥环中

- **致命错误**（无论是否强制均拒绝）：
  - 内存分配失败、签名格式错误、哈希不匹配等

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/verification.h>`：提供 `verify_pkcs7_signature()` 接口
  - `<crypto/public_key.h>`：PKCS#7 验证所需的密码学支持
  - `<linux/module_signature.h>`：定义 `module_signature` 结构
  - `"internal.h"`：模块子系统内部头文件

- **内核配置依赖**：
  - `CONFIG_MODULE_SIG`：启用模块签名功能
  - `CONFIG_MODULE_SIG_FORCE`：决定 `sig_enforce` 的默认值
  - `CONFIG_SECURITY_LOCKDOWN_LSM`：提供 `security_locked_down()` 支持

- **密钥管理依赖**：  
  依赖内核密钥环服务（Key Retention Service），特别是 `.module_signing` 二级密钥环存储用于验证模块的公钥。

## 5. 使用场景

- **模块加载流程**：  
  在 `load_module()` 函数中，内核调用 `module_sig_check()` 对待加载模块进行签名验证，是模块安全加载的关键环节。

- **安全启动（Secure Boot）环境**：  
  当系统启用 UEFI Secure Boot 时，通常会强制启用模块签名（`sig_enforce = true`），确保所有内核模块均来自可信源。

- **内核 Lockdown 模式**：  
  在 Lockdown 的 `integrity` 或 `confidentiality` 级别下，即使未设置 `CONFIG_MODULE_SIG_FORCE`，也会通过 `security_locked_down()` 阻止未签名模块加载。

- **动态策略调整**：  
  安全模块（如 Lockdown LSM）可在运行时调用 `set_module_sig_enforced()` 动态提升安全策略，禁止后续未签名模块加载。