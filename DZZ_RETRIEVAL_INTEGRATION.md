# dzz 检索系统集成说明

## ✅ 集成完成

已成功将 dzz 项目的两阶段检索逻辑集成到 `CodeRAGWorkflow` 的第二步检索部分。

## 📋 修改内容

### 1. 导入模块 (`simple_rag_workflow.py`)
- 添加了 `rank_chunks_by_semantic` 模块的导入逻辑
- 支持自动路径检测和错误处理

### 2. `CodeRAGWorkflow.__init__` 方法
新增参数：
- `chroma_md_path`: dzz 检索系统的 ChromaDB 路径（默认: `./dzz_retrieval/chroma_md`）
- `top_files`: 文件级检索返回的文件数量（默认: 3）
- `top_chunks`: 每个文件返回的代码块数量（默认: 5）

新增方法：
- `_init_dzz_retrieval()`: 初始化 dzz 的文件摘要向量库

### 3. `_retrieve_code_with_suggestion` 方法
完全重写，使用 dzz 的两阶段检索逻辑：

**阶段1：文件级检索**
- 使用 `kernel_file_summaries` 集合进行向量检索
- 找到最相关的源文件（默认 top 3）

**阶段2：代码块级语义排序**
- 使用 `rank_chunks_by_semantic` 对候选文件中的代码块进行语义排序
- 返回最相关的代码块（默认每个文件 top 5）

### 4. `rank_chunks_by_semantic.py` 路径修复
- 添加了自动路径检测功能
- 支持在不同目录结构下找到 JSON 文件

## 🧪 测试结果

### 测试查询：`"Linux 如何实现进程记账"`

**阶段1 - 文件级检索结果：**
- ✅ `acct.c` (相似度: 0.7519)
- ✅ `tsacct.c` (相似度: 0.6995)
- ✅ `taskstats.c` (相似度: 0.6469)

**阶段2 - 代码块级检索结果：**
- ✅ 找到 5 个相关代码块
- ✅ 最高相似度: 0.6842
- ✅ 代码块包含完整的函数名、行号、描述等信息

## 📊 工作流程

现在的完整检索流程：

```
用户查询
    ↓
步骤1: 生成源码检索建议 (CodeRetrievalSuggester)
    ↓
步骤2: 两阶段检索 (dzz 检索逻辑)
    ├─ 阶段1: 文件级检索 (kernel_file_summaries 集合)
    └─ 阶段2: 代码块级语义排序 (rank_chunks_by_semantic)
    ↓
步骤3: 生成代码描述 (LLM)
```

## 🚀 使用方法

### 基本使用

```python
from simple_rag_workflow import CodeRAGWorkflow

# 初始化工作流
workflow = CodeRAGWorkflow(
    llm_path="...",
    embedding_model_path="...",
    chroma_md_path="./dzz_retrieval/chroma_md",  # dzz 检索系统路径
    top_files=3,      # 文件级检索数量
    top_chunks=5      # 代码块级检索数量
)

# 处理查询
response = workflow.process_code_query("Linux 如何实现进程记账")

# 查看结果
for chunk in response.retrieved_chunks:
    print(f"文件: {chunk.filename}")
    print(f"路径: {chunk.metadata['file_path']}")
    print(f"行号: {chunk.metadata['line_range']}")
    print(f"函数: {chunk.metadata['function_name']}")
    print(f"描述: {chunk.metadata['description']}")
    print(f"相似度: {chunk.score}")
```

## 📁 文件结构

```
workflow_wxk/
├── simple_rag_workflow.py          # 主工作流文件（已修改）
├── dzz_retrieval/                  # dzz 检索系统
│   ├── chroma_md/                  # 文件摘要向量库
│   │   └── chroma.sqlite3         # ChromaDB 数据库（487个文件）
│   ├── kernel_chunks_with_descriptions.json  # 代码块数据（437文件，3113块）
│   ├── rank_chunks_by_semantic.py  # 代码块语义排序（已修复路径）
│   └── retrieval_engine.py         # 原始检索引擎（参考）
├── test_dzz_retrieval_integration.py  # 完整测试脚本
└── test_dzz_retrieval_only.py      # 轻量级测试脚本（仅检索）
```

## ✅ 验证清单

- [x] dzz 检索系统文件已复制
- [x] 文件摘要向量库初始化成功（487个文件）
- [x] 代码块索引加载成功（437个文件，3113个代码块）
- [x] 文件级检索正常工作
- [x] 代码块级检索正常工作
- [x] 两阶段检索逻辑集成成功
- [x] 检索结果转换为 RetrievedChunk 格式
- [x] 备用检索方法保留（当 dzz 系统不可用时）

## 🔧 故障排除

### 如果检索失败

1. **检查路径配置**
   ```python
   # 确保 chroma_md_path 指向正确的目录
   chroma_md_path = "./dzz_retrieval/chroma_md"
   ```

2. **检查数据文件**
   ```bash
   # 确认文件存在
   ls -lh dzz_retrieval/kernel_chunks_with_descriptions.json
   ls -lh dzz_retrieval/chroma_md/chroma.sqlite3
   ```

3. **检查集合名称**
   - 文件摘要集合名称：`kernel_file_summaries`
   - 如果集合不存在，会使用备用检索方法

### 备用检索方法

如果 dzz 检索系统初始化失败，会自动回退到原有的 `CodeRAGEngine` 检索方法。

## 📝 注意事项

1. **性能考虑**
   - 文件级检索：快速（向量检索）
   - 代码块级检索：需要加载模型和计算相似度，可能较慢
   - 建议 `top_files` 和 `top_chunks` 不要设置过大

2. **数据更新**
   - 如果更新了 `kernel_chunks_with_descriptions.json`，需要重启程序
   - 如果更新了文件摘要，需要重新构建 ChromaDB

3. **内存使用**
   - `rank_chunks_by_semantic` 会在启动时加载所有代码块索引到内存
   - 确保有足够的内存（约 18MB JSON 文件）

## 🎉 总结

dzz 检索系统已成功集成到 `CodeRAGWorkflow` 中，两阶段检索逻辑工作正常。现在可以：
- 使用文件级检索快速定位相关文件
- 使用代码块级语义排序找到最相关的代码片段
- 获得包含完整元数据（文件路径、行号、函数名、描述）的检索结果

