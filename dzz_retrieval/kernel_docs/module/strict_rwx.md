# module\strict_rwx.c

> 自动生成时间: 2025-10-25 15:07:28
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `module\strict_rwx.c`

---

# `module/strict_rwx.c` 技术文档

## 1. 文件概述

`strict_rwx.c` 是 Linux 内核模块子系统中用于实现 **严格 RWX（Read-Write-Execute）内存权限控制** 的核心文件。其主要功能是在模块加载、初始化和运行过程中，对模块不同内存段（如代码段、只读数据段等）施加严格的内存保护策略，确保：

- **可执行段不可写**（W^X 原则）
- **只读段不可写也不可执行**
- **数据段不可执行**

该机制通过 `CONFIG_STRICT_MODULE_RWX` 配置选项启用，旨在提升内核模块的安全性，防止代码注入、ROP（Return-Oriented Programming）等攻击。

---

## 2. 核心功能

### 主要函数

| 函数名 | 功能描述 |
|--------|--------|
| `module_set_memory()` | 内部辅助函数，对指定类型的模块内存区域应用指定的内存权限设置（如 `set_memory_x`、`set_memory_ro` 等） |
| `module_enable_x()` | 启用模块文本段（text sections）的可执行权限（`set_memory_x`） |
| `module_disable_ro()` | **（仅在 `CONFIG_LIVEPATCH_WO_FTRACE` 下）** 临时将只读段设为可写，用于热补丁（livepatch）更新 |
| `module_enable_ro()` | 将模块的文本段和只读数据段设为只读（`set_memory_ro`），可选择是否包含 `MOD_RO_AFTER_INIT` 段 |
| `module_enable_nx()` | 对模块的数据段（data sections）应用不可执行（NX）权限（`set_memory_nx`） |
| `module_enforce_rwx_sections()` | 在模块加载时检查 ELF 节区是否违反 W^X 原则（即同时设置了 `SHF_WRITE` 和 `SHF_EXECINSTR`），若违反则拒绝加载 |

### 关键数据结构/宏

- `enum mod_mem_type`：定义模块内存类型（如 `MOD_TEXT`, `MOD_RODATA`, `MOD_RO_AFTER_INIT` 等）
- `struct module_memory`：存储每种内存类型的基地址和大小
- `for_class_mod_mem_type(type, text/data)`：宏，用于遍历指定类别的内存类型（文本类或数据类）

---

## 3. 关键实现

### 3.1 内存权限设置机制

- `module_set_memory()` 封装了通用的内存权限设置逻辑：
  - 调用 `set_vm_flush_reset_perms()` 重置页表项的权限并刷新 TLB
  - 调用底层架构相关的 `set_memory_*` 函数（如 `set_memory_ro`）应用新权限
  - 权限粒度为页（`PAGE_SHIFT`）

### 3.2 W^X 强制执行

- `module_enforce_rwx_sections()` 在模块加载早期（解析 ELF 后）扫描所有节区头：
  - 若发现同时包含 `SHF_WRITE | SHF_EXECINSTR` 的节区，立即报错并返回 `-ENOEXEC`
  - 此检查独立于运行时权限设置，是静态安全屏障

### 3.3 权限阶段控制

- 模块加载流程中分阶段应用权限：
  - **加载时**：数据段设为 NX，文本段设为可执行
  - **初始化后**：调用 `module_enable_ro(..., true)` 将 `MOD_RO_AFTER_INIT` 段也设为只读
- 热补丁场景（`CONFIG_LIVEPATCH_WO_FTRACE`）下，可通过 `module_disable_ro()` 临时解除只读保护以修改代码

### 3.4 配置依赖

- 所有运行时权限操作均受 `CONFIG_STRICT_MODULE_RWX` 控制
- 即使未启用 `STRICT_MODULE_RWX`，`module_enable_x()` 仍会被调用（因其被架构代码依赖）

---

## 4. 依赖关系

### 头文件依赖
- `<linux/module.h>`：模块核心结构定义
- `<linux/mm.h>`、`<linux/vmalloc.h>`：内存管理接口
- `<linux/set_memory.h>`：提供 `set_memory_ro/x/nx/rw` 等架构相关函数
- `"internal.h"`：模块子系统内部头文件，定义 `mod_mem_type` 和 `module_memory`

### 架构依赖
- 依赖底层架构实现的 `set_memory_*` 函数（如 x86、ARM64 等）
- 依赖 `set_vm_flush_reset_perms()`（定义在 `mm/vmalloc.c`）处理 vmalloc 区域的页表刷新

### 配置选项依赖
- `CONFIG_STRICT_MODULE_RWX`：主开关
- `CONFIG_LIVEPATCH_WO_FTRACE`：控制 `module_disable_ro()` 的编译
- `rodata_enabled`：运行时开关，可在启动参数中关闭（如 `rodata=off`）

---

## 5. 使用场景

1. **模块加载过程**：
   - 内核在 `load_module()` 中调用 `module_enforce_rwx_sections()` 检查 ELF 节区合法性
   - 加载完成后调用 `module_enable_nx()` 和 `module_enable_x()` 设置初始权限

2. **模块初始化完成**：
   - 调用 `module_enable_ro(mod, true)` 将 `__ro_after_init` 段设为只读，防止运行时篡改

3. **内核热补丁（Livepatch）**：
   - 当使用 `CONFIG_LIVEPATCH_WO_FTRACE` 时，热补丁框架调用 `module_disable_ro()` 临时解除只读保护以写入新指令，补丁应用后再恢复只读

4. **安全加固**：
   - 防止恶意模块或漏洞利用通过可写+可执行内存执行任意代码
   - 符合现代操作系统安全最佳实践（如 DEP/NX、W^X）