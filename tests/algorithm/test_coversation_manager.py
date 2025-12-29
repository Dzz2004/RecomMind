import pytest
from datetime import datetime

from simple_rag_workflow import ConversationManager, ConversationMessage

def test_add_message_basic():
    cm = ConversationManager(max_history_length=5)

    cm.add_message("user", "hello")
    cm.add_message("assistant", "hi")

    history = cm.get_history()
    assert len(history) == 2

    assert history[0].role == "user"
    assert history[0].content == "hello"
    assert isinstance(history[0].timestamp, datetime)

    assert history[1].role == "assistant"
    assert history[1].content == "hi"

def test_history_truncation_by_max_length():
    cm = ConversationManager(max_history_length=3)

    for i in range(5):
        cm.add_message("user", f"msg-{i}")

    history = cm.get_history()
    assert len(history) == 3

    # Should keep the last 3 messages
    contents = [m.content for m in history]
    assert contents == ["msg-2", "msg-3", "msg-4"]

def test_get_history_last_n():
    cm = ConversationManager()

    for i in range(4):
        cm.add_message("user", f"q{i}")

    last_two = cm.get_history(last_n=2)
    assert len(last_two) == 2
    assert [m.content for m in last_two] == ["q2", "q3"]

def test_get_history_last_n_zero_or_negative():
    cm = ConversationManager()

    cm.add_message("user", "hello")

    assert cm.get_history(last_n=0) == []
    assert cm.get_history(last_n=-1) == []

def test_get_context_string_format():
    cm = ConversationManager()

    cm.add_message("user", "你好")
    cm.add_message("assistant", "你好，有什么可以帮你")

    context = cm.get_context_string()

    assert "用户: 你好" in context
    assert "助手: 你好，有什么可以帮你" in context

def test_get_context_string_empty():
    cm = ConversationManager()
    assert cm.get_context_string() == ""

def test_get_last_user_message():
    cm = ConversationManager()

    cm.add_message("user", "first")
    cm.add_message("assistant", "answer")
    cm.add_message("user", "second")

    last_user = cm.get_last_user_message()
    assert last_user is not None
    assert last_user.content == "second"

def test_clear_conversation():
    cm = ConversationManager()

    cm.add_message("user", "hello")
    cm.add_message("assistant", "hi")

    cm.clear()
    assert cm.get_history() == []
