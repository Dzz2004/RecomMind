# Linux Kernel 教学检索系统（RAG 上下文生成器）

本系统专为**操作系统教材师生**设计，支持通过自然语言查询（如 “Linux 如何实现进程记账？”）自动检索 Linux 内核源码中相关的**文件摘要**与**关键代码片段描述**，生成结构化上下文，供下游大模型（如 Qwen3）生成教学友好型解释。

---

## 📦 系统组成

- **`kernel_docs/`**：人工/半自动生成的 `.md` 文件，每个对应一个内核源文件（如 `acct.md` ↔ `kernel/acct.c`），包含：
  - 文件概述
  - 核心功能
  - 关键实现
  - 依赖关系
  - 使用场景
- **`kernel_chunks_with_descriptions.json`**：基于 Tree-sitter 的语义分块结果，包含 437 个文件、3113 个 chunks，每个 chunk 含：
  - 代码范围（行号）
  - 涉及函数名
  - LLM 生成的 description
- **`chroma_md/`**：基于 BGE-M3 的 `.md` 文件向量库（文件级检索）
- **`RetrievalEngine`**：两阶段检索引擎（文件 → chunks），输出结构化 JSON

---

## 🚀 快速开始（下游开发者）

### 1. 安装依赖

```bash
pip install chromadb sentence-transformers tqdm
```

> ✅ 确保已下载 BGE-M3 模型至：
> ```
> /home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/...
> ```

### 2. 目录结构要求

```
your_project/
├── kernel_docs/               # .md 文件目录（必须）
├── embeddings_md.py          # .md 向量化脚本（可选）
├── kernel_chunks_with_descriptions.json  # chunk 数据（必须）
├── chroma_md/                 # 已构建的向量库（必须）
├── retrieval_engine.py        # 本系统核心 检索引擎模块
└── rank_chunks_by_semantic.py # 语义排序模块
```

### 3. 调用检索接口（Python）

```python
from retrieval_engine import RetrievalEngine

engine = RetrievalEngine(
    chroma_md_path="./chroma_md",
    top_files=3,      # 返回最相关的 3 个文件
    top_chunks=5      # 每个文件返回 top-5 chunks
)

# 执行检索
result = engine.retrieve("Linux 如何实现进程记账？")

# result 是 dict，可直接作为 RAG 上下文传给 LLM
print(result["retrieved_files"][0]["chunks"][0]["description"])
```

### 4. 输出结构说明

```json
{
  "query": "用户查询",
  "timestamp": "2025-10-28 15:30:45",
  "retrieved_files": [
    {
      "source_file": "kernel/acct.c",
      "md_summary": "该文件实现了进程记账机制...",
      "similarity": 0.92,
      "chunks": [
        {
          "chunk_id": 3,
          "file_path": "kernel\\acct.c",
          "start_line": 544,
          "end_line": 644,
          "function_name": "acct_write_process, do_acct_process, ...",
          "description": "该代码块将进程退出时的资源使用情况写入记账文件...",
          "similarity": 0.89
        }
      ]
    }
  ]
}
```

> 💡 **下游 LLM Prompt 建议**：
> ```
> 你是一名操作系统教师。请基于以下内核实现上下文，用通俗易懂的语言解释：
> 
> 【文件摘要】
> {md_summary}
> 
> 【关键代码逻辑】
> - {chunk1.description}
> - {chunk2.description}
> 
> 问题：{user_query}
> ```

---

## 🔧 上游开发者：如何更新知识库

### 1. 更新 `.md` 文件

- 将新的 `xxx.md` 放入 `kernel_docs/`，确保：
  - 第一行为 `# kernel/xxx.c`（路径需与内核源码一致）
  - 内容包含五大部分（概述、功能、实现、依赖、场景）

### 2. 重建 ChromaDB（仅当 .md 变更时）

运行 `vectorize_md_docs.py`（见配套脚本）：

```bash
python vectorize_md_docs.py
```

> ⚠️ 无需重新生成 chunks 或 description。

### 3. 更新 chunk 数据（仅当源码或分块逻辑变更）

- 重新运行 Tree-sitter 分块 + LLM description 生成
- 替换 `kernel_treesitter_chunks.json`

> ✅ **注意**：`RetrievalEngine` 会自动加载最新 JSON，无需重启服务。

---

## 🧪 终端交互测试

```bash
python retrieval_engine.py
```

输入自然语言问题，系统将：
- 打印检索结果
- 保存 JSON 到 `./retrieval_results/`
- 返回结构化 dict（可用于调试）

---

## ✅ 优势总结

| 角色 | 收益 |
|------|------|
| **下游 LLM 开发者** | 获得高质量、教学导向的 RAG 上下文，无需处理原始代码 |
| **上游知识库维护者** | 模块化更新（.md / chunks 独立），低维护成本 |
| **终端师生用户** | 用自然语言理解内核机制，无需记忆函数名或文件路径 |

---

> 📌 **适用场景**：操作系统教学、内核机制问答、源码学习辅助  
> 🚫 **不适用场景**：精确符号查找（如 “`acct_write_process` 在哪？”）——此类需求建议搭配 cscope/tags

--- 

**项目维护**：建议定期用最新内核版本更新 `.md` 和 chunks，保持知识库时效性。