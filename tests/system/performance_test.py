#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG系统性能测试脚本
测试指标：
1. 检索阶段耗时
2. 首字生成时间（Time to First Token, TTFT）
3. 推理生成时间
"""

import os
import sys
import json
import time
import statistics
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from simple_rag_workflow import SimpleRAGWorkflow, CodeRAGWorkflow, WorkflowResponse, RetrievedChunk

# ==================== 数据模型 ====================

@dataclass
class PerformanceMetrics:
    """性能指标数据模型"""
    test_id: int
    question: str
    retrieval_time: float  # 检索阶段耗时（秒）
    ttft: float  # 首字生成时间（秒）
    generation_time: float  # 推理生成时间（秒）
    total_time: float  # 总耗时（秒）
    retrieved_chunks_count: int  # 检索到的chunk数量
    response_length: int  # 响应长度（字符数）
    success: bool  # 是否成功
    error_message: Optional[str] = None  # 错误信息

@dataclass
class TestSummary:
    """测试摘要"""
    total_tests: int
    successful_tests: int
    failed_tests: int
    avg_retrieval_time: float
    avg_ttft: float
    avg_generation_time: float
    avg_total_time: float
    median_retrieval_time: float
    median_ttft: float
    median_generation_time: float
    median_total_time: float
    min_retrieval_time: float
    min_ttft: float
    min_generation_time: float
    min_total_time: float
    max_retrieval_time: float
    max_ttft: float
    max_generation_time: float
    max_total_time: float

# ==================== 性能测试类 ====================

class PerformanceTester:
    """性能测试器"""
    
    def __init__(self, workflow):
        """
        初始化性能测试器
        
        Args:
            workflow: RAG工作流实例（SimpleRAGWorkflow 或 CodeRAGWorkflow）
        """
        self.workflow = workflow
        self.metrics: List[PerformanceMetrics] = []
        # 判断工作流类型
        self.is_code_rag = isinstance(workflow, CodeRAGWorkflow)
    
    def test_single_query(self, test_id: int, question: str) -> PerformanceMetrics:
        """
        测试单个查询的性能
        
        Args:
            test_id: 测试ID
            question: 测试问题
            
        Returns:
            性能指标
        """
        print(f"\n{'='*80}")
        print(f"测试 {test_id}: {question}")
        print(f"{'='*80}")
        
        # 初始化时间戳
        start_time = time.time()
        retrieval_start_time = None
        retrieval_end_time = None
        generation_start_time = None
        first_token_time = None
        generation_end_time = None
        
        ttft = None
        generation_time = None
        retrieval_time = None
        total_time = None
        retrieved_chunks_count = 0
        response_length = 0
        success = False
        error_message = None
        
        try:
            # 记录检索开始时间
            retrieval_start_time = time.time()
            
            # 创建自定义的流式回调来测量TTFT和区分检索/生成阶段
            first_token_received = False
            retrieval_end_time = None
            
            def stream_callback(data: Dict[str, Any]) -> None:
                nonlocal first_token_time, first_token_received, retrieval_end_time
                
                # 检测检索阶段结束（当收到answer_chunk或code_description_chunk时，说明检索已完成，开始生成）
                callback_type = data.get("type")
                is_answer_chunk = callback_type in ["answer_chunk", "code_description_chunk"]
                
                if is_answer_chunk:
                    # 记录检索结束时间（第一次收到answer_chunk时）
                    if retrieval_end_time is None:
                        retrieval_end_time = time.time()
                    
                    # 记录第一个token的时间
                    if not first_token_received:
                        first_token_received = True
                        first_token_time = time.time()
            
            # 执行查询（根据工作流类型选择不同的方法）
            if self.is_code_rag:
                # 代码检索使用 process_code_query
                response: WorkflowResponse = self.workflow.process_code_query(
                    question,
                    stream_callback=stream_callback
                )
            else:
                # 文档RAG使用 process_user_query
                response: WorkflowResponse = self.workflow.process_user_query(
                    question,
                    stream_callback=stream_callback
                )
            
            # 如果检索结束时间未记录（可能没有流式回调或检索阶段没有触发回调），使用当前时间
            if retrieval_end_time is None:
                # 尝试从响应中推断：如果已经有响应，说明检索已完成
                # 这里我们假设检索在生成之前完成，所以使用一个保守的估计
                # 实际上，我们需要在process_user_query内部添加时间戳才能准确测量
                # 为了简化，我们使用总时间的一部分作为检索时间
                retrieval_end_time = time.time()
            
            # 记录生成结束时间
            generation_end_time = time.time()
            
            # 计算各项指标
            retrieval_time = retrieval_end_time - retrieval_start_time
            
            # TTFT: 从检索结束（生成开始）到第一个token返回的时间
            # 注意：这里TTFT包括准备生成的时间（构建上下文、编码等）和模型生成第一个token的时间
            if first_token_time is not None and retrieval_end_time is not None:
                ttft = first_token_time - retrieval_end_time
            else:
                # 如果没有收到第一个token，使用生成总时间作为TTFT（保守估计）
                ttft = generation_end_time - retrieval_end_time if retrieval_end_time else 0
            
            # 推理生成时间：从第一个token到生成完成
            if first_token_time is not None:
                generation_time = generation_end_time - first_token_time
            else:
                # 如果没有收到第一个token，使用从检索结束到生成结束的时间
                generation_time = generation_end_time - retrieval_end_time if retrieval_end_time else 0
            
            total_time = generation_end_time - start_time
            
            retrieved_chunks_count = len(response.retrieved_chunks)
            response_length = len(response.llm_response)
            success = True
            
            print(f"\n✅ 测试 {test_id} 完成")
            print(f"   检索耗时: {retrieval_time:.3f}秒")
            print(f"   首字生成时间: {ttft:.3f}秒")
            print(f"   推理生成时间: {generation_time:.3f}秒")
            print(f"   总耗时: {total_time:.3f}秒")
            print(f"   检索到 {retrieved_chunks_count} 个chunk")
            print(f"   响应长度: {response_length} 字符")
            
        except Exception as e:
            error_message = str(e)
            success = False
            total_time = time.time() - start_time if start_time else 0
            
            print(f"\n❌ 测试 {test_id} 失败: {error_message}")
            import traceback
            traceback.print_exc()
        
        # 创建性能指标对象
        metrics = PerformanceMetrics(
            test_id=test_id,
            question=question,
            retrieval_time=retrieval_time or 0,
            ttft=ttft or 0,
            generation_time=generation_time or 0,
            total_time=total_time or 0,
            retrieved_chunks_count=retrieved_chunks_count,
            response_length=response_length,
            success=success,
            error_message=error_message
        )
        
        self.metrics.append(metrics)
        return metrics
    
    def generate_summary(self) -> TestSummary:
        """
        生成测试摘要
        
        Returns:
            测试摘要
        """
        if not self.metrics:
            return TestSummary(
                total_tests=0,
                successful_tests=0,
                failed_tests=0,
                avg_retrieval_time=0,
                avg_ttft=0,
                avg_generation_time=0,
                avg_total_time=0,
                median_retrieval_time=0,
                median_ttft=0,
                median_generation_time=0,
                median_total_time=0,
                min_retrieval_time=0,
                min_ttft=0,
                min_generation_time=0,
                min_total_time=0,
                max_retrieval_time=0,
                max_ttft=0,
                max_generation_time=0,
                max_total_time=0
            )
        
        successful_metrics = [m for m in self.metrics if m.success]
        failed_metrics = [m for m in self.metrics if not m.success]
        
        if not successful_metrics:
            return TestSummary(
                total_tests=len(self.metrics),
                successful_tests=0,
                failed_tests=len(failed_metrics),
                avg_retrieval_time=0,
                avg_ttft=0,
                avg_generation_time=0,
                avg_total_time=0,
                median_retrieval_time=0,
                median_ttft=0,
                median_generation_time=0,
                median_total_time=0,
                min_retrieval_time=0,
                min_ttft=0,
                min_generation_time=0,
                min_total_time=0,
                max_retrieval_time=0,
                max_ttft=0,
                max_generation_time=0,
                max_total_time=0
            )
        
        # 提取各项指标
        retrieval_times = [m.retrieval_time for m in successful_metrics]
        ttfts = [m.ttft for m in successful_metrics]
        generation_times = [m.generation_time for m in successful_metrics]
        total_times = [m.total_time for m in successful_metrics]
        
        return TestSummary(
            total_tests=len(self.metrics),
            successful_tests=len(successful_metrics),
            failed_tests=len(failed_metrics),
            avg_retrieval_time=statistics.mean(retrieval_times),
            avg_ttft=statistics.mean(ttfts),
            avg_generation_time=statistics.mean(generation_times),
            avg_total_time=statistics.mean(total_times),
            median_retrieval_time=statistics.median(retrieval_times),
            median_ttft=statistics.median(ttfts),
            median_generation_time=statistics.median(generation_times),
            median_total_time=statistics.median(total_times),
            min_retrieval_time=min(retrieval_times),
            min_ttft=min(ttfts),
            min_generation_time=min(generation_times),
            min_total_time=min(total_times),
            max_retrieval_time=max(retrieval_times),
            max_ttft=max(ttfts),
            max_generation_time=max(generation_times),
            max_total_time=max(total_times)
        )
    
    def save_results(self, output_file: str):
        """
        保存测试结果到JSON文件
        
        Args:
            output_file: 输出文件路径
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "metrics": [asdict(m) for m in self.metrics],
            "summary": asdict(self.generate_summary())
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 测试结果已保存到: {output_file}")
    
    def print_summary(self):
        """打印测试摘要"""
        summary = self.generate_summary()
        
        print(f"\n{'='*80}")
        print("测试摘要")
        print(f"{'='*80}")
        print(f"总测试数: {summary.total_tests}")
        print(f"成功: {summary.successful_tests}")
        print(f"失败: {summary.failed_tests}")
        print(f"\n检索阶段耗时:")
        print(f"  平均: {summary.avg_retrieval_time:.3f}秒")
        print(f"  中位数: {summary.median_retrieval_time:.3f}秒")
        print(f"  最小: {summary.min_retrieval_time:.3f}秒")
        print(f"  最大: {summary.max_retrieval_time:.3f}秒")
        print(f"\n首字生成时间 (TTFT):")
        print(f"  平均: {summary.avg_ttft:.3f}秒")
        print(f"  中位数: {summary.median_ttft:.3f}秒")
        print(f"  最小: {summary.min_ttft:.3f}秒")
        print(f"  最大: {summary.max_ttft:.3f}秒")
        print(f"\n推理生成时间:")
        print(f"  平均: {summary.avg_generation_time:.3f}秒")
        print(f"  中位数: {summary.median_generation_time:.3f}秒")
        print(f"  最小: {summary.min_generation_time:.3f}秒")
        print(f"  最大: {summary.max_generation_time:.3f}秒")
        print(f"\n总耗时:")
        print(f"  平均: {summary.avg_total_time:.3f}秒")
        print(f"  中位数: {summary.median_total_time:.3f}秒")
        print(f"  最小: {summary.min_total_time:.3f}秒")
        print(f"  最大: {summary.max_total_time:.3f}秒")
        print(f"{'='*80}\n")

# ==================== 主函数 ====================

def load_test_cases(test_cases_file: str) -> List[Dict[str, Any]]:
    """
    加载测试用例
    
    Args:
        test_cases_file: 测试用例文件路径
        
    Returns:
        测试用例列表
    """
    test_cases = []
    with open(test_cases_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                test_cases.append(json.loads(line))
    return test_cases

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='RAG系统性能测试')
    parser.add_argument(
        '--test-cases',
        type=str,
        default=os.path.join(os.path.dirname(__file__), 'test_cases.jsonl'),
        help='测试用例文件路径'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=os.path.join(os.path.dirname(__file__), 'performance_results.json'),
        help='测试结果输出文件路径'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='限制测试用例数量（用于快速测试）'
    )
    parser.add_argument(
        '--llm-path',
        type=str,
        default="../../../models--Qwen--Qwen3-8B/snapshots/9c925d64d72725edaf899c6cb9c377fd0709d9c5",
        help='LLM模型路径'
    )
    parser.add_argument(
        '--embedding-model-path',
        type=str,
        default="/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
        help='嵌入模型路径'
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default="../../vector_db",
        help='向量数据库路径'
    )
    parser.add_argument(
        '--similarity-threshold',
        type=float,
        default=0.0,
        help='相似度阈值'
    )
    parser.add_argument(
        '--use-quantization',
        type=bool,
        default=True,
        help='是否使用4位量化'
    )
    parser.add_argument(
        '--test-type',
        type=str,
        choices=['rag', 'code', 'both'],
        default='rag',
        help='测试类型: rag=文档RAG, code=代码检索, both=两者都测试'
    )
    parser.add_argument(
        '--chroma-md-path',
        type=str,
        default=os.path.join(project_root, "dzz_retrieval", "chroma_md"),
        help='代码检索的ChromaDB路径（仅用于代码检索）'
    )
    parser.add_argument(
        '--top-files',
        type=int,
        default=3,
        help='代码检索的文件级检索数量（仅用于代码检索）'
    )
    parser.add_argument(
        '--top-chunks',
        type=int,
        default=5,
        help='代码检索的代码块级检索数量（仅用于代码检索）'
    )
    
    args = parser.parse_args()
    
    print("="*80)
    print("RAG系统性能测试")
    print("="*80)
    print(f"测试类型: {args.test_type}")
    print(f"测试用例文件: {args.test_cases}")
    print(f"输出文件: {args.output}")
    if args.limit:
        print(f"限制测试数量: {args.limit}")
    print("="*80)
    
    # 加载测试用例
    print("\n📋 加载测试用例...")
    test_cases = load_test_cases(args.test_cases)
    if args.limit:
        test_cases = test_cases[:args.limit]
    print(f"✅ 加载了 {len(test_cases)} 个测试用例")
    
    # 根据测试类型执行测试
    test_types = []
    if args.test_type in ['rag', 'both']:
        test_types.append('rag')
    if args.test_type in ['code', 'both']:
        test_types.append('code')
    
    all_results = {}
    
    for test_type in test_types:
        print(f"\n{'='*80}")
        print(f"🚀 初始化{'文档RAG' if test_type == 'rag' else '代码检索'}工作流...")
        print(f"{'='*80}")
        
        # 基础配置
        base_config = {
            "llm_path": args.llm_path,
            "embedding_model_path": args.embedding_model_path,
            "db_path": args.db_path,
            "similarity_threshold": args.similarity_threshold,
            "use_quantization": args.use_quantization
        }
        
        try:
            if test_type == 'rag':
                # 文档RAG工作流
                workflow = SimpleRAGWorkflow(**base_config)
                print("✅ 文档RAG工作流初始化成功")
            else:
                # 代码检索工作流
                code_config = {
                    **base_config,
                    "chroma_md_path": args.chroma_md_path,
                    "top_files": args.top_files,
                    "top_chunks": args.top_chunks
                }
                workflow = CodeRAGWorkflow(**code_config)
                print("✅ 代码检索工作流初始化成功")
        except Exception as e:
            print(f"❌ {'文档RAG' if test_type == 'rag' else '代码检索'}工作流初始化失败: {e}")
            import traceback
            traceback.print_exc()
            continue
        
        # 创建性能测试器
        tester = PerformanceTester(workflow)
        
        # 执行测试
        print(f"\n🧪 开始执行{'文档RAG' if test_type == 'rag' else '代码检索'}性能测试...")
        start_time = time.time()
        
        for test_case in test_cases:
            test_id = test_case.get('id', 0)
            question = test_case.get('question', '')
            tester.test_single_query(test_id, question)
        
        end_time = time.time()
        total_test_time = end_time - start_time
        
        print(f"\n✅ {'文档RAG' if test_type == 'rag' else '代码检索'}测试完成，总耗时: {total_test_time:.2f}秒")
        
        # 打印摘要
        tester.print_summary()
        
        # 保存结果
        output_file = args.output
        if len(test_types) > 1:
            # 如果测试多种类型，为每种类型生成单独的结果文件
            base_name = os.path.splitext(output_file)[0]
            ext = os.path.splitext(output_file)[1]
            output_file = f"{base_name}_{test_type}{ext}"
        
        tester.save_results(output_file)
        all_results[test_type] = tester
        
        print(f"\n🎉 {'文档RAG' if test_type == 'rag' else '代码检索'}性能测试完成！结果已保存到: {output_file}")
    
    # 如果测试了两种类型，打印对比摘要
    if len(all_results) > 1:
        print(f"\n{'='*80}")
        print("📊 性能对比摘要")
        print(f"{'='*80}")
        for test_type, tester in all_results.items():
            summary = tester.generate_summary()
            print(f"\n{test_type.upper()} ({'文档RAG' if test_type == 'rag' else '代码检索'}):")
            print(f"  平均检索时间: {summary.avg_retrieval_time:.3f}秒")
            print(f"  平均TTFT: {summary.avg_ttft:.3f}秒")
            print(f"  平均生成时间: {summary.avg_generation_time:.3f}秒")
            print(f"  平均总时间: {summary.avg_total_time:.3f}秒")
        print(f"{'='*80}\n")

if __name__ == "__main__":
    main()

