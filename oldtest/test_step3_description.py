#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试步骤3：验证预处理好的代码描述是否正确组装
"""

import sys
from simple_rag_workflow import CodeRAGWorkflow

def test_step3_description():
    """测试步骤3的描述组装"""
    
    print("="*60)
    print("🧪 测试步骤3：预处理好的代码描述组装")
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
    
    try:
        print("\n🔧 正在初始化...")
        workflow = CodeRAGWorkflow(**config)
        print("✅ 初始化成功!\n")
        
        # 测试查询
        test_query = "Linux 如何实现进程记账"
        print(f"📝 测试查询: {test_query}\n")
        
        # 处理查询
        response = workflow.process_code_query(test_query)
        
        # 检查结果
        print("\n" + "="*60)
        print("📊 步骤3结果检查")
        print("="*60)
        
        # 1. 检查是否有LLM响应
        print(f"\n1. LLM响应内容:")
        print(f"   - 长度: {len(response.llm_response)} 字符")
        print(f"   - 前500字符预览:")
        print(f"   {response.llm_response[:500]}...")
        
        # 2. 检查是否包含文件摘要
        has_file_summary = "相关文件摘要" in response.llm_response or "文件摘要" in response.llm_response
        print(f"\n2. 是否包含文件摘要: {'✅ 是' if has_file_summary else '❌ 否'}")
        
        # 3. 检查是否包含代码块描述
        has_chunk_description = "关键代码片段" in response.llm_response or "代码片段" in response.llm_response
        print(f"3. 是否包含代码块描述: {'✅ 是' if has_chunk_description else '❌ 否'}")
        
        # 4. 检查检索到的代码块是否包含description
        print(f"\n4. 检索到的代码块描述检查:")
        chunks_with_desc = 0
        chunks_without_desc = 0
        
        for i, chunk in enumerate(response.retrieved_chunks[:5], 1):
            description = chunk.metadata.get('description', '')
            if description:
                chunks_with_desc += 1
                print(f"   [{i}] ✅ {chunk.filename} - 有描述 ({len(description)} 字符)")
                print(f"       描述预览: {description[:100]}...")
            else:
                chunks_without_desc += 1
                print(f"   [{i}] ❌ {chunk.filename} - 无描述")
        
        print(f"\n   统计: {chunks_with_desc} 个有描述, {chunks_without_desc} 个无描述")
        
        # 5. 检查文件摘要是否被正确存储
        has_file_summaries = hasattr(workflow, '_retrieved_file_summaries')
        print(f"\n5. 文件摘要存储检查:")
        if has_file_summaries:
            file_summaries = workflow._retrieved_file_summaries
            print(f"   ✅ 已存储 {len(file_summaries)} 个文件摘要")
            for file_path, summary in list(file_summaries.items())[:2]:
                print(f"      - {os.path.basename(file_path)}: {len(summary)} 字符")
        else:
            print(f"   ❌ 未找到文件摘要存储")
        
        # 6. 完整响应内容展示
        print(f"\n" + "="*60)
        print("📄 完整响应内容（前1000字符）:")
        print("="*60)
        print(response.llm_response[:1000])
        if len(response.llm_response) > 1000:
            print(f"\n... (还有 {len(response.llm_response) - 1000} 字符)")
        
        # 总结
        print(f"\n" + "="*60)
        print("✅ 测试完成!")
        print("="*60)
        
        # 验证结果
        success = (
            len(response.llm_response) > 0 and
            has_file_summary and
            has_chunk_description and
            chunks_with_desc > 0
        )
        
        if success:
            print("\n🎉 所有检查通过！步骤3正确使用了预处理好的描述。")
        else:
            print("\n⚠️ 部分检查未通过，请检查代码。")
        
        return success
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import os
    success = test_step3_description()
    sys.exit(0 if success else 1)

