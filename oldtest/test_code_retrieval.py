#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
源码检索工作流测试脚本
测试 CodeRAGWorkflow 的完整功能
"""

import sys
from simple_rag_workflow import CodeRAGWorkflow

def test_code_retrieval_workflow():
    """测试源码检索工作流"""
    
    print("="*60)
    print("🧪 源码检索工作流测试")
    print("="*60)
    
    # 配置参数
    config = {
        "llm_path": "../models--Qwen--Qwen3-8B/snapshots/9c925d64d72725edaf899c6cb9c377fd0709d9c5",
        "embedding_model_path": "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
        "db_path": "./vector_db",
        "similarity_threshold": 0.3
    }
    
    print("\n📋 配置信息:")
    print(f"  - LLM路径: {config['llm_path']}")
    print(f"  - 嵌入模型路径: {config['embedding_model_path']}")
    print(f"  - 向量数据库路径: {config['db_path']}")
    print(f"  - 相似度阈值: {config['similarity_threshold']}")
    
    try:
        # 初始化源码检索工作流
        print("\n" + "="*60)
        print("🔧 正在初始化源码检索工作流...")
        print("="*60)
        
        workflow = CodeRAGWorkflow(**config)
        
        print("\n" + "="*60)
        print("✅ 初始化成功!")
        print("="*60)
        
        # 检查代码数据库是否有数据
        code_engine_info = workflow.code_rag_engine.get_collection_info()
        code_count = code_engine_info.get('document_count', 0)
        print(f"\n📊 代码数据库信息:")
        print(f"  - 集合名称: {code_engine_info.get('collection_name', 'source_code')}")
        print(f"  - 文档数量: {code_count}")
        
        # 如果没有数据，提示用户
        if code_count == 0:
            print("\n⚠️  警告: 代码数据库为空，无法进行检索测试")
            print("💡 请先准备代码数据并加载到向量数据库中")
            print("   数据库路径: ./vector_db")
            print("   集合名称: source_code")
            return False
        else:
            print("✅ 使用现有代码数据")
        
        # 测试查询列表（先测试一个简单的查询）
        test_queries = [
            "查找文件系统相关的代码"
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
                
                # 显示检索到的代码片段
                if response.retrieved_chunks:
                    print(f"\n💻 检索到的代码片段:")
                    for j, chunk in enumerate(response.retrieved_chunks[:3], 1):
                        print(f"\n  片段 {j}:")
                        print(f"    - 文件名: {chunk.filename}")
                        print(f"    - 文件路径: {chunk.metadata.get('file_path', 'N/A')}")
                        print(f"    - 行号范围: {chunk.metadata.get('line_range', 'N/A')}")
                        print(f"    - 语言: {chunk.metadata.get('language', 'N/A')}")
                        print(f"    - 相似度: {chunk.score:.4f}")
                        print(f"    - 内容预览: {chunk.content[:100]}...")
                else:
                    print("\n⚠️  未检索到相关代码片段")
                
                # 显示LLM生成的描述（前200字符）
                if response.llm_response:
                    print(f"\n🤖 LLM生成的代码描述（预览）:")
                    print(f"  {response.llm_response[:200]}...")
                
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
        
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_single_query():
    """测试单个查询（交互式）"""
    
    print("="*60)
    print("🧪 源码检索工作流 - 单查询测试")
    print("="*60)
    
    # 配置参数
    config = {
        "llm_path": "../models--Qwen--Qwen3-8B/snapshots/9c925d64d72725edaf899c6cb9c377fd0709d9c5",
        "embedding_model_path": "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
        "db_path": "./vector_db",
        "similarity_threshold": 0.3
    }
    
    try:
        # 初始化工作流
        print("\n🔧 正在初始化源码检索工作流...")
        workflow = CodeRAGWorkflow(**config)
        print("✅ 初始化成功!\n")
        
        # 检查代码数据库是否有数据
        code_engine_info = workflow.code_rag_engine.get_collection_info()
        code_count = code_engine_info.get('document_count', 0)
        print(f"📊 代码数据库文档数量: {code_count}")
        
        # 如果没有数据，提示用户
        if code_count == 0:
            print("\n⚠️  警告: 代码数据库为空，无法进行检索测试")
            print("💡 请先准备代码数据并加载到向量数据库中")
            print("   数据库路径: ./vector_db")
            print("   集合名称: source_code")
            return False
        else:
            print("✅ 使用现有代码数据\n")
        
        # 交互式查询
        while True:
            try:
                user_input = input("💬 请输入您的源码查询（输入 'exit' 退出）: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'exit':
                    print("👋 退出测试")
                    break
                
                if user_input.lower() == 'clear':
                    workflow.clear_conversation()
                    print("✅ 对话历史已清空\n")
                    continue
                
                # 处理查询
                response = workflow.process_code_query(user_input)
                
                # 显示完整结果
                workflow.display_response(response)
                
                print("\n" + "="*60 + "\n")
                
            except KeyboardInterrupt:
                print("\n\n👋 退出测试")
                break
            except Exception as e:
                print(f"\n❌ 处理查询时出错: {e}")
                import traceback
                traceback.print_exc()
                print()
        
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="源码检索工作流测试脚本")
    parser.add_argument(
        "--mode",
        choices=["batch", "interactive"],
        default="batch",
        help="测试模式: batch(批量测试) 或 interactive(交互式测试)"
    )
    
    args = parser.parse_args()
    
    if args.mode == "interactive":
        success = test_single_query()
    else:
        success = test_code_retrieval_workflow()
    
    sys.exit(0 if success else 1)

