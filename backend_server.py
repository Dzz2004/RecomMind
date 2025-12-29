#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG工作流后端API服务器
基于Flask实现，集成SimpleRAGWorkflow
"""

import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from dataclasses import dataclass, asdict
import traceback
from queue import Queue
from threading import Thread

# 导入RAG工作流
from simple_rag_workflow import (
    SimpleRAGWorkflow, 
    CodeRAGWorkflow,
    WorkflowResponse, 
    RetrievedChunk
)

# ==================== 配置 ====================

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 应用配置
app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 全局RAG工作流实例
rag_workflow: Optional[SimpleRAGWorkflow] = None
code_rag_workflow: Optional[CodeRAGWorkflow] = None

# ==================== 数据模型 ====================

@dataclass
class ChatRequest:
    """聊天请求模型"""
    userInput: str
    useRag: bool
    useCodeRetrieval: bool = False

@dataclass
class RetrievedDocument:
    """检索到的文档模型"""
    source: str
    page: int
    content: str
    chapter: Optional[int] = None
    finalPage: Optional[int] = None
    pageRange: Optional[str] = None

@dataclass
class CodeReference:
    """代码引用模型"""
    path: str
    startLine: int
    endLine: int
    description: Optional[str] = None

@dataclass
class ChatResponse:
    """聊天响应模型"""
    thought: str
    answer: str
    documents: List[RetrievedDocument]
    codes: List[CodeReference] = None

@dataclass
class ApiResponse:
    """API响应模型"""
    code: int
    message: str
    data: Any
    timestamp: str

# ==================== 工具函数 ====================

def init_rag_workflow():
    """初始化RAG工作流"""
    global rag_workflow, code_rag_workflow
    
    try:
        logger.info("正在初始化RAG工作流...")
        
        # 配置参数
        # use_quantization: True=使用4位量化（节省显存，推荐），False=全精度（更高精度，需要更多显存）
        config = {
            "llm_path": "../models--Qwen--Qwen3-8B/snapshots/9c925d64d72725edaf899c6cb9c377fd0709d9c5",
            "embedding_model_path": "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
            "db_path": "./vector_db",
            "similarity_threshold": 0.0,  # 教材检索使用0.0阈值
            "use_quantization": True  # 是否使用4位量化，True=开启（默认），False=关闭
        }
        
        # 代码检索配置（使用 dzz 检索系统）
        code_config = {
            "llm_path": config["llm_path"],
            "embedding_model_path": config["embedding_model_path"],
            "db_path": config["db_path"],
            "similarity_threshold": 0.0,  # 代码检索使用0.0阈值，确保能检索到结果
            "chroma_md_path": "./dzz_retrieval/chroma_md",  # dzz 检索系统的 ChromaDB 路径
            "top_files": 3,  # 文件级检索数量
            "top_chunks": 5,  # 代码块级检索数量
            "use_quantization": config["use_quantization"]  # 使用相同的量化配置
        }
        
        rag_workflow = SimpleRAGWorkflow(**config)
        logger.info("✅ RAG工作流初始化成功")
        
        # 初始化源码检索工作流
        logger.info("正在初始化源码检索工作流...")
        code_rag_workflow = CodeRAGWorkflow(**code_config)
        logger.info("✅ 源码检索工作流初始化成功")
        
    except Exception as e:
        logger.error(f"❌ RAG工作流初始化失败: {e}")
        logger.error(traceback.format_exc())
        raise

def convert_retrieved_chunks_to_documents(chunks: List[RetrievedChunk]) -> List[RetrievedDocument]:
    """将RetrievedChunk转换为RetrievedDocument"""
    documents = []
    
    for chunk in chunks:
        # 从文件名中提取章节号
        chapter = None
        if chunk.filename:
            import re
            match = re.search(r'ch(\d+)\.pdf', chunk.filename)
            if match:
                chapter = int(match.group(1))
        
        # 计算最终页码：page_range的起点 + 10
        final_page = None
        page_range = chunk.metadata.get('page_range', '')
        if page_range:
            # 解析pageRange，例如 "79-84" 或 "79"
            import re
            page_range_match = re.match(r'(\d+)(?:-(\d+))?', page_range)
            if page_range_match:
                start_page = int(page_range_match.group(1))
                final_page = start_page + 10
        
        doc = RetrievedDocument(
            source=chunk.filename or "unknown.pdf",
            page=chunk.metadata.get('page', 1),
            content=chunk.content,
            chapter=chapter,
            finalPage=final_page,
            pageRange=chunk.metadata.get('page_range', '')
        )
        documents.append(doc)
    
    return documents

def convert_code_chunks_to_references(chunks: List[RetrievedChunk]) -> List[CodeReference]:
    """将代码RetrievedChunk转换为CodeReference"""
    code_refs = []
    
    for chunk in chunks:
        # 解析行号范围（优先使用 start_line 和 end_line）
        start_line = chunk.metadata.get('start_line', 1)
        end_line = chunk.metadata.get('end_line', 1)
        
        # 如果没有 start_line/end_line，尝试从 line_range 解析
        if start_line == 1 and end_line == 1:
            line_range = chunk.metadata.get('line_range', '')
            if line_range:
                import re
                # 解析 "10-25" 或 "10" 格式
                line_match = re.match(r'(\d+)(?:-(\d+))?', line_range)
                if line_match:
                    start_line = int(line_match.group(1))
                    end_line = int(line_match.group(2)) if line_match.group(2) else start_line
        
        # 获取文件路径（优先使用file_path，否则使用relative_path或filename）
        file_path = (
            chunk.metadata.get('file_path') or 
            chunk.relative_path or 
            chunk.filename or 
            'unknown'
        )
        
        # 生成描述（优先使用 metadata 中的 description，否则使用函数名或代码第一行）
        description = chunk.metadata.get('description', '')
        
        # 如果 description 为空，尝试使用函数名
        if not description:
            function_name = chunk.metadata.get('function_name', 'N/A')
            if function_name and function_name != 'N/A':
                description = f"函数: {function_name}"
        
        # 如果还是没有描述，使用代码的第一行
        if not description and chunk.content:
            first_line = chunk.content.split('\n')[0].strip()
            if first_line and len(first_line) < 100:
                description = first_line
        
        code_ref = CodeReference(
            path=file_path,
            startLine=start_line,
            endLine=end_line,
            description=description
        )
        code_refs.append(code_ref)
    
    return code_refs

def create_api_response(code: int, message: str, data: Any = None) -> Dict[str, Any]:
    """创建标准API响应"""
    return {
        "code": code,
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }

# ==================== API路由 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    try:
        rag_status = "healthy" if rag_workflow is not None else "unhealthy"
        code_status = "healthy" if code_rag_workflow is not None else "unhealthy"
        
        status = {
            "rag_workflow": rag_status,
            "code_rag_workflow": code_status,
            "overall": "healthy" if (rag_workflow is not None or code_rag_workflow is not None) else "unhealthy"
        }
        
        return jsonify(create_api_response(200, "服务正常", status))
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return jsonify(create_api_response(500, "服务异常", {"error": str(e)}))

@app.route('/api/chat', methods=['POST'])
def chat():
    """聊天接口"""
    try:
        # 检查RAG工作流是否已初始化
        if rag_workflow is None:
            return jsonify(create_api_response(500, "RAG工作流未初始化"))

        # 解析请求数据
        request_data = request.get_json()
        if not request_data:
            return jsonify(create_api_response(400, "请求数据为空"))

        # 验证请求字段
        user_input = request_data.get('userInput', '').strip()
        use_rag = request_data.get('useRag', True)
        use_code_retrieval = request_data.get('useCodeRetrieval', False)

        if not user_input:
            return jsonify(create_api_response(400, "用户输入不能为空"))

        logger.info(f"收到聊天请求: userInput='{user_input}', useRag={use_rag}, useCodeRetrieval={use_code_retrieval}")

        # 检查是否需要使用工作流
        if not use_rag and not use_code_retrieval:
            # 未启用RAG和代码检索时仍通过SSE返回静态响应，保持前端逻辑一致
            def non_rag_stream():
                chat_response = ChatResponse(
                    thought=f"用户询问: {user_input}。由于未启用RAG和代码检索，我将基于模型知识直接回答。",
                    answer=f"这是对'{user_input}'的回答。由于未启用RAG检索和代码检索，我无法提供基于文档或代码的详细信息。",
                    documents=[],
                    codes=[]
                )
                payload = json.dumps(asdict(chat_response), ensure_ascii=False)
                yield f"data: {payload}\n\n"
                yield "data: [DONE]\n\n"

            return Response(stream_with_context(non_rag_stream()), mimetype='text/event-stream')
        
        # 确定使用哪个工作流
        # 如果同时启用RAG和代码检索，先执行RAG，然后执行代码检索并追加结果
        use_code_workflow = use_code_retrieval
        use_textbook_workflow = use_rag
        
        if use_code_workflow and code_rag_workflow is None:
            return jsonify(create_api_response(500, "源码检索工作流未初始化"))
        if use_textbook_workflow and rag_workflow is None:
            return jsonify(create_api_response(500, "RAG工作流未初始化"))

        # 使用队列桥接工作流事件与SSE输出
        event_queue: "Queue[Dict[str, Any]]" = Queue()
        code_event_queue: "Queue[Dict[str, Any]]" = Queue() if use_code_workflow else None

        def enqueue_event(event: Dict[str, Any]) -> None:
            event_queue.put(event)

        def enqueue_code_event(event: Dict[str, Any]) -> None:
            if code_event_queue:
                code_event_queue.put(event)

        def run_textbook_workflow() -> None:
            """运行教材检索工作流"""
            try:
                response = rag_workflow.process_user_query(
                    user_input,
                    stream_callback=enqueue_event,
                )
                # 工作流完成后，记录完整结果到日志
                logger.info("="*60)
                logger.info("📊 教材检索处理结果摘要")
                logger.info("="*60)
                logger.info(f"用户查询: {response.user_query}")
                logger.info(f"检索建议数量: {len(response.retrieval_suggestion.suggested_queries) if response.retrieval_suggestion else 0}")
                logger.info(f"检索到的文档片段数: {len(response.retrieved_chunks)}")
                logger.info(f"回答长度: {len(response.llm_response)} 字符")
                
                if response.retrieved_chunks:
                    logger.info("检索到的文档片段详情:")
                    for i, chunk in enumerate(response.retrieved_chunks[:5], 1):
                        logger.info(f"  [{i}] {chunk.filename}")
                        logger.info(f"      章节: {chunk.metadata.get('section', 'N/A')}")
                        logger.info(f"      页码范围: {chunk.metadata.get('page_range', 'N/A')}")
                        logger.info(f"      相似度: {chunk.score:.4f}")
                        content_preview = chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content
                        logger.info(f"      内容预览: {content_preview}")
                
                logger.info(f"回答预览（前500字符）:")
                logger.info(f"{response.llm_response[:500]}...")
                logger.info("="*60)
            except Exception as workflow_error:
                logger.error(f"教材检索工作流执行失败: {workflow_error}")
                event_queue.put({"type": "error", "message": str(workflow_error)})
            finally:
                event_queue.put({"type": "textbook_done"})

        def run_code_workflow() -> None:
            """运行源码检索工作流（在RAG完成后执行）"""
            try:
                response = code_rag_workflow.process_code_query(
                    user_input,
                    stream_callback=enqueue_code_event,
                )
                # 工作流完成后，记录完整结果到日志
                logger.info("="*60)
                logger.info("📊 源码查询处理结果摘要")
                logger.info("="*60)
                logger.info(f"用户查询: {response.user_query}")
                logger.info(f"检索建议数量: {len(response.retrieval_suggestion.suggested_queries) if response.retrieval_suggestion else 0}")
                logger.info(f"检索到的代码片段数: {len(response.retrieved_chunks)}")
                logger.info(f"生成回复长度: {len(response.llm_response)} 字符")
                
                if response.retrieved_chunks:
                    logger.info("检索到的代码片段详情:")
                    for i, chunk in enumerate(response.retrieved_chunks[:5], 1):
                        logger.info(f"  [{i}] {chunk.filename}")
                        logger.info(f"      路径: {chunk.metadata.get('file_path', 'N/A')}")
                        logger.info(f"      行号: {chunk.metadata.get('line_range', 'N/A')}")
                        logger.info(f"      函数: {chunk.metadata.get('function_name', 'N/A')}")
                        logger.info(f"      相似度: {chunk.score:.4f}")
                
                logger.info(f"生成回复预览（前500字符）:")
                logger.info(f"{response.llm_response[:500]}...")
                logger.info("="*60)
            except Exception as workflow_error:
                logger.error(f"源码检索工作流执行失败: {workflow_error}")
                if code_event_queue:
                    code_event_queue.put({"type": "error", "message": str(workflow_error)})
            finally:
                if code_event_queue:
                    code_event_queue.put({"type": "code_done"})

        # 启动工作流线程
        # 如果同时启用，先启动RAG工作流
        if use_textbook_workflow:
            Thread(target=run_textbook_workflow, daemon=True).start()
        
        # 如果只启用代码检索（没有RAG），直接启动代码检索
        if use_code_workflow and not use_textbook_workflow:
            Thread(target=run_code_workflow, daemon=True).start()
        
        # 如果两个都未启用，直接返回
        if not use_textbook_workflow and not use_code_workflow:
            event_queue.put({"type": "done"})

        @stream_with_context
        def event_stream():
            try:
                textbook_done = False
                code_done = False
                code_chunks_received = False
                documents_received = []
                code_references_received = []
                thought_sent = False
                code_workflow_started = False
                answer_started = False  # 跟踪是否已开始生成回答
                code_answer_started = False  # 跟踪是否已开始生成代码回答
                last_heartbeat = time.time()
                heartbeat_interval = 15  # 每15秒发送一次心跳
                
                while True:
                    # 心跳机制：定期发送空数据保持连接
                    current_time = time.time()
                    if current_time - last_heartbeat > heartbeat_interval:
                        try:
                            # 发送心跳（空注释，SSE规范允许）
                            yield ": heartbeat\n\n"
                            last_heartbeat = current_time
                        except (BrokenPipeError, ConnectionError, OSError, GeneratorExit):
                            logger.info("客户端断开连接（心跳检测）")
                            return
                    # 处理教材检索事件（优先处理）
                    if use_textbook_workflow and not textbook_done:
                        try:
                            event = event_queue.get(timeout=0.1)
                            event_type = event.get("type")

                            if event_type == "retrieval":
                                chunks: List[RetrievedChunk] = event.get("retrieved_chunks", []) or []
                                round_num = event.get("round", 1)  # 获取检索轮次
                                documents = convert_retrieved_chunks_to_documents(chunks)
                                
                                # 累积多轮检索的结果（去重）
                                seen_content = {doc.content for doc in documents_received}
                                new_documents = [doc for doc in documents if doc.content not in seen_content]
                                
                                # 在extend之前记录第一轮的文档数量（用于第二轮显示）
                                round1_count = len(documents_received) if round_num == 2 else 0
                                
                                documents_received.extend(new_documents)
                                
                                # 构建thought文本
                                if round_num == 1:
                                    thought_text = f"用户询问: {user_input}。我通过第一轮RAG检索到了{len(chunks)}个文档片段，正在判断它们是否与问题相关..."
                                else:
                                    # 第二轮检索时，更新thought信息，包含第一轮的结果
                                    thought_text = f"用户询问: {user_input}。第一轮检索到{round1_count}个相关文档片段，但内容不足。我通过第二轮RAG检索到了{len(new_documents)}个新的文档片段，正在判断它们是否与问题相关..."
                                
                                payload = {
                                    "documents": [asdict(doc) for doc in documents_received],  # 发送累积的所有文档
                                    "thought": thought_text  # 始终发送thought字段，前端会更新显示
                                }
                                thought_sent = True  # 标记已发送thought
                                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                            elif event_type == "answer_chunk":
                                chunk_text = event.get("chunk", "")
                                if chunk_text:
                                    try:
                                        # 如果是第一个answer_chunk，更新thought信息
                                        if not answer_started:
                                            answer_started = True
                                            total_relevant = len(documents_received)
                                            thought_update = f"用户询问: {user_input}。已筛选出{total_relevant}个相关文档片段，正在基于这些内容生成回答..."
                                            payload = {"thought": thought_update, "answer_chunk": chunk_text}
                                        else:
                                            payload = {"answer_chunk": chunk_text}
                                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                                    except (BrokenPipeError, ConnectionError, OSError):
                                        # 客户端断开，停止发送
                                        logger.info("客户端断开连接，停止发送回答片段")
                                        return

                            elif event_type == "error":
                                error_payload = {"error": event.get("message", "发生未知错误")}
                                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

                            elif event_type == "textbook_done":
                                textbook_done = True
                                # RAG完成后，如果启用了代码检索，现在启动代码检索工作流
                                if use_code_workflow and not code_workflow_started:
                                    logger.info("RAG工作流完成，开始启动代码检索工作流...")
                                    Thread(target=run_code_workflow, daemon=True).start()
                                    code_workflow_started = True

                        except:
                            pass  # 队列为空，继续
                    
                    # 处理代码检索事件（在RAG完成后或单独执行）
                    if use_code_workflow and code_event_queue and not code_done:
                        try:
                            code_event = code_event_queue.get(timeout=0.1)
                            code_event_type = code_event.get("type")

                            if code_event_type == "code_retrieval":
                                code_chunks: List[RetrievedChunk] = code_event.get("retrieved_chunks", []) or []
                                round_num = code_event.get("round", 1)  # 获取检索轮次
                                code_refs = convert_code_chunks_to_references(code_chunks)
                                
                                # 累积多轮检索的结果（去重）
                                seen_paths = {(ref.path, ref.startLine, ref.endLine) for ref in code_references_received}
                                new_code_refs = [
                                    ref for ref in code_refs 
                                    if (ref.path, ref.startLine, ref.endLine) not in seen_paths
                                ]
                                code_references_received.extend(new_code_refs)
                                code_chunks_received = True
                                
                                # 构建thought文本
                                if round_num == 1:
                                    thought_text = f"用户询问: {user_input}。我通过第一轮源码检索找到了{len(code_chunks)}个代码片段，正在判断这些内容是否足以回答问题..."
                                else:
                                    # 第二轮检索时，更新thought信息
                                    round1_count = len(code_references_received) - len(new_code_refs)
                                    thought_text = f"用户询问: {user_input}。第一轮检索到{round1_count}个代码片段，但内容不足。我通过第二轮源码检索找到了{len(new_code_refs)}个新的代码片段，正在基于这些代码内容生成智能回复..."
                                
                                # 发送代码引用
                                payload = {
                                    "codes": [asdict(ref) for ref in code_references_received],  # 发送累积的所有代码引用
                                    "thought": thought_text  # 始终发送thought字段，前端会更新显示
                                }
                                
                                # 如果同时启用了RAG，追加分隔文本
                                if use_textbook_workflow:
                                    separator = "\n\n---\n\n### 相关源代码\n\n"
                                    payload_separator = {"answer_chunk": separator}
                                    yield f"data: {json.dumps(payload_separator, ensure_ascii=False)}\n\n"
                                
                                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                                thought_sent = True  # 标记已发送thought

                            elif code_event_type == "code_description_chunk":
                                chunk_text = code_event.get("chunk", "")
                                if chunk_text:
                                    try:
                                        # 如果是第一个code_description_chunk，更新thought信息
                                        if not code_answer_started:
                                            code_answer_started = True
                                            total_code_refs = len(code_references_received)
                                            thought_update = f"用户询问: {user_input}。已检索到{total_code_refs}个相关代码片段，正在基于这些代码内容生成智能回复..."
                                            payload = {"thought": thought_update, "answer_chunk": chunk_text}
                                        else:
                                            payload = {"answer_chunk": chunk_text}
                                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                                    except (BrokenPipeError, ConnectionError, OSError):
                                        # 客户端断开，停止发送
                                        logger.info("客户端断开连接，停止发送代码描述")
                                        return

                            elif code_event_type == "error":
                                error_payload = {"error": code_event.get("message", "发生未知错误")}
                                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

                            elif code_event_type == "code_done":
                                code_done = True

                        except:
                            pass  # 队列为空，继续
                    
                    # 检查是否都完成了
                    textbook_finished = not use_textbook_workflow or textbook_done
                    code_finished = not use_code_workflow or code_done
                    
                    if textbook_finished and code_finished:
                        # 发送最终的代码引用（如果之前没有发送）
                        if use_code_workflow and code_references_received and not code_chunks_received:
                            payload = {
                                "codes": [asdict(ref) for ref in code_references_received],
                            }
                            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        
                        yield "data: [DONE]\n\n"
                        break

            except GeneratorExit:
                # 客户端断开连接，正常退出
                logger.info("客户端关闭了SSE连接")
                return
            except BrokenPipeError:
                # 管道断开，正常退出
                logger.info("客户端断开连接（BrokenPipe）")
                return
            except Exception as stream_error:
                logger.error(f"SSE流处理失败: {stream_error}")
                try:
                    error_payload = {"error": str(stream_error)}
                    yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                except (GeneratorExit, BrokenPipeError):
                    # 如果客户端已断开，直接返回
                    return

        return Response(event_stream(), mimetype='text/event-stream')

    except Exception as e:
        logger.error(f"聊天处理失败: {e}")
        logger.error(traceback.format_exc())
        return jsonify(create_api_response(500, "聊天处理失败", {"error": str(e)}))

@app.route('/api/conversation/clear', methods=['POST'])
def clear_conversation():
    """清空对话历史（同时清空教材和源码检索的对话历史）"""
    try:
        cleared = []
        
        if rag_workflow is not None:
            rag_workflow.clear_conversation()
            cleared.append("教材检索")
        
        if code_rag_workflow is not None:
            code_rag_workflow.clear_conversation()
            cleared.append("源码检索")
        
        if not cleared:
            return jsonify(create_api_response(500, "没有可清空的对话历史"))
        
        logger.info(f"对话历史已清空: {', '.join(cleared)}")
        
        return jsonify(create_api_response(200, "对话历史清空成功", {"cleared": cleared}))
        
    except Exception as e:
        logger.error(f"清空对话历史失败: {e}")
        return jsonify(create_api_response(500, "清空对话历史失败", {"error": str(e)}))

@app.route('/api/conversation/summary', methods=['GET'])
def get_conversation_summary():
    """获取对话摘要"""
    try:
        if rag_workflow is None:
            return jsonify(create_api_response(500, "RAG工作流未初始化"))
        
        summary = rag_workflow.get_conversation_summary()
        
        return jsonify(create_api_response(200, "获取对话摘要成功", {"summary": summary}))
        
    except Exception as e:
        logger.error(f"获取对话摘要失败: {e}")
        return jsonify(create_api_response(500, "获取对话摘要失败", {"error": str(e)}))

@app.route('/api/config/similarity-threshold', methods=['POST'])
def update_similarity_threshold():
    """更新相似度阈值"""
    try:
        if rag_workflow is None:
            return jsonify(create_api_response(500, "RAG工作流未初始化"))
        
        request_data = request.get_json()
        if not request_data or 'threshold' not in request_data:
            return jsonify(create_api_response(400, "缺少threshold参数"))
        
        threshold = float(request_data['threshold'])
        if not (0.0 <= threshold <= 1.0):
            return jsonify(create_api_response(400, "阈值必须在0.0到1.0之间"))
        
        # 更新阈值
        rag_workflow.similarity_threshold = threshold
        rag_workflow.rag_engine.similarity_threshold = threshold
        
        logger.info(f"相似度阈值已更新为: {threshold}")
        
        return jsonify(create_api_response(200, "相似度阈值更新成功", {"threshold": threshold}))
        
    except Exception as e:
        logger.error(f"更新相似度阈值失败: {e}")
        return jsonify(create_api_response(500, "更新相似度阈值失败", {"error": str(e)}))

@app.route('/api/rag/info', methods=['GET'])
def get_rag_info():
    """获取RAG系统信息"""
    try:
        if rag_workflow is None:
            return jsonify(create_api_response(500, "RAG工作流未初始化"))
        
        # 获取集合信息
        collection_info = rag_workflow.rag_engine.get_collection_info()
        
        info = {
            "collection_info": collection_info,
            "similarity_threshold": rag_workflow.similarity_threshold,
            "conversation_count": len(rag_workflow.conversation_manager.conversations),
            "llm_path": rag_workflow.llm_path,
            "embedding_model_path": rag_workflow.rag_engine.embedding_model_path
        }
        
        return jsonify(create_api_response(200, "获取RAG信息成功", info))
        
    except Exception as e:
        logger.error(f"获取RAG信息失败: {e}")
        return jsonify(create_api_response(500, "获取RAG信息失败", {"error": str(e)}))

@app.route('/api/code/info', methods=['GET'])
def get_code_rag_info():
    """获取源码检索系统信息"""
    try:
        if code_rag_workflow is None:
            return jsonify(create_api_response(500, "源码检索工作流未初始化"))
        
        # 获取 dzz 集合信息
        dzz_collection_info = code_rag_workflow.dzz_collections_info if hasattr(code_rag_workflow, 'dzz_collections_info') else {'info': '未知'}
        
        # 获取源码RAG引擎信息
        code_rag_engine_info = code_rag_workflow.code_rag_engine.get_collection_info()
        
        info = {
            "code_rag_engine": code_rag_engine_info,
            "dzz_collection": dzz_collection_info,
            "similarity_threshold": code_rag_workflow.similarity_threshold,
            "conversation_count": len(code_rag_workflow.conversation_manager.conversations),
            "llm_path": code_rag_workflow.llm_path,
            "chroma_md_path": code_rag_workflow.chroma_md_path,
            "top_files": code_rag_workflow.top_files,
            "top_chunks": code_rag_workflow.top_chunks
        }
        
        return jsonify(create_api_response(200, "获取源码检索信息成功", info))
        
    except Exception as e:
        logger.error(f"获取源码检索信息失败: {e}")
        return jsonify(create_api_response(500, "获取源码检索信息失败", {"error": str(e)}))

@app.route('/api/code/query', methods=['POST'])
def code_query():
    """源码检索专用接口（仅源码检索，不包含教材检索）"""
    try:
        if code_rag_workflow is None:
            return jsonify(create_api_response(500, "源码检索工作流未初始化"))
        
        # 解析请求数据
        request_data = request.get_json()
        if not request_data:
            return jsonify(create_api_response(400, "请求数据为空"))
        
        # 验证请求字段
        user_input = request_data.get('userInput', '').strip()
        if not user_input:
            return jsonify(create_api_response(400, "用户输入不能为空"))
        
        logger.info(f"收到源码检索请求: userInput='{user_input}'")
        
        # 使用队列桥接工作流事件与SSE输出
        event_queue: "Queue[Dict[str, Any]]" = Queue()
        
        def enqueue_event(event: Dict[str, Any]) -> None:
            event_queue.put(event)
        
        def run_code_workflow() -> None:
            """运行源码检索工作流"""
            try:
                response = code_rag_workflow.process_code_query(
                    user_input,
                    stream_callback=enqueue_event,
                )
                # 工作流完成后，记录完整结果到日志
                logger.info("="*60)
                logger.info("📊 源码查询处理结果摘要")
                logger.info("="*60)
                logger.info(f"用户查询: {response.user_query}")
                logger.info(f"检索建议数量: {len(response.retrieval_suggestion.suggested_queries) if response.retrieval_suggestion else 0}")
                logger.info(f"检索到的代码片段数: {len(response.retrieved_chunks)}")
                logger.info(f"生成回复长度: {len(response.llm_response)} 字符")
                
                if response.retrieved_chunks:
                    logger.info("检索到的代码片段详情:")
                    for i, chunk in enumerate(response.retrieved_chunks[:5], 1):
                        logger.info(f"  [{i}] {chunk.filename}")
                        logger.info(f"      路径: {chunk.metadata.get('file_path', 'N/A')}")
                        logger.info(f"      行号: {chunk.metadata.get('line_range', 'N/A')}")
                        logger.info(f"      函数: {chunk.metadata.get('function_name', 'N/A')}")
                        logger.info(f"      相似度: {chunk.score:.4f}")
                
                logger.info(f"生成回复预览（前500字符）:")
                logger.info(f"{response.llm_response[:500]}...")
                logger.info("="*60)
            except Exception as workflow_error:
                logger.error(f"源码检索工作流执行失败: {workflow_error}")
                event_queue.put({"type": "error", "message": str(workflow_error)})
            finally:
                event_queue.put({"type": "done"})
        
        # 启动工作流线程
        Thread(target=run_code_workflow, daemon=True).start()
        
        @stream_with_context
        def event_stream():
            try:
                code_references_received = []
                thought_sent = False
                code_answer_started = False
                
                while True:
                    try:
                        event = event_queue.get(timeout=0.1)
                        event_type = event.get("type")
                        
                        if event_type == "code_retrieval":
                            code_chunks: List[RetrievedChunk] = event.get("retrieved_chunks", []) or []
                            round_num = event.get("round", 1)  # 获取检索轮次
                            code_refs = convert_code_chunks_to_references(code_chunks)
                            
                            # 累积多轮检索的结果（去重）
                            seen_paths = {(ref.path, ref.startLine, ref.endLine) for ref in code_references_received}
                            new_code_refs = [
                                ref for ref in code_refs 
                                if (ref.path, ref.startLine, ref.endLine) not in seen_paths
                            ]
                            code_references_received.extend(new_code_refs)
                            
                            # 构建thought文本
                            if round_num == 1:
                                thought_text = f"用户询问: {user_input}。我通过第一轮源码检索找到了{len(code_chunks)}个代码片段，正在判断这些内容是否足以回答问题..."
                            else:
                                # 第二轮检索时，更新thought信息
                                round1_count = len(code_references_received) - len(new_code_refs)
                                thought_text = f"用户询问: {user_input}。第一轮检索到{round1_count}个代码片段，但内容不足。我通过第二轮源码检索找到了{len(new_code_refs)}个新的代码片段，正在基于这些代码内容生成智能回复..."
                            
                            # 发送代码引用
                            payload = {
                                "codes": [asdict(ref) for ref in code_references_received],  # 发送累积的所有代码引用
                                "thought": thought_text  # 始终发送thought字段，前端会更新显示
                            }
                            thought_sent = True  # 标记已发送thought
                            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        
                        elif event_type == "code_description_chunk":
                            chunk_text = event.get("chunk", "")
                            if chunk_text:
                                try:
                                    # 如果是第一个code_description_chunk，更新thought信息
                                    if not code_answer_started:
                                        code_answer_started = True
                                        total_code_refs = len(code_references_received)
                                        thought_update = f"用户询问: {user_input}。已检索到{total_code_refs}个相关代码片段，正在基于这些代码内容生成智能回复..."
                                        payload = {"thought": thought_update, "answer_chunk": chunk_text}
                                    else:
                                        payload = {"answer_chunk": chunk_text}
                                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                                except (BrokenPipeError, ConnectionError, OSError):
                                    # 客户端断开，停止发送
                                    logger.info("客户端断开连接，停止发送代码描述")
                                    return
                        
                        elif event_type == "error":
                            error_payload = {"error": event.get("message", "发生未知错误")}
                            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
                        
                        elif event_type == "done":
                            # 发送最终的代码引用（如果之前没有发送）
                            if code_references_received and not thought_sent:
                                payload = {
                                    "thought": f"用户询问: {user_input}。我通过源码检索找到了{len(code_references_received)}个相关代码片段，已基于这些代码内容生成智能回复。",
                                    "codes": [asdict(ref) for ref in code_references_received],
                                }
                                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                            
                            yield "data: [DONE]\n\n"
                            break
                    
                    except:
                        pass  # 队列为空，继续
                        
            except GeneratorExit:
                # 客户端断开连接，正常退出
                logger.info("客户端关闭了SSE连接")
                return
            except BrokenPipeError:
                # 管道断开，正常退出
                logger.info("客户端断开连接（BrokenPipe）")
                return
            except Exception as stream_error:
                logger.error(f"SSE流处理失败: {stream_error}")
                try:
                    error_payload = {"error": str(stream_error)}
                    yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
                    yield "data: [DONE]\n\n"
                except (GeneratorExit, BrokenPipeError):
                    # 如果客户端已断开，直接返回
                    return
        
        return Response(event_stream(), mimetype='text/event-stream')
        
    except Exception as e:
        logger.error(f"源码检索处理失败: {e}")
        logger.error(traceback.format_exc())
        return jsonify(create_api_response(500, "源码检索处理失败", {"error": str(e)}))

@app.route('/api/code/conversation/clear', methods=['POST'])
def clear_code_conversation():
    """清空源码检索对话历史"""
    try:
        if code_rag_workflow is None:
            return jsonify(create_api_response(500, "源码检索工作流未初始化"))
        
        code_rag_workflow.clear_conversation()
        logger.info("源码检索对话历史已清空")
        
        return jsonify(create_api_response(200, "源码检索对话历史清空成功"))
        
    except Exception as e:
        logger.error(f"清空源码检索对话历史失败: {e}")
        return jsonify(create_api_response(500, "清空源码检索对话历史失败", {"error": str(e)}))

@app.route('/api/question/judge', methods=['POST'])
def judge_answer():
    """大模型智能判题接口（选择题/填空题/问答题通用）"""
    try:
        if rag_workflow is None:
            return jsonify(create_api_response(500, "RAG工作流未初始化"))
        
        # 解析请求数据
        request_data = request.get_json()
        if not request_data:
            return jsonify(create_api_response(400, "请求数据为空"))
        
        # 验证请求字段
        question_content = request_data.get('questionContent', '').strip()
        student_answer = request_data.get('studentAnswer', '').strip()
        question_options = request_data.get('questionOptions', [])
        question_type = request_data.get('questionType', '选择题').strip()
        correct_answer = request_data.get('correctAnswer', '').strip()
        knowledge_point = request_data.get('knowledgePoint', '').strip()
        
        if not question_content or not student_answer:
            return jsonify(create_api_response(400, "题目内容和学生答案不能为空"))
        
        logger.info(f"收到智能判题请求: question='{question_content[:50]}...', answer='{student_answer[:30]}...', type='{question_type}'")
        
        # 根据题目类型选择判题方法
        if question_type in ['填空题', '问答题']:
            # 使用文本判题
            judge_result = rag_workflow.judge_text_answer(
                question_content=question_content,
                student_answer=student_answer,
                question_type=question_type,
                knowledge_point=knowledge_point
            )
        else:
            # 使用选择题判题
            judge_result = rag_workflow.judge_answer(
                question_content=question_content,
                question_options=question_options,
                selected_answer=student_answer,
                correct_answer=correct_answer,
                knowledge_point=knowledge_point
            )
        
        logger.info(f"智能判题完成: isCorrect={judge_result['isCorrect']}")
        
        return jsonify(create_api_response(200, "智能判题成功", judge_result))
        
    except Exception as e:
        logger.error(f"智能判题失败: {e}")
        logger.error(traceback.format_exc())
        return jsonify(create_api_response(500, "智能判题失败", {"error": str(e)}))

@app.route('/api/question/explanation', methods=['POST'])
def generate_explanation():
    """大模型生成题目解析接口"""
    try:
        if rag_workflow is None:
            return jsonify(create_api_response(500, "RAG工作流未初始化"))
        
        # 解析请求数据
        request_data = request.get_json()
        if not request_data:
            return jsonify(create_api_response(400, "请求数据为空"))
        
        # 验证请求字段
        question_content = request_data.get('questionContent', '').strip()
        question_options = request_data.get('questionOptions', [])
        selected_answer = request_data.get('selectedAnswer', '').strip()
        correct_answer = request_data.get('correctAnswer', '').strip()
        knowledge_point = request_data.get('knowledgePoint', '').strip()
        is_correct = request_data.get('isCorrect', False)
        
        if not question_content:
            return jsonify(create_api_response(400, "题目内容不能为空"))
        
        logger.info(f"收到解析生成请求: question='{question_content[:50]}...', isCorrect={is_correct}")
        
        # 使用大模型生成解析
        explanation = rag_workflow.generate_explanation(
            question_content=question_content,
            question_options=question_options,
            selected_answer=selected_answer,
            correct_answer=correct_answer,
            knowledge_point=knowledge_point,
            is_correct=is_correct
        )
        
        logger.info(f"解析生成完成: length={len(explanation)}")
        
        return jsonify(create_api_response(200, "解析生成成功", {"explanation": explanation}))
        
    except Exception as e:
        logger.error(f"解析生成失败: {e}")
        logger.error(traceback.format_exc())
        return jsonify(create_api_response(500, "解析生成失败", {"error": str(e)}))

# ==================== 错误处理 ====================

@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return jsonify(create_api_response(404, "接口不存在"))

@app.errorhandler(405)
def method_not_allowed(error):
    """405错误处理"""
    return jsonify(create_api_response(405, "请求方法不允许"))

@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    logger.error(f"内部服务器错误: {error}")
    return jsonify(create_api_response(500, "内部服务器错误"))

# ==================== 主函数 ====================

def main():
    """主函数"""
    try:
        # 初始化RAG工作流
        init_rag_workflow()
        
        # 启动Flask应用
        logger.info("🚀 启动RAG工作流后端API服务器...")
        logger.info("📡 API接口:")
        logger.info("  POST /api/chat - 聊天接口（支持教材和源码检索）")
        logger.info("  POST /api/code/query - 源码检索专用接口")
        logger.info("  POST /api/conversation/clear - 清空对话历史（教材+源码）")
        logger.info("  POST /api/code/conversation/clear - 清空源码检索对话历史")
        logger.info("  GET  /api/conversation/summary - 获取对话摘要")
        logger.info("  POST /api/config/similarity-threshold - 更新相似度阈值")
        logger.info("  GET  /api/rag/info - 获取教材RAG系统信息")
        logger.info("  GET  /api/code/info - 获取源码检索系统信息")
        logger.info("  GET  /api/health - 健康检查")
        
        # 启动服务器
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,  # 生产环境建议设为False
            threaded=True
        )
        
    except Exception as e:
        logger.error(f"❌ 服务器启动失败: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()
