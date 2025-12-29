from dzz_retrieval import RetrievalEngine

class CodeRAGWorkFlow:
    def __init__(self) -> None:
        self.engine = RetrievalEngine(
            chroma_md_path="dzz_retrieval/chroma_md"
        )

    def run(self, query: str):
        return self.engine.retrieve(query)
    
if __name__ == "__main__":
    workflow = CodeRAGWorkFlow()
    query = "解释linux的内存管理机制"
    results = workflow.run(query)
    for result in results:
        print(result)