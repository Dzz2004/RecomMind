import os
from datetime import datetime
from types import SimpleNamespace

import pytest

from simple_rag_workflow import (
    CodeRAGWorkflow,
    RetrievedChunk,
    RetrievalSuggestion,
    ConversationMessage,
)


class DummyConversationManager:
    def __init__(self):
        self.messages = []

    def add_message(self, role, content, metadata=None):
        self.messages.append(
            ConversationMessage(
                role=role,
                content=content,
                timestamp=datetime.now(),
                metadata=metadata or {},
            )
        )

    def get_history(self, last_n=None):
        if last_n is None or last_n <= 0:
            return list(self.messages)
        return self.messages[-last_n:]

    def clear(self):
        self.messages.clear()


class FakeRetrievalEngine:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    def retrieve(self, query):
        self.calls.append(query)
        return self._responses.get(query, {"retrieved_files": []})


def make_retrieval_response(source_file, chunk_specs):
    return {
        "retrieved_files": [
            {
                "source_file": source_file,
                "chunks": [
                    {
                        "chunk_id": spec["chunk_id"],
                        "file_path": source_file,
                        "start_line": spec.get("start", 1),
                        "end_line": spec.get("end", 10),
                        "content": spec.get("content", f"{source_file}:{spec['chunk_id']}"),
                        "function_name": spec.get("function", "fn"),
                        "description": spec.get("description", ""),
                        "language": spec.get("language", "c"),
                        "similarity": spec["similarity"],
                    }
                    for spec in chunk_specs
                ],
            }
        ]
    }


def make_chunk(file_path, chunk_id, score, round_no):
    return RetrievedChunk(
        content=f"{file_path}:{chunk_id}",
        source=file_path,
        filename=os.path.basename(file_path),
        relative_path=file_path,
        extension=".c",
        score=score,
        metadata={
            "file_name": os.path.basename(file_path),
            "file_path": file_path,
            "chunk_id": chunk_id,
            "round": round_no,
            "function_name": "fn",
        },
    )


def test_convert_retrieval_output_preserves_metadata():
    workflow = CodeRAGWorkflow.__new__(CodeRAGWorkflow)
    response = make_retrieval_response(
        "mm/mmap.c",
        [
            {"chunk_id": "m1", "similarity": 0.9, "function": "mmap_init"},
            {"chunk_id": "m2", "similarity": 0.7, "function": "mmap_do"},
        ],
    )

    chunks = workflow._convert_retrieval_output(response, "vm search", round_no=2)

    assert len(chunks) == 2
    assert chunks[0].metadata["round"] == 2
    assert chunks[0].metadata["query_used"] == "vm search"
    assert chunks[0].metadata["function_name"] == "mmap_init"


def test_retrieve_code_with_suggestion_deduplicates_queries():
    workflow = CodeRAGWorkflow.__new__(CodeRAGWorkflow)
    workflow._retrieved_file_summaries = {}
    workflow.top_files = 3
    workflow.top_chunks = 5
    workflow.code_rag_engine = None

    responses = {
        "alpha": make_retrieval_response("mm/a.c", [{"chunk_id": "mm_a", "similarity": 0.95}]),
        "beta": make_retrieval_response("kernel/b.c", [{"chunk_id": "k_b", "similarity": 0.92}]),
        "orig": make_retrieval_response("mm/a.c", [{"chunk_id": "mm_a", "similarity": 0.80}]),
    }
    workflow.retrieval_engine = FakeRetrievalEngine(responses)

    suggestion = RetrievalSuggestion(
        original_query="orig",
        intent="函数查找",
        confidence=0.9,
        search_keywords=["vm"],
        suggested_queries=["alpha", "alpha", "beta"],
        reasoning="",
    )

    chunks = workflow._retrieve_code_with_suggestion(suggestion)

    assert workflow.retrieval_engine.calls == ["alpha", "beta", "orig"]
    assert len(chunks) == 2  # duplicate chunk_id filtered
    assert {chunk.metadata["file_path"] for chunk in chunks} == {"mm/a.c", "kernel/b.c"}


def test_process_code_query_triggers_second_round_when_insufficient():
    workflow = CodeRAGWorkflow.__new__(CodeRAGWorkflow)
    workflow.conversation_manager = DummyConversationManager()
    workflow._retrieved_file_summaries = {}
    workflow.retrieval_engine = None
    workflow.code_rag_engine = None

    suggestion = RetrievalSuggestion(
        original_query="orig",
        intent="函数查找",
        confidence=0.8,
        search_keywords=["vm"],
        suggested_queries=["alpha"],
        reasoning="",
    )
    workflow.code_retrieval_suggester = SimpleNamespace(
        generate_suggestion=lambda user_query, history: suggestion
    )

    first_round_chunks = [make_chunk("mm/a.c", "c1", 0.9, 1)]
    second_round_chunks = [make_chunk("kernel/b.c", "c2", 0.88, 2)]

    workflow._retrieve_code_with_suggestion = lambda s: list(first_round_chunks)
    workflow._judge_sufficiency_and_suggest_keywords = (
        lambda user_query, chunks: {"is_sufficient": False, "new_keywords": ["extra"], "reasoning": ""}
    )

    keyword_call = {}

    def fake_second_round(keywords, seen_chunk_ids):
        keyword_call["keywords"] = keywords
        return list(second_round_chunks)

    workflow._retrieve_code_with_keywords = fake_second_round
    workflow._generate_response_with_context = (
        lambda user_query, chunks, token_callback=None: "final answer"
    )

    response = workflow.process_code_query("explain mmap")

    assert keyword_call["keywords"] == ["extra"]
    assert response.retrieved_chunks == first_round_chunks + second_round_chunks
    history = workflow.conversation_manager.get_history()
    assert history[-1].role == "assistant"
    assert response.llm_response == "final answer"


def test_process_code_query_skips_second_round_when_sufficient():
    workflow = CodeRAGWorkflow.__new__(CodeRAGWorkflow)
    workflow.conversation_manager = DummyConversationManager()
    workflow._retrieved_file_summaries = {}
    workflow.retrieval_engine = None
    workflow.code_rag_engine = None

    suggestion = RetrievalSuggestion(
        original_query="orig",
        intent="函数查找",
        confidence=0.8,
        search_keywords=["vm"],
        suggested_queries=["alpha"],
        reasoning="",
    )
    workflow.code_retrieval_suggester = SimpleNamespace(
        generate_suggestion=lambda user_query, history: suggestion
    )

    first_round_chunks = [make_chunk("mm/a.c", "c1", 0.9, 1)]
    workflow._retrieve_code_with_suggestion = lambda s: list(first_round_chunks)
    workflow._judge_sufficiency_and_suggest_keywords = (
        lambda user_query, chunks: {"is_sufficient": True, "new_keywords": [], "reasoning": ""}
    )

    called = {"count": 0}

    def fail_if_called(*args, **kwargs):
        called["count"] += 1
        return []

    workflow._retrieve_code_with_keywords = fail_if_called
    workflow._generate_response_with_context = (
        lambda user_query, chunks, token_callback=None: "succinct answer"
    )

    response = workflow.process_code_query("need nothing more")

    assert called["count"] == 0
    assert response.retrieved_chunks == first_round_chunks
    assert response.llm_response == "succinct answer"