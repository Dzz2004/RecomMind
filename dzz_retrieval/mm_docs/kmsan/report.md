# kmsan\report.c

> 自动生成时间: 2025-12-07 16:32:55
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `kmsan\report.c`

---

# `kmsan/report.c` 技术文档

## 1. 文件概述

`kmsan/report.c` 是 Linux 内核内存安全检测工具 **KMSAN**（Kernel Memory Sanitizer）的错误报告模块。该文件负责在检测到未初始化内存使用或释放后使用（use-after-free）等内存安全问题时，生成结构化、可读性强的错误报告，并支持通过内核参数控制是否触发 panic。其核心目标是帮助开发者快速定位和诊断内核中的内存初始化缺陷。

## 2. 核心功能

### 主要函数

- **`get_stack_skipnr()`**  
  过滤调用栈中属于 KMSAN 内部运行时的函数帧（如 `__msan_*` 和 `kmsan_*`），返回需要跳过的帧数，确保报告只显示用户代码相关的调用路径。

- **`pretty_descr()`**  
  对 Clang 编译器生成的局部变量描述字符串（格式如 `----local_name@function_name`）进行清洗，仅保留变量名部分，并将结果存入全局缓冲区以避免动态内存分配。

- **`kmsan_print_origin()`**  
  解析并打印未初始化值的**起源信息**（origin）。支持三种类型的 origin：
  - 局部变量创建点（含变量名和创建位置）
  - 内存写入点（通过 origin 链追踪）
  - 基础未初始化来源（直接打印创建栈）

- **`kmsan_report()`**  
  KMSAN 的主错误报告入口。根据 bug 类型（普通未初始化、copy_to_user 信息泄露、USB URB 提交等）和是否为 use-after-free，生成完整的错误摘要，包括：
  - 错误类型
  - 触发位置的调用栈
  - 起源信息
  - 访问的字节范围和地址
  - 用户空间目标地址（如适用）
  - 最终决定是否触发内核 panic

### 关键数据结构与变量

- **`report_local_descr[DESCR_SIZE]`**  
  全局静态缓冲区，用于存储清洗后的局部变量名，受 `kmsan_report_lock` 保护。

- **`panic_on_kmsan`**  
  模块参数（可通过 `kmsan.panic=1` 启用），控制检测到 KMSAN 错误时是否立即触发内核 panic。

- **`kmsan_report_lock`**  
  原始自旋锁，确保多 CPU 上的错误报告输出不会交错。

## 3. 关键实现

### 起源（Origin）编码与解析
KMSAN 使用 `depot_stack_handle_t` 存储内存未初始化状态的“起源”。该句柄不仅指向一个调用栈，还通过额外位（extra bits）编码元信息：
- **`KMSAN_ALLOCA_MAGIC_ORIGIN`**：标识该 origin 来自栈上局部变量，附加数据包括变量描述符、创建函数 PC 等。
- **`KMSAN_CHAIN_MAGIC_ORIGIN`**：表示这是一个**起源链**节点，用于追踪未初始化值通过多次内存拷贝/赋值的传播路径。链深度受 `KMSAN_MAX_ORIGIN_DEPTH` 限制，超深链会提示信息可能不完整。

`kmsan_print_origin()` 通过循环解码这些 magic 值，递归展开链式结构，还原完整的污染传播路径。

### 调用栈净化
`get_stack_skipnr()` 利用 `%ps` 格式化符号地址为函数名，并通过字符串匹配跳过 KMSAN 运行时内部函数（如 `kmsan_memmove_meta`、`__msan_loadn` 等），使报告聚焦于内核业务逻辑代码。

### 安全上下文管理
- 使用 `user_access_save()/restore()` 临时关闭用户空间访问检查，确保在报告过程中访问用户地址（如 `copy_to_user` 目标）不会触发额外异常。
- 通过 `current->kmsan_ctx.allow_reporting` 防止嵌套报告（即报告过程中再次触发 KMSAN 检查导致递归）。

### 内存安全保证
- 所有字符串处理使用固定大小缓冲区（`report_local_descr`、`buf`），避免动态分配。
- 全局输出受自旋锁保护，保证 SMP 下日志完整性。

## 4. 依赖关系

- **`<linux/stackdepot.h>` / `<linux/stacktrace.h>`**：用于存储和打印压缩调用栈。
- **`"kmsan.h"`**：包含 KMSAN 核心定义，如 `depot_stack_handle_t` 解码宏、origin magic 值、上下文结构等。
- **`<linux/uaccess.h>`**：提供 `user_access_save/restore` 接口。
- **Clang 编译器支持**：依赖 Clang 的 `-fsanitize=kernel-memory` 插桩生成 origin 信息和局部变量描述。

## 5. 使用场景

- **内核开发与调试**：当启用 KMSAN 编译内核后，任何使用未初始化内存的操作（如读取未初始化的栈变量、结构体字段，或 copy_to_user 未初始化数据）都会触发此报告。
- **安全漏洞挖掘**：用于检测可能导致信息泄露（infoleak）的未初始化内存问题，特别是在系统调用、驱动程序和网络子系统中。
- **CI/CD 集成测试**：结合 `kmsan.panic=1` 参数，可在自动化测试中将 KMSAN 错误视为致命故障，阻止有缺陷的内核合并。
- **Use-after-free 检测**：当配合 KMSAN 的 UAF 检测机制时，可区分普通未初始化和释放后使用错误，提供更精确的诊断信息。