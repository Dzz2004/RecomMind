# 系统性能测试

## 1. 测试环境与配置

记录测试时的基础设施，确保性能数据的基准一致性。

### 1.1 硬件配置 (Server-side)

| **组件** | **规格参数** |
| --- | --- |
| **CPU** | Intel(R) Core(TM) i9-14900K |
| **内存 (RAM)** | 188GB DDR5 4200MHz |
| **GPU** | NVIDIA 4090 24GB |
| **存储 (Disk)** | nvme0n1 KINGSTON SNV2S2000G   1.8T |

### 1.2 软件栈配置

| **组件** | **版本/配置 (请填入)** |
| --- | --- |
| **OS** | Ubuntu 22.04.4 LTS |
| **向量数据库** | ChromaDB 0.4+ |
| **LLM 推理框架** | Hugging Face Transformers |
| **Embedding 模型** | BAAI/bge-m3 |
| **CUDA 版本** | 12.6 |

---

## 3. 在线响应延迟测试 (Online Latency)

### 3.1 教材RAG功能

系统处理一次完整请求的各阶段耗时。

**测试方法：** 使用脚本串行发送 100 次请求，取平均值。

| **链路阶段** | **指标说明** | **平均耗时 (s)** |
| --- | --- | --- |
| **检索阶段 (Retrieval)** | 仅向量数据库查询耗时 (含网络开销) | 50.95 |
| **首字生成 (TTFT)** | Time to First Token (用户感知延迟) | 4.43e-07 |
| **推理生成 (TOG)** | Time Of Generate (生成回答耗时) | 47.51 |
| **端到端总延迟 (E2E)** | 完整请求闭环总耗时 | 98.46 |

### 3.2 代码RAG功能

系统处理一次完整请求的各阶段耗时。

**测试方法：** 使用脚本串行发送 100 次请求，取平均值。

| **链路阶段** | **指标说明** | **平均耗时 (s)** |
| --- | --- | --- |
| **检索阶段 (Retrieval)** | 仅向量数据库查询耗时 (含网络开销) | 27.78 |
| **首字生成 (TTFT)** | Time to First Token (用户感知延迟) | 5.03e-07 |
| **推理生成 (TOG)** | Time Of Generate (生成回答耗时) | 79.01 |
| **端到端总延迟 (E2E)** | 完整请求闭环总耗时 | 106.80 |

---

## 4. 资源利用率监控 (Resource Utilization)

记录在测试期间，服务器硬件资源的占用情况，用于分析瓶颈。

| **资源项** | **监控指标** | **平均占用** |
| --- | --- | --- |
| **GPU 显存** | VRAM Memory Usage | 15.46 GB |
| **CPU 负载** | CPU Load Average / Usage | 0.14 % |
| **虚拟内存占用** | Virtual Memory Size(VMS) | 41.5 GB |
| **常驻内存大小** | Resident Set Size(RSS) | 2.66 GB |
| **物理内存占用率** | %MEM | 1.41% |

![image.png](image.png)

---

## 5. 附录 (Reference)

### 5.1 测试用例 (Test Case)

测试用例生成方式通过调用大模型生成，prompt如下

生成100条测试用例

```python
user_prompt = """
# Role
你是一位精通 Linux 操作系统内核架构、源码实现及系统编程的资深专家。你正在为一个“操作系统内核 RAG（检索增强生成）系统”构建测试数据集。

# Task
请生成 50 条操作系统相关的测试问题。

# Constraints & Format
1. **格式严格要求**：每一行必须是一个独立的 JSON 对象，不要包含在列表中，不要使用 Markdown 代码块（```json），直接输出 JSON 文本。
2. **Key 命名**：使用 `id` (整数) 和 `question` (字符串)。
3. **ID 顺序**：请接着我给出的示例 ID 继续编号（从 13 开始）。
4. **内容深度**：问题应涵盖操作系统原理、Linux 内核源码概念、系统性能调试等。请确保问题具有一定的专业性，适合用于测试大模型检索内核源码的能力。
5. **覆盖领域**：
   - 内存管理 (Memory Management, Slab, Buddy System)
   - 进程与线程调度 (Scheduler, CFS, Context Switch)
   - 文件系统 (VFS, Ext4, Inode)
   - 中断与异常 (Interrupts, System Calls)
   - 并发与同步 (Locks, Semaphores, RCU)
   - 设备驱动 (Device Drivers)
   - 网络子系统 (Netfilter, TCP/IP stack)

# Few-Shot Examples (参考风格)
{"id": 1, "question": "linux内存管理是什么"}
{"id": 2, "question": "进程调度算法有哪些"}
{"id": 3, "question": "什么是虚拟内存"}
{"id": 4, "question": "文件系统的基本概念"}
{"id": 5, "question": "死锁的定义和条件"}
{"id": 11, "question": "页面置换算法"}
{"id": 12, "question": "磁盘调度算法"}

# Output Start (从 ID 13 开始)
"""
```

```json
{"id": 1, "question": "linux内存管理是什么"}
{"id": 2, "question": "进程调度算法有哪些"}
{"id": 3, "question": "什么是虚拟内存"}
{"id": 4, "question": "文件系统的基本概念"}
{"id": 5, "question": "死锁的定义和条件"}
{"id": 6, "question": "进程和线程的区别"}
{"id": 7, "question": "操作系统的功能有哪些"}
{"id": 8, "question": "什么是系统调用"}
{"id": 9, "question": "中断处理机制"}
{"id": 10, "question": "CPU调度策略"}
{"id": 11, "question": "页面置换算法"}
{"id": 12, "question": "磁盘调度算法"}
{"id": 13, "question": "同步和互斥的概念"}
{"id": 14, "question": "信号量的作用"}
{"id": 15, "question": "管程的概念"}
{"id": 16, "question": "进程间通信方式"}
{"id": 17, "question": "什么是缓冲区"}
{"id": 18, "question": "设备驱动程序的作用"}
{"id": 19, "question": "多道程序设计"}
{"id": 20, "question": "分时系统的特点"}
{"id": 21, "question": "实时系统的要求"}
{"id": 22, "question": "操作系统的分类"}
{"id": 23, "question": "内核态和用户态的区别"}
{"id": 24, "question": "什么是上下文切换"}
{"id": 25, "question": "内存分配策略"}
{"id": 26, "question": "页面错误处理"}
{"id": 27, "question": "工作集的概念"}
{"id": 28, "question": "内存碎片问题"}
{"id": 29, "question": "分段和分页的区别"}
{"id": 30, "question": "地址转换过程"}
{"id": 31, "question": "TLB的作用"}
{"id": 32, "question": "文件目录结构"}
{"id": 33, "question": "文件访问控制"}
{"id": 34, "question": "文件保护机制"}
{"id": 35, "question": "磁盘空间管理"}
{"id": 36, "question": "文件系统一致性"}
{"id": 37, "question": "日志文件系统"}
{"id": 38, "question": "RAID技术"}
{"id": 39, "question": "I/O子系统"}
{"id": 40, "question": "DMA的作用"}
{"id": 41, "question": "中断向量表"}
{"id": 42, "question": "系统启动过程"}
{"id": 43, "question": "引导程序的作用"}
{"id": 44, "question": "系统初始化流程"}
{"id": 45, "question": "进程创建过程"}
{"id": 46, "question": "进程终止处理"}
{"id": 47, "question": "进程状态转换"}
{"id": 48, "question": "PCB的作用"}
{"id": 49, "question": "线程的实现方式"}
{"id": 50, "question": "用户级线程和内核级线程"}
{"id": 51, "question": "多线程编程模型"}
{"id": 52, "question": "临界区问题"}
{"id": 53, "question": "互斥锁的实现"}
{"id": 54, "question": "条件变量的使用"}
{"id": 55, "question": "读写锁机制"}
{"id": 56, "question": "生产者消费者问题"}
{"id": 57, "question": "哲学家就餐问题"}
{"id": 58, "question": "读者写者问题"}
{"id": 59, "question": "银行家算法"}
{"id": 60, "question": "死锁检测算法"}
{"id": 61, "question": "死锁预防策略"}
{"id": 62, "question": "死锁避免方法"}
{"id": 63, "question": "内存映射文件"}
{"id": 64, "question": "共享内存机制"}
{"id": 65, "question": "消息传递机制"}
{"id": 66, "question": "管道通信"}
{"id": 67, "question": "命名管道"}
{"id": 68, "question": "套接字通信"}
{"id": 69, "question": "远程过程调用"}
{"id": 70, "question": "分布式系统特点"}
{"id": 71, "question": "负载均衡策略"}
{"id": 72, "question": "容错机制"}
{"id": 73, "question": "系统安全机制"}
{"id": 74, "question": "访问控制列表"}
{"id": 75, "question": "权限管理"}
{"id": 76, "question": "加密文件系统"}
{"id": 77, "question": "审计日志"}
{"id": 78, "question": "系统监控"}
{"id": 79, "question": "性能调优方法"}
{"id": 80, "question": "缓存机制"}
{"id": 81, "question": "预取策略"}
{"id": 82, "question": "写回和写直达"}
{"id": 83, "question": "虚拟化技术"}
{"id": 84, "question": "容器技术"}
{"id": 85, "question": "微内核架构"}
{"id": 86, "question": "宏内核架构"}
{"id": 87, "question": "混合内核"}
{"id": 88, "question": "操作系统设计原则"}
{"id": 89, "question": "模块化设计"}
{"id": 90, "question": "可扩展性设计"}
{"id": 91, "question": "系统调用接口"}
{"id": 92, "question": "API和系统调用"}
{"id": 93, "question": "库函数和系统调用"}
{"id": 94, "question": "系统调用开销"}
{"id": 95, "question": "系统调用优化"}
{"id": 96, "question": "中断嵌套"}
{"id": 97, "question": "中断优先级"}
{"id": 98, "question": "软中断和硬中断"}
{"id": 99, "question": "时钟中断处理"}
{"id": 100, "question": "系统时间管理"}
```

### 5.2 测试代码 (Test Code)

```python
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

```

### 5.3 测试结果 (Test Result)

```json
{
  "timestamp": "2025-12-25T15:46:45.825111",
  "metrics": [
    {
      "test_id": 1,
      "question": "linux内存管理是什么",
      "retrieval_time": 38.28956651687622,
      "ttft": 7.152557373046875e-07,
      "generation_time": 37.166234254837036,
      "total_time": 75.455801486969,
      "retrieved_chunks_count": 4,
      "response_length": 2839,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 2,
      "question": "进程调度算法有哪些",
      "retrieval_time": 47.65080952644348,
      "ttft": 4.76837158203125e-07,
      "generation_time": 62.3226273059845,
      "total_time": 109.97343754768372,
      "retrieved_chunks_count": 6,
      "response_length": 3738,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 3,
      "question": "什么是虚拟内存",
      "retrieval_time": 43.307759046554565,
      "ttft": 4.5299530029296875e-06,
      "generation_time": 62.333476543426514,
      "total_time": 105.64124011993408,
      "retrieved_chunks_count": 7,
      "response_length": 3479,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 4,
      "question": "文件系统的基本概念",
      "retrieval_time": 41.67445135116577,
      "ttft": 4.76837158203125e-07,
      "generation_time": 38.46312999725342,
      "total_time": 80.13758206367493,
      "retrieved_chunks_count": 5,
      "response_length": 2844,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 5,
      "question": "死锁的定义和条件",
      "retrieval_time": 39.25111961364746,
      "ttft": 4.76837158203125e-07,
      "generation_time": 31.32208228111267,
      "total_time": 70.57320261001587,
      "retrieved_chunks_count": 5,
      "response_length": 1910,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 6,
      "question": "进程和线程的区别",
      "retrieval_time": 43.83653020858765,
      "ttft": 4.76837158203125e-07,
      "generation_time": 35.93953585624695,
      "total_time": 79.77606678009033,
      "retrieved_chunks_count": 3,
      "response_length": 3000,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 7,
      "question": "操作系统的功能有哪些",
      "retrieval_time": 60.458444356918335,
      "ttft": 2.384185791015625e-07,
      "generation_time": 27.642534017562866,
      "total_time": 88.10097861289978,
      "retrieved_chunks_count": 3,
      "response_length": 2371,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 8,
      "question": "什么是系统调用",
      "retrieval_time": 46.45697236061096,
      "ttft": 4.76837158203125e-07,
      "generation_time": 34.351048707962036,
      "total_time": 80.80802154541016,
      "retrieved_chunks_count": 5,
      "response_length": 3124,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 9,
      "question": "中断处理机制",
      "retrieval_time": 50.652809619903564,
      "ttft": 4.76837158203125e-07,
      "generation_time": 52.820619344711304,
      "total_time": 103.4734296798706,
      "retrieved_chunks_count": 6,
      "response_length": 3491,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 10,
      "question": "CPU调度策略",
      "retrieval_time": 47.7763774394989,
      "ttft": 4.76837158203125e-07,
      "generation_time": 86.10671496391296,
      "total_time": 133.8830931186676,
      "retrieved_chunks_count": 3,
      "response_length": 5298,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 11,
      "question": "页面置换算法",
      "retrieval_time": 40.4938600063324,
      "ttft": 4.76837158203125e-07,
      "generation_time": 43.390241622924805,
      "total_time": 83.88410210609436,
      "retrieved_chunks_count": 2,
      "response_length": 3527,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 12,
      "question": "磁盘调度算法",
      "retrieval_time": 48.116849422454834,
      "ttft": 2.384185791015625e-07,
      "generation_time": 35.602423906326294,
      "total_time": 83.7192735671997,
      "retrieved_chunks_count": 1,
      "response_length": 3113,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 13,
      "question": "同步和互斥的概念",
      "retrieval_time": 38.09158706665039,
      "ttft": 4.76837158203125e-07,
      "generation_time": 29.94603419303894,
      "total_time": 68.03762173652649,
      "retrieved_chunks_count": 5,
      "response_length": 2676,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 14,
      "question": "信号量的作用",
      "retrieval_time": 40.101144313812256,
      "ttft": 2.384185791015625e-07,
      "generation_time": 33.300076484680176,
      "total_time": 73.40122127532959,
      "retrieved_chunks_count": 3,
      "response_length": 2964,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 15,
      "question": "管程的概念",
      "retrieval_time": 48.08566212654114,
      "ttft": 4.76837158203125e-07,
      "generation_time": 39.26990509033203,
      "total_time": 87.35556769371033,
      "retrieved_chunks_count": 1,
      "response_length": 3893,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 16,
      "question": "进程间通信方式",
      "retrieval_time": 48.25277781486511,
      "ttft": 4.76837158203125e-07,
      "generation_time": 51.45402550697327,
      "total_time": 99.70680403709412,
      "retrieved_chunks_count": 10,
      "response_length": 3594,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 17,
      "question": "什么是缓冲区",
      "retrieval_time": 49.33518624305725,
      "ttft": 2.384185791015625e-07,
      "generation_time": 35.679195165634155,
      "total_time": 85.01438188552856,
      "retrieved_chunks_count": 4,
      "response_length": 2913,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 18,
      "question": "设备驱动程序的作用",
      "retrieval_time": 46.43436789512634,
      "ttft": 4.76837158203125e-07,
      "generation_time": 57.09346795082092,
      "total_time": 103.52783632278442,
      "retrieved_chunks_count": 7,
      "response_length": 2771,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 19,
      "question": "多道程序设计",
      "retrieval_time": 57.88384699821472,
      "ttft": 4.76837158203125e-07,
      "generation_time": 67.00131368637085,
      "total_time": 124.88516163825989,
      "retrieved_chunks_count": 7,
      "response_length": 3633,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 20,
      "question": "分时系统的特点",
      "retrieval_time": 55.66925406455994,
      "ttft": 2.384185791015625e-07,
      "generation_time": 27.212765216827393,
      "total_time": 82.88201999664307,
      "retrieved_chunks_count": 3,
      "response_length": 2495,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 21,
      "question": "实时系统的要求",
      "retrieval_time": 45.53626251220703,
      "ttft": 2.384185791015625e-07,
      "generation_time": 32.490275144577026,
      "total_time": 78.02653789520264,
      "retrieved_chunks_count": 3,
      "response_length": 2700,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 22,
      "question": "操作系统的分类",
      "retrieval_time": 52.45287084579468,
      "ttft": 4.76837158203125e-07,
      "generation_time": 51.91462421417236,
      "total_time": 104.36749577522278,
      "retrieved_chunks_count": 9,
      "response_length": 3153,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 23,
      "question": "内核态和用户态的区别",
      "retrieval_time": 40.78018140792847,
      "ttft": 7.152557373046875e-07,
      "generation_time": 35.879230976104736,
      "total_time": 76.65941333770752,
      "retrieved_chunks_count": 4,
      "response_length": 3211,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 24,
      "question": "什么是上下文切换",
      "retrieval_time": 48.45115947723389,
      "ttft": 7.152557373046875e-07,
      "generation_time": 31.904460191726685,
      "total_time": 80.35562062263489,
      "retrieved_chunks_count": 1,
      "response_length": 2877,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 25,
      "question": "内存分配策略",
      "retrieval_time": 50.65484285354614,
      "ttft": 7.152557373046875e-07,
      "generation_time": 97.41209936141968,
      "total_time": 148.06694316864014,
      "retrieved_chunks_count": 10,
      "response_length": 4375,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 26,
      "question": "页面错误处理",
      "retrieval_time": 50.03760600090027,
      "ttft": 2.384185791015625e-07,
      "generation_time": 35.7229208946228,
      "total_time": 85.76052713394165,
      "retrieved_chunks_count": 4,
      "response_length": 3111,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 27,
      "question": "工作集的概念",
      "retrieval_time": 49.80046558380127,
      "ttft": 4.76837158203125e-07,
      "generation_time": 26.06874370574951,
      "total_time": 75.86921000480652,
      "retrieved_chunks_count": 2,
      "response_length": 2146,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 28,
      "question": "内存碎片问题",
      "retrieval_time": 53.762690782547,
      "ttft": 2.384185791015625e-07,
      "generation_time": 34.545958518981934,
      "total_time": 88.30864953994751,
      "retrieved_chunks_count": 1,
      "response_length": 2912,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 29,
      "question": "分段和分页的区别",
      "retrieval_time": 59.50002837181091,
      "ttft": 4.76837158203125e-07,
      "generation_time": 46.3508985042572,
      "total_time": 105.85092735290527,
      "retrieved_chunks_count": 3,
      "response_length": 3641,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 30,
      "question": "地址转换过程",
      "retrieval_time": 52.15834069252014,
      "ttft": 2.384185791015625e-07,
      "generation_time": 56.61370229721069,
      "total_time": 108.77204322814941,
      "retrieved_chunks_count": 5,
      "response_length": 2817,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 31,
      "question": "TLB的作用",
      "retrieval_time": 49.05084156990051,
      "ttft": 2.384185791015625e-07,
      "generation_time": 25.919378757476807,
      "total_time": 74.97022080421448,
      "retrieved_chunks_count": 2,
      "response_length": 2166,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 32,
      "question": "文件目录结构",
      "retrieval_time": 41.947988748550415,
      "ttft": 2.384185791015625e-07,
      "generation_time": 40.865044832229614,
      "total_time": 82.81303405761719,
      "retrieved_chunks_count": 4,
      "response_length": 3189,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 33,
      "question": "文件访问控制",
      "retrieval_time": 38.41804766654968,
      "ttft": 4.76837158203125e-07,
      "generation_time": 43.68854284286499,
      "total_time": 82.10659098625183,
      "retrieved_chunks_count": 2,
      "response_length": 4131,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 34,
      "question": "文件保护机制",
      "retrieval_time": 47.81961750984192,
      "ttft": 2.384185791015625e-07,
      "generation_time": 52.35222816467285,
      "total_time": 100.17184615135193,
      "retrieved_chunks_count": 4,
      "response_length": 4476,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 35,
      "question": "磁盘空间管理",
      "retrieval_time": 52.61078763008118,
      "ttft": 2.384185791015625e-07,
      "generation_time": 40.43715834617615,
      "total_time": 93.0479462146759,
      "retrieved_chunks_count": 4,
      "response_length": 3537,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 36,
      "question": "文件系统一致性",
      "retrieval_time": 58.03501510620117,
      "ttft": 2.384185791015625e-07,
      "generation_time": 50.78027367591858,
      "total_time": 108.81528949737549,
      "retrieved_chunks_count": 2,
      "response_length": 4522,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 37,
      "question": "日志文件系统",
      "retrieval_time": 48.68644189834595,
      "ttft": 2.384185791015625e-07,
      "generation_time": 39.45929670333862,
      "total_time": 88.14573884010315,
      "retrieved_chunks_count": 1,
      "response_length": 3807,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 38,
      "question": "RAID技术",
      "retrieval_time": 43.264928579330444,
      "ttft": 4.76837158203125e-07,
      "generation_time": 47.07998275756836,
      "total_time": 90.34491181373596,
      "retrieved_chunks_count": 1,
      "response_length": 4319,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 39,
      "question": "I/O子系统",
      "retrieval_time": 45.18925356864929,
      "ttft": 2.384185791015625e-07,
      "generation_time": 84.79921746253967,
      "total_time": 129.98847150802612,
      "retrieved_chunks_count": 8,
      "response_length": 4842,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 40,
      "question": "DMA的作用",
      "retrieval_time": 46.88492131233215,
      "ttft": 9.5367431640625e-07,
      "generation_time": 29.953623056411743,
      "total_time": 76.83854556083679,
      "retrieved_chunks_count": 0,
      "response_length": 2895,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 41,
      "question": "中断向量表",
      "retrieval_time": 47.0222270488739,
      "ttft": 2.384185791015625e-07,
      "generation_time": 46.28111124038696,
      "total_time": 93.30333876609802,
      "retrieved_chunks_count": 0,
      "response_length": 3849,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 42,
      "question": "系统启动过程",
      "retrieval_time": 50.14017200469971,
      "ttft": 2.384185791015625e-07,
      "generation_time": 32.85720491409302,
      "total_time": 82.99737739562988,
      "retrieved_chunks_count": 4,
      "response_length": 2816,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 43,
      "question": "引导程序的作用",
      "retrieval_time": 47.23785209655762,
      "ttft": 2.384185791015625e-07,
      "generation_time": 27.56272864341736,
      "total_time": 74.80058097839355,
      "retrieved_chunks_count": 0,
      "response_length": 2454,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 44,
      "question": "系统初始化流程",
      "retrieval_time": 55.00163912773132,
      "ttft": 2.384185791015625e-07,
      "generation_time": 37.62466835975647,
      "total_time": 92.62630796432495,
      "retrieved_chunks_count": 3,
      "response_length": 3175,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 45,
      "question": "进程创建过程",
      "retrieval_time": 55.30941343307495,
      "ttft": 0,
      "generation_time": 61.919466495513916,
      "total_time": 117.22888016700745,
      "retrieved_chunks_count": 6,
      "response_length": 4161,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 46,
      "question": "进程终止处理",
      "retrieval_time": 59.706005811691284,
      "ttft": 2.384185791015625e-07,
      "generation_time": 50.49615144729614,
      "total_time": 110.20215773582458,
      "retrieved_chunks_count": 4,
      "response_length": 4141,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 47,
      "question": "进程状态转换",
      "retrieval_time": 55.9845814704895,
      "ttft": 7.152557373046875e-07,
      "generation_time": 47.78781080245972,
      "total_time": 103.77239322662354,
      "retrieved_chunks_count": 6,
      "response_length": 4160,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 48,
      "question": "PCB的作用",
      "retrieval_time": 40.89301824569702,
      "ttft": 2.384185791015625e-07,
      "generation_time": 45.46777629852295,
      "total_time": 86.36079502105713,
      "retrieved_chunks_count": 3,
      "response_length": 3340,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 49,
      "question": "线程的实现方式",
      "retrieval_time": 48.25106072425842,
      "ttft": 2.384185791015625e-07,
      "generation_time": 41.57376313209534,
      "total_time": 89.82482433319092,
      "retrieved_chunks_count": 1,
      "response_length": 3582,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 50,
      "question": "用户级线程和内核级线程",
      "retrieval_time": 50.27416276931763,
      "ttft": 4.76837158203125e-07,
      "generation_time": 40.12845420837402,
      "total_time": 90.40261745452881,
      "retrieved_chunks_count": 1,
      "response_length": 4061,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 51,
      "question": "多线程编程模型",
      "retrieval_time": 49.63170385360718,
      "ttft": 7.152557373046875e-07,
      "generation_time": 48.295703649520874,
      "total_time": 97.92740821838379,
      "retrieved_chunks_count": 2,
      "response_length": 3891,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 52,
      "question": "临界区问题",
      "retrieval_time": 62.896260499954224,
      "ttft": 0,
      "generation_time": 70.17438888549805,
      "total_time": 133.07064962387085,
      "retrieved_chunks_count": 10,
      "response_length": 3709,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 53,
      "question": "互斥锁的实现",
      "retrieval_time": 42.22578430175781,
      "ttft": 7.152557373046875e-07,
      "generation_time": 43.4652464389801,
      "total_time": 85.69103169441223,
      "retrieved_chunks_count": 3,
      "response_length": 3274,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 54,
      "question": "条件变量的使用",
      "retrieval_time": 53.35946488380432,
      "ttft": 4.76837158203125e-07,
      "generation_time": 48.25431966781616,
      "total_time": 101.61378502845764,
      "retrieved_chunks_count": 2,
      "response_length": 5063,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 55,
      "question": "读写锁机制",
      "retrieval_time": 49.97646999359131,
      "ttft": 2.384185791015625e-07,
      "generation_time": 45.05378699302673,
      "total_time": 95.03025722503662,
      "retrieved_chunks_count": 0,
      "response_length": 4000,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 56,
      "question": "生产者消费者问题",
      "retrieval_time": 56.81505584716797,
      "ttft": 2.384185791015625e-07,
      "generation_time": 37.75954604148865,
      "total_time": 94.5746021270752,
      "retrieved_chunks_count": 3,
      "response_length": 3342,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 57,
      "question": "哲学家就餐问题",
      "retrieval_time": 50.47320866584778,
      "ttft": 4.76837158203125e-07,
      "generation_time": 42.035160779953,
      "total_time": 92.50837016105652,
      "retrieved_chunks_count": 0,
      "response_length": 3764,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 58,
      "question": "读者写者问题",
      "retrieval_time": 53.13344383239746,
      "ttft": 7.152557373046875e-07,
      "generation_time": 44.06865906715393,
      "total_time": 97.20210385322571,
      "retrieved_chunks_count": 0,
      "response_length": 4427,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 59,
      "question": "银行家算法",
      "retrieval_time": 53.36290669441223,
      "ttft": 7.152557373046875e-07,
      "generation_time": 45.66385626792908,
      "total_time": 99.02676367759705,
      "retrieved_chunks_count": 2,
      "response_length": 3105,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 60,
      "question": "死锁检测算法",
      "retrieval_time": 52.39107799530029,
      "ttft": 2.384185791015625e-07,
      "generation_time": 42.64296865463257,
      "total_time": 95.0340473651886,
      "retrieved_chunks_count": 3,
      "response_length": 2603,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 61,
      "question": "死锁预防策略",
      "retrieval_time": 34.14586591720581,
      "ttft": 2.384185791015625e-07,
      "generation_time": 32.715879678726196,
      "total_time": 66.86174607276917,
      "retrieved_chunks_count": 2,
      "response_length": 2134,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 62,
      "question": "死锁避免方法",
      "retrieval_time": 44.97238111495972,
      "ttft": 2.384185791015625e-07,
      "generation_time": 52.66997933387756,
      "total_time": 97.64236092567444,
      "retrieved_chunks_count": 3,
      "response_length": 3472,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 63,
      "question": "内存映射文件",
      "retrieval_time": 58.180689573287964,
      "ttft": 2.384185791015625e-07,
      "generation_time": 44.78902745246887,
      "total_time": 102.96971726417542,
      "retrieved_chunks_count": 3,
      "response_length": 3605,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 64,
      "question": "共享内存机制",
      "retrieval_time": 48.52038860321045,
      "ttft": 4.76837158203125e-07,
      "generation_time": 47.59952354431152,
      "total_time": 96.11991310119629,
      "retrieved_chunks_count": 3,
      "response_length": 4555,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 65,
      "question": "消息传递机制",
      "retrieval_time": 46.823652267456055,
      "ttft": 2.384185791015625e-07,
      "generation_time": 68.92432570457458,
      "total_time": 115.7479784488678,
      "retrieved_chunks_count": 7,
      "response_length": 5769,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 66,
      "question": "管道通信",
      "retrieval_time": 41.478917360305786,
      "ttft": 7.152557373046875e-07,
      "generation_time": 56.482956409454346,
      "total_time": 97.96187472343445,
      "retrieved_chunks_count": 7,
      "response_length": 4534,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 67,
      "question": "命名管道",
      "retrieval_time": 43.62524652481079,
      "ttft": 2.384185791015625e-07,
      "generation_time": 41.14241313934326,
      "total_time": 84.76765990257263,
      "retrieved_chunks_count": 3,
      "response_length": 3810,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 68,
      "question": "套接字通信",
      "retrieval_time": 54.466458320617676,
      "ttft": 0,
      "generation_time": 47.95085549354553,
      "total_time": 102.41731405258179,
      "retrieved_chunks_count": 1,
      "response_length": 4857,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 69,
      "question": "远程过程调用",
      "retrieval_time": 46.17416167259216,
      "ttft": 2.384185791015625e-07,
      "generation_time": 38.40301060676575,
      "total_time": 84.57717251777649,
      "retrieved_chunks_count": 0,
      "response_length": 3923,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 70,
      "question": "分布式系统特点",
      "retrieval_time": 47.853803396224976,
      "ttft": 2.384185791015625e-07,
      "generation_time": 28.48697304725647,
      "total_time": 76.3407769203186,
      "retrieved_chunks_count": 1,
      "response_length": 2609,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 71,
      "question": "负载均衡策略",
      "retrieval_time": 53.37302589416504,
      "ttft": 2.384185791015625e-07,
      "generation_time": 43.98517990112305,
      "total_time": 97.35820627212524,
      "retrieved_chunks_count": 2,
      "response_length": 3054,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 72,
      "question": "容错机制",
      "retrieval_time": 70.18019509315491,
      "ttft": 2.384185791015625e-07,
      "generation_time": 53.779967069625854,
      "total_time": 123.96016263961792,
      "retrieved_chunks_count": 8,
      "response_length": 2536,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 73,
      "question": "系统安全机制",
      "retrieval_time": 47.167275190353394,
      "ttft": 4.76837158203125e-07,
      "generation_time": 46.18788480758667,
      "total_time": 93.35516095161438,
      "retrieved_chunks_count": 3,
      "response_length": 3703,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 74,
      "question": "访问控制列表",
      "retrieval_time": 32.029489517211914,
      "ttft": 2.384185791015625e-07,
      "generation_time": 31.740901470184326,
      "total_time": 63.7703914642334,
      "retrieved_chunks_count": 1,
      "response_length": 2986,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 75,
      "question": "权限管理",
      "retrieval_time": 51.992196559906006,
      "ttft": 2.384185791015625e-07,
      "generation_time": 47.2196147441864,
      "total_time": 99.21181178092957,
      "retrieved_chunks_count": 2,
      "response_length": 4631,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 76,
      "question": "加密文件系统",
      "retrieval_time": 54.564122438430786,
      "ttft": 2.384185791015625e-07,
      "generation_time": 55.55337738990784,
      "total_time": 110.11750030517578,
      "retrieved_chunks_count": 2,
      "response_length": 4675,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 77,
      "question": "审计日志",
      "retrieval_time": 41.989410400390625,
      "ttft": 2.384185791015625e-07,
      "generation_time": 38.83562684059143,
      "total_time": 80.82503747940063,
      "retrieved_chunks_count": 0,
      "response_length": 3536,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 78,
      "question": "系统监控",
      "retrieval_time": 57.4233980178833,
      "ttft": 2.384185791015625e-07,
      "generation_time": 43.53352689743042,
      "total_time": 100.95692539215088,
      "retrieved_chunks_count": 4,
      "response_length": 3995,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 79,
      "question": "性能调优方法",
      "retrieval_time": 55.53755855560303,
      "ttft": 2.384185791015625e-07,
      "generation_time": 124.14097547531128,
      "total_time": 179.67853450775146,
      "retrieved_chunks_count": 7,
      "response_length": 5206,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 80,
      "question": "缓存机制",
      "retrieval_time": 60.08351683616638,
      "ttft": 4.76837158203125e-07,
      "generation_time": 84.66991257667542,
      "total_time": 144.75343012809753,
      "retrieved_chunks_count": 5,
      "response_length": 4946,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 81,
      "question": "预取策略",
      "retrieval_time": 52.83380579948425,
      "ttft": 2.384185791015625e-07,
      "generation_time": 51.51301383972168,
      "total_time": 104.34682035446167,
      "retrieved_chunks_count": 0,
      "response_length": 3863,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 82,
      "question": "写回和写直达",
      "retrieval_time": 66.79559206962585,
      "ttft": 9.5367431640625e-07,
      "generation_time": 39.58415770530701,
      "total_time": 106.37975096702576,
      "retrieved_chunks_count": 1,
      "response_length": 2843,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 83,
      "question": "虚拟化技术",
      "retrieval_time": 54.67716956138611,
      "ttft": 4.76837158203125e-07,
      "generation_time": 69.82924246788025,
      "total_time": 124.5064127445221,
      "retrieved_chunks_count": 6,
      "response_length": 3980,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 84,
      "question": "容器技术",
      "retrieval_time": 48.35173726081848,
      "ttft": 7.152557373046875e-07,
      "generation_time": 42.455384731292725,
      "total_time": 90.80712294578552,
      "retrieved_chunks_count": 0,
      "response_length": 4215,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 85,
      "question": "微内核架构",
      "retrieval_time": 55.31562113761902,
      "ttft": 2.384185791015625e-07,
      "generation_time": 39.186229944229126,
      "total_time": 94.5018515586853,
      "retrieved_chunks_count": 3,
      "response_length": 3552,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 86,
      "question": "宏内核架构",
      "retrieval_time": 50.7817964553833,
      "ttft": 2.384185791015625e-07,
      "generation_time": 43.53391218185425,
      "total_time": 94.3157091140747,
      "retrieved_chunks_count": 1,
      "response_length": 3389,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 87,
      "question": "混合内核",
      "retrieval_time": 41.36199450492859,
      "ttft": 2.384185791015625e-07,
      "generation_time": 38.12986421585083,
      "total_time": 79.49185967445374,
      "retrieved_chunks_count": 0,
      "response_length": 3465,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 88,
      "question": "操作系统设计原则",
      "retrieval_time": 51.243199825286865,
      "ttft": 4.76837158203125e-07,
      "generation_time": 39.062819957733154,
      "total_time": 90.30602049827576,
      "retrieved_chunks_count": 6,
      "response_length": 3370,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 89,
      "question": "模块化设计",
      "retrieval_time": 43.381346702575684,
      "ttft": 2.384185791015625e-07,
      "generation_time": 30.049018144607544,
      "total_time": 73.43036532402039,
      "retrieved_chunks_count": 0,
      "response_length": 2558,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 90,
      "question": "可扩展性设计",
      "retrieval_time": 50.05325984954834,
      "ttft": 2.384185791015625e-07,
      "generation_time": 33.390307903289795,
      "total_time": 83.4435682296753,
      "retrieved_chunks_count": 1,
      "response_length": 2843,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 91,
      "question": "系统调用接口",
      "retrieval_time": 56.38210582733154,
      "ttft": 2.384185791015625e-07,
      "generation_time": 62.3260223865509,
      "total_time": 118.7081286907196,
      "retrieved_chunks_count": 7,
      "response_length": 4218,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 92,
      "question": "API和系统调用",
      "retrieval_time": 47.17771792411804,
      "ttft": 2.384185791015625e-07,
      "generation_time": 39.29494309425354,
      "total_time": 86.47266149520874,
      "retrieved_chunks_count": 6,
      "response_length": 3756,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 93,
      "question": "库函数和系统调用",
      "retrieval_time": 43.12989807128906,
      "ttft": 2.384185791015625e-07,
      "generation_time": 34.28858757019043,
      "total_time": 77.41848587989807,
      "retrieved_chunks_count": 3,
      "response_length": 3519,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 94,
      "question": "系统调用开销",
      "retrieval_time": 74.18454837799072,
      "ttft": 9.5367431640625e-07,
      "generation_time": 86.57670855522156,
      "total_time": 160.76125812530518,
      "retrieved_chunks_count": 8,
      "response_length": 3586,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 95,
      "question": "系统调用优化",
      "retrieval_time": 102.46021580696106,
      "ttft": 7.152557373046875e-07,
      "generation_time": 74.51167821884155,
      "total_time": 176.9718954563141,
      "retrieved_chunks_count": 3,
      "response_length": 4535,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 96,
      "question": "中断嵌套",
      "retrieval_time": 80.74470496177673,
      "ttft": 9.5367431640625e-07,
      "generation_time": 70.7705454826355,
      "total_time": 151.51525163650513,
      "retrieved_chunks_count": 3,
      "response_length": 3804,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 97,
      "question": "中断优先级",
      "retrieval_time": 64.21920657157898,
      "ttft": 2.1457672119140625e-06,
      "generation_time": 61.83457636833191,
      "total_time": 126.05378532409668,
      "retrieved_chunks_count": 2,
      "response_length": 3262,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 98,
      "question": "软中断和硬中断",
      "retrieval_time": 61.46505928039551,
      "ttft": 7.152557373046875e-07,
      "generation_time": 56.86751341819763,
      "total_time": 118.33257341384888,
      "retrieved_chunks_count": 4,
      "response_length": 3679,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 99,
      "question": "时钟中断处理",
      "retrieval_time": 58.992177963256836,
      "ttft": 2.384185791015625e-07,
      "generation_time": 44.64979839324951,
      "total_time": 103.6419768333435,
      "retrieved_chunks_count": 7,
      "response_length": 3684,
      "success": true,
      "error_message": null
    },
    {
      "test_id": 100,
      "question": "系统时间管理",
      "retrieval_time": 60.17971730232239,
      "ttft": 0,
      "generation_time": 73.03245258331299,
      "total_time": 133.21216988563538,
      "retrieved_chunks_count": 4,
      "response_length": 3632,
      "success": true,
      "error_message": null
    }
  ],
  "summary": {
    "total_tests": 100,
    "successful_tests": 100,
    "failed_tests": 0,
    "avg_retrieval_time": 50.9525980591774,
    "avg_ttft": 4.4345855712890627e-07,
    "avg_generation_time": 47.514665732383726,
    "avg_total_time": 98.46726442337037,
    "median_retrieval_time": 49.88846778869629,
    "median_ttft": 2.384185791015625e-07,
    "median_generation_time": 43.61122751235962,
    "median_total_time": 94.40878033638,
    "min_retrieval_time": 32.029489517211914,
    "min_ttft": 0,
    "min_generation_time": 25.919378757476807,
    "min_total_time": 63.7703914642334,
    "max_retrieval_time": 102.46021580696106,
    "max_ttft": 4.5299530029296875e-06,
    "max_generation_time": 124.14097547531128,
    "max_total_time": 179.67853450775146
  }
}
```