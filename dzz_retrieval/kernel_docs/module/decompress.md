# module\decompress.c

> 自动生成时间: 2025-10-25 14:59:42
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `module\decompress.c`

---

# module/decompress.c 技术文档

## 文件概述

`module/decompress.c` 是 Linux 内核模块加载子系统中的一个关键组件，负责对压缩格式的内核模块进行解压。该文件实现了对多种压缩算法（GZIP、XZ、ZSTD）的支持，将压缩的模块二进制数据解压到内核可执行内存中，供后续的模块加载流程使用。该功能由 `CONFIG_MODULE_COMPRESS_*` 配置选项启用，是内核模块按需压缩部署机制的核心部分。

## 核心功能

### 主要函数

- **`module_extend_max_pages()`**  
  动态扩展 `load_info` 结构中用于存储解压后页面指针的数组容量。

- **`module_get_next_page()`**  
  为解压过程分配新的高内存页，并将其记录到 `load_info->pages` 数组中。

- **`module_gzip_decompress()`**  
  使用 zlib 库对 GZIP 格式的压缩模块进行解压。

- **`module_xz_decompress()`**  
  使用 XZ 解压库对 XZ 格式的压缩模块进行解压。

- **`module_zstd_decompress()`**  
  使用 ZSTD 库对 ZSTD 格式的压缩模块进行解压。

- **`module_decompress()`**  
  模块解压的统一入口函数，根据编译配置调用对应的解压实现，并完成内存映射。

- **`module_decompress_cleanup()`**  
  清理解压过程中分配的资源，包括页面、页表映射和页指针数组。

- **`module_decompress_sysfs_init()`**（仅当 `CONFIG_SYSFS` 启用）  
  在 sysfs 中创建 `compression` 只读属性，暴露当前内核使用的模块压缩算法。

### 数据结构

- **`struct load_info`**（定义于 `internal.h`）  
  模块加载过程中的核心上下文结构，本文件主要使用其以下字段：
  - `pages`：指向已分配页面的指针数组
  - `max_pages`：`pages` 数组的当前容量
  - `used_pages`：已使用的页面数量
  - `hdr`：解压后模块内容的虚拟地址映射
  - `len`：解压后模块的实际字节长度
  - `compressed_len`：（仅当 `CONFIG_MODULE_STATS` 启用）原始压缩数据长度

## 关键实现

### 动态页面管理机制

解压过程采用按需分配页面的策略：
1. 初始预分配页面数为压缩数据所需页数的两倍（启发式估计）
2. 当页面用尽时，通过 `module_extend_max_pages()` 将容量翻倍
3. 所有页面通过 `alloc_page(GFP_KERNEL | __GFP_HIGHMEM)` 分配，支持高内存区域
4. 解压完成后通过 `vmap()` 将离散页面映射为连续虚拟地址空间供后续解析使用

### 压缩格式识别与处理

每种压缩格式实现包含两个关键步骤：
1. **签名验证**：检查输入数据头部是否匹配特定压缩格式的魔数
   - GZIP: `0x1f 0x8b 0x08`
   - XZ: `0xfd '7' 'z' 'X' 'Z' 0x00`
   - ZSTD: `0x28 0xb5 0x2f 0xfd`
2. **流式解压**：循环分配页面并填充解压数据，直到解压完成或出错

### GZIP 特殊处理

GZIP 头部可能包含可选文件名字段，`module_gzip_header_len()` 函数通过扫描 `\0` 终止符动态计算头部长度，确保解压器从正确位置开始处理压缩数据流。

### 错误处理与资源清理

所有解压函数采用统一的错误处理模式：
1. 遇到错误时立即跳转到清理标签
2. 释放工作区内存（zlib/xz/zstd 各自的工作空间）
3. 顶层 `module_decompress()` 调用 `module_decompress_cleanup()` 确保无资源泄漏

### Sysfs 集成

当启用 `CONFIG_SYSFS` 时，通过 `late_initcall` 在 `/sys/module/` 目录下创建 `compression` 属性文件，内容为当前配置的压缩算法名称（如 "gzip"），便于用户空间查询内核模块压缩策略。

## 依赖关系

- **内部依赖**：
  - `internal.h`：定义 `struct load_info` 和模块加载内部接口
  - `linux/module.h`：模块子系统核心头文件

- **压缩库依赖**（根据配置）：
  - `linux/zlib.h`：提供 GZIP 解压支持
  - `linux/xz.h`：提供 XZ 解压支持  
  - `linux/zstd.h`：提供 ZSTD 解压支持

- **内存管理依赖**：
  - `linux/vmalloc.h`：提供 `vmap()`/`vunmap()` 用于页面映射
  - `linux/highmem.h`：提供 `kmap_local_page()`/`kunmap_local()` 用于高内存页访问
  - `linux/slab.h`：提供 `kvmalloc()`/`kvfree()` 用于大块内存分配

- **系统设施依赖**：
  - `linux/sysfs.h`：提供 sysfs 属性创建接口（当 `CONFIG_SYSFS` 启用时）
  - `linux/kobject.h`：提供 kobject 操作接口

## 使用场景

1. **模块加载流程**：当内核通过 `init_module()` 或 `finit_module()` 系统调用加载压缩模块时，`module_decompress()` 被调用以解压模块二进制数据。

2. **内核启动阶段**：在早期用户空间（如 initramfs）加载压缩驱动模块时，此解压机制确保关键驱动能被正确加载。

3. **内存受限环境**：在嵌入式或资源受限系统中，通过压缩模块减少存储占用，运行时按需解压到内存。

4. **安全启动场景**：某些安全启动实现可能要求模块以压缩形式存储，加载时验证并解压，此文件提供基础解压能力。

5. **运行时诊断**：通过 sysfs 的 `compression` 属性，系统管理员可确认当前内核支持的模块压缩格式，用于调试或兼容性检查。