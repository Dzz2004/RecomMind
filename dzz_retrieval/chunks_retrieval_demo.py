import chromadb
from chromadb.utils import embedding_functions
import os
from rank_chunks_by_semantic import rank_chunks_by_description

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

        top_files = [meta['source_file'] for meta in results['metadatas'][0]]
        #为每个filepath加上kernel/前缀
        top_files = [os.path.join("kernel", f) for f in top_files]
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


    except Exception as e:
        print(f"❌ 检索出错: {e}")