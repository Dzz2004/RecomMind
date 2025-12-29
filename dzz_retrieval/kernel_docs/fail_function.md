# fail_function.c

> 自动生成时间: 2025-10-25 13:29:07
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `fail_function.c`

---

# fail_function.c 技术文档

## 1. 文件概述

`fail_function.c` 实现了基于函数的错误注入（Function-based Error Injection, FEI）机制，允许内核开发者在指定的可注入函数调用点动态注入预定义的错误返回值。该机制通过 kprobe 技术拦截目标函数的执行，并在满足故障注入条件时覆盖其返回值，用于测试内核错误处理路径的健壮性。所有功能通过 debugfs 接口暴露给用户空间，便于运行时控制。

## 2. 核心功能

### 主要数据结构

- **`struct fei_attr`**  
  表示一个错误注入点的元数据，包含：
  - `list`：用于链入全局 `fei_attr_list` 链表
  - `kp`：关联的 kprobe 实例，用于拦截函数执行
  - `retval`：预设的错误返回值

- **全局变量**
  - `fei_lock`：保护 `fei_attr_list` 的互斥锁
  - `fei_attr_list`：所有已注册错误注入点的链表
  - `fei_fault_attr`：故障注入属性，控制注入概率/条件
  - `fei_debugfs_dir`：debugfs 根目录句柄

### 主要函数

- **错误值调整**
  - `adjust_error_retval()`：根据函数的可注入错误类型（如 `EI_ETYPE_ERRNO`、`EI_ETYPE_NULL` 等）校验并标准化返回值

- **注入点管理**
  - `fei_attr_new()` / `fei_attr_free()`：创建/销毁 `fei_attr` 实例
  - `fei_attr_lookup()`：通过符号名查找注入点
  - `fei_attr_is_valid()`：验证 `fei_attr` 是否仍在全局链表中
  - `fei_attr_remove()` / `fei_attr_remove_all()`：移除单个或所有注入点

- **Kprobe 处理**
  - `fei_kprobe_handler()`：kprobe 前置处理函数，决定是否注入错误并覆盖返回值
  - `fei_post_handler()`：空后置处理函数，防止 kprobe 优化

- **Debugfs 接口**
  - `fei_retval_get()` / `fei_retval_set()`：读写指定注入点的返回值
  - `fei_write()`：主控制接口，支持添加/删除注入点
  - `fei_seq_*()`：实现 `/sys/kernel/debug/fail_function/inject` 的列表读取

- **初始化**
  - `fei_debugfs_init()`：创建 debugfs 目录和文件

## 3. 关键实现

### 错误注入机制
1. **函数拦截**：通过 kprobe 在目标函数入口处设置断点，触发 `fei_kprobe_handler`
2. **条件判断**：调用 `should_fail(&fei_fault_attr, 1)` 检查是否满足注入条件（基于 `fail_function` 的故障属性配置）
3. **返回值覆盖**：
   - 调用 `regs_set_return_value(regs, attr->retval)` 设置返回值
   - 调用 `override_function_with_return(regs)` 跳过原函数执行，直接返回

### 安全性保障
- **防优化**：`fei_post_handler` 作为空函数存在，阻止 kprobe 的跳转优化（因优化不支持执行路径覆盖）
- **并发保护**：所有链表操作受 `fei_lock` 互斥锁保护
- **有效性验证**：在 debugfs 回调中通过 `fei_attr_is_valid()` 检查对象是否已被释放

### Debugfs 接口设计
- **主控制文件** (`inject`)：
  - **写入函数名**：添加新注入点（需在 `error_injection/list` 中注册）
  - **写入 `!函数名`**：移除指定注入点
  - **写入空内容**：清空所有注入点
- **返回值文件** (`retval`)：每个注入点目录下独立的 `retval` 文件，支持动态修改返回值
- **符号链接** (`injectable`)：指向 `error_injection/list`，显示所有可注入函数

### 返回值类型处理
`adjust_error_retval()` 根据函数声明的错误类型自动校验返回值：
- `EI_ETYPE_NULL`：强制返回 `0`
- `EI_ETYPE_ERRNO`：非错误值转换为 `-EINVAL`
- `EI_ETYPE_ERRNO_NULL`：非零且非错误值转换为 `-EINVAL`
- `EI_ETYPE_TRUE`：强制返回 `1`

## 4. 依赖关系

- **`<linux/error-injection.h>`**  
  提供 `get_injectable_error_type()` 和 `within_error_injection_list()`，用于验证函数是否支持错误注入
- **`<linux/fault-inject.h>`**  
  提供 `DECLARE_FAULT_ATTR` 和 `should_fail()`，实现概率性故障注入控制
- **`<linux/kprobes.h>`**  
  核心拦截机制，通过 kprobe 动态修改函数执行流
- **`<linux/kallsyms.h>`**  
  通过 `kallsyms_lookup_name()` 解析函数符号地址
- **`<linux/debugfs.h>`**  
  提供用户空间控制接口
- **`<linux/uaccess.h>`**  
  处理用户空间数据拷贝（`memdup_user_nul`）

## 5. 使用场景

1. **内核错误路径测试**  
   开发者可通过注入特定错误（如 `-ENOMEM`、`-EINVAL`）验证内核模块对异常返回值的处理逻辑

2. **故障恢复验证**  
   模拟硬件/驱动故障（如 I/O 失败），测试系统恢复机制（如重试、降级、崩溃防护）

3. **安全边界测试**  
   验证内核在非法返回值（如非错误码的正数）下的行为是否符合预期

4. **动态调试**  
   运行时无需重新编译内核，通过 debugfs 快速启用/禁用特定函数的错误注入

**典型操作流程**：
```bash
# 查看可注入函数列表
cat /sys/kernel/debug/error_injection/list

# 为目标函数添加注入点
echo "some_function" > /sys/kernel/debug/fail_function/inject

# 设置返回值为 -ENOMEM
echo -12 > /sys/kernel/debug/fail_function/some_function/retval

# 触发故障（需先配置故障属性）
echo 100 > /sys/kernel/debug/fail_function/probability  # 100% 概率

# 移除注入点
echo "!some_function" > /sys/kernel/debug/fail_function/inject
```