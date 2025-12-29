# bpf\tnum.c

> 自动生成时间: 2025-10-25 12:35:17
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `bpf\tnum.c`

---

# `bpf/tnum.c` 技术文档

## 1. 文件概述

`bpf/tnum.c` 实现了 **tnum（tracked number 或 tristate number）** 抽象数据类型，用于在 eBPF 验证器（verifier）中对整数值的位级知识进行建模和传播。  
每个位可以处于三种状态之一：
- **已知为 0**
- **已知为 1**
- **未知（用 `x` 表示）**

tnum 通过 `value` 和 `mask` 两个字段表示：
- `value`：所有**已知位**的实际值（未知位在 `value` 中为 0）
- `mask`：指示哪些位是**未知的**（`mask` 中为 1 的位表示该位未知）

该机制使得 eBPF 验证器能够在不确切知道寄存器具体值的情况下，安全地推断其可能的取值范围，从而进行边界检查、指针算术验证等关键安全分析。

---

## 2. 核心功能

### 数据结构
- `struct tnum`：核心结构体，包含 `u64 value` 和 `u64 mask`

### 常量
- `tnum_unknown`：表示完全未知的值（`value=0, mask=-1`）

### 构造函数
- `tnum_const(u64 value)`：创建一个所有位都已知的常量 tnum
- `tnum_range(u64 min, u64 max)`：根据最小值和最大值构造一个覆盖该区间的 tnum

### 位移操作
- `tnum_lshift(struct tnum a, u8 shift)`：逻辑左移
- `tnum_rshift(struct tnum a, u8 shift)`：逻辑右移
- `tnum_arshift(struct tnum a, u8 min_shift, u8 insn_bitness)`：算术右移（考虑符号扩展）

### 算术与逻辑运算
- `tnum_add(a, b)`：加法
- `tnum_sub(a, b)`：减法
- `tnum_and(a, b)`：按位与
- `tnum_or(a, b)`：按位或
- `tnum_xor(a, b)`：按位异或
- `tnum_mul(a, b)`：乘法（基于部分积算法）

### 集合与关系操作
- `tnum_intersect(a, b)`：计算两个 tnum 的交集（保守合并已知信息）
- `tnum_in(a, b)`：判断 tnum `b` 是否是 tnum `a` 的子集（即 `b` 的所有可能值都在 `a` 的可能值中）
- `tnum_is_aligned(a, u64 size)`：检查 tnum 表示的所有可能值是否对齐到 `size`（`size` 必须是 2 的幂）

### 类型转换与子寄存器操作
- `tnum_cast(a, u8 size)`：将 tnum 截断为指定字节数（如 1、2、4、8 字节）
- `tnum_subreg(a)`：提取低 32 位（等价于 `tnum_cast(a, 4)`）
- `tnum_clear_subreg(a)`：清空低 32 位（高 32 位保留，低 32 位置 0）
- `tnum_with_subreg(reg, subreg)`：将 `subreg` 的低 32 位写入 `reg` 的低 32 位
- `tnum_const_subreg(a, u32 value)`：将 `a` 的低 32 位设为常量 `value`

### 调试辅助
- `tnum_sbin(char *str, size_t size, struct tnum a)`：将 tnum 转换为二进制字符串（`0`/`1`/`x`），用于调试输出

---

## 3. 关键实现

### tnum 表示原理
- 对于任意位 `i`：
  - 若 `mask[i] == 0`，则该位已知，值为 `value[i]`
  - 若 `mask[i] == 1`，则该位未知（可为 0 或 1）
- 所有可能的实际值集合为：`{ value | x, 其中 x & ~mask == 0 }`

### `tnum_range` 算法
- 计算 `min ^ max` 得到差异位 `chi`
- 找到最高差异位位置 `bits = fls64(chi)`
- 构造掩码 `delta = (1ULL << bits) - 1`，覆盖从最低位到最高差异位的所有位
- 返回 `TNUM(min & ~delta, delta)`，即高位与 `min` 相同，低位全为未知

### `tnum_add` / `tnum_sub` 的进位传播
- 利用 `sigma = (a.mask + a.value) + (b.mask + b.value)` 和 `sv = a.value + b.value`
- 通过 `chi = sigma ^ sv` 检测进位影响的位
- 最终 `mu = chi | a.mask | b.mask` 表示所有可能受未知位或进位影响的位

### `tnum_mul` 的部分积算法
- 参考论文 [arXiv:2105.05398](https://arxiv.org/abs/2105.05398)
- 遍历乘数 `a` 的每一位：
  - 若为确定 1：累加 `b.mask` 到 mask 累加器
  - 若为不确定（mask 位为 1）：累加 `b.value | b.mask`（即 `b` 的最大可能值）
- 最终结果 = `tnum_add(常量部分, mask 累加器)`

### `tnum_intersect` 的保守合并
- `v = a.value | b.value`：只有当两个 tnum 在某位都为 0 时，结果才为 0
- `mu = a.mask & b.mask`：只有当两个 tnum 在某位都未知时，结果才未知
- 结果 `TNUM(v & ~mu, mu)` 保证是两个输入 tnum 的公共可能值集合的超集（保守）

---

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/kernel.h>`：提供基本内核宏和函数（如 `fls64`）
  - `<linux/tnum.h>`：定义 `struct tnum` 和函数声明
- **被依赖模块**：
  - **eBPF 验证器（`kernel/bpf/verifier.c`）**：核心使用者，用于寄存器状态跟踪
  - **BPF JIT 编译器**：部分后端可能使用 tnum 进行优化
  - **BPF 类型格式（BTF）和 map 实现**：间接依赖验证器的分析结果

---

## 5. 使用场景

1. **eBPF 程序验证**：
   - 跟踪寄存器在每条指令执行后的可能值范围
   - 验证指针算术不会越界（如 `ptr + offset` 中 `offset` 的 tnum 用于检查是否超出 map 边界）
   - 确保条件分支（如 `if (reg > 0)`）后，寄存器状态被正确约束

2. **常量传播与死代码消除**：
   - 若 tnum 表示常量（`mask == 0`），验证器可进行常量折叠
   - 若某分支条件恒假（如 `tnum_is_const(reg) && reg.value == 0`），可标记为不可达

3. **内存安全分析**：
   - 结合 tnum 与指针类型信息，验证 load/store 操作的地址合法性
   - 检查数组/结构体访问是否在合法偏移范围内

4. **调试与日志**：
   - `tnum_sbin` 用于在 verifier 日志中打印寄存器状态（如 `R0_w=invP(id=0,umax_value=255,var_off=(0x0; 0xff))` 中的 `var_off` 即 tnum 的二进制表示）