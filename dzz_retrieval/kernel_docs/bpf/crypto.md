# bpf\crypto.c

> 自动生成时间: 2025-10-25 12:08:13
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\crypto.c`

---

# `bpf/crypto.c` 技术文档

## 1. 文件概述

`bpf/crypto.c` 是 Linux 内核中为 BPF（Berkeley Packet Filter）程序提供加密功能支持的核心实现文件。该文件定义了 BPF 加密上下文（`bpf_crypto_ctx`）的创建、引用管理、加解密操作等接口，并通过可扩展的类型注册机制（`bpf_crypto_type`）支持多种加密算法后端。所有接口均以 `__bpf_kfunc` 标记，供 sleepable BPF 程序在内核态安全调用。

## 2. 核心功能

### 主要数据结构

- **`struct bpf_crypto_params`**  
  BPF 程序传入的加密初始化参数结构体，包含：
  - `type`：加密操作类型（如 "skcipher"）
  - `algo`：具体算法名称（如 "aes-gcm"）
  - `key` / `key_len`：密钥及其长度
  - `authsize`：认证标签长度（用于 AEAD 算法）

- **`struct bpf_crypto_ctx`**  
  引用计数的 BPF 加密上下文，封装了底层 crypto API 的变换对象（`tfm`），包含：
  - `type`：指向注册的加密类型操作集
  - `tfm`：由 `alloc_tfm()` 创建的 crypto 变换实例
  - `siv_len`：IV（初始向量）与状态存储总大小
  - `usage`：引用计数器，支持多 BPF 程序共享
  - `rcu`：用于 RCU 安全释放资源

- **`struct bpf_crypto_type_list`**  
  全局加密类型注册链表节点，用于管理所有已注册的 `bpf_crypto_type`。

### 主要函数

- **`bpf_crypto_register_type()` / `bpf_crypto_unregister_type()`**  
  向全局链表注册/注销一种 BPF 加密类型（如对称加密、AEAD 等），支持模块动态加载。

- **`bpf_crypto_ctx_create()`**  
  根据 `bpf_crypto_params` 创建并初始化加密上下文，执行密钥设置、认证大小配置等操作。

- **`bpf_crypto_ctx_acquire()` / `bpf_crypto_ctx_release()`**  
  实现引用计数管理，支持 BPF 程序安全地共享和释放上下文。

- **`bpf_crypto_decrypt()` / `bpf_crypto_encrypt()`（隐含于 `bpf_crypto_crypt()`）**  
  执行实际的加解密操作，通过 `bpf_dynptr_kern` 安全访问源/目标缓冲区及 IV/状态数据。

## 3. 关键实现

- **类型注册机制**  
  使用读写信号量 `bpf_crypto_types_sem` 保护全局类型链表 `bpf_crypto_types`，确保并发安全。注册时检查名称唯一性，卸载时自动清理。

- **模块引用管理**  
  在 `bpf_crypto_get_type()` 中调用 `try_module_get()` 获取模块引用，在上下文释放时通过 `module_put()` 释放，防止模块卸载时使用悬空指针。

- **内存与资源安全释放**  
  上下文释放采用 RCU 机制：当引用计数归零时，通过 `call_rcu()` 异步调用 `crypto_free_cb()`，确保在所有 CPU 完成读取后再释放 `tfm` 和结构体内存。

- **参数校验严格性**  
  `bpf_crypto_ctx_create()` 对输入参数进行多层校验：
  - 检查 `reserved` 字段是否为零（预留扩展）
  - 验证 `params__sz` 是否匹配结构体大小
  - 确保 `authsize` 与算法能力匹配（有/无 `setauthsize` 回调）
  - 密钥长度合法性检查

- **动态指针（dynptr）集成**  
  加解密操作通过 `bpf_dynptr_kern` 接口访问数据，确保源/目标缓冲区权限正确（目标必须可写），并验证 IV 长度与上下文 `siv_len` 一致。

## 4. 依赖关系

- **BPF 子系统**  
  依赖 `bpf_mem_alloc.h`（BPF 内存分配）、`filter.h`（BPF 程序基础）、`btf_ids.h`（BTF 类型信息）及 `__bpf_kfunc` 基础设施。

- **Crypto API**  
  通过 `crypto/skcipher.h` 等头文件调用内核加密框架，具体算法由 `bpf_crypto_type` 的回调函数（如 `alloc_tfm`, `encrypt`）桥接。

- **内核通用机制**  
  使用 `refcount_t`（引用计数）、`RCU`（安全释放）、`GFP_KERNEL`（睡眠分配）等标准内核原语。

- **网络子系统**（间接）  
  可能与 `skbuff.h` 交互（如处理网络包加密），但当前代码未直接操作 `sk_buff`。

## 5. 使用场景

- **BPF 程序内加密操作**  
  Sleepable BPF 程序（如 LSM、syscall hook）可调用 `bpf_crypto_ctx_create()` 初始化 AES-GCM 等上下文，对用户数据进行加解密。

- **安全协议实现**  
  在 BPF 中实现 TLS/DTLS 记录层、IPsec ESP 等协议的加解密逻辑，利用内核 crypto API 的硬件加速能力。

- **密钥管理集成**  
  与 BPF map 结合，将加密上下文作为 `kptr` 存储，实现密钥轮换、会话管理等高级功能。

- **模块化扩展**  
  第三方模块可通过 `bpf_crypto_register_type()` 注册自定义加密类型（如国密算法），扩展 BPF 加密能力。