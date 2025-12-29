#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成简化RAG工作流的Qwen3模型演示脚本
不依赖langchain，基于Transformers实现完整的RAG功能
"""

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from simple_rag_workflow import SimpleRAGWorkflow

def main():
    """演示如何使用集成RAG工作流的Qwen3模型"""
    
    print("🚀 集成RAG工作流的Qwen3模型演示")
    print("="*60)
    print("功能特点:")
    print("1. 不依赖langchain，纯Transformers实现")
    print("2. 支持向量检索增强生成(RAG)")
    print("3. 多轮对话管理")
    print("4. 基于文档内容的智能问答")
    print("="*60)
    
    # 配置参数
    config = {
        "llm_path": "../models--Qwen--Qwen3-8B/snapshots/9c925d64d72725edaf899c6cb9c377fd0709d9c5",
        "embedding_model_path": "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
        "db_path": "./vector_db",
        "similarity_threshold": 0.0  # 相似度阈值，低于此值的结果将被过滤
    }
    
    try:
        # 初始化RAG工作流
        print("\n🔧 正在初始化RAG工作流...")
        workflow = SimpleRAGWorkflow(**config)
        
        print("\n✅ 系统启动完成!")
        print("\n使用说明:")
        print("  - 输入您的问题，系统将进行向量检索并生成回答")
        print("  - 输入 'clear' 清空对话历史")
        print("  - 输入 'summary' 查看对话摘要")
        print("  - 输入 'demo' 运行演示对话")
        print("  - 输入 'threshold <数值>' 调整相似度阈值 (当前: {:.2f})".format(config["similarity_threshold"]))
        print("  - 输入 'exit' 退出系统")
        
        while True:
            try:
                user_input = input("\n💬 请输入您的问题: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'exit':
                    print("👋 感谢使用RAG工作流系统!")
                    break
                elif user_input.lower() == 'clear':
                    workflow.clear_conversation()
                    continue
                elif user_input.lower() == 'summary':
                    summary = workflow.get_conversation_summary()
                    print(f"📊 对话摘要: {summary}")
                    continue
                elif user_input.lower() == 'demo':
                    run_demo(workflow)
                    continue
                elif user_input.lower().startswith('threshold'):
                    try:
                        # 解析阈值命令
                        parts = user_input.split()
                        if len(parts) == 2:
                            new_threshold = float(parts[1])
                            if 0.0 <= new_threshold <= 1.0:
                                workflow.similarity_threshold = new_threshold
                                workflow.rag_engine.similarity_threshold = new_threshold
                                config["similarity_threshold"] = new_threshold
                                print(f"✅ 相似度阈值已更新为: {new_threshold:.2f}")
                            else:
                                print("❌ 阈值必须在 0.0 到 1.0 之间")
                        else:
                            print("❌ 用法: threshold <数值> (例如: threshold 0.5)")
                    except ValueError:
                        print("❌ 请输入有效的数值")
                    continue
                
                # 处理用户查询
                response = workflow.process_user_query(user_input)
                
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
        print("3. 向量数据库是否已初始化")

def run_demo(workflow):
    """运行演示对话"""
    print("\n🎭 开始演示对话...")
    print("-" * 60)
    
    # 演示问题列表
    demo_questions = [
        "你好，请介绍一下你自己",
        "你能帮我做什么？",
        "请解释一下机器学习的基本概念",
        "什么是深度学习？",
        "你刚才提到了什么？"
    ]
    
    for i, question in enumerate(demo_questions, 1):
        print(f"\n📝 演示问题 {i}: {question}")
        print("-" * 40)
        
        try:
            response = workflow.process_user_query(question)
            print(f"🤖 AI回答: {response.llm_response}")
            
            if response.retrieved_chunks:
                print(f"📚 检索到 {len(response.retrieved_chunks)} 个相关文档片段")
                for j, chunk in enumerate(response.retrieved_chunks[:2]):  # 只显示前2个
                    print(f"   文档{j+1}: {chunk.filename} (相似度: {chunk.score:.3f})")
            
        except Exception as e:
            print(f"❌ 演示问题处理失败: {e}")
        
        print("-" * 40)
    
    print("\n✅ 演示对话完成!")

def simple_chat_demo():
    """简单的对话演示（不包含RAG功能）"""
    print("\n💬 简单对话演示（无RAG功能）")
    print("-" * 40)
    
    # 模型路径
    model_path = "../models--Qwen--Qwen3-8B/snapshots/9c925d64d72725edaf899c6cb9c377fd0709d9c5"
    
    # 加载分词器
    print("1. 加载分词器...")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    
    # 配置量化
    print("2. 配置量化...")
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )
    
    # 加载模型
    print("3. 加载模型...")
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        quantization_config=quantization_config,
        device_map="auto",
        trust_remote_code=True,
    )
    
    # 初始化对话历史
    chat_history = []
    
    def chat_with_model(user_input):
        """与模型进行单轮对话"""
        # 添加用户消息到历史
        chat_history.append({"role": "user", "content": user_input})
        
        # 构建完整对话上下文
        messages = [
            {"role": "system", "content": "你是一个有用的AI助手，请用中文回答用户的问题。"}
        ] + chat_history
        
        # 格式化输入
        text = tokenizer.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=True
        )
        
        # 编码
        inputs = tokenizer(text, return_tensors="pt")
        
        # 确保输入在正确的设备上
        if torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
        
        # 生成
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=500,
                temperature=0.7,
                do_sample=True
            )
        
        # 解码输出
        response = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
        
        # 添加AI回复到历史
        chat_history.append({"role": "assistant", "content": response})
        
        return response
    
    # 演示多轮对话
    print("\n开始多轮对话演示:")
    print("-" * 40)
    
    # 第一轮对话
    user_msg1 = "你好，请介绍一下你自己"
    print(f"user: {user_msg1}")
    response1 = chat_with_model(user_msg1)
    print(f"assistant: {response1}")
    print()
    
    # 第二轮对话（基于上下文）
    user_msg2 = "你刚才提到了什么？"
    print(f"user: {user_msg2}")
    response2 = chat_with_model(user_msg2)
    print(f"assistant: {response2}")
    print()
    
    # 第三轮对话（继续上下文）
    user_msg3 = "你能帮我写一个Python函数吗？"
    print(f"user: {user_msg3}")
    response3 = chat_with_model(user_msg3)
    print(f"assistant: {response3}")
    print()
    
    # 显示对话历史
    print("对话历史:")
    print("-" * 40)
    for i, msg in enumerate(chat_history):
        role = "用户" if msg["role"] == "user" else "助手"
        print(f"{i+1}. {role}: {msg['content']}")
    print("-" * 40)
    
    print("\n✅ 简单对话演示完成!")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--simple":
        # 运行简单对话演示
        simple_chat_demo()
    else:
        # 运行RAG工作流
        main()
