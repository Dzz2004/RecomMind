# page_reporting.c

> 自动生成时间: 2025-12-07 17:05:31
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `page_reporting.c`

---

# page_reporting.c 技术文档

## 1. 文件概述

`page_reporting.c` 是 Linux 内核中实现**空闲页报告（Page Reporting）**机制的核心模块。该机制允许内核将大块连续的空闲物理内存信息异步上报给注册的设备驱动（如 virtio-balloon、内存热插拔管理器等），以便这些设备可以回收或迁移这些内存，从而提升系统整体内存利用效率。本文件负责协调从伙伴系统（buddy allocator）中提取符合要求的空闲页、构建散列表（scatterlist）、调用设备驱动的报告回调，并在报告完成后将页面安全地归还到伙伴系统。

## 2. 核心功能

### 主要全局变量
- `page_reporting_order`: 可通过内核启动参数或 sysfs 配置的全局变量，指定待报告空闲页块的最小阶数（order）。默认值为 `-1`（表示未设置），有效范围为 `[0, MAX_PAGE_ORDER]`。导出为 GPL 符号供其他驱动访问。
- `pr_dev_info`: 指向当前注册的 `page_reporting_dev_info` 结构的 RCU 保护指针，代表提供页报告服务的设备。

### 主要函数
- `__page_reporting_notify(void)`: 通知已注册的页报告设备有新的空闲页可供报告。这是内核其他部分（如内存释放路径）触发报告流程的入口点。
- `__page_reporting_request(struct page_reporting_dev_info *prdev)`: 内部函数，用于向指定设备请求启动页报告工作。包含状态机管理和延迟调度逻辑。
- `page_reporting_drain(...)`: 在设备完成页报告（无论成功与否）后，将散列表中的页面重新放回伙伴系统的对应 free_area 和 migratetype 列表中，并根据报告结果设置 `PG_reported` 标志位。
- `page_reporting_cycle(...)`: 核心处理循环，遍历指定 zone、order 和 migratetype 的 free_list，隔离未报告的页面到散列表中，达到容量后触发设备报告回调。
- `page_reporting_process_zone(...)`: 处理单个内存区域（zone）的入口函数，负责水位线检查并按 order 从高到低调用 `page_reporting_cycle`。

### 关键数据结构（外部定义）
- `struct page_reporting_dev_info`: 由设备驱动提供，包含报告回调函数 `report()`、工作队列 `work` 和状态原子变量 `state` 等。

## 3. 关键实现

### 状态机与延迟调度
- 使用原子变量 `prdev->state` 管理三种状态：`IDLE`（空闲）、`REQUESTED`（已请求）、`ACTIVE`（活跃中）。
- 当收到报告请求时，若当前为空闲状态，则调度一个延迟为 `2 * HZ`（约 2 秒）的 `delayed_work`。此延迟旨在累积足够多的空闲页再进行批量报告，减少频繁调用设备驱动的开销。

### 页面隔离与归还
- **隔离**: 在持有 zone 自旋锁期间，使用 `__isolate_free_page()` 将符合条件的 Buddy 页面从 free_list 中移除。
- **归还**: 报告完成后，在 `page_reporting_drain()` 中调用 `__putback_isolated_page()` 将页面放回原 free_area 和 migratetype 列表。
- **报告标记**: 仅当页面在报告后仍保持 Buddy 状态且其阶数未变时，才设置 `PG_reported` 标志，避免对已合并的大页面重复报告。

### 散列表（Scatterlist）管理
- 使用固定大小（`PAGE_REPORTING_CAPACITY`）的散列表作为设备驱动和内核之间的传输缓冲区。
- 采用“填满即报”的策略：当散列表填满或遍历完当前 free_list 后，立即调用设备驱动的 `report()` 回调。
- 报告完成后重置散列表（`sg_init_table`）以供下次使用。

### 遍历策略与预算控制
- **遍历顺序**: 按内存区域（zone）、迁移类型（migratetype）、页面阶数（order，从高到低）进行嵌套遍历。
- **预算限制**: 对每个 `(zone, order, mt)` 组合设置处理预算（`budget`），防止单次处理耗时过长影响系统响应。预算基于该 free_area 中空闲页数量动态计算。
- **列表旋转**: 在中断遍历时，将下一个待处理页面旋转到 free_list 头部（`list_rotate_to_front`），确保下次从断点继续，避免饥饿。

### 水位线保护
- 在 `page_reporting_process_zone()` 中检查 zone 的空闲页是否高于 `low_wmark + (capacity << reporting_order)`，防止因报告操作导致内存水位过低而引发分配失败或 OOM。

## 4. 依赖关系

- **内部依赖**:
  - `mm/internal.h`: 提供 `__putback_isolated_page()`、`__isolate_free_page()` 等伙伴系统内部操作函数。
  - `page_reporting.h` (本地): 定义本地辅助函数和常量（如 `PAGE_REPORTING_CAPACITY`）。
- **外部依赖**:
  - `<linux/mm.h>`, `<linux/mmzone.h>`: 内存管理核心头文件，提供 `struct zone`、`free_area`、页面操作宏等。
  - `<linux/page_reporting.h>`: 定义公共接口 `struct page_reporting_dev_info` 和注册/注销 API。
  - `<linux/scatterlist.h>`: 提供散列表操作函数（`sg_set_page`, `sg_next` 等）。
  - 设备驱动: 必须实现 `page_reporting_dev_info.report` 回调函数，并通过 `page_reporting_register()` 注册。

## 5. 使用场景

- **虚拟化环境**: Virtio-balloon 驱动利用此机制向宿主机报告客户机中大块空闲内存，宿主机可将其回收用于其他虚拟机，提高物理内存利用率。
- **内存热插拔/卸载**: 在移除内存前，通过页报告机制确保目标内存区域尽可能空闲，减少迁移成本。
- **透明大页（THP）优化**: 协助识别和释放可用于 THP 分配的大块连续空闲内存。
- **通用内存回收**: 任何需要感知系统大块空闲内存布局的子系统（如 CMA、HMM）均可注册为页报告设备，实现定制化内存管理策略。