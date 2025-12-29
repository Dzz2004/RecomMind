import json
import pytest

from simple_rag_workflow import (
    RetrievalSuggester,
    CodeRetrievalSuggester,
    RetrievalSuggestion,
)

def _expected_default_intent(instance):
    """Return the fallback intent emitted when parsing fails."""
    if isinstance(instance, RetrievalSuggester):
        return "信息查询"
    if isinstance(instance, CodeRetrievalSuggester):
        return "函数查找"
    raise AssertionError("Unknown suggester type")


@pytest.fixture(params=[
    RetrievalSuggester,
    CodeRetrievalSuggester,
])
def suggester(request):
    """
    Build suggester without real model/tokenizer.
    Only parsing / cleaning logic is tested.
    """
    cls = request.param
    try:
        instance = cls.__new__(cls)
        return instance
    except Exception as e:
        pytest.skip(f"Could not instantiate {cls.__name__}: {e}")

def test_clean_response_text_removes_markers(suggester):
    raw = """
    ```json
    {
      "intent": "函数查找",
      "confidence": 0.9
    }
    ```
    """

    cleaned = suggester._clean_response_text(raw)

    assert "```" not in cleaned
    assert "json" not in cleaned
    assert "intent" in cleaned

def test_parse_response_valid_json(suggester):
    response = json.dumps({
        "intent": "函数查找",
        "confidence": 0.85,
        "search_keywords": ["mmap", "vm"],
        "suggested_queries": ["linux mmap"],
        "reasoning": "测试用例"
    })

    suggestion = suggester._parse_response("origin query", response)

    assert isinstance(suggestion, RetrievalSuggestion)
    assert suggestion.intent == "函数查找"
    assert suggestion.confidence == 0.85
    assert suggestion.search_keywords == ["mmap", "vm"]
    assert suggestion.suggested_queries == ["linux mmap"]

def test_parse_response_missing_fields(suggester):
    response = json.dumps({
        "intent": "函数查找"
    })

    suggestion = suggester._parse_response("fallback", response)

    assert suggestion.intent == _expected_default_intent(suggester)
    assert suggestion.confidence == 0.5
    assert suggestion.search_keywords == ["fallback"]
    assert suggestion.suggested_queries == ["fallback"]

def test_parse_response_wrapped_json(suggester):
    response = """
    这是模型的回答：
    ```json
    {
      "intent": "概念解释",
      "confidence": 0.7,
      "search_keywords": ["虚拟内存"]
    }
    ```
    """

    suggestion = suggester._parse_response("vm", response)

    assert suggestion.intent == _expected_default_intent(suggester)
    assert suggestion.search_keywords == ["vm"]

def test_parse_response_invalid_json(suggester):
    response = "这不是 JSON"

    suggestion = suggester._parse_response("raw query", response)

    assert suggestion.intent == _expected_default_intent(suggester)
    assert suggestion.search_keywords == ["raw query"]
    assert suggestion.suggested_queries == ["raw query"]

def test_parse_response_empty_keywords(suggester):
    response = json.dumps({
        "intent": "函数查找",
        "confidence": 0.9,
        "search_keywords": [],
        "suggested_queries": []
    })

    suggestion = suggester._parse_response("default", response)

    assert suggestion.search_keywords == ["default"]
    assert suggestion.suggested_queries == ["default"]