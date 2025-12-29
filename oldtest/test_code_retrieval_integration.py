#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
源码检索功能集成测试
演示如何使用 CodeRAGWorkflow 进行源码检索
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simple_rag_workflow import (
    CodeRAGWorkflow, 
    CodeRAGEngine, 
    CodeRetrievalSuggester,
    ConversationMessage,
    RetrievedChunk
)
from datetime import datetime

def test_code_rag_engine_with_sample_data():
    """测试 CodeRAGEngine 的基本功能（使用示例数据）"""
    print("=" * 60)
    print("测试: CodeRAGEngine 基本功能")
    print("=" * 60)
    
    try:
        # 初始化引擎（使用临时数据库路径）
        print("\n1. 初始化 CodeRAGEngine...")
        engine = CodeRAGEngine(
            embedding_model_path="/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
            db_path="./test_code_vector_db",
            collection_name="test_source_code",
            similarity_threshold=0.3
        )
        print("   ✅ CodeRAGEngine 初始化成功")
        
        # 添加示例源码数据
        print("\n2. 添加示例源码数据...")
        sample_code_snippets = [
            "def read_file(filepath):\n    with open(filepath, 'r') as f:\n        return f.read()",
            "class FileHandler:\n    def __init__(self, filename):\n        self.filename = filename\n    def read(self):\n        return open(self.filename).read()",
            "import json\ndef load_json(filepath):\n    with open(filepath, 'r') as f:\n        return json.load(f)",
            "def write_file(filepath, content):\n    with open(filepath, 'w') as f:\n        f.write(content)",
            "class DataProcessor:\n    def process(self, data):\n        return data.upper()"
        ]
        
        metadatas = [
            {
                'file_name': 'file_utils.py',
                'file_path': '/src/utils/file_utils.py',
                'line_range': '1-3',
                'language': 'python'
            },
            {
                'file_name': 'file_handler.py',
                'file_path': '/src/core/file_handler.py',
                'line_range': '1-5',
                'language': 'python'
            },
            {
                'file_name': 'json_loader.py',
                'file_path': '/src/utils/json_loader.py',
                'line_range': '1-4',
                'language': 'python'
            },
            {
                'file_name': 'file_writer.py',
                'file_path': '/src/utils/file_writer.py',
                'line_range': '1-3',
                'language': 'python'
            },
            {
                'file_name': 'data_processor.py',
                'file_path': '/src/core/data_processor.py',
                'line_range': '1-3',
                'language': 'python'
            }
        ]
        
        ids = [f"code_snippet_{i}" for i in range(len(sample_code_snippets))]
        
        engine.add_documents(sample_code_snippets, metadatas, ids)
        print(f"   ✅ 添加了 {len(sample_code_snippets)} 个代码片段")
        
        # 测试搜索
        print("\n3. 测试源码搜索...")
        test_queries = [
            "如何读取文件",
            "文件处理类",
            "JSON加载函数"
        ]
        
        for query in test_queries:
            print(f"\n   查询: '{query}'")
            results = engine.query(query, top_k=2)
            
            if results.get('contents'):
                print(f"   找到 {len(results['contents'])} 个结果:")
                for i, (content, similarity, file_name) in enumerate(zip(
                    results['contents'],
                    results['similarities'],
                    results['file_names']
                )):
                    print(f"      [{i+1}] {file_name} (相似度: {similarity:.3f})")
                    print(f"          {content[:50]}...")
            else:
                print("   未找到相关结果")
        
        print("\n   ✅ 源码搜索测试完成")
        return True
        
    except Exception as e:
        print(f"\n   ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_retrieval_suggestion_structure():
    """测试检索建议的数据结构"""
    print("\n" + "=" * 60)
    print("测试: RetrievalSuggestion 数据结构")
    print("=" * 60)
    
    try:
        from simple_rag_workflow import RetrievalSuggestion
        
        # 创建示例检索建议
        suggestion = RetrievalSuggestion(
            original_query="如何读取文件",
            intent="函数查找",
            confidence=0.85,
            search_keywords=["文件", "读取", "open", "read"],
            suggested_queries=[
                "文件读取函数实现",
                "Python open函数使用",
                "读取文件的方法"
            ],
            reasoning="用户想查找文件读取相关的代码，生成了多个角度的查询建议"
        )
        
        print("\n✅ RetrievalSuggestion 创建成功")
        print(f"   - 原始查询: {suggestion.original_query}")
        print(f"   - 意图: {suggestion.intent}")
        print(f"   - 置信度: {suggestion.confidence}")
        print(f"   - 关键词: {suggestion.search_keywords}")
        print(f"   - 建议查询数: {len(suggestion.suggested_queries)}")
        print(f"   - 推理: {suggestion.reasoning[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_workflow_response_structure():
    """测试工作流响应的数据结构"""
    print("\n" + "=" * 60)
    print("测试: WorkflowResponse 数据结构")
    print("=" * 60)
    
    try:
        from simple_rag_workflow import WorkflowResponse, RetrievalSuggestion, RetrievedChunk
        
        # 创建示例检索建议
        suggestion = RetrievalSuggestion(
            original_query="如何读取文件",
            intent="函数查找",
            confidence=0.85,
            search_keywords=["文件", "读取"],
            suggested_queries=["文件读取函数"],
            reasoning="测试"
        )
        
        # 创建示例代码片段
        chunks = [
            RetrievedChunk(
                content="def read_file(filepath):\n    with open(filepath, 'r') as f:\n        return f.read()",
                source="/src/utils/file_utils.py",
                filename="file_utils.py",
                relative_path="/src/utils/file_utils.py",
                extension=".py",
                score=0.92,
                metadata={
                    'file_name': 'file_utils.py',
                    'file_path': '/src/utils/file_utils.py',
                    'line_range': '1-3',
                    'language': 'python'
                }
            )
        ]
        
        # 创建响应
        response = WorkflowResponse(
            user_query="如何读取文件",
            retrieval_suggestion=suggestion,
            retrieved_chunks=chunks,
            llm_response="这是一个文件读取函数，使用Python的open函数打开文件并读取内容。",
            conversation_history=[],
            timestamp=datetime.now()
        )
        
        print("\n✅ WorkflowResponse 创建成功")
        print(f"   - 用户查询: {response.user_query}")
        print(f"   - 检索建议: {response.retrieval_suggestion.intent}")
        print(f"   - 检索到的代码片段数: {len(response.retrieved_chunks)}")
        print(f"   - LLM响应长度: {len(response.llm_response)} 字符")
        
        # 显示代码片段信息
        if response.retrieved_chunks:
            chunk = response.retrieved_chunks[0]
            print(f"\n   代码片段信息:")
            print(f"     - 文件名: {chunk.filename}")
            print(f"     - 文件路径: {chunk.metadata.get('file_path')}")
            print(f"     - 行号: {chunk.metadata.get('line_range')}")
            print(f"     - 语言: {chunk.metadata.get('language')}")
            print(f"     - 相似度: {chunk.score:.3f}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def demonstrate_usage():
    """演示如何使用源码检索功能"""
    print("\n" + "=" * 60)
    print("使用示例")
    print("=" * 60)
    
    print("""
# 1. 初始化源码检索工作流
from simple_rag_workflow import CodeRAGWorkflow

workflow = CodeRAGWorkflow(
    llm_path="path/to/your/llm/model",
    embedding_model_path="path/to/embedding/model",
    db_path="./vector_db",
    similarity_threshold=0.3
)

# 2. 处理源码查询
response = workflow.process_code_query("如何实现文件读取功能？")

# 3. 查看结果
workflow.display_response(response)

# 4. 访问响应数据
print(f"检索到的代码片段数: {len(response.retrieved_chunks)}")
for chunk in response.retrieved_chunks:
    print(f"文件: {chunk.filename}")
    print(f"路径: {chunk.metadata.get('file_path')}")
    print(f"行号: {chunk.metadata.get('line_range')}")
    print(f"代码: {chunk.content[:100]}...")
    print(f"相似度: {chunk.score:.3f}")
""")

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("源码检索功能集成测试")
    print("=" * 60)
    
    results = []
    
    # 运行测试
    print("\n注意: 以下测试需要实际的模型文件，部分测试可能会跳过模型加载")
    print("=" * 60)
    
    # 测试数据结构
    results.append(("RetrievalSuggestion 结构", test_retrieval_suggestion_structure()))
    results.append(("WorkflowResponse 结构", test_workflow_response_structure()))
    
    # 测试 CodeRAGEngine（需要嵌入模型）
    print("\n提示: 以下测试需要加载嵌入模型，可能需要一些时间...")
    try:
        results.append(("CodeRAGEngine 功能", test_code_rag_engine_with_sample_data()))
    except Exception as e:
        print(f"\n⚠️ CodeRAGEngine 测试跳过（需要模型文件）: {e}")
        results.append(("CodeRAGEngine 功能", False))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {test_name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    # 显示使用示例
    demonstrate_usage()
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️ 部分测试失败或跳过")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
