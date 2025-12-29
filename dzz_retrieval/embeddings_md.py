import os
import re
import json
import chromadb
from chromadb.utils import embedding_functions
from tqdm import tqdm

# === 配置 ===
MD_ROOT = "./kernel_docs"
MD_ROOT2= "./mm_docs"
CHROMA_DB_PATH = "./chroma_md"
MODEL_PATH = "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/"

# 忽略 generation_stats.json
IGNORE_FILES = {"generation_stats.json"}

# === 初始化 ChromaDB ===
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)


# 使用本地 BGE-M3 的 dense embedding（sentence-transformers 兼容）
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=MODEL_PATH,
    device="cuda",  # 自动使用 GPU
    normalize_embeddings=True  # BGE 推荐归一化
)

collection = client.create_collection(
    name="mm_file_summaries",
    embedding_function=embedding_fn,
    metadata={"hnsw:space": "cosine"}  # BGE 用 cosine 更好
)

# === 遍历所有 .md 文件 ===
def extract_source_path(md_content: str) -> str:
    """从 md 第一行提取源码路径，统一为 Linux 风格路径"""
    first_line = md_content.split('\n', 1)[0].strip()
    if first_line.startswith("# "):
        path = first_line[2:].strip()
        # 统一路径分隔符为 /
        path = path.replace("\\", "/")
        return path
    return "unknown"

def load_all_md_files(md_root: str):
    md_files = []
    for root, _, files in os.walk(md_root):
        for file in files:
            if file.endswith(".md") and file not in IGNORE_FILES:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, md_root)
                md_files.append((rel_path, full_path))
    return md_files

print("🔍 扫描 .md 文件...")
md_list = load_all_md_files(MD_ROOT2)
print(f"✅ 找到 {len(md_list)} 个 .md 文件")

# === 批量加载并添加到 ChromaDB ===
documents = []
metadatas = []
ids = []

for rel_path, full_path in tqdm(md_list, desc="Loading MD files"):
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not content.strip():
            continue

        # 提取源码路径（作为 ID 和 metadata）
        source_path = extract_source_path(content)
        if source_path == "unknown":
            print(f"⚠️ 无法解析源码路径: {full_path}")
            continue

        # 移除第一行（标题行），保留其余内容作为 document
        body = "\n".join(content.split('\n')[1:]).strip()

        documents.append(body)
        metadatas.append({
            "source_file": source_path,          # kernel/acct.c
            "md_file": rel_path,                 # acct.md 或 bpf/preload/....md
            "type": "file_summary"
        })
        ids.append(source_path)  # 用源码路径作为唯一 ID

    except Exception as e:
        print(f"❌ 加载失败 {full_path}: {e}")

# === 添加到 ChromaDB（自动 batch）===
print("🧠 向量化并存入 ChromaDB...")
collection.add(
    documents=documents,
    metadatas=metadatas,
    ids=ids
)

print(f"✅ 成功向量化 {len(documents)} 个文件摘要")
print(f"💾 ChromaDB 存储路径: {CHROMA_DB_PATH}")