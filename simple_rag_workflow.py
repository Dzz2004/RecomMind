#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
不依赖langchain的RAG工作流系统
基于Transformers实现完整的RAG功能
"""

import os
import json
import torch
import chromadb
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig, pipeline, TextIteratorStreamer
from threading import Thread
import numpy as np
from sentence_transformers import SentenceTransformer
import sys

# 添加 dzz_retrieval 路径以便导入
dzz_path = os.path.join(os.path.dirname(__file__), 'dzz_retrieval')
if os.path.exists(dzz_path):
    sys.path.insert(0, dzz_path)
    try:
        from rank_chunks_by_semantic import rank_chunks_by_description  # type: ignore
        print("✅ 成功导入 rank_chunks_by_semantic")
    except ImportError:
        rank_chunks_by_description = None
        print("⚠️ 警告: 无法导入 rank_chunks_by_semantic，将使用备用检索方法")
else:
    rank_chunks_by_description = None
    print("⚠️ 警告: dzz_retrieval 目录不存在，将使用备用检索方法")

# ==================== 数据模型 ====================

@dataclass
class ConversationMessage:
    """对话消息模型"""
    role: str  # "user" 或 "assistant"
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class RetrievedChunk:
    """检索到的文档片段"""
    content: str
    source: str
    filename: str
    relative_path: str
    extension: str
    score: float
    metadata: Dict[str, Any]

@dataclass
class RetrievalSuggestion:
    """检索建议模型"""
    original_query: str
    intent: str
    confidence: float
    search_keywords: List[str]
    suggested_queries: List[str]
    reasoning: str

@dataclass
class WorkflowResponse:
    """工作流响应模型"""
    user_query: str
    retrieval_suggestion: Optional[RetrievalSuggestion]
    retrieved_chunks: List[RetrievedChunk]
    llm_response: str
    conversation_history: List[ConversationMessage]
    timestamp: datetime

# ==================== 检索建议生成器 ====================

class RetrievalSuggester:
    """检索建议生成器"""
    
    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer
    
    def generate_suggestion(self, user_query: str, conversation_history: List[ConversationMessage]) -> RetrievalSuggestion:
        """生成检索建议"""
        
        # 分析对话上下文
        context_analysis = self._analyze_conversation_context(conversation_history)
        
        # 构建系统提示词
        system_prompt = self._create_suggestion_prompt(user_query, conversation_history, context_analysis)
        
        # 生成建议
        response = self._generate_response_with_history(system_prompt, user_query, conversation_history)
        print(f"检索建议中间过程: {response}")
        
        # 解析响应
        suggestion = self._parse_response(user_query, response)
        
        # 后处理：基于历史记录优化建议
        suggestion = self._post_process_suggestion(suggestion, conversation_history)
        
        return suggestion
    
    def _create_suggestion_prompt(self, user_query: str, conversation_history: List[ConversationMessage], context_analysis: dict) -> str:
        """创建检索建议提示词"""
        
        prompt = f"""
你是一名“操作系统课程内容智能检索助手”，你的任务是：分析用户的真实查询意图，并为**RAG向量检索系统**生成可用的、语义丰富的检索建议。

请根据以下信息生成输出：
对话上下文分析: {context_analysis.get('summary', '无特殊上下文')}
历史关键词: {', '.join(context_analysis.get('keywords', []))}

---

输出必须是严格的 JSON 格式，示例如下：
{{
    "intent": "用户意图描述",
    "confidence": 0.8,
    "search_keywords": ["关键词1", "关键词2", "关键词3"],
    "suggested_queries": ["建议查询1", "建议查询2", "建议查询3"],
    "reasoning": "生成建议的推理过程"
}}

---

### 生成要求：
1. **intent**：简洁描述用户意图（如“信息查询”、“概念解释”、“比较分析”、“原理探讨”、“考试准备”等）
2. **confidence**：模型对意图识别的置信度，范围 0~1
3. **search_keywords**：提取 3–5 个核心概念或术语，结合历史记录和当前问题（关键词尽量通用、课程相关）
4. **suggested_queries**：
   - 生成 3–5 条优化后的检索查询，用于向量召回；
   - 每条建议应是对原问题的**语义改写、泛化或延展**，而非简单复述；
   - 优先包含核心关键词，确保对教学内容的相关性；
   - 避免无意义短语或用户输入的噪声（如“think”、“上一个问题”等）。
5. **reasoning**：简述推理过程，包括如何利用上下文、关键词来生成更具召回效果的检索建议。

---

### 注意事项：
- **注意检索素材**：你的检索范围面向的是向量化后的操作系统课程教材内容，而非互联网，生成的检索建议需要和检索范围相适应。
- **不要直接复述用户原始 query**，而要生成“语义等价或更具检索价值”的查询句。
- **检索建议应有策略性**：可包括同义改写、细化问题、或扩展到相关概念。
- **仅输出 JSON，不要包含任何额外文本或解释**。
"""

        return prompt
    
    def _generate_response_with_history(self, system_prompt: str, user_query: str, conversation_history: List[ConversationMessage]) -> str:
        """使用对话历史生成LLM响应"""
        try:
            # 构建消息列表
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # 添加历史对话（最近5轮）
            for msg in conversation_history[-5:]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # 添加当前用户查询
            messages.append({
                "role": "user", 
                "content": user_query
            })
            
            # 使用tokenizer的chat template
            text = self.tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            
            # 编码输入
            inputs = self.tokenizer(text, return_tensors="pt")
            if torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            # 生成响应
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=100000,
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            
            # 解码输出
            response = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
            
            # 清理输出
            response = response.strip()
            
            return response
            
        except Exception as e:
            print(f"生成检索建议时出错: {e}")
            # 返回一个空的JSON，让_parse_response方法使用原始查询
            return '{"intent": "信息查询", "confidence": 0.5, "search_keywords": [], "suggested_queries": [], "reasoning": "生成失败"}'
    
    def _analyze_conversation_context(self, conversation_history: List[ConversationMessage]) -> dict:
        """分析对话上下文"""
        if not conversation_history:
            return {"summary": "新对话开始", "keywords": [], "intent_pattern": "未知"}
        
        # 提取所有文本
        all_text = ""
        user_queries = []
        assistant_responses = []
        
        for msg in conversation_history[-5:]:  # 最近5轮对话
            all_text += msg.content + " "
            if msg.role == "user":
                user_queries.append(msg.content)
            else:
                assistant_responses.append(msg.content)
        
        # 关键词提取
        keywords = self._extract_keywords(all_text)
        
        # 意图模式分析
        intent_pattern = self._analyze_intent_pattern(user_queries)
        
        # 生成摘要
        summary = self._generate_context_summary(user_queries, assistant_responses, keywords)
        
        return {
            "summary": summary,
            "keywords": keywords,
            "intent_pattern": intent_pattern,
            "user_queries": user_queries,
            "assistant_responses": assistant_responses
        }
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简单的关键词提取
        import re
        
        # 移除标点符号
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # 分词
        words = text.split()
        
        # 过滤停用词和短词
        stop_words = {"的", "是", "在", "有", "和", "与", "或", "但", "因为", "所以", "如果", "那么", 
                     "什么", "怎么", "为什么", "如何", "这个", "那个", "一个", "一些", "很多", 
                     "非常", "很", "太", "更", "最", "还", "也", "都", "就", "会", "要", "能", "可以"}
        
        keywords = []
        for word in words:
            if len(word) > 1 and word not in stop_words:
                keywords.append(word)
        
        # 去重并限制数量
        unique_keywords = list(set(keywords))[:8]
        return unique_keywords
    
    def _analyze_intent_pattern(self, user_queries: List[str]) -> str:
        """分析用户意图模式"""
        if not user_queries:
            return "未知"
        
        # 分析问题类型
        question_patterns = {
            "概念解释": ["什么是", "定义", "概念", "含义", "意思"],
            "方法步骤": ["如何", "怎么", "步骤", "方法", "流程"],
            "原因分析": ["为什么", "原因", "为什么", "导致"],
            "比较分析": ["区别", "比较", "对比", "差异"],
            "深入探讨": ["详细", "深入", "具体", "更多", "进一步"]
        }
        
        last_query = user_queries[-1].lower()
        
        for intent, patterns in question_patterns.items():
            for pattern in patterns:
                if pattern in last_query:
                    return intent
        
        return "信息查询"
    
    def _generate_context_summary(self, user_queries: List[str], assistant_responses: List[str], keywords: List[str]) -> str:
        """生成上下文摘要"""
        if not user_queries:
            return "新对话开始"
        
        # 分析对话长度
        total_length = len(user_queries) + len(assistant_responses)
        
        if total_length <= 2:
            return f"对话刚开始，用户询问: {user_queries[-1][:50]}..."
        elif total_length <= 6:
            return f"简短对话，主要讨论: {', '.join(keywords[:3])}"
        else:
            return f"深入对话，已进行{total_length}轮，主要话题: {', '.join(keywords[:3])}"
    
    def _post_process_suggestion(self, suggestion: RetrievalSuggestion, conversation_history: List[ConversationMessage]) -> RetrievalSuggestion:
        """后处理检索建议"""
        if not conversation_history:
            return suggestion
        
        # 确保suggestion.suggested_queries不为空
        if not suggestion.suggested_queries:
            print("⚠️ 警告: suggested_queries为空，使用原始查询作为默认值")
            suggestion.suggested_queries = [suggestion.original_query]
        
        # 基于历史记录优化关键词
        history_keywords = self._extract_keywords(" ".join([msg.content for msg in conversation_history[-3:]]))
        
        # 合并关键词
        combined_keywords = list(set(suggestion.search_keywords + history_keywords[:3]))
        suggestion.search_keywords = combined_keywords[:5]  # 限制为5个
        
        # 优化建议查询
        if len(conversation_history) > 1 and suggestion.suggested_queries:
            # 如果有历史记录，添加上下文相关的查询
            context_queries = []
            for keyword in history_keywords[:2]:
                # 安全访问列表，避免index out of range
                if suggestion.suggested_queries and keyword not in suggestion.suggested_queries[0]:
                    context_queries.append(f"{keyword} {suggestion.original_query}")
            
            suggestion.suggested_queries = suggestion.suggested_queries + context_queries[:2]
            suggestion.suggested_queries = suggestion.suggested_queries[:5]  # 限制为5个
        
        return suggestion
    
    def _generate_response(self, prompt: str) -> str:
        """生成LLM响应（已废弃，请使用_generate_response_with_history）"""
        # 这个方法已经不再使用，保留是为了兼容性
        # 实际使用的是 _generate_response_with_history 方法
        return '{"intent": "信息查询", "confidence": 0.5, "search_keywords": ["查询"], "suggested_queries": ["查询"], "reasoning": "使用默认查询"}'
    
    def _parse_response(self, original_query: str, response: str) -> RetrievalSuggestion:
        """解析LLM响应"""
        try:
            # 清理响应文本
            cleaned_response = self._clean_response_text(response)
            
            # 尝试提取JSON
            import re
            json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_response, re.DOTALL)
            
            # 找到最完整的JSON
            best_json = None
            for json_str in json_matches:
                try:
                    data = json.loads(json_str)
                    # 检查是否包含必要字段
                    if all(key in data for key in ["intent", "confidence", "search_keywords", "suggested_queries"]):
                        best_json = data
                        break
                except:
                    continue
            
            if best_json:
                # 如果suggested_queries为空列表，使用原始查询
                suggested_queries = best_json.get("suggested_queries", [original_query])
                if not suggested_queries:
                    suggested_queries = [original_query]
                    best_json["reasoning"] = "JSON解析成功但建议为空，使用原始查询"
                
                # 如果search_keywords为空列表，使用原始查询
                search_keywords = best_json.get("search_keywords", [original_query])
                if not search_keywords:
                    search_keywords = [original_query]
                
                return RetrievalSuggestion(
                    original_query=original_query,
                    intent=best_json.get("intent", "信息查询"),
                    confidence=float(best_json.get("confidence", 0.5)),
                    search_keywords=search_keywords,
                    suggested_queries=suggested_queries,
                    reasoning=best_json.get("reasoning", "解析成功")
                )
            else:
                # 如果解析失败，使用原始查询
                return RetrievalSuggestion(
                    original_query=original_query,
                    intent="信息查询",
                    confidence=0.5,
                    search_keywords=[original_query],
                    suggested_queries=[original_query],
                    reasoning="JSON解析失败，使用原始查询"
                )
                
        except Exception as e:
            print(f"解析检索建议时出错: {e}")
            return RetrievalSuggestion(
                original_query=original_query,
                intent="信息查询",
                confidence=0.5,
                search_keywords=[original_query],
                suggested_queries=[original_query],
                reasoning=f"解析错误: {str(e)}"
            )
    
    def _clean_response_text(self, response: str) -> str:
        """清理响应文本"""
        import re
        
        # 移除markdown代码块标记
        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'```\s*', '', response)
        
        # 移除多余的空行和换行
        response = re.sub(r'\n\s*\n', '\n', response)
        
        # 移除Human:和AI:标记
        response = re.sub(r'Human:\s*', '', response)
        response = re.sub(r'AI:\s*', '', response)
        
        return response.strip()

# ==================== 源码检索建议生成器 ====================

class CodeRetrievalSuggester:
    """源码检索建议生成器"""
    
    def __init__(self, model, tokenizer):
        self.model = model
        self.tokenizer = tokenizer
    
    def generate_suggestion(self, user_query: str, conversation_history: List[ConversationMessage]) -> RetrievalSuggestion:
        """生成源码检索建议"""
        
        # 分析对话上下文
        context_analysis = self._analyze_conversation_context(conversation_history)
        
        # 构建系统提示词
        system_prompt = self._create_suggestion_prompt(user_query, conversation_history, context_analysis)
        
        # 生成建议
        response = self._generate_response_with_history(system_prompt, user_query, conversation_history)
        print(f"源码检索建议中间过程: {response}")
        
        # 解析响应
        suggestion = self._parse_response(user_query, response)
        
        # 后处理：基于历史记录优化建议
        suggestion = self._post_process_suggestion(suggestion, conversation_history)
        
        return suggestion
    
    def _create_suggestion_prompt(self, user_query: str, conversation_history: List[ConversationMessage], context_analysis: dict) -> str:
        """创建源码检索建议提示词"""
        
        prompt = f"""
你是一名"源代码智能检索助手"，你的任务是：分析用户的真实查询意图，并为**源码RAG向量检索系统**生成可用的、语义丰富的检索建议。

请根据以下信息生成输出：
对话上下文分析: {context_analysis.get('summary', '无特殊上下文')}
历史关键词: {', '.join(context_analysis.get('keywords', []))}

---

输出必须是严格的 JSON 格式，示例如下：
{{
    "intent": "用户意图描述",
    "confidence": 0.8,
    "search_keywords": ["关键词1", "关键词2", "关键词3"],
    "suggested_queries": ["建议查询1", "建议查询2", "建议查询3"],
    "reasoning": "生成建议的推理过程"
}}

---

### 生成要求：
1. **intent**：简洁描述用户意图（如"函数查找"、"类定义查找"、"API使用示例"、"实现原理"、"代码逻辑分析"等）
2. **confidence**：模型对意图识别的置信度，范围 0~1
3. **search_keywords**：提取 3–5 个核心概念或术语，结合历史记录和当前问题（关键词应包含函数名、类名、API名称、技术术语等）
4. **suggested_queries**：
   - 生成 3–5 条优化后的检索查询，用于向量召回源码；
   - 每条建议应是对原问题的**语义改写、泛化或延展**，而非简单复述；
   - 优先包含核心关键词（函数名、类名、API、技术术语等），确保对源代码的相关性；
   - 避免无意义短语或用户输入的噪声（如"think"、"上一个问题"等）；
   - 考虑代码检索的特殊性，可以包含函数调用、数据结构、算法名称等技术术语。
5. **reasoning**：简述推理过程，包括如何利用上下文、关键词来生成更具召回效果的检索建议。

---

### 注意事项：
- **注意检索素材**：你的检索范围面向的是向量化后的源代码内容，而非教材或文档，生成的检索建议需要和源码检索范围相适应。
- **不要直接复述用户原始 query**，而要生成"语义等价或更具检索价值"的查询句。
- **检索建议应有策略性**：可包括同义改写、细化问题、或扩展到相关概念。
- **源码检索特点**：考虑代码检索的特殊性，可以包含：
  - 函数名、类名、变量名等标识符
  - API调用模式
  - 数据结构名称
  - 算法或设计模式名称
  - 技术栈相关术语
- **仅输出 JSON，不要包含任何额外文本或解释**。
"""
        
        return prompt
    
    def _generate_response_with_history(self, system_prompt: str, user_query: str, conversation_history: List[ConversationMessage]) -> str:
        """使用对话历史生成LLM响应"""
        try:
            # 构建消息列表
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # 添加历史对话（最近5轮）
            for msg in conversation_history[-5:]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # 添加当前用户查询
            messages.append({
                "role": "user", 
                "content": user_query
            })
            
            # 使用tokenizer的chat template
            text = self.tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            
            # 编码输入
            inputs = self.tokenizer(text, return_tensors="pt")
            if torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            # 生成响应
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=100000,
                    temperature=0.7,
                    top_p=0.9,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            
            # 解码输出
            response = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
            
            # 清理输出
            response = response.strip()
            
            return response
            
        except Exception as e:
            print(f"生成源码检索建议时出错: {e}")
            # 返回一个空的JSON，让_parse_response方法使用原始查询
            return '{"intent": "函数查找", "confidence": 0.5, "search_keywords": [], "suggested_queries": [], "reasoning": "生成失败"}'
    
    def _analyze_conversation_context(self, conversation_history: List[ConversationMessage]) -> dict:
        """分析对话上下文"""
        if not conversation_history:
            return {"summary": "新对话开始", "keywords": [], "intent_pattern": "未知"}
        
        # 提取所有文本
        all_text = ""
        user_queries = []
        assistant_responses = []
        
        for msg in conversation_history[-5:]:  # 最近5轮对话
            all_text += msg.content + " "
            if msg.role == "user":
                user_queries.append(msg.content)
            else:
                assistant_responses.append(msg.content)
        
        # 关键词提取（针对代码）
        keywords = self._extract_keywords(all_text)
        
        # 意图模式分析
        intent_pattern = self._analyze_intent_pattern(user_queries)
        
        # 生成摘要
        summary = self._generate_context_summary(user_queries, assistant_responses, keywords)
        
        return {
            "summary": summary,
            "keywords": keywords,
            "intent_pattern": intent_pattern,
            "user_queries": user_queries,
            "assistant_responses": assistant_responses
        }
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（针对代码检索）"""
        import re
        
        # 移除标点符号
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # 分词
        words = text.split()
        
        # 过滤停用词和短词
        stop_words = {"的", "是", "在", "有", "和", "与", "或", "但", "因为", "所以", "如果", "那么", 
                     "什么", "怎么", "为什么", "如何", "这个", "那个", "一个", "一些", "很多", 
                     "非常", "很", "太", "更", "最", "还", "也", "都", "就", "会", "要", "能", "可以",
                     "查找", "找到", "搜索", "检索", "源码", "代码"}
        
        keywords = []
        for word in words:
            if len(word) > 1 and word not in stop_words:
                # 优先保留可能的技术术语（如驼峰命名、下划线命名等）
                if re.match(r'^[A-Z][a-zA-Z0-9]*$', word) or re.match(r'^[a-z_][a-z0-9_]*$', word):
                    keywords.append(word)
                elif word not in stop_words:
                    keywords.append(word)
        
        # 去重并限制数量
        unique_keywords = list(set(keywords))[:8]
        return unique_keywords
    
    def _analyze_intent_pattern(self, user_queries: List[str]) -> str:
        """分析用户意图模式"""
        if not user_queries:
            return "未知"
        
        # 分析问题类型（针对代码）
        question_patterns = {
            "函数查找": ["函数", "function", "如何调用", "如何使用", "怎么用"],
            "类定义": ["类", "class", "定义", "结构"],
            "实现原理": ["原理", "实现", "如何实现", "怎样", "怎么"],
            "代码逻辑": ["逻辑", "流程", "过程", "步骤"],
            "API查找": ["API", "接口", "方法", "method"],
            "错误排查": ["错误", "bug", "问题", "异常", "为什么"]
        }
        
        last_query = user_queries[-1].lower()
        
        for intent, patterns in question_patterns.items():
            for pattern in patterns:
                if pattern in last_query:
                    return intent
        
        return "函数查找"
    
    def _generate_context_summary(self, user_queries: List[str], assistant_responses: List[str], keywords: List[str]) -> str:
        """生成上下文摘要"""
        if not user_queries:
            return "新对话开始"
        
        # 分析对话长度
        total_length = len(user_queries) + len(assistant_responses)
        
        if total_length <= 2:
            return f"对话刚开始，用户询问: {user_queries[-1][:50]}..."
        elif total_length <= 6:
            return f"简短对话，主要讨论: {', '.join(keywords[:3])}"
        else:
            return f"深入对话，已进行{total_length}轮，主要话题: {', '.join(keywords[:3])}"
    
    def _post_process_suggestion(self, suggestion: RetrievalSuggestion, conversation_history: List[ConversationMessage]) -> RetrievalSuggestion:
        """后处理检索建议"""
        if not conversation_history:
            return suggestion
        
        # 确保suggestion.suggested_queries不为空
        if not suggestion.suggested_queries:
            print("⚠️ 警告: suggested_queries为空，使用原始查询作为默认值")
            suggestion.suggested_queries = [suggestion.original_query]
        
        # 基于历史记录优化关键词
        history_keywords = self._extract_keywords(" ".join([msg.content for msg in conversation_history[-3:]]))
        
        # 合并关键词
        combined_keywords = list(set(suggestion.search_keywords + history_keywords[:3]))
        suggestion.search_keywords = combined_keywords[:5]  # 限制为5个
        
        # 优化建议查询
        if len(conversation_history) > 1 and suggestion.suggested_queries:
            # 如果有历史记录，添加上下文相关的查询
            context_queries = []
            for keyword in history_keywords[:2]:
                # 安全访问列表，避免index out of range
                if suggestion.suggested_queries and keyword not in suggestion.suggested_queries[0]:
                    context_queries.append(f"{keyword} {suggestion.original_query}")
            
            suggestion.suggested_queries = suggestion.suggested_queries + context_queries[:2]
            suggestion.suggested_queries = suggestion.suggested_queries[:5]  # 限制为5个
        
        return suggestion
    
    def _parse_response(self, original_query: str, response: str) -> RetrievalSuggestion:
        """解析LLM响应"""
        try:
            # 清理响应文本
            cleaned_response = self._clean_response_text(response)
            
            # 尝试提取JSON
            import re
            json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_response, re.DOTALL)
            
            # 找到最完整的JSON
            best_json = None
            for json_str in json_matches:
                try:
                    data = json.loads(json_str)
                    # 检查是否包含必要字段
                    if all(key in data for key in ["intent", "confidence", "search_keywords", "suggested_queries"]):
                        best_json = data
                        break
                except:
                    continue
            
            if best_json:
                # 如果suggested_queries为空列表，使用原始查询
                suggested_queries = best_json.get("suggested_queries", [original_query])
                if not suggested_queries:
                    suggested_queries = [original_query]
                    best_json["reasoning"] = "JSON解析成功但建议为空，使用原始查询"
                
                # 如果search_keywords为空列表，使用原始查询
                search_keywords = best_json.get("search_keywords", [original_query])
                if not search_keywords:
                    search_keywords = [original_query]
                
                return RetrievalSuggestion(
                    original_query=original_query,
                    intent=best_json.get("intent", "函数查找"),
                    confidence=float(best_json.get("confidence", 0.5)),
                    search_keywords=search_keywords,
                    suggested_queries=suggested_queries,
                    reasoning=best_json.get("reasoning", "解析成功")
                )
            else:
                # 如果解析失败，使用原始查询
                return RetrievalSuggestion(
                    original_query=original_query,
                    intent="函数查找",
                    confidence=0.5,
                    search_keywords=[original_query],
                    suggested_queries=[original_query],
                    reasoning="JSON解析失败，使用原始查询"
                )
                
        except Exception as e:
            print(f"解析源码检索建议时出错: {e}")
            return RetrievalSuggestion(
                original_query=original_query,
                intent="函数查找",
                confidence=0.5,
                search_keywords=[original_query],
                suggested_queries=[original_query],
                reasoning=f"解析错误: {str(e)}"
            )
    
    def _clean_response_text(self, response: str) -> str:
        """清理响应文本"""
        import re
        
        # 移除markdown代码块标记
        response = re.sub(r'```json\s*', '', response)
        response = re.sub(r'```\s*', '', response)
        
        # 移除多余的空行和换行
        response = re.sub(r'\n\s*\n', '\n', response)
        
        # 移除Human:和AI:标记
        response = re.sub(r'Human:\s*', '', response)
        response = re.sub(r'AI:\s*', '', response)
        
        return response.strip()

# ==================== 对话管理器 ====================

class ConversationManager:
    """对话历史管理器"""
    
    def __init__(self, max_history_length: int = 10):
        self.conversations: List[ConversationMessage] = []
        self.max_history_length = max_history_length
    
    def add_message(self, role: str, content: str, metadata: Optional[dict] = None) -> None:
        message = ConversationMessage(
            role=role,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        self.conversations.append(message)
        
        # 保持历史记录长度限制
        if len(self.conversations) > self.max_history_length:
            self.conversations = self.conversations[-self.max_history_length:]
    
    def get_history(self, last_n: Optional[int] = None) -> List[ConversationMessage]:
        if last_n is None:
            return self.conversations.copy()
        else:
            return self.conversations[-last_n:] if last_n > 0 else []
    
    def get_context_string(self, last_n: Optional[int] = None) -> str:
        history = self.get_history(last_n)
        if not history:
            return ""
        
        context_parts = []
        for msg in history:
            role_name = "用户" if msg.role == "user" else "助手"
            context_parts.append(f"{role_name}: {msg.content}")
        
        return "\n".join(context_parts)
    
    def clear(self) -> None:
        self.conversations.clear()
    
    def get_last_user_message(self) -> Optional[ConversationMessage]:
        for msg in reversed(self.conversations):
            if msg.role == "user":
                return msg
        return None

# ==================== 简化的RAG引擎 ====================

class SimpleRAGEngine:
    """简化的RAG引擎，不依赖langchain"""
    
    def __init__(self, 
                 embedding_model_path: str = "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
                 db_path: str = "./vector_db",
                 collection_name: str = "textbook_content",
                 similarity_threshold: float = 0.3):
        """
        初始化RAG引擎
        
        Args:
            embedding_model_path: 嵌入模型路径
            db_path: 向量数据库路径
            collection_name: 集合名称
            similarity_threshold: 相似度阈值，低于此值的结果将被过滤
        """
        self.embedding_model_path = embedding_model_path
        self.db_path = db_path
        self.collection_name = collection_name
        self.similarity_threshold = similarity_threshold
        
        # 创建数据库目录
        os.makedirs(db_path, exist_ok=True)
        
        # 初始化嵌入模型
        print("🔧 正在加载嵌入模型...")
        self.embedding_model = SentenceTransformer(embedding_model_path)
        print("   ✅ 嵌入模型加载成功")
        
        # 初始化ChromaDB
        print("🔧 正在初始化向量数据库...")
        self.client = chromadb.PersistentClient(path=db_path)
        
        try:
            self.collection = self.client.get_collection(collection_name)
            print(f"   ✅ 找到现有集合: {collection_name}")
        except:
            self.collection = self.client.create_collection(collection_name)
            print(f"   ✅ 创建新集合: {collection_name}")
        
        # 显示集合信息
        info = self.get_collection_info()
        print(f"   📊 集合信息: {info}")
    
    def get_collection_info(self) -> dict:
        """获取集合信息"""
        try:
            count = self.collection.count()
            return {"collection_name": self.collection_name, "document_count": count}
        except:
            return {"collection_name": self.collection_name, "document_count": 0}
    
    def add_documents(self, documents: List[str], metadatas: List[dict], ids: List[str]):
        """添加文档到向量数据库"""
        print(f"📚 正在添加 {len(documents)} 个文档到向量数据库...")
        
        # 生成嵌入
        embeddings = self.embedding_model.encode(documents).tolist()
        
        # 添加到集合
        self.collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"   ✅ 文档添加完成")
    
    def search_similar(self, query: str, n_results: int = 5) -> dict:
        """搜索相似文档"""
        # 生成查询嵌入
        query_embedding = self.embedding_model.encode([query]).tolist()
        
        # 搜索
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results
        )
        
        return results
    
    def query(self, query_text: str, top_k: int = 5) -> dict:
        """查询RAG引擎"""
        results = self.search_similar(query_text, n_results=top_k)
        self._display_search_results(results, query_text)
        processed_results = self._handle_search_results(query_text, results)
        return processed_results
    
    def _display_search_results(self, results, query):
        """显示搜索结果"""
        print(f"\n{'='*60}")
        print(f"搜索查询: '{query}'")
        print(f"{'='*60}")
        
        if results['documents'] and results['documents'][0]:
            print("搜索结果:")
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0], 
                results['metadatas'][0], 
                results['distances'][0]
            )):
                similarity = 1 - distance
                print(f"\n结果 {i+1} (相似度: {similarity:.4f}):")
                print(f"  章节: {metadata.get('section', 'N/A')}")
                print(f"  文件: {metadata.get('file_name', 'N/A')}")
                print(f"  内容预览: {doc[:200]}...")
                print("-" * 40)
        else:
            print("  没有找到相关结果")
    
    def _handle_search_results(self, query, results) -> dict:
        """处理搜索结果，过滤低相似度结果"""
        processed_results = {
            "query": [query],
            "similarities": [],
            "file_names": [],
            "sections": [],
            "page_ranges": [],
            "contents": []  
        }
        
        if results['documents'] and results['documents'][0]:
            filtered_count = 0
            for doc, metadata, distance in zip(
                results['documents'][0], 
                results['metadatas'][0], 
                results['distances'][0]
            ):
                similarity = 1 - distance
                
                # 应用相似度阈值过滤
                if similarity >= self.similarity_threshold:
                    processed_results["similarities"].append(similarity)
                    processed_results["file_names"].append(metadata.get('file_name', 'unknown'))
                    processed_results["sections"].append(metadata.get('section', 'unknown'))
                    processed_results["page_ranges"].append(metadata.get('page_range', ''))
                    processed_results["contents"].append(doc)
                else:
                    filtered_count += 1
            
            if filtered_count > 0:
                print(f"   🔍 过滤了 {filtered_count} 个低相似度结果 (阈值: {self.similarity_threshold:.2f})")
        
        return processed_results

# ==================== 源码RAG引擎 ====================

class CodeRAGEngine:
    """源码RAG引擎，用于检索源代码"""
    
    def __init__(self, 
                 embedding_model_path: str = "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
                 db_path: str = "./vector_db",
                 collection_name: str = "source_code",
                 similarity_threshold: float = 0.3):
        """
        初始化源码RAG引擎
        
        Args:
            embedding_model_path: 嵌入模型路径
            db_path: 向量数据库路径
            collection_name: 集合名称（默认为 source_code）
            similarity_threshold: 相似度阈值，低于此值的结果将被过滤
        """
        self.embedding_model_path = embedding_model_path
        self.db_path = db_path
        self.collection_name = collection_name
        self.similarity_threshold = similarity_threshold
        
        # 创建数据库目录
        os.makedirs(db_path, exist_ok=True)
        
        # 初始化嵌入模型
        print("🔧 正在加载嵌入模型（源码检索）...")
        self.embedding_model = SentenceTransformer(embedding_model_path)
        print("   ✅ 嵌入模型加载成功")
        
        # 初始化ChromaDB
        print("🔧 正在初始化源码向量数据库...")
        self.client = chromadb.PersistentClient(path=db_path)
        
        try:
            self.collection = self.client.get_collection(collection_name)
            print(f"   ✅ 找到现有集合: {collection_name}")
        except:
            self.collection = self.client.create_collection(collection_name)
            print(f"   ✅ 创建新集合: {collection_name}")
        
        # 显示集合信息
        info = self.get_collection_info()
        print(f"   📊 集合信息: {info}")
    
    def get_collection_info(self) -> dict:
        """获取集合信息"""
        try:
            count = self.collection.count()
            return {"collection_name": self.collection_name, "document_count": count}
        except:
            return {"collection_name": self.collection_name, "document_count": 0}
    
    def add_documents(self, documents: List[str], metadatas: List[dict], ids: List[str]):
        """添加文档到向量数据库"""
        print(f"📚 正在添加 {len(documents)} 个源码文档到向量数据库...")
        
        # 生成嵌入
        embeddings = self.embedding_model.encode(documents).tolist()
        
        # 添加到集合
        self.collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"   ✅ 源码文档添加完成")
    
    def search_similar(self, query: str, n_results: int = 5) -> dict:
        """搜索相似源码"""
        # 生成查询嵌入
        query_embedding = self.embedding_model.encode([query]).tolist()
        
        # 搜索
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results
        )
        
        return results
    
    def query(self, query_text: str, top_k: int = 5) -> dict:
        """查询源码RAG引擎"""
        results = self.search_similar(query_text, n_results=top_k)
        self._display_search_results(results, query_text)
        processed_results = self._handle_search_results(query_text, results)
        return processed_results
    
    def _display_search_results(self, results, query):
        """显示搜索结果"""
        print(f"\n{'='*60}")
        print(f"源码搜索查询: '{query}'")
        print(f"{'='*60}")
        
        if results['documents'] and results['documents'][0]:
            print("搜索结果:")
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0], 
                results['metadatas'][0], 
                results['distances'][0]
            )):
                similarity = 1 - distance
                print(f"\n结果 {i+1} (相似度: {similarity:.4f}):")
                print(f"  文件路径: {metadata.get('file_path', 'N/A')}")
                print(f"  文件名: {metadata.get('file_name', 'N/A')}")
                print(f"  行号: {metadata.get('line_range', 'N/A')}")
                print(f"  语言: {metadata.get('language', 'N/A')}")
                print(f"  内容预览: {doc[:200]}...")
                print("-" * 40)
        else:
            print("  没有找到相关结果")
    
    def _handle_search_results(self, query, results) -> dict:
        """处理搜索结果，过滤低相似度结果"""
        processed_results = {
            "query": [query],
            "similarities": [],
            "file_names": [],
            "file_paths": [],
            "line_ranges": [],
            "languages": [],
            "contents": []  
        }
        
        if results['documents'] and results['documents'][0]:
            filtered_count = 0
            total_count = len(results['documents'][0])
            for doc, metadata, distance in zip(
                results['documents'][0], 
                results['metadatas'][0], 
                results['distances'][0]
            ):
                similarity = 1 - distance
                
                # 应用相似度阈值过滤
                if similarity >= self.similarity_threshold:
                    processed_results["similarities"].append(similarity)
                    processed_results["file_names"].append(metadata.get('file_name', 'unknown'))
                    processed_results["file_paths"].append(metadata.get('file_path', 'unknown'))
                    processed_results["line_ranges"].append(metadata.get('line_range', ''))
                    processed_results["languages"].append(metadata.get('language', 'unknown'))
                    processed_results["contents"].append(doc)
                else:
                    filtered_count += 1
            
            if filtered_count > 0:
                print(f"   🔍 过滤了 {filtered_count}/{total_count} 个低相似度结果 (阈值: {self.similarity_threshold:.2f})")
            elif total_count == 0:
                # 检查集合是否为空
                collection_count = self.collection.count()
                if collection_count == 0:
                    print(f"   ⚠️  集合 '{self.collection_name}' 为空，没有可检索的代码数据")
                else:
                    print(f"   ⚠️  查询未找到匹配结果（集合中有 {collection_count} 条数据，但相似度都低于阈值 {self.similarity_threshold:.2f}）")
        else:
            # 检查集合是否为空
            collection_count = self.collection.count()
            if collection_count == 0:
                print(f"   ⚠️  集合 '{self.collection_name}' 为空，没有可检索的代码数据")
            else:
                print(f"   ⚠️  查询未找到匹配结果（集合中有 {collection_count} 条数据）")
        
        return processed_results

# ==================== 源码检索工作流类 ====================
# 优先使用 dzz_retrieval 的 RetrievalEngine，失败则降级备用
try:
    from dzz_retrieval import RetrievalEngine
    print("✅ 成功导入 RetrievalEngine")
except ImportError:
    RetrievalEngine = None
    print("⚠️ 警告: 无法导入 RetrievalEngine，将使用备用检索方法")


class CodeRAGWorkflow:
    """源码检索工作流，用于检索源代码并生成描述"""
    
    def __init__(self, 
                 llm_path: str = "../models--Qwen--Qwen3-8B/snapshots/9c925d64d72725edaf899c6cb9c377fd0709d9c5",
                 embedding_model_path: str = "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
                 db_path: str = "./vector_db",
                 similarity_threshold: float = 0.3,
                 chroma_md_path: str = "./dzz_retrieval/chroma_md",
                 top_files: int = 3,
                 top_chunks: int = 5,
                 use_quantization: bool = True):
        # ...existing code...
        self.top_files = top_files
        self.top_chunks = top_chunks
        self.use_quantization = use_quantization
        self.llm_path = llm_path
        self.similarity_threshold = similarity_threshold
        self.chroma_md_path = chroma_md_path
        # 初始化组件
        self.conversation_manager = ConversationManager()
        self.code_rag_engine = CodeRAGEngine(embedding_model_path, db_path, similarity_threshold=similarity_threshold)

        # 使用 RetrievalEngine 作为主检索入口（覆盖 kernel / mm / 未来扩展）
        self.retrieval_engine = None
        if RetrievalEngine is not None:
            try:
                self.retrieval_engine = RetrievalEngine(
                    chroma_md_path=chroma_md_path,
                    bge_model_path=embedding_model_path,
                    top_files=top_files,
                    top_chunks=top_chunks,
                )
                self.dzz_collections_info = self.retrieval_engine.get_collections_info()
            except Exception as e:
                print(f"⚠️ 初始化 RetrievalEngine 失败: {e}，将使用备用检索")
        
        # 初始化LLM
        self._load_llm()
        
        # 初始化源码检索建议生成器
        self.code_retrieval_suggester = CodeRetrievalSuggester(self.model, self.tokenizer)
        
        # 供后续使用的文件摘要缓存
        self._retrieved_file_summaries: Dict[str, str] = {}
        
        print("✅ 源码检索工作流初始化完成!")

    
    def _load_llm(self):
        """加载大语言模型"""
        print("🤖 正在加载大语言模型...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # 加载分词器和模型
        self.tokenizer = AutoTokenizer.from_pretrained(self.llm_path, trust_remote_code=True)
        
        # 配置量化（根据 use_quantization 参数决定）
        quantization_config = None
        if self.use_quantization:
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
            )
        
        model_kwargs = {
            "device_map": "auto",
            "trust_remote_code": True,
        }
        if quantization_config:
            model_kwargs["quantization_config"] = quantization_config
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.llm_path,
            **model_kwargs
        )
        
        print(f"   ✅ 模型加载成功，使用设备: {device}, 量化: {'开启' if self.use_quantization else '关闭'}")
    
    def _convert_retrieval_output(self, resp: Dict[str, Any], query_used: str, round_no: int = 1) -> List[RetrievedChunk]:
        """将 RetrievalEngine.retrieve 的结果转为 RetrievedChunk 列表"""
        chunks: List[RetrievedChunk] = []
        if not resp:
            return chunks
        for f in resp.get("retrieved_files", []):
            src = f.get("source_file", "")
            for ch in f.get("chunks", []):
                file_path = ch.get("file_path", src) or src
                file_path = file_path.replace("\\", "/")
                content = ch.get("content", "")
                if isinstance(content, list):
                    content = "\n".join(content)
                score = ch.get("similarity", ch.get("_score", 0.0))
                start_line = ch.get("start_line")
                end_line = ch.get("end_line")
                line_range = ""
                if start_line or end_line:
                    s = start_line or ""
                    e = end_line or ""
                    line_range = f"{s}-{e}".strip("-")
                chunk = RetrievedChunk(
                    content=content,
                    source=file_path,
                    filename=os.path.basename(file_path) if file_path else "unknown",
                    relative_path=file_path,
                    extension=os.path.splitext(file_path)[1] or ".c",
                    score=score,
                    metadata={
                        "file_name": os.path.basename(file_path) if file_path else "unknown",
                        "file_path": file_path,
                        "line_range": line_range,
                        "start_line": start_line,
                        "end_line": end_line,
                        "function_name": ch.get("function_name", "N/A"),
                        "description": ch.get("description", ""),
                        "chunk_id": ch.get("chunk_id", ""),
                        "similarity": score,
                        "query_used": query_used,
                        "language": ch.get("language", "c"),
                        "round": round_no,
                    }
                )
                chunks.append(chunk)
        return chunks
    
    def _judge_sufficiency_and_suggest_keywords(
        self, 
        user_query: str, 
        retrieved_chunks: List[RetrievedChunk]
    ) -> Dict[str, Any]:
        """
        判断已检索的内容是否足以回答问题，如果不足则生成新的检索关键词
        
        Args:
            user_query: 用户问题
            retrieved_chunks: 已检索到的代码片段列表
            
        Returns:
            字典，包含：
            - is_sufficient: 是否足够回答问题
            - new_keywords: 如果不足，新的检索关键词列表
            - reasoning: 判断理由
        """
        try:
            # 构建已检索内容的摘要
            if retrieved_chunks:
                chunks_summary = "\n\n".join([
                    f"代码片段{i+1} (文件: {chunk.filename}, 函数: {chunk.metadata.get('function_name', 'N/A')}):\n{chunk.content[:300]}..."
                    for i, chunk in enumerate(retrieved_chunks)
                ])
            else:
                chunks_summary = "暂无相关代码片段"
            
            system_prompt = f"""你是一个代码信息充分性判断助手。请判断已检索到的代码内容是否足以回答用户问题。

用户问题：{user_query}

已检索到的相关代码内容：
{chunks_summary}

请判断：
1. 已检索到的代码内容是否足以完整回答用户问题
2. 如果不足，需要补充哪些方面的信息
3. 如果不足，请提供2-3个新的检索关键词，用于进行第二轮检索

请以JSON格式输出结果，格式如下：
{{
    "is_sufficient": false,
    "reasoning": "判断理由",
    "new_keywords": ["关键词1", "关键词2", "关键词3"]
}}

如果内容已足够，is_sufficient应为true，new_keywords可以为空数组。
只输出JSON，不要输出其他内容。"""
            
            # 构建消息
            messages = [{"role": "system", "content": system_prompt}]
            text = self.tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            
            # 生成判断结果
            inputs = self.tokenizer(text, return_tensors="pt")
            if torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=500,
                    temperature=0.3,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            
            response = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
            
            # 解析JSON结果
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "is_sufficient": result.get("is_sufficient", True),
                    "new_keywords": result.get("new_keywords", []),
                    "reasoning": result.get("reasoning", "")
                }
            else:
                # 如果解析失败，默认认为足够
                print(f"   ⚠️ 无法解析充分性判断结果，默认内容已足够")
                return {
                    "is_sufficient": True,
                    "new_keywords": [],
                    "reasoning": "无法解析判断结果，默认认为内容已足够"
                }
                
        except Exception as e:
            print(f"   ⚠️ 判断内容充分性时出错: {e}")
            # 出错时默认认为足够
            return {
                "is_sufficient": True,
                "new_keywords": [],
                "reasoning": f"判断过程出错: {str(e)}"
            }
    
    def _retrieve_code_with_keywords(self, keywords: List[str], seen_chunk_ids: set = None) -> List[RetrievedChunk]:
        """
        使用关键词列表检索源码（用于第二轮检索，沿用 RetrievalEngine）
        """
        if seen_chunk_ids is None:
            seen_chunk_ids = set()
        all_chunks: List[RetrievedChunk] = []
        for keyword in keywords[:3]:
            try:
                if self.retrieval_engine is not None:
                    resp = self.retrieval_engine.retrieve(keyword)
                    query_chunks = self._convert_retrieval_output(resp, keyword, round_no=2)
                else:
                    print(f"      ⚠️ 备用检索 (关键词: '{keyword}')...")
                    results = self.code_rag_engine.query(keyword, top_k=self.top_files * self.top_chunks)
                    query_chunks = []
                    if results.get("contents"):
                        file_paths = results.get("file_paths", [""] * len(results["contents"]))
                        line_ranges = results.get("line_ranges", [""] * len(results["contents"]))
                        languages = results.get("languages", [""] * len(results["contents"]))
                        for content, similarity, file_name, file_path, line_range, language in zip(
                            results["contents"],
                            results["similarities"],
                            results["file_names"],
                            file_paths,
                            line_ranges,
                            languages,
                        ):
                            chunk = RetrievedChunk(
                                content=content,
                                source=file_path or file_name,
                                filename=file_name,
                                relative_path=file_path or file_name,
                                extension=self._get_extension_from_language(language) or ".txt",
                                score=similarity,
                                metadata={
                                    "file_name": file_name,
                                    "file_path": file_path,
                                    "line_range": line_range,
                                    "language": language,
                                    "similarity": similarity,
                                    "query_used": keyword,
                                    "round": 2,
                                },
                            )
                            query_chunks.append(chunk)
                query_chunks.sort(key=lambda x: x.score, reverse=True)
                for chunk in query_chunks:
                    cid = f"{chunk.metadata.get('file_path','')}_{chunk.metadata.get('chunk_id','')}"
                    if cid in seen_chunk_ids:
                        continue
                    seen_chunk_ids.add(cid)
                    all_chunks.append(chunk)
            except Exception as e:
                print(f"      ❌ 使用关键词 '{keyword}' 检索时出错: {e}")
                continue
        all_chunks.sort(key=lambda x: x.score, reverse=True)
        return all_chunks[:5]
    
    def _generate_response_with_context(
        self,
        user_query: str,
        chunks: List[RetrievedChunk],
        token_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """生成带有代码上下文的回答"""
        try:
            # 构建上下文信息（包含代码块的实际内容）
            context_parts = []
            for i, chunk in enumerate(chunks):
                file_path = chunk.metadata.get('file_path', chunk.filename or 'unknown')
                line_range = chunk.metadata.get('line_range', '')
                function_name = chunk.metadata.get('function_name', '')
                
                # 构建代码块标识信息
                chunk_info = f"代码片段{i+1}"
                if file_path:
                    chunk_info += f" (文件: {file_path}"
                    if line_range:
                        chunk_info += f", 行号: {line_range}"
                    if function_name and function_name != 'N/A':
                        chunk_info += f", 函数: {function_name}"
                    chunk_info += ")"
                
                # 添加代码块的实际内容
                context_parts.append(
                    f"{chunk_info}:\n{chunk.content}"
                )
            context = "\n\n".join(context_parts)
            
            # 获取对话历史
            conversation_history = self.conversation_manager.get_history()
            
            # 构建系统提示词，强调要基于代码内容回答
            system_prompt = f"""你是一个专业的代码分析助手，请基于提供的源代码内容回答用户的问题。

提供的源代码内容：
{context}

请仔细分析这些代码，理解其功能、逻辑和实现细节，然后基于这些实际代码内容回答用户的问题。如果代码内容与问题相关，请详细解释代码的工作原理；如果代码内容不足以回答问题，请说明原因。"""
            
            # 构建消息列表
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # 添加历史对话（最近3轮）
            for msg in conversation_history[-3:]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # 添加当前用户查询
            messages.append({
                "role": "user", 
                "content": user_query
            })
            
            # 格式化输入
            text = self.tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            
            # 编码
            inputs = self.tokenizer(text, return_tensors="pt")
            
            # 确保输入在正确的设备上
            if torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            # 设置流式输出组件
            streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
            generation_kwargs = dict(inputs)
            generation_kwargs.update({
                "max_new_tokens": 3000,
                "temperature": 0.7,
                "do_sample": True,
                "pad_token_id": self.tokenizer.eos_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
                "streamer": streamer
            })
            response_chunks: List[str] = []

            def generate():
                """在后台线程中执行生成，驱动流式输出"""
                with torch.no_grad():
                    self.model.generate(**generation_kwargs)

            generation_thread = Thread(target=generate, daemon=True)
            generation_thread.start()

            show_console = token_callback is None
            if show_console:
                print("   💬 实时输出:", end=" ", flush=True)

            for new_text in streamer:
                if token_callback is not None:
                    token_callback(new_text)
                else:
                    print(new_text, end="", flush=True)
                response_chunks.append(new_text)

            generation_thread.join()
            if show_console:
                print()

            return "".join(response_chunks).strip()
            
        except Exception as e:
            print(f"      ❌ 生成回答时出错: {e}")
            import traceback
            traceback.print_exc()
            return f"抱歉，生成回答时遇到错误: {str(e)}"
    
    def process_code_query(
        self,
        user_query: str,
        stream_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> WorkflowResponse:
        """
        处理源码查询的完整工作流（迭代式RAG）
        
        Args:
            user_query: 用户查询
            stream_callback: 流式输出回调函数
            
        Returns:
            工作流响应对象
        """
        print(f"\n{'='*60}")
        print("🚀 开始处理源码查询（迭代式RAG）...")
        print(f"📝 用户问题: {user_query}")
        print(f"{'='*60}")
        
        # 步骤1: 记录用户输入
        self.conversation_manager.add_message("user", user_query)
        conversation_history = self.conversation_manager.get_history()
        
        # 步骤2: 生成初始源码检索建议
        print("\n🔍 步骤1: 生成初始源码检索建议...")
        retrieval_suggestion = self.code_retrieval_suggester.generate_suggestion(
            user_query, conversation_history[:-1]  # 不包含当前用户消息
        )
        
        print(f"   📋 原始查询: {retrieval_suggestion.original_query}")
        print(f"   🎯 意图识别: {retrieval_suggestion.intent}")
        print(f"   📊 置信度: {retrieval_suggestion.confidence:.2f}")
        print(f"   🔑 关键词: {retrieval_suggestion.search_keywords}")
        print(f"   📝 建议查询: {retrieval_suggestion.suggested_queries}")
        
        # 步骤3: 第一轮检索
        print("\n💻 步骤2: 执行第一轮源码向量检索...")
        first_round_chunks = self._retrieve_code_with_suggestion(retrieval_suggestion)
        print(f"   ✅ 第一轮检索到 {len(first_round_chunks)} 个代码片段")
        
        # 如需流式输出，通知外部第一轮检索结果
        if stream_callback is not None:
            try:
                stream_callback({
                    "type": "code_retrieval",
                    "retrieved_chunks": first_round_chunks,
                    "user_query": user_query,
                    "round": 1,
                })
            except Exception as callback_error:
                print(f"   ⚠️ 流式回调异常: {callback_error}")
        
        # 步骤4: 判断已检索的内容是否足以回答问题
        print("\n🔍 步骤3: 判断已检索内容是否足以回答问题...")
        sufficiency_result = self._judge_sufficiency_and_suggest_keywords(user_query, first_round_chunks)
        is_sufficient = sufficiency_result.get("is_sufficient", True)
        new_keywords = sufficiency_result.get("new_keywords", [])
        reasoning = sufficiency_result.get("reasoning", "")
        
        print(f"   📊 判断结果: {'内容已足够' if is_sufficient else '内容不足，需要补充'}")
        if reasoning:
            print(f"   💭 判断理由: {reasoning}")
        
        # 步骤5: 如果内容不足，进行第二轮检索
        all_chunks = first_round_chunks.copy()
        second_round_chunks = []
        seen_chunk_ids = set()
        
        # 记录第一轮chunk的ID
        for chunk in first_round_chunks:
            chunk_id = f"{chunk.metadata.get('file_path', '')}_{chunk.metadata.get('chunk_id', '')}"
            seen_chunk_ids.add(chunk_id)
        
        if not is_sufficient and new_keywords:
            print(f"\n💻 步骤4: 执行第二轮源码向量检索（关键词: {new_keywords}）...")
            # 使用新的关键词进行检索
            second_round_chunks = self._retrieve_code_with_keywords(new_keywords, seen_chunk_ids)
            print(f"   ✅ 第二轮检索到 {len(second_round_chunks)} 个新的代码片段")
            
            # 合并两轮检索的chunk
            all_chunks.extend(second_round_chunks)
            
            # 如需流式输出，通知外部第二轮检索结果
            if stream_callback is not None:
                try:
                    stream_callback({
                        "type": "code_retrieval",
                        "retrieved_chunks": second_round_chunks,
                        "user_query": user_query,
                        "round": 2,
                    })
                except Exception as callback_error:
                    print(f"   ⚠️ 流式回调异常: {callback_error}")
        else:
            print("\n   ℹ️ 内容已足够，跳过第二轮检索")
        
        # 步骤6: 使用所有检索到的chunk生成最终回答
        print(f"\n🤖 步骤{'4' if is_sufficient or not new_keywords else '5'}: 基于检索到的代码内容生成回复...")
        print(f"   📚 使用 {len(all_chunks)} 个代码片段生成回答")
        
        # 设置流式输出回调
        token_callback = None
        if stream_callback is not None:
            def handle_token(token_text: str) -> None:
                try:
                    stream_callback({
                        "type": "code_description_chunk",
                        "chunk": token_text,
                    })
                except Exception as callback_error:
                    print(f"   ⚠️ 流式回调异常: {callback_error}")

            token_callback = handle_token

        # 使用大模型基于检索到的代码块内容生成回复
        llm_response = self._generate_response_with_context(
            user_query,
            all_chunks,
            token_callback=token_callback,
        )
        print(f"   ✅ 回答生成完成")
        
        # 记录助手回答
        self.conversation_manager.add_message("assistant", llm_response)
        
        # 构建完整响应（包含所有检索到的chunk）
        workflow_response = WorkflowResponse(
            user_query=user_query,
            retrieval_suggestion=retrieval_suggestion,
            retrieved_chunks=all_chunks,  # 使用所有检索到的chunk
            llm_response=llm_response,
            conversation_history=self.conversation_manager.get_history(),
            timestamp=datetime.now()
        )
        
        print(f"\n{'='*60}")
        print("✅ 源码查询处理完成!")
        print(f"{'='*60}")
        
        # 打印完整的处理结果到后台
        print(f"\n{'='*60}")
        print("📊 源码查询处理结果摘要（迭代式RAG）")
        print(f"{'='*60}")
        print(f"用户查询: {workflow_response.user_query}")
        print(f"初始检索建议数量: {len(workflow_response.retrieval_suggestion.suggested_queries) if workflow_response.retrieval_suggestion else 0}")
        print(f"第一轮检索片段数: {len(first_round_chunks)}")
        if second_round_chunks:
            print(f"第二轮检索片段数: {len(second_round_chunks)}")
            print(f"第二轮相关片段数: {len([c for c in all_chunks if c.metadata.get('round') == 2])}")
        print(f"最终使用的代码片段数: {len(workflow_response.retrieved_chunks)}")
        print(f"生成回复长度: {len(workflow_response.llm_response)} 字符")
        
        if workflow_response.retrieved_chunks:
            print(f"\n最终使用的代码片段详情:")
            for i, chunk in enumerate(workflow_response.retrieved_chunks[:5], 1):
                round_num = chunk.metadata.get('round', 1)
                print(f"  [{i}] {chunk.filename} (第{round_num}轮检索)")
                print(f"      路径: {chunk.metadata.get('file_path', 'N/A')}")
                print(f"      行号: {chunk.metadata.get('line_range', 'N/A')}")
                print(f"      函数: {chunk.metadata.get('function_name', 'N/A')}")
                print(f"      相似度: {chunk.score:.4f}")
        
        print(f"\n生成回复预览（前500字符）:")
        print(f"{workflow_response.llm_response[:500]}...")
        print(f"{'='*60}\n")
        
        return workflow_response
    
    def _retrieve_code_with_suggestion(self, suggestion: RetrievalSuggestion) -> List[RetrievedChunk]:
        """基于检索建议检索源码（优先使用 RetrievalEngine，两阶段已封装）"""
        all_chunks: List[RetrievedChunk] = []
        seen_chunk_ids = set()
        self._retrieved_file_summaries = {}
        
        queries_to_try = suggestion.suggested_queries + [suggestion.original_query] if suggestion.suggested_queries else [suggestion.original_query]
        # 去重保序
        uniq = []
        seen_q = set()
        for q in queries_to_try:
            if q not in seen_q:
                seen_q.add(q)
                uniq.append(q)
        queries_to_try = uniq[:5]
        
        print(f"      📋 将使用 {len(queries_to_try)} 个查询进行逐个检索（每个查询由 RetrievalEngine 控制 top_k）")
        
        for query in queries_to_try:
            try:
                if self.retrieval_engine is not None:
                    resp = self.retrieval_engine.retrieve(query)
                    # 缓存文件摘要
                    for f in resp.get("retrieved_files", []):
                        if f.get("source_file") and f.get("md_summary"):
                            self._retrieved_file_summaries[f["source_file"]] = f["md_summary"]
                    query_chunks = self._convert_retrieval_output(resp, query, round_no=1)
                else:
                    # 备用：原 CodeRAGEngine
                    print(f"      ⚠️ 使用备用检索方法 (查询: '{query}')...")
                    results = self.code_rag_engine.query(query, top_k=self.top_files * self.top_chunks)
                    query_chunks = []
                    if results.get("contents"):
                        file_paths = results.get("file_paths", [""] * len(results["contents"]))
                        line_ranges = results.get("line_ranges", [""] * len(results["contents"]))
                        languages = results.get("languages", [""] * len(results["contents"]))
                        for content, similarity, file_name, file_path, line_range, language in zip(
                            results["contents"],
                            results["similarities"],
                            results["file_names"],
                            file_paths,
                            line_ranges,
                            languages,
                        ):
                            chunk = RetrievedChunk(
                                content=content,
                                source=file_path or file_name,
                                filename=file_name,
                                relative_path=file_path or file_name,
                                extension=self._get_extension_from_language(language) or ".txt",
                                score=similarity,
                                metadata={
                                    "file_name": file_name,
                                    "file_path": file_path,
                                    "line_range": line_range,
                                    "language": language,
                                    "similarity": similarity,
                                    "query_used": query,
                                    "round": 1,
                                },
                            )
                            query_chunks.append(chunk)
                # 去重并合并
                query_chunks.sort(key=lambda x: x.score, reverse=True)
                for chunk in query_chunks:
                    cid = f"{chunk.metadata.get('file_path','')}_{chunk.metadata.get('chunk_id','')}"
                    if cid not in seen_chunk_ids:
                        seen_chunk_ids.add(cid)
                        all_chunks.append(chunk)
            except Exception as e:
                print(f"      ❌ 检索查询 '{query}' 时出错: {e}")
                import traceback; traceback.print_exc()
                continue
        
        all_chunks.sort(key=lambda x: x.score, reverse=True)
        return all_chunks[:8]
    
    def _extract_file_overview(self, summary: str) -> str:
        """从文件摘要中提取"文件概述"部分"""
        if not summary:
            return ""
        
        # 查找"文件概述"部分
        # 可能的标记：## 文件概述、## 1. 文件概述、文件概述等
        import re
        patterns = [
            r'##\s*文件概述\s*\n\n(.*?)(?=\n##|\n#|$)',
            r'##\s*1\.\s*文件概述\s*\n\n(.*?)(?=\n##|\n#|$)',
            r'文件概述\s*\n\n(.*?)(?=\n##|\n#|$)',
            r'##\s*文件概述\s*\n(.*?)(?=\n##|\n#|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, summary, re.DOTALL | re.IGNORECASE)
            if match:
                overview = match.group(1).strip()
                # 限制长度，最多500字符
                if len(overview) > 500:
                    overview = overview[:500] + "..."
                return overview
        
        # 如果找不到"文件概述"，尝试查找第一个段落（在"技术文档"标题之后）
        # 查找"技术文档"标题后的第一个段落
        tech_doc_match = re.search(r'#.*?技术文档\s*\n\n(.*?)(?=\n##|\n#|$)', summary, re.DOTALL | re.IGNORECASE)
        if tech_doc_match:
            first_para = tech_doc_match.group(1).strip()
            # 取第一个段落，最多500字符
            if len(first_para) > 500:
                first_para = first_para[:500] + "..."
            return first_para
        
        return ""
    
    def _get_extension_from_language(self, language: str) -> str:
        """根据编程语言获取文件扩展名"""
        language_extensions = {
            'python': '.py',
            'javascript': '.js',
            'typescript': '.ts',
            'java': '.java',
            'cpp': '.cpp',
            'c': '.c',
            'go': '.go',
            'rust': '.rs',
            'php': '.php',
            'ruby': '.rb',
            'swift': '.swift',
            'kotlin': '.kt',
        }
        return language_extensions.get(language.lower(), '.txt')
    
    def _generate_code_description(
        self,
        user_query: str,
        chunks: List[RetrievedChunk],
        token_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """生成代码描述"""
        try:
            # 构建上下文信息
            context_parts = []
            for i, chunk in enumerate(chunks):
                file_info = f"文件: {chunk.filename}"
                if chunk.metadata.get('line_range'):
                    file_info += f" (行号: {chunk.metadata.get('line_range')})"
                if chunk.metadata.get('language'):
                    file_info += f" [语言: {chunk.metadata.get('language')}]"
                
                context_parts.append(
                    f"代码片段{i+1} ({file_info}):\n```\n{chunk.content}\n```"
                )
            context = "\n\n".join(context_parts)
            
            # 获取对话历史
            conversation_history = self.conversation_manager.get_history()
            
            # 构建消息列表
            messages = [
                {"role": "system", "content": f"""你是一个专业的代码分析助手，请基于提供的源代码片段回答用户的问题，并生成详细的代码描述。

源代码片段：
{context}

请生成详细的代码描述，包括：
1. 代码的功能和作用
2. 关键函数、类或方法的说明
3. 代码逻辑流程
4. 重要的技术细节
5. 与用户问题的关联性

请使用中文回答，语言要专业但通俗易懂。"""}
            ]
            
            # 添加历史对话（最近3轮）
            for msg in conversation_history[-3:]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # 添加当前用户查询
            messages.append({
                "role": "user", 
                "content": user_query
            })
            
            # 格式化输入
            text = self.tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            
            # 编码
            inputs = self.tokenizer(text, return_tensors="pt")
            
            # 确保输入在正确的设备上
            if torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            # 设置流式输出组件
            streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
            generation_kwargs = dict(inputs)
            generation_kwargs.update({
                "max_new_tokens": 3000,
                "temperature": 0.7,
                "do_sample": True,
                "pad_token_id": self.tokenizer.eos_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
                "streamer": streamer
            })
            response_chunks: List[str] = []

            def generate():
                """在后台线程中执行生成，驱动流式输出"""
                with torch.no_grad():
                    self.model.generate(**generation_kwargs)

            generation_thread = Thread(target=generate, daemon=True)
            generation_thread.start()

            show_console = token_callback is None
            if show_console:
                print("   💬 实时输出:", end=" ", flush=True)

            for new_text in streamer:
                if token_callback is not None:
                    token_callback(new_text)
                else:
                    print(new_text, end="", flush=True)
                response_chunks.append(new_text)

            generation_thread.join()
            if show_console:
                print()

            return "".join(response_chunks).strip()
            
        except Exception as e:
            print(f"      ❌ 生成代码描述时出错: {e}")
            return f"抱歉，生成代码描述时遇到错误: {str(e)}"
    
    def display_response(self, response: WorkflowResponse):
        """格式化显示响应结果"""
        print(f"\n🤖 AI代码描述:")
        print("=" * 60)
        print(response.llm_response)
        print("=" * 60)
        
        print(f"\n💻 检索到的代码片段 ({len(response.retrieved_chunks)} 个):")
        print("-" * 60)
        for i, chunk in enumerate(response.retrieved_chunks):
            print(f"\n代码片段 {i+1}:")
            print(f"   文件名: {chunk.filename}")
            print(f"   文件路径: {chunk.metadata.get('file_path', 'N/A')}")
            print(f"   行号: {chunk.metadata.get('line_range', 'N/A')}")
            print(f"   语言: {chunk.metadata.get('language', 'N/A')}")
            print(f"   相似度: {chunk.score:.4f}")
            print(f"   内容预览:")
            content = chunk.content
            if len(content) > 200:
                content = content[:200] + "..."
            print(f"      {content}")
            print("-" * 40)
    
    def clear_conversation(self):
        """清空对话历史"""
        self.conversation_manager.clear()
        print("✅ 对话历史已清空")

# ==================== 主工作流类 ====================

class SimpleRAGWorkflow:
    """简化的RAG工作流，不依赖langchain"""
    
    def __init__(self, 
                 llm_path: str = "../models--Qwen--Qwen3-8B/snapshots/9c925d64d72725edaf899c6cb9c377fd0709d9c5",
                 embedding_model_path: str = "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
                 db_path: str = "./vector_db",
                 similarity_threshold: float = 0.3,
                 use_quantization: bool = True):
        """
        初始化RAG工作流
        
        Args:
            llm_path: 大语言模型路径
            embedding_model_path: 嵌入模型路径
            db_path: 向量数据库路径
            similarity_threshold: 相似度阈值，低于此值的结果将被过滤
            use_quantization: 是否使用4位量化，True表示使用量化（节省显存），False表示不使用量化（更高精度）
        """
        self.llm_path = llm_path
        self.similarity_threshold = similarity_threshold
        self.use_quantization = use_quantization
        
        # 初始化组件
        self.conversation_manager = ConversationManager()
        self.rag_engine = SimpleRAGEngine(embedding_model_path, db_path, similarity_threshold=similarity_threshold)
        
        # 初始化LLM
        self._load_llm()
        
        # 初始化检索建议生成器
        self.retrieval_suggester = RetrievalSuggester(self.model, self.tokenizer)
        
        print("✅ 简化RAG工作流初始化完成!")
    
    def _load_llm(self):
        """加载大语言模型"""
        print("🤖 正在加载大语言模型...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # 加载分词器和模型
        self.tokenizer = AutoTokenizer.from_pretrained(self.llm_path, trust_remote_code=True)
        
        # 根据配置决定是否使用量化
        if self.use_quantization:
            print("   📦 使用4位量化加载模型（节省显存）...")
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.llm_path,
                quantization_config=quantization_config,
                device_map="auto",
                trust_remote_code=True,
            )
        else:
            print("   🚀 使用全精度加载模型（更高精度，需要更多显存）...")
            self.model = AutoModelForCausalLM.from_pretrained(
                self.llm_path,
                device_map="auto",
                trust_remote_code=True,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            )
        
        print(f"   ✅ 模型加载成功，使用设备: {device}, 量化: {'开启' if self.use_quantization else '关闭'}")
    
    def process_user_query(
        self,
        user_query: str,
        stream_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> WorkflowResponse:
        """
        处理用户查询的完整工作流（迭代式RAG）
        
        Args:
            user_query: 用户查询
            stream_callback: 流式输出回调函数
            
        Returns:
            工作流响应对象
        """
        print(f"\n{'='*60}")
        print("🚀 开始处理用户查询（迭代式RAG）...")
        print(f"📝 用户问题: {user_query}")
        print(f"{'='*60}")
        
        # 步骤1: 记录用户输入
        self.conversation_manager.add_message("user", user_query)
        conversation_history = self.conversation_manager.get_history()
        
        # 步骤2: 生成初始检索建议
        print("\n🔍 步骤1: 生成初始检索建议...")
        retrieval_suggestion = self.retrieval_suggester.generate_suggestion(
            user_query, conversation_history[:-1]  # 不包含当前用户消息
        )
        
        print(f"   📋 原始查询: {retrieval_suggestion.original_query}")
        print(f"   🎯 意图识别: {retrieval_suggestion.intent}")
        print(f"   📊 置信度: {retrieval_suggestion.confidence:.2f}")
        print(f"   🔑 关键词: {retrieval_suggestion.search_keywords}")
        print(f"   📝 建议查询: {retrieval_suggestion.suggested_queries}")
        
        # 步骤3: 第一轮检索
        print("\n📚 步骤2: 执行第一轮向量检索...")
        first_round_chunks = self._retrieve_documents_with_suggestion(retrieval_suggestion)
        print(f"   ✅ 第一轮检索到 {len(first_round_chunks)} 个文档片段")
        
        # 步骤4: 判断每个chunk是否与问题相关
        print("\n🔍 步骤3: 判断检索到的chunk是否与问题相关...")
        relevance_flags = self._judge_chunk_relevance(user_query, first_round_chunks)
        relevant_chunks_round1 = [
            chunk for i, chunk in enumerate(first_round_chunks) 
            if (relevance_flags[i] if i < len(relevance_flags) else True)
        ]
        print(f"   ✅ 第一轮检索中，{len(relevant_chunks_round1)}/{len(first_round_chunks)} 个chunk被判定为相关")
        
        # 如需流式输出，通知外部第一轮检索结果
        if stream_callback is not None:
            try:
                stream_callback({
                    "type": "retrieval",
                    "retrieved_chunks": first_round_chunks,
                    "user_query": user_query,
                    "round": 1,
                })
            except Exception as callback_error:
                print(f"   ⚠️ 流式回调异常: {callback_error}")
        
        # 步骤5: 判断已检索的内容是否足以回答问题
        print("\n🔍 步骤4: 判断已检索内容是否足以回答问题...")
        sufficiency_result = self._judge_sufficiency_and_suggest_keywords(user_query, relevant_chunks_round1)
        is_sufficient = sufficiency_result.get("is_sufficient", True)
        new_keywords = sufficiency_result.get("new_keywords", [])
        reasoning = sufficiency_result.get("reasoning", "")
        
        print(f"   📊 判断结果: {'内容已足够' if is_sufficient else '内容不足，需要补充'}")
        if reasoning:
            print(f"   💭 判断理由: {reasoning}")
        
        # 步骤6: 如果内容不足，进行第二轮检索
        all_relevant_chunks = relevant_chunks_round1.copy()
        second_round_chunks = []
        
        if not is_sufficient and new_keywords:
            print(f"\n📚 步骤5: 执行第二轮向量检索（关键词: {new_keywords}）...")
            # 使用新的关键词进行检索
            for keyword in new_keywords[:3]:  # 最多使用3个关键词
                try:
                    results = self.rag_engine.query(keyword, top_k=3)
                    if results.get('contents'):
                        page_ranges = results.get('page_ranges', [''] * len(results['contents']))
                        seen_content = {chunk.content for chunk in all_relevant_chunks}
                        
                        for content, similarity, file_name, section, page_range in zip(
                            results['contents'],
                            results['similarities'],
                            results['file_names'],
                            results['sections'],
                            page_ranges
                        ):
                            # 去重：检查是否已在第一轮检索结果中
                            if content in seen_content:
                                continue
                            seen_content.add(content)
                            
                            chunk = RetrievedChunk(
                                content=content,
                                source=file_name,
                                filename=file_name,
                                relative_path=file_name,
                                extension=".pdf",
                                score=similarity,
                                metadata={
                                    'file_name': file_name,
                                    'section': section,
                                    'page_range': page_range,
                                    'similarity': similarity,
                                    'query_used': keyword,
                                    'round': 2
                                }
                            )
                            second_round_chunks.append(chunk)
                except Exception as e:
                    print(f"      ❌ 使用关键词 '{keyword}' 检索时出错: {e}")
                    continue
            
            # 按相似度排序
            second_round_chunks.sort(key=lambda x: x.score, reverse=True)
            second_round_chunks = second_round_chunks[:5]  # 最多5个
            print(f"   ✅ 第二轮检索到 {len(second_round_chunks)} 个新的文档片段")
            
            # 判断第二轮检索的chunk是否相关
            if second_round_chunks:
                print("\n🔍 步骤6: 判断第二轮检索的chunk是否与问题相关...")
                relevance_flags_round2 = self._judge_chunk_relevance(user_query, second_round_chunks)
                relevant_chunks_round2 = [
                    chunk for i, chunk in enumerate(second_round_chunks) 
                    if (relevance_flags_round2[i] if i < len(relevance_flags_round2) else True)
                ]
                print(f"   ✅ 第二轮检索中，{len(relevant_chunks_round2)}/{len(second_round_chunks)} 个chunk被判定为相关")
                
                # 合并两轮检索的相关chunk
                all_relevant_chunks.extend(relevant_chunks_round2)
                
                # 如需流式输出，通知外部第二轮检索结果
                if stream_callback is not None:
                    try:
                        stream_callback({
                            "type": "retrieval",
                            "retrieved_chunks": second_round_chunks,
                            "user_query": user_query,
                            "round": 2,
                        })
                    except Exception as callback_error:
                        print(f"   ⚠️ 流式回调异常: {callback_error}")
        else:
            print("\n   ℹ️ 内容已足够，跳过第二轮检索")
        
        # 步骤7: 使用所有相关chunk生成最终回答
        print(f"\n🤖 步骤{'6' if is_sufficient or not new_keywords else '7'}: 生成最终回答...")
        print(f"   📚 使用 {len(all_relevant_chunks)} 个相关文档片段生成回答")
        
        token_callback = None
        if stream_callback is not None:
            def handle_token(token_text: str) -> None:
                try:
                    stream_callback({
                        "type": "answer_chunk",
                        "chunk": token_text,
                    })
                except Exception as callback_error:
                    print(f"   ⚠️ 流式回调异常: {callback_error}")

            token_callback = handle_token

        llm_response = self._generate_response_with_context(
            user_query,
            all_relevant_chunks,
            token_callback=token_callback,
        )
        print(f"   ✅ 回答生成完成")
        
        # 记录助手回答
        self.conversation_manager.add_message("assistant", llm_response)
        
        # 构建完整响应（包含所有相关chunk）
        workflow_response = WorkflowResponse(
            user_query=user_query,
            retrieval_suggestion=retrieval_suggestion,
            retrieved_chunks=all_relevant_chunks,  # 使用所有相关chunk
            llm_response=llm_response,
            conversation_history=self.conversation_manager.get_history(),
            timestamp=datetime.now()
        )
        
        print(f"\n{'='*60}")
        print("✅ 查询处理完成!")
        print(f"{'='*60}")
        
        # 打印完整的处理结果到后台
        print(f"\n{'='*60}")
        print("📊 教材检索处理结果摘要（迭代式RAG）")
        print(f"{'='*60}")
        print(f"用户查询: {workflow_response.user_query}")
        print(f"初始检索建议数量: {len(workflow_response.retrieval_suggestion.suggested_queries) if workflow_response.retrieval_suggestion else 0}")
        print(f"第一轮检索片段数: {len(first_round_chunks)}")
        print(f"第一轮相关片段数: {len(relevant_chunks_round1)}")
        if second_round_chunks:
            print(f"第二轮检索片段数: {len(second_round_chunks)}")
            print(f"第二轮相关片段数: {len([c for c in all_relevant_chunks if c.metadata.get('round') == 2])}")
        print(f"最终使用的相关片段数: {len(workflow_response.retrieved_chunks)}")
        print(f"回答长度: {len(workflow_response.llm_response)} 字符")
        
        if workflow_response.retrieved_chunks:
            print(f"\n最终使用的相关文档片段详情:")
            for i, chunk in enumerate(workflow_response.retrieved_chunks[:5], 1):
                round_num = chunk.metadata.get('round', 1)
                print(f"  [{i}] {chunk.filename} (第{round_num}轮检索)")
                print(f"      页码: {chunk.metadata.get('page', 'N/A')}")
                print(f"      页码范围: {chunk.metadata.get('page_range', 'N/A')}")
                print(f"      章节: {chunk.metadata.get('chapter', 'N/A')}")
                print(f"      相似度: {chunk.score:.4f}")
                # 显示内容预览
                content_preview = chunk.content[:150] + "..." if len(chunk.content) > 150 else chunk.content
                print(f"      内容预览: {content_preview}")
        
        print(f"\n回答预览（前500字符）:")
        print(f"{workflow_response.llm_response[:500]}...")
        print(f"{'='*60}\n")
        
        return workflow_response
    
    def _retrieve_documents_with_suggestion(self, suggestion: RetrievalSuggestion) -> List[RetrievedChunk]:
        """基于检索建议检索文档"""
        all_chunks = []
        seen_content = set()
        
        # 使用建议的查询进行检索
        queries_to_try = suggestion.suggested_queries + [suggestion.original_query]
        
        for query in queries_to_try:
            try:
                # 使用RAG引擎检索
                results = self.rag_engine.query(query, top_k=3)
                
                # 处理结果
                if results.get('contents'):
                    # 获取page_ranges信息，如果不存在则使用空字符串列表
                    page_ranges = results.get('page_ranges', [''] * len(results['contents']))
                    
                    for i, (content, similarity, file_name, section, page_range) in enumerate(zip(
                        results['contents'],
                        results['similarities'],
                        results['file_names'],
                        results['sections'],
                        page_ranges
                    )):
                        # 去重
                        if content in seen_content:
                            continue
                        seen_content.add(content)
                        
                        # 创建RetrievedChunk对象
                        chunk = RetrievedChunk(
                            content=content,
                            source=file_name,
                            filename=file_name,
                            relative_path=file_name,
                            extension=".pdf",
                            score=similarity,
                            metadata={
                                'file_name': file_name,
                                'section': section,
                                'page_range': page_range,
                                'similarity': similarity,
                                'query_used': query
                            }
                        )
                        all_chunks.append(chunk)
                        
            except Exception as e:
                print(f"      ❌ 检索查询 '{query}' 时出错: {e}")
                continue
        
        # 按相似度分数排序
        all_chunks.sort(key=lambda x: x.score, reverse=True)
        
        return all_chunks[:8]  # 最多返回8个片段
    
    def _retrieve_documents(self, user_query: str) -> List[RetrievedChunk]:
        """检索文档，应用相似度阈值过滤"""
        all_chunks = []
        
        try:
            # 使用RAG引擎进行检索
            search_results = self.rag_engine.query(user_query)
            
            # 处理RAG引擎的返回结果
            if search_results.get('contents'):
                for i, (content, similarity, file_name, section) in enumerate(zip(
                    search_results['contents'],
                    search_results['similarities'],
                    search_results['file_names'],
                    search_results['sections']
                )):
                    # 双重阈值检查（RAG引擎已经过滤了一次，这里再次确认）
                    if similarity >= self.similarity_threshold:
                        # 创建RetrievedChunk对象
                        chunk = RetrievedChunk(
                            content=content,
                            source=file_name,
                            filename=file_name,
                            relative_path=file_name,
                            extension=".pdf",
                            score=similarity,
                            metadata={
                                'file_name': file_name,
                                'section': section,
                                'similarity': similarity
                            }
                        )
                        all_chunks.append(chunk)
                    else:
                        print(f"   ⚠️  跳过低相似度结果: {similarity:.3f} < {self.similarity_threshold:.3f}")
                    
        except Exception as e:
            print(f"      ❌ 检索查询 '{user_query}' 时出错: {e}")
            return []
        
        # 按相似度排序
        all_chunks.sort(key=lambda x: x.score, reverse=True)
        
        # 如果没有找到符合阈值的结果，给出提示
        if not all_chunks:
            print(f"   ⚠️  没有找到相似度 >= {self.similarity_threshold:.2f} 的相关文档")
            print(f"   💡 建议: 尝试降低相似度阈值或重新表述问题")
        
        return all_chunks[:8]  # 最多返回8个片段
    
    def _judge_chunk_relevance(self, user_query: str, chunks: List[RetrievedChunk]) -> List[bool]:
        """
        判断每个检索到的chunk是否与问题相关
        
        Args:
            user_query: 用户问题
            chunks: 检索到的chunk列表
            
        Returns:
            布尔值列表，True表示相关，False表示不相关
        """
        if not chunks:
            return []
        
        try:
            # 构建判断提示词
            chunk_texts = []
            for i, chunk in enumerate(chunks):
                chunk_texts.append(f"文档片段{i+1}:\n{chunk.content[:500]}...")  # 限制长度避免过长
            
            chunks_text = "\n\n".join(chunk_texts)
            
            system_prompt = f"""你是一个文档相关性判断助手。请判断每个检索到的文档片段是否与用户问题相关。

用户问题：{user_query}

检索到的文档片段：
{chunks_text}

请对每个文档片段进行判断，判断标准：
1. 文档片段的内容是否直接或间接回答了用户问题
2. 文档片段是否包含与问题相关的关键信息
3. 文档片段是否有助于理解或解决用户问题

请以JSON格式输出结果，格式如下：
{{
    "judgments": [
        {{"chunk_index": 0, "is_relevant": true, "reason": "相关原因"}},
        {{"chunk_index": 1, "is_relevant": false, "reason": "不相关原因"}},
        ...
    ]
}}

只输出JSON，不要输出其他内容。"""
            
            # 构建消息
            messages = [{"role": "system", "content": system_prompt}]
            text = self.tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            
            # 生成判断结果
            inputs = self.tokenizer(text, return_tensors="pt")
            if torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=1000,
                    temperature=0.3,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            
            response = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
            
            # 解析JSON结果
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                judgments = result.get('judgments', [])
                relevance_list = [False] * len(chunks)
                for judgment in judgments:
                    idx = judgment.get('chunk_index', -1)
                    if 0 <= idx < len(chunks):
                        relevance_list[idx] = judgment.get('is_relevant', False)
                return relevance_list
            else:
                # 如果解析失败，默认全部相关
                print(f"   ⚠️ 无法解析相关性判断结果，默认所有chunk相关")
                return [True] * len(chunks)
                
        except Exception as e:
            print(f"   ⚠️ 判断chunk相关性时出错: {e}")
            # 出错时默认全部相关
            return [True] * len(chunks)
    
    def _judge_sufficiency_and_suggest_keywords(
        self, 
        user_query: str, 
        relevant_chunks: List[RetrievedChunk]
    ) -> Dict[str, Any]:
        """
        判断已检索的内容是否足以回答问题，如果不足则生成新的检索关键词
        
        Args:
            user_query: 用户问题
            relevant_chunks: 被判定为相关的chunk列表
            
        Returns:
            字典，包含：
            - is_sufficient: 是否足够回答问题
            - new_keywords: 如果不足，新的检索关键词列表
            - reasoning: 判断理由
        """
        try:
            # 构建已检索内容的摘要
            if relevant_chunks:
                chunks_summary = "\n\n".join([
                    f"文档片段{i+1} (来源: {chunk.filename}):\n{chunk.content[:300]}..."
                    for i, chunk in enumerate(relevant_chunks)
                ])
            else:
                chunks_summary = "暂无相关文档片段"
            
            system_prompt = f"""你是一个信息充分性判断助手。请判断已检索到的文档内容是否足以回答用户问题。

用户问题：{user_query}

已检索到的相关文档内容：
{chunks_summary}

请判断：
1. 已检索到的内容是否足以完整回答用户问题
2. 如果不足，需要补充哪些方面的信息
3. 如果不足，请提供2-3个新的检索关键词，用于进行第二轮检索

请以JSON格式输出结果，格式如下：
{{
    "is_sufficient": false,
    "reasoning": "判断理由",
    "new_keywords": ["关键词1", "关键词2", "关键词3"]
}}

如果内容已足够，is_sufficient应为true，new_keywords可以为空数组。
只输出JSON，不要输出其他内容。"""
            
            # 构建消息
            messages = [{"role": "system", "content": system_prompt}]
            text = self.tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            
            # 生成判断结果
            inputs = self.tokenizer(text, return_tensors="pt")
            if torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=500,
                    temperature=0.3,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )
            
            response = self.tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
            
            # 解析JSON结果
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "is_sufficient": result.get("is_sufficient", True),
                    "new_keywords": result.get("new_keywords", []),
                    "reasoning": result.get("reasoning", "")
                }
            else:
                # 如果解析失败，默认认为足够
                print(f"   ⚠️ 无法解析充分性判断结果，默认内容已足够")
                return {
                    "is_sufficient": True,
                    "new_keywords": [],
                    "reasoning": "无法解析判断结果，默认认为内容已足够"
                }
                
        except Exception as e:
            print(f"   ⚠️ 判断内容充分性时出错: {e}")
            # 出错时默认认为足够
            return {
                "is_sufficient": True,
                "new_keywords": [],
                "reasoning": f"判断过程出错: {str(e)}"
            }
    
    def _generate_response_with_context(
        self,
        user_query: str,
        chunks: List[RetrievedChunk],
        token_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        """生成带有上下文的回答"""
        try:
            # 构建上下文信息
            context_parts = []
            for i, chunk in enumerate(chunks):
                context_parts.append(
                    f"文档片段{i+1} (来源: {chunk.filename}):\n{chunk.content}"
                )
            context = "\n\n".join(context_parts)
            
            # 获取对话历史
            conversation_history = self.conversation_manager.get_history()
            
            # 构建消息列表
            messages = [
                {"role": "system", "content": f"你是一个有用的AI助手，请基于提供的文档内容回答用户的问题。\n\n文档内容：\n{context}"}
            ]
            
            # 添加历史对话（最近3轮）
            for msg in conversation_history[-3:]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # 添加当前用户查询
            messages.append({
                "role": "user", 
                "content": user_query
            })
            
            # 格式化输入
            text = self.tokenizer.apply_chat_template(
                messages, 
                tokenize=False, 
                add_generation_prompt=True
            )
            
            # 编码
            inputs = self.tokenizer(text, return_tensors="pt")
            
            # 确保输入在正确的设备上
            if torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}
            
            # 设置流式输出组件
            streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
            generation_kwargs = dict(inputs)
            generation_kwargs.update({
                "max_new_tokens": 3000,
                "temperature": 0.7,
                "do_sample": True,
                "pad_token_id": self.tokenizer.eos_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
                "streamer": streamer
            })
            response_chunks: List[str] = []

            def generate():
                """在后台线程中执行生成，驱动流式输出"""
                with torch.no_grad():
                    self.model.generate(**generation_kwargs)

            generation_thread = Thread(target=generate, daemon=True)
            generation_thread.start()

            show_console = token_callback is None
            if show_console:
                print("   💬 实时输出:", end=" ", flush=True)

            for new_text in streamer:
                if token_callback is not None:
                    token_callback(new_text)
                else:
                    print(new_text, end="", flush=True)
                response_chunks.append(new_text)

            generation_thread.join()
            if show_console:
                print()

            return "".join(response_chunks).strip()
            
        except Exception as e:
            print(f"      ❌ 生成回答时出错: {e}")
            return f"抱歉，生成回答时遇到错误: {str(e)}"
    
    def display_response(self, response: WorkflowResponse):
        """格式化显示响应结果"""
        print(f"\n🤖 AI回答:")
        print("=" * 60)
        print(response.llm_response)
        print("=" * 60)
        
        print(f"\n📄 检索到的文档片段 ({len(response.retrieved_chunks)} 个):")
        print("-" * 60)
        for i, chunk in enumerate(response.retrieved_chunks):
            print(f"\n文档 {i+1}:")
            print(f"   文件名: {chunk.filename}")
            print(f"   相似度: {chunk.score:.4f}")
            print(f"   内容预览:")
            content = chunk.content
            if len(content) > 200:
                content = content[:200] + "..."
            print(f"      {content}")
            print("-" * 40)
    
    def clear_conversation(self):
        """清空对话历史"""
        self.conversation_manager.clear()
        print("✅ 对话历史已清空")
    
    def get_conversation_summary(self) -> str:
        """获取对话摘要"""
        return f"对话消息数: {len(self.conversation_manager.conversations)}"
    
    def judge_answer(self, question_content: str, question_options: list, selected_answer: str, 
                    correct_answer: str = "", knowledge_point: str = "") -> dict:
        """
        使用大模型智能判题（基于RAG检索的独立判断）
        
        Args:
            question_content: 题目内容
            question_options: 选项列表
            selected_answer: 学生选择的答案
            correct_answer: 正确答案（仅用于后端验证，不传递给大模型）
            knowledge_point: 知识点
            
        Returns:
            判题结果字典
        """
        try:
            print(f"\n🤖 开始智能判题...")
            print(f"题目: {question_content[:100]}...")
            print(f"选择答案: {selected_answer}")
            
            # 步骤1: 使用题目内容进行RAG检索
            print("📚 步骤1: 基于题目内容进行RAG检索...")
            retrieved_chunks = self._retrieve_documents(question_content)
            print(f"   ✅ 检索到 {len(retrieved_chunks)} 个相关文档片段")
            
            # 构建判题提示词
            options_text = ""
            if question_options:
                for i, option in enumerate(question_options):
                    if isinstance(option, dict):
                        key = option.get('key', chr(65 + i))
                        text = option.get('text', '')
                    else:
                        key = chr(65 + i)
                        text = str(option)
                    options_text += f"{key}. {text}\n"
            
            # 构建检索到的文档上下文
            context_parts = []
            for i, chunk in enumerate(retrieved_chunks):
                context_parts.append(
                    f"参考资料{i+1} (来源: {chunk.filename}, 相似度: {chunk.score:.3f}):\n{chunk.content}"
                )
            context = "\n\n".join(context_parts)
            
            judge_prompt = f"""你是一个专业的操作系统课程判题助手。请基于提供的参考资料，仔细分析题目内容和选项，独立判断正确答案，然后评估学生选择的答案是否正确。

参考资料：
{context}

题目内容：{question_content}

选项：
{options_text}

学生的答案：{selected_answer}
{f"相关知识点：{knowledge_point}" if knowledge_point else ""}

请按照以下步骤进行分析：
1. 首先分析题目考查的知识点
2. 结合参考资料逐一分析每个选项的正确性
3. 确定正确答案
4. 评估学生答案的正确性
5. 提供详细的推理过程

请严格按照以下JSON格式输出判题结果：

{{
    "isCorrect": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "判题推理过程",
    "correctAnswer": "正确答案选项",
    "analysis": "详细分析",
    "knowledgePoint": "题目考查的知识点",
    "optionAnalysis": "各选项分析"
}}

要求：
1. isCorrect: 布尔值，表示学生答案是否正确
2. confidence: 0-1之间的数值，表示判题置信度
3. reasoning: 简洁的判题推理过程
4. correctAnswer: 你判断的正确答案选项（如A、B、C、D）
5. analysis: 对题目和答案的详细分析
6. knowledgePoint: 题目考查的主要知识点
7. optionAnalysis: 对各选项的详细分析

请直接输出JSON，不要其他内容："""

            # 使用LLM进行判题
            response = self.retrieval_suggester._generate_response_with_history(judge_prompt, "", [])
            
            # 添加调试输出
            print(f"🔍 LLM原始响应:")
            print(f"   {response[:200]}...")
            print(f"   响应长度: {len(response)}")
            
            # 解析响应
            result = self._parse_judge_response(response, selected_answer, correct_answer)
            
            print(f"判题结果: {result['isCorrect']} (置信度: {result['confidence']:.2f})")
            print(f"AI判断的正确答案: {result['correctAnswer']}")
            if correct_answer:
                print(f"预设正确答案: {correct_answer}")
                if result['correctAnswer'] == correct_answer:
                    print("✅ AI判断与预设答案一致")
                else:
                    print("⚠️ AI判断与预设答案不一致")
            
            return result
            
        except Exception as e:
            print(f"智能判题失败: {e}")
            # 降级到简单判断
            is_correct = selected_answer == correct_answer if correct_answer else False
            return {
                "isCorrect": is_correct,
                "confidence": 0.5,
                "reasoning": "智能判题失败，使用简单判断",
                "correctAnswer": correct_answer or "未知",
                "analysis": f"学生选择了{selected_answer}，{'正确' if is_correct else '错误'}。",
                "knowledgePoint": knowledge_point or "未知",
                "optionAnalysis": "分析失败"
            }
    
    def generate_explanation(self, question_content: str, question_options: list, selected_answer: str,
                           correct_answer: str = "", knowledge_point: str = "", is_correct: bool = False) -> str:
        """
        使用大模型生成题目解析（基于AI判断结果）
        
        Args:
            question_content: 题目内容
            question_options: 选项列表
            selected_answer: 学生选择的答案
            correct_answer: 正确答案（仅用于后端验证，不传递给大模型）
            knowledge_point: 知识点
            is_correct: 答案是否正确
            
        Returns:
            解析文本
        """
        try:
            print(f"\n📝 开始生成解析...")
            print(f"题目: {question_content[:100]}...")
            print(f"学生答案: {selected_answer} ({'正确' if is_correct else '错误'})")
            
            # 构建解析生成提示词
            options_text = ""
            if question_options:
                for i, option in enumerate(question_options):
                    if isinstance(option, dict):
                        key = option.get('key', chr(65 + i))
                        text = option.get('text', '')
                    else:
                        key = chr(65 + i)
                        text = str(option)
                    options_text += f"{key}. {text}\n"
            
            explanation_prompt = f"""你是一个专业的操作系统课程教学助手。请为学生生成详细的题目解析。

题目内容：{question_content}

选项：
{options_text}

学生的答案：{selected_answer}
{f"相关知识点：{knowledge_point}" if knowledge_point else ""}
学生答案：{'正确' if is_correct else '错误'}

请生成详细的解析，包括：
1. 题目考查的核心知识点
2. 各选项的详细分析（为什么对或错）
3. 正确答案的详细解释
4. 如果学生答错了，说明错误原因和正确思路
5. 相关的扩展知识点和学习建议

要求：
- 解析要详细、准确、易懂
- 使用中文回答
- 语言要专业但通俗易懂
- 适当举例说明
- 字数控制在300-500字
- 重点突出知识点的理解和应用

请直接输出解析内容，不要其他格式："""

            # 使用LLM生成解析
            explanation = self.retrieval_suggester._generate_response_with_history(explanation_prompt, "", [])
            
            # 清理和格式化解析
            explanation = self._clean_explanation(explanation)
            
            print(f"解析生成完成: {len(explanation)}字")
            
            return explanation
            
        except Exception as e:
            print(f"解析生成失败: {e}")
            # 降级到简单解析
            return self._generate_fallback_explanation(question_content, selected_answer, correct_answer, is_correct)
    
    def judge_text_answer(self, question_content: str, student_answer: str, 
                         question_type: str = "问答题", knowledge_point: str = "") -> dict:
        """
        使用大模型智能判题（基于RAG检索的填空题/问答题）
        
        Args:
            question_content: 题目内容
            student_answer: 学生答案
            question_type: 题目类型（填空题/问答题）
            knowledge_point: 知识点
            
        Returns:
            判题结果字典
        """
        try:
            print(f"\n🤖 开始文本智能判题...")
            print(f"题目: {question_content[:100]}...")
            print(f"学生答案: {student_answer[:50]}...")
            print(f"题目类型: {question_type}")
            
            # 步骤1: 使用题目内容进行RAG检索
            print("📚 步骤1: 基于题目内容进行RAG检索...")
            retrieved_chunks = self._retrieve_documents(question_content)
            print(f"   ✅ 检索到 {len(retrieved_chunks)} 个相关文档片段")
            
            # 构建检索到的文档上下文
            context_parts = []
            for i, chunk in enumerate(retrieved_chunks):
                context_parts.append(
                    f"参考资料{i+1} (来源: {chunk.filename}, 相似度: {chunk.score:.3f}):\n{chunk.content}"
                )
            context = "\n\n".join(context_parts)
            
            # 构建文本判题提示词
            judge_prompt = f"""你是一个专业的操作系统课程判题助手。请基于提供的参考资料，仔细分析题目内容和学生答案，独立判断学生答案的正确性。

参考资料：
{context}

题目内容：{question_content}

学生答案：{student_answer}

题目类型：{question_type}
{f"相关知识点：{knowledge_point}" if knowledge_point else ""}

请按照以下步骤进行分析：
1. 首先分析题目考查的知识点
2. 结合参考资料理解学生答案的核心内容
3. 判断学生答案是否正确（考虑表达方式的不同）
4. 评估答案的完整性和准确性
5. 提供详细的推理过程

请严格按照以下JSON格式输出判题结果：

{{
    "isCorrect": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "判题推理过程",
    "correctAnswer": "标准答案要点",
    "analysis": "详细分析",
    "knowledgePoint": "题目考查的知识点",
    "answerQuality": "答案质量评估",
    "improvementSuggestions": "改进建议"
}}

要求：
1. isCorrect: 布尔值，表示学生答案是否正确
2. confidence: 0-1之间的数值，表示判题置信度
3. reasoning: 简洁的判题推理过程
4. correctAnswer: 标准答案的要点总结
5. analysis: 对题目和答案的详细分析
6. knowledgePoint: 题目考查的主要知识点
7. answerQuality: 答案质量评估（优秀/良好/一般/较差）
8. improvementSuggestions: 改进建议

请直接输出JSON，不要其他内容："""

            # 使用LLM进行判题
            response = self.retrieval_suggester._generate_response_with_history(judge_prompt, "", [])
            
            # 添加调试输出
            print(f"🔍 LLM原始响应:")
            print(f"   {response[:200]}...")
            print(f"   响应长度: {len(response)}")
            
            # 解析响应
            result = self._parse_text_judge_response(response, student_answer)
            
            print(f"文本判题结果: {result['isCorrect']} (置信度: {result['confidence']:.2f})")
            print(f"答案质量: {result.get('answerQuality', '未知')}")
            
            return result
            
        except Exception as e:
            print(f"文本智能判题失败: {e}")
            # 降级到简单判断
            return {
                "isCorrect": True,  # 默认认为正确，避免打击学生积极性
                "confidence": 0.5,
                "reasoning": "文本判题失败，使用默认判断",
                "correctAnswer": "请参考教材相关内容",
                "analysis": f"学生回答了{len(student_answer)}字的内容。",
                "knowledgePoint": knowledge_point or "未知",
                "answerQuality": "一般",
                "improvementSuggestions": "建议参考教材相关内容完善答案"
            }
    
    def _parse_text_judge_response(self, response: str, student_answer: str) -> dict:
        """解析文本判题响应"""
        try:
            import re
            import json
            
            print(f"🔍 开始解析文本判题响应...")
            print(f"   原始响应长度: {len(response)}")
            
            # 清理响应文本
            cleaned_response = self.retrieval_suggester._clean_response_text(response)
            print(f"   清理后响应长度: {len(cleaned_response)}")
            print(f"   清理后响应前200字符: {cleaned_response}")
            
            # 尝试提取JSON
            json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_response, re.DOTALL)
            print(f"   找到 {len(json_matches)} 个JSON匹配")
            
            # 找到最完整的JSON
            best_json = None
            for i, json_str in enumerate(json_matches):
                print(f"   尝试解析JSON {i+1}: {json_str[:100]}...")
                try:
                    data = json.loads(json_str)
                    print(f"   JSON {i+1} 解析成功，包含字段: {list(data.keys())}")
                    # 检查是否包含必要字段
                    if all(key in data for key in ["isCorrect", "confidence", "reasoning"]):
                        best_json = data
                        print(f"   ✅ JSON {i+1} 包含所有必要字段，选择此JSON")
                        break
                    else:
                        print(f"   ❌ JSON {i+1} 缺少必要字段")
                except Exception as e:
                    print(f"   ❌ JSON {i+1} 解析失败: {e}")
                    continue
            
            if best_json:
                return {
                    "isCorrect": bool(best_json.get("isCorrect", True)),
                    "confidence": float(best_json.get("confidence", 0.5)),
                    "reasoning": best_json.get("reasoning", "解析成功"),
                    "correctAnswer": best_json.get("correctAnswer", "请参考教材相关内容"),
                    "analysis": best_json.get("analysis", "分析完成"),
                    "knowledgePoint": best_json.get("knowledgePoint", "未知"),
                    "answerQuality": best_json.get("answerQuality", "一般"),
                    "improvementSuggestions": best_json.get("improvementSuggestions", "建议参考教材相关内容")
                }
            else:
                # 如果解析失败，使用默认判断
                return {
                    "isCorrect": True,
                    "confidence": 0.5,
                    "reasoning": "JSON解析失败，使用默认判断",
                    "correctAnswer": "请参考教材相关内容",
                    "analysis": f"学生回答了{len(student_answer)}字的内容。",
                    "knowledgePoint": "未知",
                    "answerQuality": "一般",
                    "improvementSuggestions": "建议参考教材相关内容"
                }
                
        except Exception as e:
            print(f"解析文本判题响应时出错: {e}")
            return {
                "isCorrect": True,
                "confidence": 0.5,
                "reasoning": f"解析错误: {str(e)}",
                "correctAnswer": "请参考教材相关内容",
                "analysis": f"学生回答了{len(student_answer)}字的内容。",
                "knowledgePoint": "未知",
                "answerQuality": "一般",
                "improvementSuggestions": "建议参考教材相关内容"
            }
    
    def _parse_judge_response(self, response: str, selected_answer: str, correct_answer: str) -> dict:
        """解析判题响应"""
        try:
            import re
            import json
            
            # 清理响应文本
            cleaned_response = self.retrieval_suggester._clean_response_text(response)
            
            # 尝试提取JSON
            json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_response, re.DOTALL)
            
            # 找到最完整的JSON
            best_json = None
            for json_str in json_matches:
                try:
                    data = json.loads(json_str)
                    # 检查是否包含必要字段
                    if all(key in data for key in ["isCorrect", "confidence", "reasoning"]):
                        best_json = data
                        break
                except:
                    continue
            
            if best_json:
                return {
                    "isCorrect": bool(best_json.get("isCorrect", False)),
                    "confidence": float(best_json.get("confidence", 0.5)),
                    "reasoning": best_json.get("reasoning", "解析成功"),
                    "correctAnswer": best_json.get("correctAnswer", correct_answer or "未知"),
                    "analysis": best_json.get("analysis", "分析完成"),
                    "knowledgePoint": best_json.get("knowledgePoint", "未知"),
                    "optionAnalysis": best_json.get("optionAnalysis", "选项分析完成")
                }
            else:
                # 如果解析失败，使用简单判断
                is_correct = selected_answer == correct_answer if correct_answer else False
                return {
                    "isCorrect": is_correct,
                    "confidence": 0.5,
                    "reasoning": "JSON解析失败，使用简单判断",
                    "correctAnswer": correct_answer or "未知",
                    "analysis": f"学生选择了{selected_answer}，{'正确' if is_correct else '错误'}。",
                    "knowledgePoint": "未知",
                    "optionAnalysis": "分析失败"
                }
                
        except Exception as e:
            print(f"解析判题响应时出错: {e}")
            is_correct = selected_answer == correct_answer if correct_answer else False
            return {
                "isCorrect": is_correct,
                "confidence": 0.5,
                "reasoning": f"解析错误: {str(e)}",
                "correctAnswer": correct_answer or "未知",
                "analysis": f"学生选择了{selected_answer}，{'正确' if is_correct else '错误'}。",
                "knowledgePoint": "未知",
                "optionAnalysis": "分析失败"
            }
    
    def _clean_explanation(self, explanation: str) -> str:
        """清理和格式化解析文本"""
        import re
        
        # 移除多余的空白字符
        explanation = re.sub(r'\s+', ' ', explanation)
        
        # 移除特殊标记
        explanation = re.sub(r'解析[:：]\s*', '', explanation)
        explanation = re.sub(r'答案[:：]\s*', '', explanation)
        
        # 确保以句号结尾
        if explanation and not explanation.endswith(('。', '.', '！', '!')):
            explanation += '。'
        
        return explanation.strip()
    
    def _generate_fallback_explanation(self, question_content: str, selected_answer: str, 
                                      correct_answer: str, is_correct: bool) -> str:
        """生成降级解析"""
        if is_correct:
            return f"恭喜！您选择了{selected_answer}，这是正确答案。这道题考查了相关的操作系统知识点，您的理解是正确的。"
        else:
            return f"很遗憾，您选择了{selected_answer}，但正确答案是{correct_answer}。建议您重新学习相关知识点，加深理解。"

# ==================== 主函数 ====================

def main():
    """主函数 - 交互式RAG工作流系统"""
    print("🚀 简化RAG工作流系统启动中...")
    print("实现工作流程:")
    print("1. 用户给出要求")
    print("2. 直接使用原始查询进行向量检索")
    print("3. 把检索到的chunk内容和对话历史作为输入给LLM生成最终回答")
    print()
    
    # 配置参数
    config = {
        "llm_path": "../models--Qwen--Qwen3-8B/snapshots/9c925d64d72725edaf899c6cb9c377fd0709d9c5",
        "embedding_model_path": "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
        "db_path": "./vector_db"
    }
    
    try:
        # 初始化工作流
        workflow = SimpleRAGWorkflow(**config)
        
        print("\n✅ 系统启动完成!")
        print("\n使用说明:")
        print("  - 输入您的问题，系统将按照2步工作流处理")
        print("  - 输入 'clear' 清空对话历史")
        print("  - 输入 'summary' 查看对话摘要")
        print("  - 输入 'exit' 退出系统")
        
        last_response = None
        
        while True:
            try:
                user_input = input("\n💬 请输入您的问题: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'exit':
                    print("👋 感谢使用简化RAG工作流系统!")
                    break
                elif user_input.lower() == 'clear':
                    workflow.clear_conversation()
                    continue
                elif user_input.lower() == 'summary':
                    summary = workflow.get_conversation_summary()
                    print(f"📊 对话摘要: {summary}")
                    continue
                
                # 处理用户查询
                response = workflow.process_user_query(user_input)
                last_response = response
                
                # 显示结果
                workflow.display_response(response)
                
            except KeyboardInterrupt:
                print("\n\n👋 系统已中断，感谢使用!")
                break
            except Exception as e:
                print(f"\n❌ 处理过程中发生错误: {e}")
                print("请重试或输入 'exit' 退出系统")
                
    except Exception as e:
        print(f"\n❌ 系统初始化失败: {e}")
        print("请检查:")
        print("1. 模型路径是否正确")
        print("2. 依赖包是否完整安装")

if __name__ == "__main__":
    main()

