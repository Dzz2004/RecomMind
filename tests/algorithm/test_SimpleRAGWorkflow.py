import os
from datetime import datetime
from types import SimpleNamespace

import pytest

from simple_rag_workflow import (
    SimpleRAGWorkflow,
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


class FakeTextRAGEngine:
    def __init__(self, responses):
        self._responses = responses
        self.calls = []

    def query(self, query_text, top_k=3):
        self.calls.append((query_text, top_k))
        return self._responses.get(
            query_text,
            {
                "contents": [],
                "similarities": [],
                "file_names": [],
                "sections": [],
                "page_ranges": [],
            },
        )


def build_query_result(contents, similarities, file_names, sections, page_ranges=None):
    page_ranges = page_ranges or [""] * len(contents)
    return {
        "contents": contents,
        "similarities": similarities,
        "file_names": file_names,
        "sections": sections,
        "page_ranges": page_ranges,
    }


def make_chunk(name, score=0.9, round_no=1):
    return RetrievedChunk(
        content=f"{name}-content",
        source=name,
        filename=f"{name}.pdf",
        relative_path=name,
        extension=".pdf",
        score=score,
        metadata={
            "file_name": f"{name}.pdf",
            "section": "sec",
            "page_range": "1-2",
            "similarity": score,
            "query_used": "alpha",
            "round": round_no,
        },
    )


def test_retrieve_documents_with_suggestion_deduplicates_content():
    workflow = SimpleRAGWorkflow.__new__(SimpleRAGWorkflow)
    workflow.rag_engine = FakeTextRAGEngine(
        {
            "alpha": build_query_result(
                ["DOC1", "DOC_DUP"],
                [0.95, 0.9],
                ["a.pdf", "dup.pdf"],
                ["secA", "secDup"],
                ["1-2", "3-4"],
            ),
            "beta": build_query_result(
                ["DOC_DUP", "DOC3"],
                [0.88, 0.86],
                ["dup.pdf", "c.pdf"],
                ["secDup", "secC"],
                ["3-4", "5-6"],
            ),
            "orig": build_query_result(
                ["ORIG"],
                [0.8],
                ["orig.pdf"],
                ["secO"],
                ["7-8"],
            ),
        }
    )

    suggestion = RetrievalSuggestion(
        original_query="orig",
        intent="信息查询",
        confidence=0.7,
        search_keywords=["alpha"],
        suggested_queries=["alpha", "beta"],
        reasoning="",
    )

    chunks = workflow._retrieve_documents_with_suggestion(suggestion)

    assert workflow.rag_engine.calls == [("alpha", 3), ("beta", 3), ("orig", 3)]
    assert len(chunks) == 4
    assert chunks[0].metadata["query_used"] == "alpha"
    assert chunks[-1].metadata["query_used"] == "orig"
    assert len({chunk.content for chunk in chunks}) == 4  # 去重成功


def test_process_user_query_triggers_second_round_when_insufficient():
    workflow = SimpleRAGWorkflow.__new__(SimpleRAGWorkflow)
    workflow.conversation_manager = DummyConversationManager()
    workflow.rag_engine = FakeTextRAGEngine(
        {
            "delta": build_query_result(
                ["DELTA_DOC"],
                [0.91],
                ["delta.pdf"],
                ["secD"],
                ["9-10"],
            )
        }
    )
    workflow.retrieval_suggester = SimpleNamespace(
        generate_suggestion=lambda user_query, history: RetrievalSuggestion(
            original_query="orig",
            intent="信息查询",
            confidence=0.8,
            search_keywords=["alpha"],
            suggested_queries=["alpha"],
            reasoning="",
        )
    )

    first_round_chunks = [make_chunk("alpha_chunk", 0.93, round_no=1)]
    workflow._retrieve_documents_with_suggestion = lambda suggestion: list(first_round_chunks)

    judge_calls = []

    def fake_judge(user_query, chunks):
        judge_calls.append([chunk.metadata.get("round") for chunk in chunks])
        return [True] * len(chunks)

    workflow._judge_chunk_relevance = fake_judge
    workflow._judge_sufficiency_and_suggest_keywords = lambda user_query, chunks: {
        "is_sufficient": False,
        "new_keywords": ["delta"],
        "reasoning": "",
    }
    workflow._generate_response_with_context = (
        lambda user_query, chunks, token_callback=None: "final answer"
    )

    response = workflow.process_user_query("explain mmap second round")

    assert workflow.rag_engine.calls == [("delta", 3)]
    assert len(response.retrieved_chunks) == 2
    assert response.retrieved_chunks[-1].metadata["round"] == 2
    assert response.llm_response == "final answer"
    assert judge_calls == [[1], [2]]
    assert workflow.conversation_manager.get_history()[-1].role == "assistant"


def test_process_user_query_skips_second_round_when_sufficient():
    workflow = SimpleRAGWorkflow.__new__(SimpleRAGWorkflow)
    workflow.conversation_manager = DummyConversationManager()
    workflow.rag_engine = FakeTextRAGEngine({})
    workflow.retrieval_suggester = SimpleNamespace(
        generate_suggestion=lambda user_query, history: RetrievalSuggestion(
            original_query="orig",
            intent="信息查询",
            confidence=0.8,
            search_keywords=["alpha"],
            suggested_queries=["alpha"],
            reasoning="",
        )
    )

    first_round_chunks = [make_chunk("alpha_chunk", 0.93, round_no=1)]
    workflow._retrieve_documents_with_suggestion = lambda suggestion: list(first_round_chunks)
    workflow._judge_chunk_relevance = lambda user_query, chunks: [True] * len(chunks)
    workflow._judge_sufficiency_and_suggest_keywords = lambda user_query, chunks: {
        "is_sufficient": True,
        "new_keywords": [],
        "reasoning": "",
    }

    response_calls = {"count": 0}

    def fake_generate_response(user_query, chunks, token_callback=None):
        response_calls["count"] += 1
        return "succinct answer"

    workflow._generate_response_with_context = fake_generate_response

    response = workflow.process_user_query("no second round needed")

    assert workflow.rag_engine.calls == []
    assert response.retrieved_chunks == first_round_chunks
    assert response.llm_response == "succinct answer"
    assert response_calls["count"] == 1
    assert workflow.conversation_manager.get_history()[-1].role == "assistant"