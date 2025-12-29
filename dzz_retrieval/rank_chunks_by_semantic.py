import os
import json
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
import numpy as np

# === 配置 ===
BGE_MODEL_PATH = "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/"

def _get_chunks_json_paths() -> List[str]:
    """返回可能存在的 chunks JSON 列表，存在即加载"""
    base = os.path.dirname(__file__)
    candidates = [
        os.path.join(base, "kernel_chunks_with_descriptions.json"),
        os.path.join(base, "mm_treesitter_chunks_with_descriptions.json"),
    ]
    # 兼容项目外层结构
    outer = os.path.dirname(os.path.dirname(base))
    candidates += [
        os.path.join(outer, "dzz_retrieval", "kernel_chunks_with_descriptions.json"),
        os.path.join(outer, "dzz_retrieval", "mm_treesitter_chunks_with_descriptions.json"),
    ]
    # 去重但保持顺序
    seen, ordered = set(), []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered

CHUNKS_JSON_PATHS = _get_chunks_json_paths()

print("🧠 加载 BGE-M3 模型（仅用于 description 语义打分）...")
_embedder = SentenceTransformer(BGE_MODEL_PATH, device="cuda")
_embedder.max_seq_length = 512  # 足够覆盖 description


def _load_one_chunks_json(path: str) -> Dict[str, List[dict]]:
    """加载单个 JSON，返回 {file_path -> [chunks]}，并为每个 chunk 附带标准化 file_path"""
    if not os.path.exists(path):
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    file_to_chunks: Dict[str, List[dict]] = {}
    # 兼容形如 {"directories": {...}} 的结构
    dirs = data.get("directories", {})
    for dir_info in dirs.values():
        for file_info in dir_info.get("files", []):
            src_path = str(file_info.get("file_path", "")).replace("\\", "/")
            if not src_path:
                continue
            file_to_chunks.setdefault(src_path, [])
            for chunk in file_info.get("chunks", []):
                chunk["file_path"] = src_path
                file_to_chunks[src_path].append(chunk)

    return file_to_chunks


def load_chunks_index() -> Dict[str, List[dict]]:
    """
    构建统一的源文件 -> chunks 列表索引（合并多个 JSON）
    e.g. "kernel/acct.c" -> [...], "mm/madvise.c" -> [...]
    """
    merged: Dict[str, List[dict]] = {}
    loaded_files = 0
    used_json = 0

    for path in CHUNKS_JSON_PATHS:
        if not os.path.exists(path):
            continue
        idx = _load_one_chunks_json(path)
        if not idx:
            continue
        used_json += 1
        for k, v in idx.items():
            merged.setdefault(k, []).extend(v)
        loaded_files += len(idx)

    print(f"✅ 已加载 {loaded_files} 个源文件的 chunks 索引（来自 {used_json} 个 JSON）")
    return merged


# 全局索引（启动时加载一次）
CHUNKS_INDEX = load_chunks_index()


def rank_chunks_by_description(query: str, candidate_source_files: List[str], top_k: int = 5) -> List[Dict]:
    """
    对候选源文件中的所有 chunks，按 description 与 query 的语义相似度排序
    Args:
        query: 用户自然语言查询
        candidate_source_files: 阶段1返回的源文件列表（如 ["kernel/acct.c", "mm/madvise.c"]）
        top_k: 返回 top-k chunks
    Returns:
        排序后的 chunk 列表，每个包含 _score 字段
    """
    if not candidate_source_files:
        return []

    # 1. 编码查询
    query_emb = _embedder.encode([query], normalize_embeddings=True)[0]

    # 2. 收集候选 chunks
    all_candidate_chunks = []
    for src_file in candidate_source_files:
        key = str(src_file).replace("\\", "/")
        for chunk in CHUNKS_INDEX.get(key, []):
            desc = chunk.get("description", "").strip()
            if not desc or desc.startswith(("[ERROR", "该块包含头文件")):
                continue
            all_candidate_chunks.append(chunk)

    if not all_candidate_chunks:
        return []

    # 3. 批量编码 descriptions
    descriptions = [c["description"] for c in all_candidate_chunks]
    desc_embs = _embedder.encode(descriptions, normalize_embeddings=True)

    # 4. 相似度与排序
    similarities = (desc_embs @ query_emb).tolist()
    for chunk, score in zip(all_candidate_chunks, similarities):
        chunk["_score"] = float(score)
    sorted_chunks = sorted(all_candidate_chunks, key=lambda x: x["_score"], reverse=True)
    return sorted_chunks[:top_k]


if __name__ == "__main__":
    # 小测
    top_files = ["kernel/acct.c", "mm/madvise.c"]
    query = "Linux 如何实现进程记账和内存回收策略？"
    top_chunks = rank_chunks_by_description(query, top_files, top_k=3)
    print(f"\n🔍 查询: {query}")
    print(f"📂 候选文件: {', '.join(top_files)}\n")
    for i, chunk in enumerate(top_chunks, 1):
        print(f"[{i}] 相似度: {chunk['_score']:.4f}")
        file_path = chunk.get('file_path', 'unknown').replace('\\', '/')
        print(f"    文件: {file_path}")
        print(f"    行号: {chunk.get('start_line', 'N/A')} - {chunk.get('end_line', 'N/A')}")
        print(f"    函数: {chunk.get('function_name', 'N/A')}")
        print(f"    描述: {chunk.get('description', '')[:200]}...\n")