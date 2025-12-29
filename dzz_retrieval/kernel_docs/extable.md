# extable.c

> 自动生成时间: 2025-10-25 13:28:12
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `extable.c`

---

# extable.c 技术文档

## 文件概述

`extable.c` 是 Linux 内核中用于管理**异常表（exception table）**的核心实现文件。异常表记录了内核中可能触发页错误（如访问用户空间地址失败）的指令地址及其对应的异常处理程序地址。该文件提供了对内核内置异常表、模块异常表和 BPF 异常表的统一搜索接口，并负责在内核初始化阶段对内置异常表进行排序，以支持高效的二分查找。此外，该文件还包含用于判断地址是否位于内核可执行文本段（text section）的辅助函数，以及在支持函数描述符（function descriptors）的架构上对函数指针进行解引用的逻辑。

## 核心功能

### 主要数据结构
- `struct exception_table_entry`：异常表项，包含故障指令地址和对应的修复处理程序地址（定义在 `<linux/extable.h>` 中）。
- `text_mutex`：互斥锁，用于保护对内核文本段的动态修改（如热补丁、ftrace、kprobes 等）。

### 主要函数
- `sort_main_extable(void)`：在内核初始化阶段对内置异常表 `__ex_table` 进行排序。
- `search_kernel_exception_table(unsigned long addr)`：在内核内置异常表中搜索指定地址对应的异常处理项。
- `search_exception_tables(unsigned long addr)`：统一接口，在内核、模块和 BPF 的异常表中搜索指定地址。
- `core_kernel_text(unsigned long addr)`：判断地址是否属于内核核心文本段（包括 init 段，在初始化内存释放前）。
- `kernel_text_address(unsigned long addr)`：判断地址是否属于任何内核可执行文本（包括模块、kprobes、BPF、ftrace 等）。
- `__kernel_text_address(unsigned long addr)`：扩展版的 `kernel_text_address`，特别包含 init 段符号以支持栈回溯。
- `dereference_function_descriptor(void *ptr)`（仅 `CONFIG_HAVE_FUNCTION_DESCRIPTORS`）：解引用函数描述符，获取真实函数地址。
- `dereference_kernel_function_descriptor(void *ptr)`（仅 `CONFIG_HAVE_FUNCTION_DESCRIPTORS`）：仅对内核 OPD 段中的函数描述符进行解引用。
- `func_ptr_is_kernel_text(void *ptr)`：判断函数指针（可能为描述符）是否指向内核文本。

## 关键实现

### 异常表管理
- 内核链接脚本将所有 `.ex_table` 段合并为 `__start___ex_table` 到 `__stop___ex_table` 的连续区域。
- 构建工具（如 `sortextable`）可能已在编译时对异常表排序；若未排序，则 `main_extable_sort_needed` 为 1，内核在 `sort_main_extable()` 中调用 `sort_extable()` 进行运行时排序。
- `search_extable()`（定义在别处）依赖表已排序，使用二分查找实现 O(log n) 查询效率。

### 文本段地址判断
- `kernel_text_address()` 是核心判断函数，依次检查：
  1. 内核核心文本（`core_kernel_text()`）
  2. 模块文本（`is_module_text_address()`）
  3. ftrace 跳板（`is_ftrace_trampoline()`）
  4. kprobes 指令槽（`is_kprobe_*_slot()`）
  5. BPF 文本（`is_bpf_text_address()`）
- 由于部分检查（如模块地址）依赖 RCU 机制，在 RCU 不活跃上下文（如 NMI、idle 退出）中，函数会临时通过 `ct_nmi_enter/exit()` 通知 RCU 子系统。

### 函数描述符支持
- 在 PowerPC64、IA-64、PARISC 等架构上，函数指针实际指向描述符（OPD），其中包含真实入口地址。
- `dereference_function_descriptor()` 使用 `get_kernel_nofault()` 安全读取描述符中的地址，避免因无效指针导致崩溃。
- `func_ptr_is_kernel_text()` 先解引用描述符，再判断真实地址是否在内核文本中。

### 并发控制
- `text_mutex` 保护所有对内核 `.text` 段的运行时修改操作（如 ftrace、kprobes、alternatives），防止并发写入导致不一致。
- 该锁**不导出给内核模块**，强调内核文本修改的高风险性。

## 依赖关系

- **头文件依赖**：
  - `<linux/extable.h>`：异常表数据结构和操作函数声明
  - `<linux/module.h>`：模块异常表搜索（`search_module_extables`）
  - `<linux/filter.h>`：BPF 异常表搜索（`search_bpf_extables`）
  - `<linux/kprobes.h>`：kprobes 指令槽判断
  - `<linux/ftrace.h>`：ftrace 跳板判断
  - `<asm/sections.h>`：内核段边界符号（`__start___ex_table` 等）
  - `<linux/uaccess.h>`：`get_kernel_nofault()` 安全内存访问
- **架构依赖**：
  - `CONFIG_HAVE_FUNCTION_DESCRIPTORS`：启用函数描述符解引用逻辑
  - 架构特定的 `is_*_text_address()` 实现（如 x86 的 `is_module_text_address`）
- **内核子系统**：
  - 内存管理（页错误处理）
  - 模块加载（模块异常表注册）
  - BPF JIT（BPF 异常表）
  - 动态追踪（ftrace、kprobes）

## 使用场景

1. **页错误处理**：当内核执行 `copy_from_user()` 等函数访问无效用户地址时，CPU 触发页错误，`do_page_fault()` 调用 `search_exception_tables()` 查找修复地址，跳转执行错误处理逻辑（如返回 `-EFAULT`）。
2. **内核调试与追踪**：
   - 栈回溯（stack unwinding）时通过 `__kernel_text_address()` 过滤有效内核符号
   - 锁依赖检测（lockdep）等子系统依赖准确的文本段地址判断
3. **动态代码修改**：
   - ftrace、kprobes、livepatch 等机制在修改内核代码前需获取 `text_mutex`
   - SMP alternatives（x86）使用同一互斥锁保证多核一致性
4. **架构兼容性**：
   - 在使用函数描述符的架构上，`kallsyms`、`perf` 等工具通过 `dereference_kernel_function_descriptor()` 获取真实函数地址
   - 函数指针比较或验证时调用 `func_ptr_is_kernel_text()` 确保安全性