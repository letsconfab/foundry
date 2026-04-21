"""
Integration tests for the full Foreman V3 graph execution.

These tests verify the complete flow through all stages.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from dataclasses import dataclass
from typing import Optional, Dict, Any

from langchain_core.messages import HumanMessage, AIMessage

from foreman_v3.graph import build_foreman_graph, get_foreman_graph
from foreman_v3.state import create_initial_state, ForemanState


@dataclass
class MockExtractionResult:
    """Mock ExtractionResult from llm_service."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    raw_response: Optional[str] = None
    error: Optional[str] = None


class TestGraphConstruction:
    """Tests for graph construction."""

    def test_build_graph_returns_compiled_graph(self):
        graph = build_foreman_graph()
        assert graph is not None
        assert hasattr(graph, "ainvoke")

    def test_get_foreman_graph_returns_singleton(self):
        graph1 = get_foreman_graph()
        graph2 = get_foreman_graph()
        assert graph1 is graph2


class TestGraphExecution:
    """Integration tests for graph execution."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_confab(self):
        """Create mock confab object."""
        confab = MagicMock()
        confab.id = 1
        confab.name = None
        confab.purpose = None
        confab.guardrails = None
        confab.setup_progress = {}
        return confab

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_purpose")
    @patch("foreman_v3.nodes.saver.define_purpose")
    @patch("foreman_v3.nodes.saver.set_confab_name")
    async def test_purpose_stage_flow(
        self, mock_set_name, mock_define_purpose, mock_extract, mock_db
    ):
        """Test complete flow through purpose stage."""
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "purpose_text": "Help with customer support",
                "suggested_name": "SupportBot",
                "is_clear": True,
            }
        )

        graph = build_foreman_graph()

        initial_state: ForemanState = {
            "messages": [HumanMessage(content="Build a customer support agent")],
            "collected_info": {
                "purpose": None, "name": None, "participants": [],
                "memory_type": None, "tools": [], "guardrails": None, "sample_io": None,
            },
            "current_stage": "purpose",
            "completed_stages": [],
            "confab_id": 1,
            "thread_id": 1,
            "is_complete": False,
            "stage_result": None,
            "is_update": False,
            "update_target": None,
            "last_error": None,
        }

        config = {"configurable": {"db": mock_db}}
        result = await graph.ainvoke(initial_state, config)

        # Should have advanced to participants
        assert result["current_stage"] == "participants"
        assert "purpose" in result["completed_stages"]
        # Should have added AI response
        assert any(isinstance(m, AIMessage) for m in result["messages"])

    @pytest.mark.asyncio
    async def test_skip_flow(self, mock_db):
        """Test skip flow advances without saving."""
        graph = build_foreman_graph()

        initial_state: ForemanState = {
            "messages": [HumanMessage(content="skip")],
            "collected_info": {
                "purpose": "Already set", "name": None, "participants": [],
                "memory_type": None, "tools": [], "guardrails": None, "sample_io": None,
            },
            "current_stage": "participants",
            "completed_stages": ["purpose"],
            "confab_id": 1,
            "thread_id": 1,
            "is_complete": False,
            "stage_result": None,
            "is_update": False,
            "update_target": None,
            "last_error": None,
        }

        config = {"configurable": {"db": mock_db}}
        result = await graph.ainvoke(initial_state, config)

        # Should have advanced to memory
        assert result["current_stage"] == "memory"
        assert "participants" in result["completed_stages"]

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_purpose")
    async def test_clarify_flow(self, mock_extract, mock_db):
        """Test clarification flow stays on same stage."""
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "purpose_text": "",
                "is_clear": False,
                "clarification_needed": "Could you be more specific?",
            }
        )

        graph = build_foreman_graph()

        initial_state: ForemanState = {
            "messages": [HumanMessage(content="hi")],
            "collected_info": {
                "purpose": None, "name": None, "participants": [],
                "memory_type": None, "tools": [], "guardrails": None, "sample_io": None,
            },
            "current_stage": "purpose",
            "completed_stages": [],
            "confab_id": 1,
            "thread_id": 1,
            "is_complete": False,
            "stage_result": None,
            "is_update": False,
            "update_target": None,
            "last_error": None,
        }

        config = {"configurable": {"db": mock_db}}
        result = await graph.ainvoke(initial_state, config)

        # Should stay on purpose (clarification needed)
        assert result["current_stage"] == "purpose"
        assert "purpose" not in result["completed_stages"]


class TestUpdateFlow:
    """Tests for out-of-order update flow."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_purpose")
    @patch("foreman_v3.nodes.saver.define_purpose")
    async def test_update_previous_stage(self, mock_define_purpose, mock_extract, mock_db):
        """Test updating a previously completed stage."""
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "purpose_text": "Updated purpose",
                "is_clear": True,
            }
        )

        graph = build_foreman_graph()

        initial_state: ForemanState = {
            "messages": [HumanMessage(content="Update the purpose: New purpose")],
            "collected_info": {
                "purpose": "Old purpose", "name": None, "participants": [],
                "memory_type": None, "tools": [], "guardrails": None, "sample_io": None,
            },
            "current_stage": "participants",
            "completed_stages": ["purpose"],
            "confab_id": 1,
            "thread_id": 1,
            "is_complete": False,
            "stage_result": None,
            "is_update": False,
            "update_target": None,
            "last_error": None,
        }

        config = {"configurable": {"db": mock_db}}
        result = await graph.ainvoke(initial_state, config)

        # Should stay on participants (update doesn't advance)
        assert result["current_stage"] == "participants"
        # Purpose should still be in completed
        assert "purpose" in result["completed_stages"]


class TestFullInterviewFlow:
    """Test complete interview flow through all stages."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_review_intent")
    @patch("foreman_v3.nodes.saver.review_and_save")
    async def test_review_completes_interview(
        self, mock_review_save, mock_extract, mock_db
    ):
        """Test review stage completes the interview."""
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={"intent": "confirm"}
        )

        graph = build_foreman_graph()

        initial_state: ForemanState = {
            "messages": [HumanMessage(content="yes, save it")],
            "collected_info": {
                "purpose": "Test", "name": "TestBot", "participants": ["a@b.com"],
                "memory_type": "yes", "tools": ["web"], "guardrails": "Be safe", "sample_io": "Q: Hi A: Hello",
            },
            "current_stage": "review",
            "completed_stages": ["purpose", "participants", "memory", "tools", "guardrails", "sample_io"],
            "confab_id": 1,
            "thread_id": 1,
            "is_complete": False,
            "stage_result": None,
            "is_update": False,
            "update_target": None,
            "last_error": None,
        }

        config = {"configurable": {"db": mock_db}}
        result = await graph.ainvoke(initial_state, config)

        # Should be complete
        assert result["current_stage"] == "complete"
        assert result["is_complete"] is True
        assert "review" in result["completed_stages"]


class TestErrorHandling:
    """Tests for error handling in graph execution."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.extractors.extract_purpose")
    @patch("foreman_v3.nodes.saver.define_purpose")
    async def test_saver_error_handled(self, mock_define_purpose, mock_extract, mock_db):
        """Test that saver errors are handled gracefully."""
        mock_extract.return_value = MockExtractionResult(
            success=True,
            data={
                "purpose_text": "Test",
                "is_clear": True,
            }
        )
        mock_define_purpose.side_effect = Exception("Database error")

        graph = build_foreman_graph()

        initial_state: ForemanState = {
            "messages": [HumanMessage(content="Build something")],
            "collected_info": {
                "purpose": None, "name": None, "participants": [],
                "memory_type": None, "tools": [], "guardrails": None, "sample_io": None,
            },
            "current_stage": "purpose",
            "completed_stages": [],
            "confab_id": 1,
            "thread_id": 1,
            "is_complete": False,
            "stage_result": None,
            "is_update": False,
            "update_target": None,
            "last_error": None,
        }

        config = {"configurable": {"db": mock_db}}
        result = await graph.ainvoke(initial_state, config)

        # Should have error in last_error or stage_result
        assert result.get("last_error") is not None or result.get("stage_result", {}).get("status") == "error"
