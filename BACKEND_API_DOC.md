# 后端API文档

## 📋 API接口列表

### 1. 健康检查

**接口**: `GET /api/health`

**描述**: 检查服务状态，包括教材RAG和源码检索工作流的状态

**响应示例**:
```json
{
  "code": 200,
  "message": "服务正常",
  "data": {
    "rag_workflow": "healthy",
    "code_rag_workflow": "healthy",
    "overall": "healthy"
  },
  "timestamp": "2024-11-14T15:50:00"
}
```

---

### 2. 聊天接口（支持教材和源码检索）

**接口**: `POST /api/chat`

**描述**: 统一的聊天接口，支持教材检索和源码检索（可同时启用）

**请求体**:
```json
{
  "userInput": "用户问题",
  "useRag": true,          // 是否启用教材检索
  "useCodeRetrieval": true // 是否启用源码检索
}
```

**响应**: SSE (Server-Sent Events) 流式响应

**事件类型**:
- `retrieval`: 教材检索结果
- `code_retrieval`: 源码检索结果
- `answer_chunk`: 回答片段（流式输出）
- `code_description_chunk`: 代码描述片段（流式输出）
- `[DONE]`: 完成标记

**示例响应**:
```
data: {"documents": [...], "thought": "..."}

data: {"codes": [{"path": "kernel/acct.c", "startLine": 544, "endLine": 644, "description": "..."}]}

data: {"answer_chunk": "这是回答的第一部分..."}

data: {"answer_chunk": "这是回答的第二部分..."}

data: [DONE]
```

---

### 3. 源码检索专用接口

**接口**: `POST /api/code/query`

**描述**: 仅进行源码检索，不包含教材检索

**请求体**:
```json
{
  "userInput": "Linux 如何实现进程记账"
}
```

**响应**: SSE 流式响应

**事件类型**:
- `code_retrieval`: 源码检索结果（包含代码引用）
- `code_description_chunk`: 代码描述片段（流式输出）
- `[DONE]`: 完成标记

**示例响应**:
```
data: {"codes": [...], "thought": "..."}

data: {"answer_chunk": "代码描述..."}

data: [DONE]
```

---

### 4. 清空对话历史

**接口**: `POST /api/conversation/clear`

**描述**: 清空教材检索和源码检索的对话历史

**响应示例**:
```json
{
  "code": 200,
  "message": "对话历史清空成功",
  "data": {
    "cleared": ["教材检索", "源码检索"]
  }
}
```

---

### 5. 清空源码检索对话历史

**接口**: `POST /api/code/conversation/clear`

**描述**: 仅清空源码检索的对话历史

**响应示例**:
```json
{
  "code": 200,
  "message": "源码检索对话历史清空成功"
}
```

---

### 6. 获取对话摘要

**接口**: `GET /api/conversation/summary`

**描述**: 获取教材检索的对话摘要

**响应示例**:
```json
{
  "code": 200,
  "message": "获取对话摘要成功",
  "data": {
    "summary": "对话消息数: 5"
  }
}
```

---

### 7. 更新相似度阈值

**接口**: `POST /api/config/similarity-threshold`

**描述**: 更新教材检索的相似度阈值

**请求体**:
```json
{
  "threshold": 0.3
}
```

**响应示例**:
```json
{
  "code": 200,
  "message": "相似度阈值更新成功",
  "data": {
    "threshold": 0.3
  }
}
```

---

### 8. 获取教材RAG系统信息

**接口**: `GET /api/rag/info`

**描述**: 获取教材RAG系统的详细信息

**响应示例**:
```json
{
  "code": 200,
  "message": "获取RAG信息成功",
  "data": {
    "collection_info": {
      "collection_name": "textbook_content",
      "document_count": 195
    },
    "similarity_threshold": 0.0,
    "conversation_count": 5,
    "llm_path": "...",
    "embedding_model_path": "..."
  }
}
```

---

### 9. 获取源码检索系统信息

**接口**: `GET /api/code/info`

**描述**: 获取源码检索系统的详细信息

**响应示例**:
```json
{
  "code": 200,
  "message": "获取源码检索信息成功",
  "data": {
    "code_rag_engine": {
      "collection_name": "source_code",
      "document_count": 0
    },
    "dzz_collection": {
      "collection_name": "kernel_file_summaries",
      "document_count": 487
    },
    "similarity_threshold": 0.0,
    "conversation_count": 3,
    "llm_path": "...",
    "chroma_md_path": "./dzz_retrieval/chroma_md",
    "top_files": 3,
    "top_chunks": 5
  }
}
```

---

## 📝 数据模型

### CodeReference（代码引用）

```typescript
interface CodeReference {
  path: string;           // 文件路径，如 "kernel/acct.c"
  startLine: number;      // 起始行号
  endLine: number;        // 结束行号
  description?: string;    // 代码描述（可选）
}
```

### ChatRequest（聊天请求）

```typescript
interface ChatRequest {
  userInput: string;      // 用户输入
  useRag: boolean;         // 是否启用教材检索
  useCodeRetrieval: boolean; // 是否启用源码检索
}
```

### ChatResponse（聊天响应）

```typescript
interface ChatResponse {
  thought: string;         // AI思考过程
  answer: string;          // AI回答
  documents: RetrievedDocument[]; // 教材文档引用
  codes?: CodeReference[]; // 代码引用（可选）
}
```

---

## 🔧 使用示例

### Python 示例

```python
import requests

# 1. 健康检查
response = requests.get("http://localhost:5000/api/health")
print(response.json())

# 2. 源码检索查询
payload = {
    "userInput": "Linux 如何实现进程记账"
}

response = requests.post(
    "http://localhost:5000/api/code/query",
    json=payload,
    stream=True
)

for line in response.iter_lines():
    if line:
        line_str = line.decode('utf-8')
        if line_str.startswith('data: '):
            data_str = line_str[6:]
            if data_str != '[DONE]':
                data = json.loads(data_str)
                print(data)
```

### JavaScript 示例

```javascript
// 使用 EventSource 接收 SSE 流
const eventSource = new EventSource('http://localhost:5000/api/code/query', {
  method: 'POST',
  body: JSON.stringify({
    userInput: 'Linux 如何实现进程记账'
  })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.codes) {
    console.log('代码引用:', data.codes);
  }
  if (data.answer_chunk) {
    console.log('回答片段:', data.answer_chunk);
  }
};
```

---

## 🚀 启动后端服务器

```bash
cd /home/ubuntu/qj_temp/workflow_wxk
python3 backend_server.py
```

服务器将在 `http://localhost:5000` 启动。

---

## ✅ 测试

运行测试脚本：

```bash
python3 test_backend_api.py
```

测试包括：
- 健康检查
- 源码检索系统信息
- 源码检索查询
- 清空对话历史

