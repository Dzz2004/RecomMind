# livepatch\patch.c

> 自动生成时间: 2025-10-25 14:32:39
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `livepatch\patch.c`

---

# livepatch/patch.c 技术文档

## 1. 文件概述

`patch.c` 是 Linux 内核 Livepatch（实时补丁）子系统的核心实现文件之一，负责管理函数级别的动态补丁应用与移除。该文件通过 ftrace 机制拦截目标函数的执行，并在运行时将其重定向到新的补丁函数。它维护一个全局的 `klp_ops` 列表，用于跟踪每个被补丁函数对应的 ftrace 操作结构，并支持补丁栈（patch stack）机制，允许多个补丁按顺序叠加或回退。

## 2. 核心功能

### 主要数据结构

- **`struct klp_ops`**  
  表示一个被补丁函数对应的 ftrace 操作上下文，包含：
  - `fops`：ftrace 操作结构体，注册 `klp_ftrace_handler` 作为回调
  - `func_stack`：RCU 保护的 `klp_func` 链表，按补丁应用顺序堆叠（栈顶为当前生效补丁）
  - `node`：用于链接到全局 `klp_ops` 列表

- **全局变量 `klp_ops`**  
  静态链表头，存储所有已注册的 `klp_ops` 实例，以 `old_func` 地址为索引。

### 主要函数

| 函数 | 功能描述 |
|------|--------|
| `klp_find_ops(void *old_func)` | 根据原始函数地址查找对应的 `klp_ops` 结构 |
| `klp_ftrace_handler(...)` | ftrace 回调函数，在目标函数执行时动态选择应调用的函数（原始/补丁/回退） |
| `klp_patch_func(struct klp_func *func)` | 为单个函数应用补丁，注册 ftrace 过滤器和处理函数 |
| `klp_unpatch_func(struct klp_func *func)` | 移除单个函数的补丁，必要时注销 ftrace 处理器 |
| `klp_patch_object(struct klp_object *obj)` | 对整个对象（如模块或 vmlinux）应用所有函数补丁 |
| `klp_unpatch_object(struct klp_object *obj)` | 移除对象上所有补丁 |
| `klp_unpatch_objects(struct klp_patch *patch)` | 移除整个补丁中所有对象的补丁 |
| `klp_unpatch_objects_dynamic(...)` | 仅移除动态生成的 NOP 补丁（用于补丁回滚） |

## 3. 关键实现

### 补丁栈（Patch Stack）机制
- 每个被补丁的函数维护一个 `func_stack` 链表（RCU 保护），栈顶（`list_first_entry`）为当前生效的补丁函数。
- 支持补丁叠加：新补丁插入栈顶；回滚时移除栈顶，恢复前一个版本。
- 在过渡状态（`func->transition == true`）下，根据当前任务的 `patch_state`（`KLP_PATCHED` / `KLP_UNPATCHED`）决定使用栈顶还是下一个函数，实现原子性过渡。

### ftrace 集成
- 使用 `ftrace_set_filter_ip()` 将目标函数地址加入 ftrace 过滤器。
- 注册 `klp_ftrace_handler` 作为动态 ftrace 回调。
- 根据架构支持情况，设置 `FTRACE_OPS_FL_SAVE_REGS`（若不支持带参数的动态 ftrace）和 `FTRACE_OPS_FL_IPMODIFY`（允许修改指令指针）。

### 内存与同步安全
- 使用 RCU 保护 `func_stack` 的读取（`list_first_or_null_rcu`、`list_entry_rcu`）。
- 在 `klp_ftrace_handler` 中使用 `ftrace_test_recursion_trylock()` 禁用抢占，确保与 `klp_synchronize_transition()` 的同步语义。
- 补丁移除时，若 `func_stack` 变为空，则注销 ftrace 处理器并释放 `klp_ops`。

### 内存屏障
- 在读取 `func->transition` 前使用 `smp_rmb()`，确保与 `__klp_enable_patch()` 和 `klp_init_transition()` 中的写屏障配对，保证内存访问顺序正确。

### NOP 补丁处理
- 若 `func->nop` 为真，表示该补丁仅用于覆盖旧补丁（恢复原始代码），此时不修改指令指针，避免无限循环。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/livepatch.h>`：Livepatch 核心 API 和数据结构定义
  - `<linux/ftrace.h>`：ftrace 注册、过滤和指令指针修改接口
  - `<linux/rculist.h>`：RCU 安全的链表操作
  - `"core.h"`, `"patch.h"`, `"transition.h"`：Livepatch 内部模块，分别提供核心状态管理、数据结构定义和过渡同步机制

- **功能依赖**：
  - 依赖 ftrace 的动态函数追踪能力（`CONFIG_DYNAMIC_FTRACE`）
  - 依赖 RCU 机制实现无锁读路径
  - 与 `transition.c` 协同完成补丁的原子切换

## 5. 使用场景

- **内核热补丁应用**：当用户通过 sysfs 或内核模块加载 Livepatch 补丁时，`klp_patch_object()` 被调用，为每个目标函数注册 ftrace 处理器。
- **补丁回滚**：当禁用补丁或加载新补丁覆盖旧补丁时，`klp_unpatch_object()` 或 `klp_unpatch_objects_dynamic()` 被调用，移除相应函数的补丁。
- **原子过渡**：在补丁启用/禁用过程中，`klp_ftrace_handler` 根据任务的 `patch_state` 动态选择执行路径，确保系统中所有任务平滑过渡到新/旧代码，避免混合执行状态。
- **动态补丁管理**：支持运行时动态添加/移除补丁函数，适用于长期运行的服务器系统，无需重启即可修复安全漏洞或关键 bug。