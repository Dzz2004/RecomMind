import chromadb
from chromadb.utils import embedding_functions
import os

# === 配置 ===
CHROMA_DB_PATH = "./chroma_md"
MODEL_PATH = "/home/ubuntu/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/5617a9f61b028005a4858fdac845db406aefb181/"

# === 初始化 ===
client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=MODEL_PATH,
    device="cuda",
    normalize_embeddings=True
)

collection = client.get_collection(
    name="kernel_file_summaries",
    embedding_function=embedding_fn
)

print("🔍 已加载 kernel 文件摘要向量库")
print(f"📊 总文档数: {collection.count()}")
print("\n请输入自然语言查询（输入 'quit' 退出）：\n")

# === 交互式测试 ===
while True:
    query = input("Query > ").strip()
    if query.lower() in {"quit", "exit", "q"}:
        break
    if not query:
        continue

    try:
        results = collection.query(
            query_texts=[query],
            n_results=5,  # top-5 文件
            include=["documents", "metadatas", "distances"]
        )

        print("\n" + "="*80)
        for i, (doc, meta, dist) in enumerate(zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        )):
            source_file = meta['source_file']
            score = 1 - dist  # cosine similarity ≈ 1 - distance
            print(f"\n[{i+1}] 源文件: {source_file}")
            print(f"     相似度: {score:.4f}")
            print(f"     摘要预览:\n{doc[:300]}{'...' if len(doc) > 300 else ''}\n")

        print("="*80 + "\n")

        

    except Exception as e:
        print(f"❌ 检索出错: {e}")