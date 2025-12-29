# audit.c

> 自动生成时间: 2025-10-25 11:49:55
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `audit.c`

---

# audit.c 技术文档

## 文件概述

`audit.c` 是 Linux 内核审计子系统的核心实现文件，负责提供内核与用户空间审计守护进程（auditd）之间的通信网关。该文件实现了审计记录的生成、队列管理、速率控制、网络命名空间支持以及与安全模块（如 SELinux）的集成。系统调用相关的审计逻辑已移至 `auditsc.c`，本文件聚焦于通用审计基础设施。

## 核心功能

### 主要全局变量
- `audit_enabled`：审计系统启用状态（导出符号）
- `audit_ever_enabled`：标记审计是否曾被启用
- `audit_failure`：审计失败时的行为策略（如打印内核日志）
- `audit_rate_limit`：每秒允许发送的审计记录上限（防 DoS）
- `audit_backlog_limit`：待发送审计消息队列的最大长度
- `audit_lost`：原子计数器，记录丢失的审计记录数量
- `audit_sig_uid/audit_sig_pid/audit_sig_sid`：关闭审计系统的用户身份信息

### 核心数据结构
- `struct audit_net`：每个网络命名空间的审计专用数据（含 netlink socket）
- `struct auditd_connection`：内核与 auditd 守护进程的连接状态（RCU 保护）
- `struct audit_buffer`：审计记录的临时格式化缓冲区
- `struct audit_reply`：审计响应消息结构
- `struct audit_ctl_mutex`：序列化用户空间请求的互斥锁（带所有者跟踪）

### 关键函数
- `auditd_test_task()`：检查指定任务是否为注册的 auditd 守护进程
- `audit_ctl_lock()/audit_ctl_unlock()`：获取/释放审计控制锁
- `audit_ctl_owner_current()`：检查当前任务是否持有审计控制锁
- `auditd_pid_vnr()`：获取 auditd 在当前 PID 命名空间中的 PID

### 队列系统
- `audit_queue`：待发送审计消息的主队列
- `audit_retry_queue`：因单播发送失败需重试的消息队列
- `audit_hold_queue`：等待新 auditd 连接建立时暂存的消息队列

## 关键实现

### 初始化状态机
审计系统通过 `audit_initialized` 三态变量控制初始化流程：
- `AUDIT_DISABLED` (-1)：显式禁用
- `AUDIT_UNINITIALIZED` (0)：初始状态
- `AUDIT_INITIALIZED` (1)：完成初始化（需在 `skb_init` 后）

### RCU 保护的 auditd 连接
`auditd_conn` 指针通过 RCU 机制保护，读操作使用 `rcu_read_lock()`，写操作需持有 `auditd_conn_lock` 自旋锁。这种设计确保高并发场景下连接状态的安全访问。

### 背压与速率控制
- **速率限制**：通过 `audit_rate_limit` 限制每秒发送记录数
- **背压机制**：当队列长度超过 `audit_backlog_limit` 时阻塞生产者，并累计等待时间到 `audit_backlog_wait_time_actual`
- **内存保护**：使用 `audit_buffer_cache` slab 缓存减少内存分配开销

### 锁所有权跟踪
`audit_ctl_mutex` 扩展标准 mutex，记录锁所有者 (`owner`)。此设计避免在 `audit_log_start()` 等路径中因递归锁导致死锁，确保审计日志生成不会阻塞持有控制锁的任务。

### 网络命名空间支持
通过 `audit_net_id` 实现 per-netns 审计 socket，每个网络命名空间拥有独立的 auditd 通信通道，符合内核网络命名空间隔离原则。

## 依赖关系

- **核心依赖**：
  - `<linux/audit.h>`：审计子系统公共接口
  - `<net/netlink.h>`：Netlink 通信机制
  - `<linux/security.h>`：LSM（Linux Security Module）集成点
- **子系统交互**：
  - **LSM 框架**：作为安全事件的消费者（如 SELinux 策略拒绝事件）
  - **PID 命名空间**：通过 `pid_vnr()` 获取命名空间内 PID
  - **RCU 机制**：用于 auditd 连接状态的无锁读取
  - **kthread**：`kauditd_task` 内核线程处理消息队列
- **配套文件**：
  - `auditsc.c`：系统调用审计逻辑
  - `audit.h`（本地）：内部头文件

## 使用场景

1. **安全事件记录**：当 LSM（如 SELinux/AppArmor）触发安全策略拒绝时，通过 `audit_log_*` 系列函数生成审计记录
2. **系统调用审计**：配合 `auditsc.c` 记录符合规则的系统调用（需启用 syscall auditing）
3. **用户空间交互**：
   - 接收 auditctl 配置命令（规则加载/查询）
   - 向 auditd 发送审计事件（通过 Netlink）
   - 处理 auditd 守护进程的生命周期事件（启动/停止）
4. **内核自检**：通过 `audit_failure` 配置项处理审计子系统内部错误（如内存不足）
5. **容器环境支持**：在 PID/net 命名空间中为每个容器提供独立的审计上下文