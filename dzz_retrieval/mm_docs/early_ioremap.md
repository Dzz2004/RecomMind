# early_ioremap.c

> 自动生成时间: 2025-12-07 15:58:03
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `early_ioremap.c`

---

# early_ioremap.c 技术文档

## 1. 文件概述

`early_ioremap.c` 提供了在内核启动早期阶段（在标准 `ioremap()` 机制尚未可用时）进行临时 I/O 或内存映射的通用支持。该文件主要用于无 MMU 架构或需要在分页初始化完成前访问物理地址空间的体系结构。其实现基于固定映射（fixmap）机制，通过预分配的虚拟地址窗口动态映射物理内存区域。

## 2. 核心功能

### 主要函数

- `early_ioremap_setup(void)`  
  初始化早期 ioremap 所需的虚拟地址槽位。

- `__early_ioremap(resource_size_t phys_addr, unsigned long size, pgprot_t prot)`  
  内部实现函数，执行实际的早期映射操作。

- `early_ioremap(resource_size_t phys_addr, unsigned long size)`  
  映射 I/O 设备内存，使用 `FIXMAP_PAGE_IO` 页属性。

- `early_memremap(resource_size_t phys_addr, unsigned long size)`  
  映射普通内存，使用 `FIXMAP_PAGE_NORMAL` 页属性，并可由架构调整保护属性。

- `early_memremap_ro(resource_size_t phys_addr, unsigned long size)`  
  （条件编译）只读方式映射内存，使用 `FIXMAP_PAGE_RO` 属性。

- `early_memremap_prot(resource_size_t phys_addr, unsigned long size, unsigned long prot_val)`  
  （条件编译）使用自定义页表属性映射内存。

- `early_iounmap(void __iomem *addr, unsigned long size)`  
  解除早期 I/O 映射。

- `early_memunmap(void *addr, unsigned long size)`  
  解除早期内存映射，是对 `early_iounmap` 的封装。

- `copy_from_early_mem(void *dest, phys_addr_t src, unsigned long size)`  
  安全地从早期物理内存复制数据，自动处理跨映射块边界的情况。

- `early_ioremap_reset(void)`  
  标记分页初始化已完成，后续映射将使用晚期 fixmap 接口。

- `check_early_ioremap_leak(void)`  
  启动后期检查是否存在未释放的早期映射（用于调试）。

### 主要数据结构与变量

- `prev_map[FIX_BTMAPS_SLOTS]`：记录每个槽位当前映射的虚拟地址。
- `prev_size[FIX_BTMAPS_SLOTS]`：记录每个槽位映射的大小。
- `slot_virt[FIX_BTMAPS_SLOTS]`：每个槽位对应的固定虚拟地址基址。
- `after_paging_init`：标志位，指示是否已完成分页初始化。
- `early_ioremap_debug`：调试开关，启用详细日志输出。

## 3. 关键实现

### 固定映射槽位管理
- 使用 `FIX_BTMAPS_SLOTS` 个独立的 fixmap 槽位（每个槽包含 `NR_FIX_BTMAPS` 个页面），支持并发的早期映射。
- 每个槽位的虚拟地址通过 `__fix_to_virt(FIX_BTMAP_BEGIN - NR_FIX_BTMAPS*i)` 预计算。
- 映射时线性搜索首个空闲槽位；解映射时通过虚拟地址反查槽位。

### 分页初始化前后区分
- 在 `paging_init()` 调用前，使用 `__early_set_fixmap()` 建立映射。
- 调用 `early_ioremap_reset()` 后（即 `after_paging_init = 1`），改用 `__late_set_fixmap()` 和 `__late_clear_fixmap()`。
- 若架构未定义晚期接口，则调用 `BUG()`，确保正确性。

### 页对齐与大小限制
- 输入物理地址和大小会被自动对齐到页边界。
- 单次映射最大为 `NR_FIX_BTMAPS << PAGE_SHIFT`（即 `MAX_MAP_CHUNK`）。
- 超出单槽容量的请求会被拒绝（`WARN_ON(nrpages > NR_FIX_BTMAPS)`）。

### 内存属性定制
- `early_memremap_pgprot_adjust()` 是弱符号函数，允许架构层根据物理地址调整页属性（如设置缓存策略）。
- 支持只读 (`FIXMAP_PAGE_RO`) 和自定义属性 (`early_memremap_prot`) 的映射。

### 泄漏检测
- 通过 `late_initcall(check_early_ioremap_leak)` 在启动后期检查是否有未释放的映射。
- 若存在泄漏且启用了 `early_ioremap_debug`，会提示用户上报 dmesg 日志。

### 无 MMU 支持
- 在 `!CONFIG_MMU` 配置下，所有 `early_*remap` 函数直接返回物理地址（无映射开销），`unmap` 操作为空。

## 4. 依赖关系

- **头文件依赖**：
  - `<asm/fixmap.h>`：提供固定映射相关定义（如 `FIX_BTMAP_BEGIN`、`__fix_to_virt`）。
  - `<asm/early_ioremap.h>`：必须由架构提供 `__early_set_fixmap` 等底层接口。
  - `"internal.h"`：可能包含内核内部辅助宏或函数。

- **架构依赖**：
  - 必须实现 `__early_set_fixmap()` 和 `FIXMAP_PAGE_CLEAR`。
  - 可选实现 `__late_set_fixmap()` / `__late_clear_fixmap()` 以支持分页初始化后的映射。
  - 可重载 `early_memremap_pgprot_adjust()` 调整内存属性。

- **内核子系统**：
  - 依赖 `mm` 子系统的页表管理机制。
  - 使用 `init` 段属性（`__init`）确保代码/数据在初始化后释放。
  - 通过 `early_param()` 注册启动参数 `early_ioremap_debug`。

## 5. 使用场景

- **内核启动早期**：在 `paging_init()` 之前访问设备寄存器或 ACPI/SMBIOS 等固件表。
- **ACPI/UEFI 初始化**：解析和访问位于高物理地址的固件数据结构。
- **内存探测**：在建立完整内存映射前读取内存控制器寄存器。
- **安全启动验证**：在初始化完整 I/O 子系统前验证硬件状态。
- **架构移植**：为新架构提供标准化的早期映射接口，避免重复实现。

> 注意：所有早期映射必须在内核进入 `SYSTEM_RUNNING` 状态前解除，否则会触发警告。生产系统应避免长期持有早期映射。