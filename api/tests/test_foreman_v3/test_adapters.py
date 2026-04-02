"""
Tests for foreman_v3.adapters module.

Tests message format conversion between ORM and LangGraph.
"""

import pytest
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage, AIMessage

from foreman_v3.adapters import (
    orm_to_langgraph,
    langgraph_to_context,
    langgraph_to_orm_style,
    get_last_user_message,
)


class MockMessage:
    """Mock Message ORM object."""

    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content


class TestOrmToLanggraph:
    """Tests for orm_to_langgraph function."""

    def test_empty_list_returns_empty(self):
        result = orm_to_langgraph([])
        assert result == []

    def test_converts_user_message(self):
        msgs = [MockMessage("user", "Hello")]
        result = orm_to_langgraph(msgs)
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "Hello"

    def test_converts_assistant_message(self):
        msgs = [MockMessage("assistant", "Hi there!")]
        result = orm_to_langgraph(msgs)
        assert len(result) == 1
        assert isinstance(result[0], AIMessage)
        assert result[0].content == "Hi there!"

    def test_converts_mixed_messages(self):
        msgs = [
            MockMessage("user", "Hello"),
            MockMessage("assistant", "Hi!"),
            MockMessage("user", "How are you?"),
        ]
        result = orm_to_langgraph(msgs)
        assert len(result) == 3
        assert isinstance(result[0], HumanMessage)
        assert isinstance(result[1], AIMessage)
        assert isinstance(result[2], HumanMessage)

    def test_skips_unknown_roles(self):
        msgs = [
            MockMessage("user", "Hello"),
            MockMessage("system", "System message"),
            MockMessage("assistant", "Hi!"),
        ]
        result = orm_to_langgraph(msgs)
        assert len(result) == 2

    def test_preserves_message_order(self):
        msgs = [
            MockMessage("user", "First"),
            MockMessage("assistant", "Second"),
            MockMessage("user", "Third"),
        ]
        result = orm_to_langgraph(msgs)
        assert result[0].content == "First"
        assert result[1].content == "Second"
        assert result[2].content == "Third"


class TestLanggraphToContext:
    """Tests for langgraph_to_context function."""

    def test_empty_list_returns_empty_string(self):
        result = langgraph_to_context([])
        assert result == ""

    def test_single_message_excluded_by_default(self):
        msgs = [HumanMessage(content="Hello")]
        result = langgraph_to_context(msgs, exclude_last=True)
        assert result == ""

    def test_single_message_included_when_not_excluded(self):
        msgs = [HumanMessage(content="Hello")]
        result = langgraph_to_context(msgs, exclude_last=False)
        assert result == "User: Hello"

    def test_formats_user_messages(self):
        msgs = [
            HumanMessage(content="Hello"),
            AIMessage(content="Response"),
        ]
        result = langgraph_to_context(msgs, exclude_last=False)
        assert "User: Hello" in result

    def test_formats_assistant_messages(self):
        msgs = [
            HumanMessage(content="Hello"),
            AIMessage(content="Response"),
        ]
        result = langgraph_to_context(msgs, exclude_last=False)
        assert "Foreman: Response" in result

    def test_excludes_last_message(self):
        msgs = [
            HumanMessage(content="First"),
            AIMessage(content="Second"),
            HumanMessage(content="Third"),
        ]
        result = langgraph_to_context(msgs, exclude_last=True)
        assert "First" in result
        assert "Second" in result
        assert "Third" not in result

    def test_joins_with_newlines(self):
        msgs = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi"),
            HumanMessage(content="Question"),
        ]
        result = langgraph_to_context(msgs, exclude_last=False)
        lines = result.split("\n")
        assert len(lines) == 3


class TestLanggraphToOrmStyle:
    """Tests for langgraph_to_orm_style function."""

    def test_empty_list_returns_empty(self):
        result = langgraph_to_orm_style([])
        assert result == []

    def test_converts_human_message(self):
        msgs = [HumanMessage(content="Hello")]
        result = langgraph_to_orm_style(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"

    def test_converts_ai_message(self):
        msgs = [AIMessage(content="Hi there!")]
        result = langgraph_to_orm_style(msgs)
        assert len(result) == 1
        assert result[0]["role"] == "assistant"
        assert result[0]["content"] == "Hi there!"

    def test_converts_mixed_messages(self):
        msgs = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi!"),
        ]
        result = langgraph_to_orm_style(msgs)
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"


class TestGetLastUserMessage:
    """Tests for get_last_user_message function."""

    def test_empty_list_returns_empty_string(self):
        result = get_last_user_message([])
        assert result == ""

    def test_returns_last_human_message(self):
        msgs = [
            HumanMessage(content="First"),
            AIMessage(content="Response"),
            HumanMessage(content="Second"),
        ]
        result = get_last_user_message(msgs)
        assert result == "Second"

    def test_skips_ai_messages_at_end(self):
        msgs = [
            HumanMessage(content="Question"),
            AIMessage(content="Answer"),
        ]
        result = get_last_user_message(msgs)
        assert result == "Question"

    def test_no_human_messages_returns_empty(self):
        msgs = [
            AIMessage(content="Only AI"),
        ]
        result = get_last_user_message(msgs)
        assert result == ""

    def test_single_human_message(self):
        msgs = [HumanMessage(content="Only message")]
        result = get_last_user_message(msgs)
        assert result == "Only message"
