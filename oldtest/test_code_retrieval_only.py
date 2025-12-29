#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
源码检索功能测试（仅测试检索部分，不加载LLM）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simple_rag_workflow import CodeRAGEngine, CodeRetrievalSuggester, ConversationMessage
from datetime import datetime

def test_code_rag_engine():
    """测试 CodeRAGEngine"""
    print("=" * 60)
    print("测试: CodeRAGEngine 源码检索功能")
    print("=" * 60)
    
    try:
        # 初始化引擎
        print("\n1. 初始化 CodeRAGEngine...")
        engine = CodeRAGEngine(
            embedding_model_path="/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
            db_path="./test_code_vector_db",
            collection_name="source_code",
            similarity_threshold=0.25  # 降低阈值以便测试
        )
        print("   ✅ 初始化成功")
        
        # 检查是否有数据
        info = engine.get_collection_info()
        print(f"   📊 当前文档数: {info.get('document_count', 0)}")
        
        # 如果没有数据，添加测试数据
        if info.get('document_count', 0) == 0:
            print("\n2. 添加测试源码数据...")
            add_test_data(engine)
        else:
            print("\n2. 使用现有数据...")
        
        # 测试检索
        print("\n3. 测试源码检索...")
        test_queries = [
            "如何读取文件",
            "文件处理类",
            "JSON加载"
        ]
        
        for query in test_queries:
            print(f"\n   查询: '{query}'")
            results = engine.query(query, top_k=3)
            
            if results.get('contents'):
                print(f"   ✅ 找到 {len(results['contents'])} 个结果:")
                for i, (content, similarity, file_name, file_path) in enumerate(zip(
                    results['contents'],
                    results['similarities'],
                    results['file_names'],
                    results['file_paths']
                ), 1):
                    print(f"      [{i}] {file_name} (相似度: {similarity:.3f})")
                    print(f"          路径: {file_path}")
                    print(f"          内容: {content[:60]}...")
            else:
                print("   ⚠️ 未找到相关结果")
        
        print("\n✅ CodeRAGEngine 测试完成")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def add_test_data(engine: CodeRAGEngine):
    """添加测试数据"""
    sample_code_snippets = [
        """def read_file(filepath):
    \"\"\"读取文件内容\"\"\"
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()""",
        
        """class FileHandler:
    \"\"\"文件处理类\"\"\"
    def __init__(self, filename):
        self.filename = filename
    def read(self):
        return open(self.filename, 'r').read()""",
        
        """import json
def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)""",
        
        """def write_file(filepath, content):
    with open(filepath, 'w') as f:
        f.write(content)"""
    ]
    
    metadatas = [
        {'file_name': 'file_utils.py', 'file_path': '/src/utils/file_utils.py', 'line_range': '1-4', 'language': 'python'},
        {'file_name': 'file_handler.py', 'file_path': '/src/core/file_handler.py', 'line_range': '1-6', 'language': 'python'},
        {'file_name': 'json_loader.py', 'file_path': '/src/utils/json_loader.py', 'line_range': '1-4', 'language': 'python'},
        {'file_name': 'file_writer.py', 'file_path': '/src/utils/file_writer.py', 'line_range': '1-3', 'language': 'python'}
    ]
    
    ids = [f"test_{i}" for i in range(len(sample_code_snippets))]
    
    engine.add_documents(sample_code_snippets, metadatas, ids)
    print(f"   ✅ 添加了 {len(sample_code_snippets)} 个代码片段")

def test_retrieval_suggestion_structure():
    """测试检索建议的数据结构（不加载LLM）"""
    print("\n" + "=" * 60)
    print("测试: RetrievalSuggestion 数据结构")
    print("=" * 60)
    
    try:
        from simple_rag_workflow import RetrievalSuggestion
        
        # 创建示例建议
        suggestion = RetrievalSuggestion(
            original_query="如何读取文件",
            intent="函数查找",
            confidence=0.85,
            search_keywords=["文件", "读取", "open"],
            suggested_queries=[
                "文件读取函数实现",
                "Python open函数使用",
                "读取文件的方法"
            ],
            reasoning="用户想查找文件读取相关的代码"
        )
        
        print("\n✅ RetrievalSuggestion 创建成功")
        print(f"   - 原始查询: {suggestion.original_query}")
        print(f"   - 意图: {suggestion.intent}")
        print(f"   - 置信度: {suggestion.confidence}")
        print(f"   - 关键词: {suggestion.search_keywords}")
        print(f"   - 建议查询数: {len(suggestion.suggested_queries)}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("源码检索功能测试（轻量级）")
    print("=" * 60)
    
    results = []
    
    # 测试数据结构
    results.append(("数据结构测试", test_retrieval_suggestion_structure()))
    
    # 测试检索引擎
    results.append(("CodeRAGEngine 测试", test_code_rag_engine()))
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{status}: {test_name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        print("\n说明:")
        print("- 源码检索引擎工作正常")
        print("- 数据结构正确")
        print("- 如需测试完整工作流（包括LLM），请运行 test_code_workflow.py")
    else:
        print("\n⚠️ 部分测试失败")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
