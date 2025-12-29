#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 dzz 检索系统集成（仅测试检索部分，不加载LLM）
"""

import sys
import os

# 测试检索逻辑（不加载LLM）
def test_retrieval_only():
    """仅测试检索逻辑，不加载LLM"""
    
    print("="*60)
    print("🧪 测试 dzz 检索系统（仅检索部分）")
    print("="*60)
    
    try:
        # 导入必要的模块
        from simple_rag_workflow import CodeRetrievalSuggester, RetrievalSuggestion, ConversationMessage
        from datetime import datetime
        import chromadb
        from chromadb.utils import embedding_functions
        import torch
        
        # 测试 dzz 检索系统初始化
        print("\n1. 测试 dzz 检索系统初始化...")
        chroma_md_path = "./dzz_retrieval/chroma_md"
        embedding_model_path = "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/"
        
        client = chromadb.PersistentClient(path=chroma_md_path)
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model_path,
            device="cuda" if torch.cuda.is_available() else "cpu",
            normalize_embeddings=True
        )
        
        collection = client.get_collection(
            name="kernel_file_summaries",
            embedding_function=embedding_fn
        )
        
        file_count = collection.count()
        print(f"   ✅ dzz 文件摘要集合初始化成功，总文件数: {file_count}")
        
        # 测试文件级检索
        print("\n2. 测试文件级检索...")
        test_query = "Linux 如何实现进程记账"
        
        md_results = collection.query(
            query_texts=[test_query],
            n_results=3,
            include=["documents", "metadatas", "distances"]
        )
        
        candidate_source_files = []
        for doc, meta, dist in zip(
            md_results['documents'][0],
            md_results['metadatas'][0],
            md_results['distances'][0]
        ):
            source_file = meta.get('source_file', '')
            if source_file:
                source_file = os.path.join("kernel", source_file) if not source_file.startswith("kernel/") else source_file
                candidate_source_files.append(source_file)
                similarity = 1 - dist
                print(f"   ✅ 文件: {os.path.basename(source_file)} (相似度: {similarity:.4f})")
        
        if not candidate_source_files:
            print("   ❌ 未找到相关文件")
            return False
        
        # 测试代码块级检索
        print(f"\n3. 测试代码块级语义排序...")
        sys.path.insert(0, './dzz_retrieval')
        from rank_chunks_by_semantic import rank_chunks_by_description
        
        all_top_chunks = rank_chunks_by_description(test_query, candidate_source_files, top_k=5)
        
        if not all_top_chunks:
            print("   ❌ 未找到相关代码块")
            return False
        
        print(f"   ✅ 找到 {len(all_top_chunks)} 个相关代码块")
        
        # 显示前3个代码块
        print(f"\n4. 显示前3个代码块详情:")
        for i, chunk in enumerate(all_top_chunks[:3], 1):
            print(f"\n   [{i}] 相似度: {chunk.get('_score', 0):.4f}")
            file_path = chunk.get('file_path', 'unknown').replace('\\', '/')
            print(f"       文件: {file_path}")
            print(f"       行号: {chunk.get('start_line', 'N/A')} - {chunk.get('end_line', 'N/A')}")
            print(f"       函数: {chunk.get('function_name', 'N/A')}")
            print(f"       描述: {chunk.get('description', 'N/A')[:100]}...")
        
        print("\n" + "="*60)
        print("✅ 检索测试完成！")
        print("="*60)
        print("\n💡 说明:")
        print("  - 文件级检索：✅ 正常工作")
        print("  - 代码块级检索：✅ 正常工作")
        print("  - 两阶段检索逻辑：✅ 集成成功")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_retrieval_only()
    sys.exit(0 if success else 1)

