# RAG工作流前后端集成系统

这是一个完整的RAG（检索增强生成）工作流系统，包含Python后端API服务器和TypeScript前端界面。

## 系统架构

```
前端 (TypeScript/React) ←→ Python后端API服务器 ←→ RAG工作流
                                    ↓
                               Qwen3-8B模型 + BGE-M3嵌入模型
                                    ↓
                               ChromaDB向量数据库
```

## 功能特点

### 后端功能
- 🤖 集成Qwen3-8B大语言模型
- 🔍 基于BGE-M3的向量检索
- 📚 ChromaDB向量数据库存储
- 🔄 多轮对话管理
- ⚙️ 相似度阈值动态调整
- 📊 RAG系统状态监控

### 前端功能
- 💬 智能聊天界面
- 🔄 RAG模式开关
- 📄 文档引用显示
- 🧹 对话历史管理
- ⚙️ 系统配置界面

## 快速开始

### 1. 环境准备

确保已安装以下依赖：
- Python 3.8+
- Node.js 18+ (推荐18.20+，与Vite 4.x兼容)
- CUDA（可选，用于GPU加速）

**注意**: 如果使用Node.js 18，请确保使用Vite 4.x版本。如果使用Node.js 20+，可以使用Vite 7.x版本。

### 2. 启动后端服务器

```bash
cd workflow_wxk
chmod +x start_server.sh
./start_server.sh
```

或者手动启动：

```bash
# 安装依赖
pip3 install -r requirements.txt

# 启动服务器
python3 backend_server.py
```

后端服务器将在 `http://localhost:5000` 启动。

### 3. 启动前端应用

```bash
cd frontend
npm install
npm run dev
```

前端应用将在 `http://localhost:5173` 启动（Vite默认端口）。

**注意**: 这是一个Vue.js + Vite项目，使用 `npm run dev` 而不是 `npm start`。

**如果遇到Node.js版本兼容性问题**，可以运行修复脚本：

```bash
cd workflow_wxk
chmod +x fix_frontend.sh
./fix_frontend.sh
```

## API接口文档

### 聊天接口
- **URL**: `POST /api/chat`
- **请求体**:
  ```json
  {
    "userInput": "用户问题",
    "useRag": true
  }
  ```
- **响应**:
  ```json
  {
    "code": 200,
    "message": "聊天处理成功",
    "data": {
      "thought": "AI思考过程",
      "answer": "AI回答",
      "documents": [
        {
          "source": "ch1.pdf",
          "page": 5,
          "content": "文档内容",
          "chapter": 1,
          "finalPage": 15
        }
      ]
    }
  }
  ```

### 其他接口
- `POST /api/conversation/clear` - 清空对话历史
- `GET /api/conversation/summary` - 获取对话摘要
- `POST /api/config/similarity-threshold` - 更新相似度阈值
- `GET /api/rag/info` - 获取RAG系统信息
- `GET /api/health` - 健康检查

## 配置说明

### 模型路径配置
在 `backend_server.py` 中修改以下配置：

```python
config = {
    "llm_path": "你的Qwen3模型路径",
    "embedding_model_path": "你的BGE-M3模型路径",
    "db_path": "./vector_db",
    "similarity_threshold": 0.3
}
```

### 前端API地址配置
在 `frontend/src/api/chatbot.ts` 中修改：

```typescript
const API_CONFIG = {
  baseURL: 'http://localhost:5000/api', // 修改为你的后端地址
  timeout: 30000
}
```

## 故障排除

### 常见问题

1. **前端启动失败**
   - 确保使用 `npm run dev` 而不是 `npm start`
   - 检查Node.js版本是否 >= 18 (推荐18.20+)
   - 如果使用Node.js 18，确保Vite版本为4.x
   - 如果使用Node.js 20+，可以使用Vite 7.x
   - 删除 `node_modules` 和 `package-lock.json`，重新运行 `npm install`
   - 检查端口5173是否被占用

2. **模型加载失败**
   - 检查模型路径是否正确
   - 确保有足够的内存/显存
   - 检查CUDA环境（如果使用GPU）

3. **向量数据库错误**
   - 确保 `./vector_db` 目录存在且有写权限
   - 检查ChromaDB版本兼容性

4. **前端连接失败**
   - 检查后端服务器是否在 `http://localhost:5000` 启动
   - 确认Vite代理配置正确（`vite.config.ts`）
   - 检查浏览器控制台是否有CORS错误

5. **依赖包问题**
   - Python: 使用 `pip3 install -r requirements.txt` 重新安装
   - Node.js: 删除 `node_modules` 重新安装
   - 检查Python和Node.js版本兼容性

### 日志查看

后端日志会显示在控制台，包括：
- 模型加载状态
- API请求处理
- RAG检索过程
- 错误信息

## 开发说明

### 后端扩展
- 在 `backend_server.py` 中添加新的API路由
- 在 `simple_rag_workflow.py` 中扩展RAG功能
- 修改数据模型以适应新需求

### 前端扩展
- 在 `frontend/src/api/chatbot.ts` 中添加新的API调用
- 在 `frontend/src/types/index.ts` 中定义新的数据类型
- 在前端组件中集成新功能

## 性能优化

1. **模型优化**
   - 使用量化模型减少内存占用
   - 启用GPU加速（如果可用）
   - 调整批处理大小

2. **检索优化**
   - 调整相似度阈值
   - 优化文档分块策略
   - 使用更高效的嵌入模型

3. **缓存策略**
   - 缓存频繁查询的结果
   - 使用Redis等缓存系统
   - 实现对话历史缓存

## 许可证

本项目采用MIT许可证。