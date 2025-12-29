import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest


class FakeCollection:
    def __init__(self, name: str, count_value: int, query_result: Dict[str, List[List[Any]]]):
        self.name = name
        self._count_value = count_value
        self._query_result = query_result
        self.last_query_kwargs = None

    def count(self) -> int:
        return self._count_value

    def query(self, **kwargs):
        # record call for verification (e.g., n_results)
        self.last_query_kwargs = kwargs
        return self._query_result


class FakeClient:
    def __init__(self, collections_map):
        self._collections_map = collections_map

    def get_collection(self, name, embedding_function=None):
        if name not in self._collections_map:
            raise Exception("no such collection")
        return self._collections_map[name]


class DummyEmbeddingFn:
    def __init__(self, model_name=None, device=None, normalize_embeddings=None):
        self.model_name = model_name
        self.device = device
        self.normalize_embeddings = normalize_embeddings


@pytest.fixture
def patch_re_engine(monkeypatch, tmp_path):
    """
    Patch RetrievalEngine dependencies:
    - chromadb.PersistentClient -> FakeClient
    - embedding_functions.SentenceTransformerEmbeddingFunction -> DummyEmbeddingFn
    Returns a helper to build engines with desired fake collections.
    """
    import dzz_retrieval.retrieval_engine as re_mod

    def _builder(collections_map: Dict[str, FakeCollection]):
        # Patch chromadb.PersistentClient to return our FakeClient
        class _ChromadbShim:
            @staticmethod
            def PersistentClient(path=None):
                return FakeClient(collections_map)

        # Apply monkeypatches to the module attributes used by RetrievalEngine
        monkeypatch.setattr(re_mod, "chromadb", _ChromadbShim, raising=True)
        
        class _EmbeddingShim:
            @staticmethod
            def SentenceTransformerEmbeddingFunction(**kwargs):
                return DummyEmbeddingFn(**kwargs)

        monkeypatch.setattr(re_mod, "embedding_functions", _EmbeddingShim, raising=True)
        return re_mod

    return _builder


def build_query_result(docs, metas, dists):
    # Shape as expected by RetrievalEngine: first element list for batch of 1 query
    return {
        "documents": [docs],
        "metadatas": [metas],
        "distances": [dists],
    }


def test_init_raises_when_no_collections(monkeypatch, tmp_path, patch_re_engine):
    re_mod = patch_re_engine({})
    from dzz_retrieval.retrieval_engine import RetrievalEngine

    with pytest.raises(RuntimeError):
        RetrievalEngine(chroma_md_path="/dev/null", output_dir=str(tmp_path))


def test_init_and_get_collections_info(monkeypatch, tmp_path, patch_re_engine, capsys):
    # Two collections: kernel and mm
    kernel = FakeCollection(
        name="kernel_file_summaries",
        count_value=2,
        query_result=build_query_result([], [], []),
    )
    mm = FakeCollection(
        name="mm_file_summaries",
        count_value=3,
        query_result=build_query_result([], [], []),
    )
    re_mod = patch_re_engine({
        "kernel_file_summaries": kernel,
        "mm_file_summaries": mm,
    })
    from dzz_retrieval.retrieval_engine import RetrievalEngine

    engine = RetrievalEngine(chroma_md_path="/dev/null", output_dir=str(tmp_path))
    info = engine.get_collections_info()

    # Expect keys formatted as "prefix:collection_name"
    assert info["kernel:kernel_file_summaries"] == 2
    assert info["mm:mm_file_summaries"] == 3

    # Also ensure the init print occurred
    captured = capsys.readouterr()
    assert "RetrievalEngine 初始化完成" in captured.out


def test_retrieve_merging_ranking_and_output(monkeypatch, tmp_path, patch_re_engine):
    # Prepare fake collections with query results
    # Distances: smaller -> more similar; engine uses similarity = 1 - dist
    kernel_docs = ["KDOC1", "KDOC2"]
    kernel_metas = [
        {"source_file": "acct.c"},          # will be prefixed to kernel/acct.c
        {"source_file": "kernel/sched.c"},  # already prefixed
    ]
    kernel_dists = [0.2, 0.4]  # sims: 0.8, 0.6

    mm_docs = ["MDOC1"]
    mm_metas = [
        {"source_file": "mm\\mmap.c"},    # backslash path -> normalized to mm/mmap.c
    ]
    mm_dists = [0.1]  # sim: 0.9 (top1)

    kernel = FakeCollection(
        name="kernel_file_summaries",
        count_value=10,
        query_result=build_query_result(kernel_docs, kernel_metas, kernel_dists),
    )
    mm = FakeCollection(
        name="mm_file_summaries",
        count_value=8,
        query_result=build_query_result(mm_docs, mm_metas, mm_dists),
    )

    re_mod = patch_re_engine({
        "kernel_file_summaries": kernel,
        "mm_file_summaries": mm,
    })

    # Patch ranker to return chunks for the selected files
    def fake_rank(query, candidate_files, top_k=1000):
        # Expect candidate_files include: mm/mmap.c (sim 0.9), kernel/acct.c (sim 0.8)
        assert "mm/mmap.c" in candidate_files
        assert "kernel/acct.c" in candidate_files
        return [
            {
                "chunk_id": 1,
                "file_path": "mm/mmap.c",
                "start_line": 10,
                "end_line": 20,
                "content": "...",
                "function_name": "foo",
                "description": "desc1",
                "_score": 0.95,
            },
            {
                "chunk_id": 2,
                "file_path": "mm/mmap.c",
                "start_line": 30,
                "end_line": 60,
                "content": "...",
                "function_name": "bar",
                "description": "desc2",
                "_score": 0.90,
            },
            {
                "chunk_id": 3,
                "file_path": "kernel/acct.c",
                "start_line": 100,
                "end_line": 120,
                "content": "...",
                "function_name": "baz",
                "description": "desc3",
                "_score": 0.88,
            },
            {
                "chunk_id": 4,
                "file_path": "kernel/acct.c",
                "start_line": 200,
                "end_line": 240,
                "content": "...",
                "function_name": "qux",
                "description": "desc4",
                "_score": 0.70,
            },
            # extra chunk beyond top_chunks to test truncation
            {
                "chunk_id": 5,
                "file_path": "kernel/acct.c",
                "start_line": 300,
                "end_line": 340,
                "content": "...",
                "function_name": "extra",
                "description": "desc5",
                "_score": 0.60,
            },
        ]

    monkeypatch.setattr(re_mod, "rank_chunks_by_description", fake_rank, raising=True)

    from dzz_retrieval.retrieval_engine import RetrievalEngine

    out_dir = tmp_path / "results"
    engine = RetrievalEngine(
        chroma_md_path="/dev/null",
        top_files=2,
        top_chunks=2,
        output_dir=str(out_dir),
    )

    result = engine.retrieve("query: mmap & acct")

    # Verify merged and sorted files: mm/mmap.c (0.9), kernel/acct.c (0.8)
    files = [f["source_file"] for f in result["retrieved_files"]]
    assert files == ["mm/mmap.c", "kernel/acct.c"]

    # Verify top_chunks truncation per file
    for item in result["retrieved_files"]:
        assert len(item["chunks"]) == 2

    # Ensure JSON output was written correctly
    assert engine.result_path_last is not None
    out_path = Path(engine.result_path_last)
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["query"] == "query: mmap & acct"

    # Verify per_domain_k logic: max(top_files, 5) -> 5
    assert kernel.last_query_kwargs is not None
    assert kernel.last_query_kwargs["n_results"] == 5
    assert mm.last_query_kwargs["n_results"] == 5


def test_retrieve_no_hits_writes_empty_structure(monkeypatch, tmp_path, patch_re_engine):
    empty = build_query_result([], [], [])
    kernel = FakeCollection("kernel_file_summaries", 0, empty)
    re_mod = patch_re_engine({"kernel_file_summaries": kernel})

    # ranker should still be called with empty candidate list; return empty
    monkeypatch.setattr(re_mod, "rank_chunks_by_description", lambda q, files, top_k=1000: [], raising=True)

    from dzz_retrieval.retrieval_engine import RetrievalEngine

    out_dir = tmp_path / "results"
    engine = RetrievalEngine(
        chroma_md_path="/dev/null",
        top_files=2,
        top_chunks=2,
        output_dir=str(out_dir),
    )

    result = engine.retrieve("no hits")
    assert result["retrieved_files"] == []
    assert Path(engine.result_path_last).exists()


def test_print_retrieval_summary_outputs(capsys):
    from dzz_retrieval.retrieval_engine import RetrievalEngine

    dummy = {
        "query": "hello",
        "timestamp": "2025-01-01 00:00:00",
        "retrieved_files": [
            {
                "source_file": "mm/mmap.c",
                "md_summary": "This is a summary",
                "similarity": 0.9876,
                "chunks": [
                    {
                        "function_name": "func",
                        "start_line": 1,
                        "end_line": 2,
                        "similarity": 0.9,
                    }
                ],
            }
        ],
    }

    RetrievalEngine.print_retrieval_summary(dummy)
    out = capsys.readouterr().out
    assert "Query: hello" in out
    assert "Time: 2025-01-01" in out
    assert "源文件: mm/mmap.c" in out
    assert "摘要预览" in out
    assert "Chunk 1" in out
