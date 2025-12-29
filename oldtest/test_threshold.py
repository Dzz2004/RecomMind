#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
相似度阈值测试脚本
演示不同阈值下的检索效果
"""

from simple_rag_workflow import SimpleRAGWorkflow

def test_similarity_thresholds():
    """测试不同相似度阈值的效果"""
    
    print("🧪 相似度阈值测试")
    print("="*60)
    
    # 配置参数
    config = {
        "llm_path": "../models--Qwen--Qwen3-8B/snapshots/9c925d64d72725edaf899c6cb9c377fd0709d9c5",
        "embedding_model_path": "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
        "db_path": "./vector_db"
    }
    
    # 测试不同的阈值
    thresholds = [0.1, 0.3, 0.5, 0.7, 0.9]
    test_query = "什么是机器学习？"
    
    print(f"测试查询: {test_query}")
    print("="*60)
    
    for threshold in thresholds:
        print(f"\n🔍 测试阈值: {threshold:.1f}")
        print("-" * 40)
        
        try:
            # 使用当前阈值初始化工作流
            config["similarity_threshold"] = threshold
            workflow = SimpleRAGWorkflow(**config)
            
            # 执行检索
            chunks = workflow._retrieve_documents(test_query)
            
            print(f"   检索结果数量: {len(chunks)}")
            if chunks:
                print(f"   最高相似度: {chunks[0].score:.3f}")
                print(f"   最低相似度: {chunks[-1].score:.3f}")
            else:
                print("   ⚠️  没有找到符合阈值的结果")
                
        except Exception as e:
            print(f"   ❌ 测试失败: {e}")
    
    print("\n" + "="*60)
    print("✅ 阈值测试完成!")
    print("\n💡 建议:")
    print("  - 阈值 0.1-0.3: 宽松，返回更多结果但可能包含不相关内容")
    print("  - 阈值 0.3-0.5: 平衡，推荐用于大多数场景")
    print("  - 阈值 0.5-0.7: 严格，只返回高相关度结果")
    print("  - 阈值 0.7-0.9: 非常严格，可能经常返回空结果")

if __name__ == "__main__":
    test_similarity_thresholds()
