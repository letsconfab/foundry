"""
Tests for foreman_v3.nodes.extractors module.

Tests all extractor nodes with mocked LLM responses.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import dataclass
from typing import Optional, Dict, Any

from langchain_core.messages import HumanMessage

from foreman_v3.nodes.extractors import (
    extract_purpose_node,
    extract_participants_node,
    extract_memory_node,
    extract_tools_node,
    extract_guardrails_node,
    extract_sample_io_node,
    extract_review_node,
)
from foreman_v3.state import create_initial_state


@dataclass
class MockExtractionResult:
    """Mock ExtractionResult from llm_service."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    raw_response: Optional[str] = None
    error: Optional[str] = None


def make_state(message: str, current_stage: str = "purpose") -> dict:
    """Helper to create state with a message."""
    state = create_initial_state(confab_id=1)
    state["messages"] = [HumanMessage(content=message)]
    state["current_stage"] = current_stage
    return state


class TestExtractPurposeNode:
    """Tests for extract_purpose_node."""

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_purpose")
    async def test_clear_purpose_returns_complete(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "purpose_text": "Help with customer support",
                "suggested_name": "SupportBot",
                "is_clear": True,
            }
        )

        state = make_state("Build an agent to help customers")
        result = await extract_purpose_node(state)

        assert result["stage_result"]["status"] == "complete"
        assert result["stage_result"]["data"]["purpose"] == "Help with customer support"
        assert result["stage_result"]["data"]["name"] == "SupportBot"

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_purpose")
    async def test_unclear_purpose_returns_clarify(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "purpose_text": "",
                "is_clear": False,
                "clarification_needed": "What should this agent help with?",
            }
        )

        state = make_state("hi")
        result = await extract_purpose_node(state)

        assert result["stage_result"]["status"] == "clarify"
        assert result["stage_result"]["next_question"] == "What should this agent help with?"

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_purpose")
    async def test_fallback_uses_raw_message(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "purpose_text": None,
                "is_clear": False,
            }
        )

        state = make_state("Help with FAQs")
        result = await extract_purpose_node(state)

        assert result["stage_result"]["status"] == "complete"
        assert result["stage_result"]["data"]["purpose"] == "Help with FAQs"


class TestExtractParticipantsNode:
    """Tests for extract_participants_node."""

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_participants")
    async def test_emails_returns_complete(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "emails": ["user@example.com", "admin@example.com"],
                "wants_to_skip": False,
            }
        )

        state = make_state("Add user@example.com and admin@example.com", "participants")
        result = await extract_participants_node(state)

        assert result["stage_result"]["status"] == "complete"
        assert len(result["stage_result"]["data"]["participants"]) == 2

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_participants")
    async def test_skip_returns_skip(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "emails": [],
                "wants_to_skip": True,
            }
        )

        state = make_state("skip", "participants")
        result = await extract_participants_node(state)

        assert result["stage_result"]["status"] == "skip"

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_participants")
    async def test_no_emails_returns_clarify(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "emails": [],
                "wants_to_skip": False,
                "clarification_needed": "Please provide an email",
            }
        )

        state = make_state("add someone", "participants")
        result = await extract_participants_node(state)

        assert result["stage_result"]["status"] == "clarify"


class TestExtractMemoryNode:
    """Tests for extract_memory_node."""

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_memory_preference")
    async def test_full_memory_returns_yes(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "memory_type": "full",
                "enable_memory": True,
            }
        )

        state = make_state("yes, remember everything", "memory")
        result = await extract_memory_node(state)

        assert result["stage_result"]["status"] == "complete"
        assert result["stage_result"]["data"]["memory_type"] == "yes"

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_memory_preference")
    async def test_no_memory_returns_no(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "memory_type": "none",
                "enable_memory": False,
            }
        )

        state = make_state("no memory", "memory")
        result = await extract_memory_node(state)

        assert result["stage_result"]["status"] == "complete"
        assert result["stage_result"]["data"]["memory_type"] == "no"

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_memory_preference")
    async def test_limited_memory_returns_limited(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "memory_type": "limited",
                "enable_memory": True,
            }
        )

        state = make_state("limited memory please", "memory")
        result = await extract_memory_node(state)

        assert result["stage_result"]["status"] == "complete"
        assert result["stage_result"]["data"]["memory_type"] == "limited"


class TestExtractToolsNode:
    """Tests for extract_tools_node."""

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_tools")
    async def test_tools_returns_complete(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "tools": ["web_search", "database"],
                "no_tools_needed": False,
            }
        )

        state = make_state("web search and database", "tools")
        result = await extract_tools_node(state)

        assert result["stage_result"]["status"] == "complete"
        assert "web_search" in result["stage_result"]["data"]["tools"]

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_tools")
    async def test_no_tools_returns_complete(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "tools": [],
                "no_tools_needed": True,
            }
        )

        state = make_state("no tools needed", "tools")
        result = await extract_tools_node(state)

        assert result["stage_result"]["status"] == "complete"
        assert result["stage_result"]["data"]["tools"] == []


class TestExtractGuardrailsNode:
    """Tests for extract_guardrails_node."""

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_guardrails")
    async def test_guardrails_returns_complete(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "guardrails_text": "1. Be polite\n2. No profanity",
                "rules_count": 2,
            }
        )

        state = make_state("be polite and no profanity", "guardrails")
        result = await extract_guardrails_node(state)

        assert result["stage_result"]["status"] == "complete"
        assert "Be polite" in result["stage_result"]["data"]["guardrails"]

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_guardrails")
    async def test_list_guardrails_converted_to_string(self, mock_extract):
        # Sometimes LLM returns list instead of string
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "guardrails_text": ["Be polite", "No profanity"],
                "rules_count": 2,
            }
        )

        state = make_state("be polite and no profanity", "guardrails")
        result = await extract_guardrails_node(state)

        assert result["stage_result"]["status"] == "complete"
        assert isinstance(result["stage_result"]["data"]["guardrails"], str)


class TestExtractSampleIoNode:
    """Tests for extract_sample_io_node."""

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_sample_io")
    async def test_sample_returns_complete(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "sample_text": "User: Hello\nAgent: Hi there!",
                "has_input": True,
                "has_output": True,
            }
        )

        state = make_state("User says hello, agent says hi", "sample_io")
        result = await extract_sample_io_node(state)

        assert result["stage_result"]["status"] == "complete"
        assert "Hello" in result["stage_result"]["data"]["sample_io"]

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_sample_io")
    async def test_skip_returns_skip(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "wants_to_skip": True,
            }
        )

        state = make_state("skip", "sample_io")
        result = await extract_sample_io_node(state)

        assert result["stage_result"]["status"] == "skip"


class TestExtractReviewNode:
    """Tests for extract_review_node."""

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_review_intent")
    async def test_confirm_returns_complete(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "intent": "confirm",
            }
        )

        state = make_state("yes, save it", "review")
        result = await extract_review_node(state)

        assert result["stage_result"]["status"] == "complete"
        assert result["stage_result"]["data"]["confirmed"] is True

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_review_intent")
    async def test_edit_returns_clarify_with_target(self, mock_extract):
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "intent": "edit",
                "edit_target": "purpose",
            }
        )

        state = make_state("I want to change the purpose", "review")
        result = await extract_review_node(state)

        assert result["stage_result"]["status"] == "clarify"
        assert "_edit:purpose" in result["stage_result"]["next_question"]

    @pytest.mark.asyncio
    async def test_show_config_returns_clarify_with_signal(self):
        state = make_state("show the configuration", "review")
        result = await extract_review_node(state)

        assert result["stage_result"]["status"] == "clarify"
        assert result["stage_result"]["next_question"] == "_show_config"
