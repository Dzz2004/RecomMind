#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 dzz 检索系统集成到 CodeRAGWorkflow
验证两阶段检索逻辑是否正常工作
"""

import sys
import os
from simple_rag_workflow import CodeRAGWorkflow

def test_dzz_retrieval_integration():
    """测试 dzz 检索系统集成"""
    
    print("="*60)
    print("🧪 测试 dzz 检索系统集成")
    print("="*60)
    
    # 配置参数
    config = {
        "llm_path": "../models--Qwen--Qwen3-8B/snapshots/9c925d64d72725edaf899c6cb9c377fd0709d9c5",
        "embedding_model_path": "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
        "db_path": "./vector_db",
        "similarity_threshold": 0.3,
        "chroma_md_path": "./dzz_retrieval/chroma_md",
        "top_files": 3,
        "top_chunks": 5
    }
    
    print("\n📋 配置信息:")
    print(f"  - LLM路径: {config['llm_path']}")
    print(f"  - 嵌入模型路径: {config['embedding_model_path']}")
    print(f"  - 向量数据库路径: {config['db_path']}")
    print(f"  - dzz ChromaDB路径: {config['chroma_md_path']}")
    print(f"  - 文件级检索数量: {config['top_files']}")
    print(f"  - 代码块级检索数量: {config['top_chunks']}")
    
    try:
        # 初始化源码检索工作流
        print("\n" + "="*60)
        print("🔧 正在初始化源码检索工作流...")
        print("="*60)
        
        workflow = CodeRAGWorkflow(**config)
        
        print("\n" + "="*60)
        print("✅ 初始化成功!")
        print("="*60)
        
        # 测试查询列表
        test_queries = [
            "Linux 如何实现进程记账",
            "文件系统相关的代码",
            "内存管理函数的实现",
            "进程调度相关的代码"
        ]
        
        print("\n" + "="*60)
        print("📝 开始测试查询...")
        print("="*60)
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n{'='*60}")
            print(f"测试 {i}/{len(test_queries)}: {query}")
            print(f"{'='*60}")
            
            try:
                # 处理源码查询
                response = workflow.process_code_query(query)
                
                # 显示结果摘要
                print(f"\n📊 结果摘要:")
                print(f"  - 检索建议数量: {len(response.retrieval_suggestion.suggested_queries) if response.retrieval_suggestion else 0}")
                print(f"  - 检索到的代码片段数: {len(response.retrieved_chunks)}")
                print(f"  - 代码描述长度: {len(response.llm_response)} 字符")
                
                # 显示检索建议详情
                if response.retrieval_suggestion:
                    print(f"\n🔍 检索建议详情:")
                    print(f"  - 意图: {response.retrieval_suggestion.intent}")
                    print(f"  - 置信度: {response.retrieval_suggestion.confidence:.2f}")
                    print(f"  - 关键词: {', '.join(response.retrieval_suggestion.search_keywords[:5])}")
                    print(f"  - 建议查询: {response.retrieval_suggestion.suggested_queries[:3]}")
                
                # 显示检索到的代码片段详情
                if response.retrieved_chunks:
                    print(f"\n💻 检索到的代码片段详情:")
                    for j, chunk in enumerate(response.retrieved_chunks[:5], 1):
                        print(f"\n  片段 {j}:")
                        print(f"    - 文件名: {chunk.filename}")
                        print(f"    - 文件路径: {chunk.metadata.get('file_path', 'N/A')}")
                        print(f"    - 行号范围: {chunk.metadata.get('line_range', 'N/A')}")
                        print(f"    - 函数名: {chunk.metadata.get('function_name', 'N/A')}")
                        print(f"    - 相似度: {chunk.score:.4f}")
                        print(f"    - 描述: {chunk.metadata.get('description', 'N/A')[:100]}...")
                        print(f"    - 内容预览: {chunk.content[:150] if chunk.content else 'N/A'}...")
                else:
                    print("\n⚠️  未检索到相关代码片段")
                
                # 显示LLM生成的描述（前300字符）
                if response.llm_response:
                    print(f"\n🤖 LLM生成的代码描述（预览）:")
                    print(f"  {response.llm_response[:300]}...")
                
                print(f"\n✅ 测试 {i} 完成")
                
            except Exception as e:
                print(f"\n❌ 测试 {i} 失败: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print("\n" + "="*60)
        print("✅ 所有测试完成!")
        print("="*60)
        
        # 测试对话历史
        print("\n📝 测试对话历史功能...")
        history = workflow.conversation_manager.get_history()
        print(f"  - 对话消息数: {len(history)}")
        if history:
            print(f"  - 最后一条消息: {history[-1].role} - {history[-1].content[:50]}...")
        
        # 清空对话历史
        print("\n🧹 清空对话历史...")
        workflow.clear_conversation()
        print("  ✅ 对话历史已清空")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_single_query():
    """测试单个查询（快速测试）"""
    
    print("="*60)
    print("🧪 快速测试 - 单个查询")
    print("="*60)
    
    config = {
        "llm_path": "../models--Qwen--Qwen3-8B/snapshots/9c925d64d72725edaf899c6cb9c377fd0709d9c5",
        "embedding_model_path": "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
        "db_path": "./vector_db",
        "similarity_threshold": 0.3,
        "chroma_md_path": "./dzz_retrieval/chroma_md",
        "top_files": 3,
        "top_chunks": 5
    }
    
    try:
        print("\n🔧 正在初始化...")
        workflow = CodeRAGWorkflow(**config)
        print("✅ 初始化成功!\n")
        
        # 测试一个查询
        test_query = "Linux 如何实现进程记账"
        print(f"📝 测试查询: {test_query}\n")
        
        response = workflow.process_code_query(test_query)
        
        # 显示结果
        print(f"\n{'='*60}")
        print("📊 检索结果:")
        print(f"{'='*60}")
        print(f"检索到的代码片段数: {len(response.retrieved_chunks)}")
        
        if response.retrieved_chunks:
            print(f"\n前3个代码片段:")
            for i, chunk in enumerate(response.retrieved_chunks[:3], 1):
                print(f"\n  [{i}] {chunk.filename}")
                print(f"      路径: {chunk.metadata.get('file_path', 'N/A')}")
                print(f"      行号: {chunk.metadata.get('line_range', 'N/A')}")
                print(f"      函数: {chunk.metadata.get('function_name', 'N/A')}")
                print(f"      相似度: {chunk.score:.4f}")
                print(f"      描述: {chunk.metadata.get('description', 'N/A')[:80]}...")
        
        print(f"\n{'='*60}")
        print("✅ 测试完成!")
        print(f"{'='*60}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="测试 dzz 检索系统集成")
    parser.add_argument(
        "--mode",
        choices=["full", "quick"],
        default="quick",
        help="测试模式: full(完整测试) 或 quick(快速测试)"
    )
    
    args = parser.parse_args()
    
    if args.mode == "full":
        success = test_dzz_retrieval_integration()
    else:
        success = test_single_query()
    
    sys.exit(0 if success else 1)

