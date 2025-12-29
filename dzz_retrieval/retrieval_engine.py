import os
import json
import time
from typing import List, Dict, Any, Optional, Tuple

import chromadb
from chromadb.utils import embedding_functions

from .rank_chunks_by_semantic import rank_chunks_by_description


class RetrievalEngine:
    def __init__(
        self,
        chroma_md_path: str = "./chroma_md",
        bge_model_path: str = "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/",
        top_files: int = 3,
        top_chunks: int = 5,
        output_dir: str = "./retrieval_results",
        collections: Optional[Dict[str, str]] = None,
    ):
        """
        collections: 可选，形如 {"kernel_file_summaries": "kernel", "mm_file_summaries": "mm"}
        - key: Chroma 集合名
        - value: 该集合对应源码前缀（与 chunks JSON 的 file_path 前缀一致）
        若为 None，则尝试加载上述两个默认集合，存在即启用。
        """
        self.top_files = top_files
        self.top_chunks = top_chunks
        self.output_dir = output_dir
        self.result_path_last: Optional[str] = None
        os.makedirs(output_dir, exist_ok=True)

        # 初始化 ChromaDB 与嵌入函数
        self.client = chromadb.PersistentClient(path=chroma_md_path)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=bge_model_path,
            device="cuda",
            normalize_embeddings=True
        )

        # 解析并加载集合
        default_map: Dict[str, str] = {
            "kernel_file_summaries": "kernel",
            "mm_file_summaries": "mm",
        }
        self._domain_map: Dict[str, str] = collections or default_map
        self._collections: List[Tuple[str, chromadb.api.models.Collection.Collection]] = []

        for coll_name, prefix in self._domain_map.items():
            try:
                coll = self.client.get_collection(
                    name=coll_name,
                    embedding_function=self.embedding_fn
                )
                self._collections.append((prefix, coll))
            except Exception:
                # 集合可能不存在，跳过
                continue

        if not self._collections:
            raise RuntimeError("未找到任何可用的 Chroma 集合，请先构建向量库或检查集合名称。")

        total = sum(c.count() for _, c in self._collections)
        enabled = ", ".join([f"{p}:{c.name}" for p, c in self._collections])
        print(f"✅ RetrievalEngine 初始化完成，启用集合: {enabled}，总文件数: {total}")

    def get_collections_info(self) -> Dict[str, int]:
        """返回当前启用的集合及其文件数"""
        info = {}
        for prefix, coll in self._collections:
            info[f"{prefix}:{coll.name}"] = coll.count()
        return info

    def retrieve(self, query: str) -> Dict[str, Any]:
        """
        完整两阶段检索，返回结构化结果
        {
            "query": "...",
            "timestamp": "...",
            "retrieved_files": [
                {
                    "source_file": "kernel/acct.c" | "mm/madvise.c" | ...,
                    "md_summary": "...",
                    "similarity": 0.85,
                    "chunks": [
                        {
                            "chunk_id": 3,
                            "file_path": "kernel/acct.c",
                            "start_line": 544,
                            "end_line": 644,
                            "function_name": "...",
                            "description": "...",
                            "similarity": 0.89
                        }
                    ]
                }
            ]
        }
        """
        # === 阶段1：跨多个集合的文件召回并全局合并 Top-K ===
        merged_hits: List[Dict[str, Any]] = []
        per_domain_k = max(self.top_files, 5)  # 适度过采样，便于全局合并

        for prefix, coll in self._collections:
            try:
                md_results = coll.query(
                    query_texts=[query],
                    n_results=per_domain_k,
                    include=["documents", "metadatas", "distances"]
                )
            except Exception:
                continue

            docs = md_results.get("documents", [[]])[0]
            metas = md_results.get("metadatas", [[]])[0]
            dists = md_results.get("distances", [[]])[0]

            for doc, meta, dist in zip(docs, metas, dists):
                raw_src = str(meta.get("source_file", "")).replace("\\", "/").lstrip("/")
                # 若未带前缀，则补齐 prefix；已带前缀则保持
                if raw_src and not raw_src.startswith(prefix + "/"):
                    source_file = f"{prefix}/{raw_src}"
                else:
                    source_file = raw_src or prefix

                merged_hits.append({
                    "source_file": source_file,
                    "md_summary": doc,
                    "similarity": 1 - float(dist),
                })

        merged_hits.sort(key=lambda x: x["similarity"], reverse=True)
        top_file_hits = merged_hits[: self.top_files]

        retrieved_files: List[Dict[str, Any]] = [
            {
                "source_file": h["source_file"],
                "md_summary": h["md_summary"],
                "similarity": h["similarity"],
                "chunks": []
            }
            for h in top_file_hits
        ]
        candidate_source_files = [h["source_file"] for h in top_file_hits]

        # === 阶段2：在候选文件中按 description 语义打分，返回该文件 Top-N chunks ===
        all_top_chunks = rank_chunks_by_description(query, candidate_source_files, top_k=1000)

        # 按文件分组并截断
        file_to_chunks: Dict[str, List[Dict[str, Any]]] = {}
        for chunk in all_top_chunks:
            src_file = str(chunk.get("file_path", "")).replace("\\", "/")
            if not src_file:
                continue
            file_to_chunks.setdefault(src_file, []).append({
                "chunk_id": chunk["chunk_id"],
                "file_path": chunk["file_path"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "content": chunk.get("content", ""),
                "function_name": chunk.get("function_name", "N/A"),
                "description": chunk.get("description", ""),
                "similarity": chunk["_score"],
            })

        # 填充到检索结果中
        for item in retrieved_files:
            src = item["source_file"].replace("\\", "/")
            item["chunks"] = file_to_chunks.get(src, [])[: self.top_chunks]

        # === 构建最终结果 ===
        result = {
            "query": query,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "retrieved_files": retrieved_files
        }

        # === 保存 JSON ===
        safe_query = "".join(c if c.isalnum() else "_" for c in query[:30])
        file_name = f"result_{safe_query}_{int(time.time())}.json"
        out_path = os.path.join(self.output_dir, file_name)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        self.result_path_last = out_path

        return result

    @staticmethod
    def print_retrieval_summary(result: Dict[str, Any]):
        print(f"Query: {result.get('query')}")
        print(f"Time: {result.get('timestamp')}")
        for i, item in enumerate(result.get("retrieved_files", []), 1):
            print(f"\n[{i}] 源文件: {item.get('source_file')}")
            print(f"     相似度: {item.get('similarity'):.4f}")
            md = item.get("md_summary", "")
            print(f"     摘要预览:\n{md[:300]}{'...' if len(md) > 300 else ''}")
            for j, c in enumerate(item.get("chunks", []), 1):
                print(f"  - Chunk {j}: {c.get('function_name', 'N/A')}  "
                      f"({c.get('start_line', 'N/A')}-{c.get('end_line', 'N/A')})  "
                      f"score={c.get('similarity', 0):.4f}")

# === 交互 Demo ===
if __name__ == "__main__":
    engine = RetrievalEngine(
        chroma_md_path="./chroma_md",
        top_files=3,
        top_chunks=3,
        output_dir="./retrieval_results",
        # 可显式传入或用默认：kernel+mm 有哪个加载哪个
        # collections={"kernel_file_summaries":"kernel", "mm_file_summaries":"mm"}
    )

    print("🚀 Linux 内核教学检索系统 (RAG 上下文生成器)")
    print("输入自然语言问题（如 'Linux 如何实现进程记账？'），输入 'quit' 退出\n")

    while True:
        query = input("❓ Query > ").strip()
        if query.lower() in {"quit", "exit", "q"}:
            break
        if not query:
            continue

        try:
            result = engine.retrieve(query)
            print("\n✅ 检索完成！返回结构化上下文（可用于下游 LLM）：")
            engine.print_retrieval_summary(result)
            print("\n" + "=" * 80 + "\n")
        except Exception as e:
            print(f"❌ 检索失败: {e}")