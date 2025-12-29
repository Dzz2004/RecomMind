# livepatch\state.c

> 自动生成时间: 2025-10-25 14:33:58
> 
> 生成工具: 通义千问 API (qwen3-max)
> 
> 原始文件: `livepatch\state.c`

---

# livepatch/state.c 技术文档

## 1. 文件概述

`livepatch/state.c` 是 Linux 内核实时补丁（Livepatch）子系统中的一个核心组件，用于管理和查询由实时补丁修改的系统状态（system state）。该文件提供了机制，使得多个实时补丁能够安全地协同工作，尤其是在处理共享或依赖的系统状态时，确保状态版本兼容性，防止因状态不一致导致系统崩溃或行为异常。

## 2. 核心功能

### 主要函数

- **`klp_get_state(struct klp_patch *patch, unsigned long id)`**  
  根据指定的补丁对象和状态 ID，查找该补丁所声明的系统状态结构体。若存在则返回指向 `struct klp_state` 的指针，否则返回 `NULL`。

- **`klp_get_prev_state(unsigned long id)`**  
  在实时补丁过渡（transition）过程中，查找所有已安装（但不包括当前正在过渡的）补丁中，对指定 ID 的系统状态的最新修改记录。返回最新（即最后安装的）补丁中的对应状态结构体，若未找到则返回 `NULL`。

- **`klp_is_state_compatible(struct klp_patch *patch, struct klp_state *old_state)`**  
  判断给定补丁是否能兼容已存在的系统状态。若补丁为累积型（`replace == true`），则必须显式声明对该状态的支持；若为非累积型，则可忽略。对于声明了该状态的补丁，其状态版本号必须不小于已有状态的版本号。

- **`klp_is_patch_compatible(struct klp_patch *patch)`**  
  检查新加载的补丁是否与所有已安装补丁所修改的系统状态兼容。遍历所有已安装补丁的状态，调用 `klp_is_state_compatible` 进行验证。只要有一个状态不兼容，即返回 `false`。

### 数据结构

- **`struct klp_state`**（定义在 `state.h` 中）  
  表示一个由实时补丁修改的系统状态，包含：
  - `id`：用户自定义的唯一状态标识符（`unsigned long`）
  - `version`：状态的版本号，用于兼容性检查
  - 其他可能的字段（如回调函数指针等，由头文件定义）

- **`struct klp_patch`**（定义在 `core.h` 中）  
  表示一个完整的实时补丁对象，包含其修改的状态数组（`states` 字段）。

## 3. 关键实现

- **状态遍历宏 `klp_for_each_state`**  
  通过 `for` 循环遍历 `patch->states` 数组，直到遇到 `id == 0` 的终止项，实现对补丁所声明状态的高效迭代。

- **状态兼容性逻辑**  
  - **累积补丁（Cumulative Patch）**：通过 `patch->replace == true` 标识，必须显式处理所有已存在的系统状态，否则视为不兼容。
  - **非累积补丁（Non-cumulative Patch）**：可选择性忽略已有状态，但若声明了相同 `id` 的状态，则其 `version` 必须 ≥ 已有状态的 `version`，确保向后兼容。

- **`klp_get_prev_state` 的上下文限制**  
  该函数仅在补丁过渡期间有效（通过 `klp_transition_patch` 全局变量判断），且遍历已安装补丁时跳过当前正在过渡的补丁，确保返回的是“之前”安装的最新状态。

- **安全断言**  
  在 `klp_get_prev_state` 中使用 `WARN_ON_ONCE(!klp_transition_patch)` 防止在非过渡上下文中误用该函数，增强代码健壮性。

## 4. 依赖关系

- **头文件依赖**：
  - `<linux/livepatch.h>`：提供 Livepatch 子系统的公共接口和数据结构定义。
  - `"core.h"`：包含 `struct klp_patch` 和补丁管理相关内部接口（如 `klp_for_each_patch` 宏）。
  - `"state.h"`：定义 `struct klp_state` 及相关辅助宏。
  - `"transition.h"`：提供 `klp_transition_patch` 全局变量，用于标识当前过渡中的补丁。

- **模块导出**：
  - `klp_get_state` 和 `klp_get_prev_state` 通过 `EXPORT_SYMBOL_GPL` 导出，供其他 GPL 兼容的内核模块（如具体的实时补丁模块）在 pre/post (un)patch 回调或补丁代码中调用。

## 5. 使用场景

- **实时补丁开发**：补丁作者在 pre/post (un)patch 回调函数中调用 `klp_get_state` 获取自身声明的状态，或调用 `klp_get_prev_state` 查询已有补丁对该状态的修改，以实现状态迁移或数据转换。

- **补丁加载时的兼容性检查**：内核在启用新补丁前调用 `klp_is_patch_compatible`，确保新补丁不会破坏由先前补丁建立的系统状态，保障系统稳定性。

- **多补丁协同工作**：当多个非累积补丁修改同一系统状态时，通过版本号机制确保状态演进有序；累积补丁则必须整合所有历史状态，实现“全量替换”语义。

- **过渡阶段状态查询**：仅在补丁启用/回滚的过渡窗口期内，允许查询“前一个”状态，用于实现平滑的状态切换逻辑。