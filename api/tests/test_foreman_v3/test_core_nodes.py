"""
Tests for foreman_v3 core nodes: validator, saver, advancer, responder.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage

from foreman_v3.nodes.validator import validator_node, route_after_validation
from foreman_v3.nodes.advancer import advancer_node
from foreman_v3.nodes.responder import responder_node
from foreman_v3.nodes.saver import saver_node
from foreman_v3.state import create_initial_state


def make_state(**overrides) -> dict:
    """Helper to create state with overrides."""
    state = create_initial_state(confab_id=1)
    state.update(overrides)
    return state


def make_config(db=None) -> dict:
    """Helper to create a mock config for nodes that need it."""
    return {"configurable": {"db": db}}


class TestValidatorNode:
    """Tests for validator_node."""

    def test_no_stage_result_returns_error(self):
        state = make_state()
        state["stage_result"] = None
        result = validator_node(state)

        assert result["stage_result"]["status"] == "error"
        assert "no extraction result" in result["stage_result"]["error_message"]

    def test_invalid_status_returns_error(self):
        state = make_state()
        state["stage_result"] = {"status": "invalid"}
        result = validator_node(state)

        assert result["stage_result"]["status"] == "error"
        assert "invalid status" in result["stage_result"]["error_message"]

    def test_valid_complete_status_passes_through(self):
        state = make_state()
        state["stage_result"] = {"status": "complete", "data": {"purpose": "test"}}
        result = validator_node(state)

        # Should pass through without modification
        assert result == {}

    def test_valid_clarify_status_passes_through(self):
        state = make_state()
        state["stage_result"] = {"status": "clarify", "next_question": "?"}
        result = validator_node(state)

        assert result == {}

    def test_valid_skip_status_passes_through(self):
        state = make_state()
        state["stage_result"] = {"status": "skip"}
        result = validator_node(state)

        assert result == {}


class TestRouteAfterValidation:
    """Tests for route_after_validation conditional edge."""

    def test_complete_routes_to_saver(self):
        state = make_state()
        state["stage_result"] = {"status": "complete"}
        assert route_after_validation(state) == "saver"

    def test_clarify_routes_to_responder(self):
        state = make_state()
        state["stage_result"] = {"status": "clarify"}
        assert route_after_validation(state) == "responder"

    def test_skip_routes_to_advancer(self):
        state = make_state()
        state["stage_result"] = {"status": "skip"}
        assert route_after_validation(state) == "advancer"

    def test_error_routes_to_responder(self):
        state = make_state()
        state["stage_result"] = {"status": "error"}
        assert route_after_validation(state) == "responder"

    def test_missing_status_routes_to_responder(self):
        state = make_state()
        state["stage_result"] = {}
        assert route_after_validation(state) == "responder"


class TestAdvancerNode:
    """Tests for advancer_node."""

    def test_advances_from_purpose_to_participants(self):
        state = make_state(current_stage="purpose", completed_stages=[])
        config = make_config()
        result = advancer_node(state, config)

        assert result["current_stage"] == "participants"
        assert "purpose" in result["completed_stages"]

    def test_advances_from_participants_to_memory(self):
        state = make_state(current_stage="participants", completed_stages=["purpose"])
        config = make_config()
        result = advancer_node(state, config)

        assert result["current_stage"] == "memory"
        assert "participants" in result["completed_stages"]

    def test_advances_from_review_to_complete(self):
        state = make_state(
            current_stage="review",
            completed_stages=["purpose", "participants", "memory", "documents", "tools", "guardrails", "sample_io"]
        )
        config = make_config()
        result = advancer_node(state, config)

        assert result["current_stage"] == "complete"
        assert result["is_complete"] is True

    def test_update_does_not_advance_stage(self):
        state = make_state(
            current_stage="participants",
            completed_stages=["purpose"],
            is_update=True,
            update_target="purpose"
        )
        config = make_config()
        result = advancer_node(state, config)

        # Should clear update flags but not advance
        assert result["is_update"] is False
        assert result["update_target"] is None
        # current_stage should not be in result (not changed)
        assert "current_stage" not in result

    def test_does_not_duplicate_completed_stages(self):
        state = make_state(
            current_stage="purpose",
            completed_stages=["purpose"]  # Already completed
        )
        config = make_config()
        result = advancer_node(state, config)

        # Should not have duplicate
        assert result["completed_stages"].count("purpose") == 1


class TestResponderNode:
    """Tests for responder_node."""

    def test_complete_response_includes_acknowledgment(self):
        state = make_state(
            current_stage="participants",  # After purpose completion
            stage_result={"status": "complete", "summary": "Purpose: test"},
        )
        result = responder_node(state)

        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)
        assert "Purpose: test" in result["messages"][0].content

    def test_clarify_response_keeps_question_in_metadata(self):
        state = make_state(
            current_stage="purpose",
            stage_result={"status": "clarify", "next_question": "What should it do?"},
        )
        result = responder_node(state)

        assert "What should it do?" not in result["messages"][0].content
        assert result["stage_result"]["interview_prompt"] == "What should it do?"
        assert "bit more detail" in result["messages"][0].content.lower()

    def test_skip_response_keeps_next_question_out_of_message(self):
        state = make_state(
            current_stage="memory",  # After participants skip
            stage_result={"status": "skip"},
        )
        result = responder_node(state)

        assert "Skipped" in result["messages"][0].content
        assert "remember" not in result["messages"][0].content.lower()
        assert "remember" in result["stage_result"]["interview_prompt"].lower()

    def test_error_response_includes_error_message(self):
        state = make_state(
            current_stage="purpose",
            stage_result={"status": "error", "error_message": "Something went wrong"},
        )
        result = responder_node(state)

        assert "Something went wrong" in result["messages"][0].content

    def test_update_response_confirms_and_re_asks(self):
        state = make_state(
            current_stage="participants",
            is_update=True,
            update_target="purpose",
            stage_result={"status": "complete", "summary": "Purpose updated"},
        )
        result = responder_node(state)

        content = result["messages"][0].content
        assert "Purpose updated" in content or "updated" in content.lower()

    def test_complete_stage_response(self):
        state = make_state(
            current_stage="complete",
            stage_result={"status": "complete", "summary": "Configuration saved"},
        )
        result = responder_node(state)

        assert "Configuration saved" in result["messages"][0].content
        assert "ready to deploy" in result["stage_result"]["interview_prompt"].lower()


class TestSaverNode:
    """Tests for saver_node."""

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.saver.define_purpose")
    @patch("foreman_v3.nodes.saver.set_confab_name")
    async def test_saves_purpose_and_name(self, mock_set_name, mock_define_purpose):
        state = make_state(
            current_stage="purpose",
            stage_result={
                "status": "complete",
                "data": {"purpose": "Test purpose", "name": "TestBot"},
            },
        )
        config = {"configurable": {"db": MagicMock()}}

        result = await saver_node(state, config)

        mock_define_purpose.assert_called_once()
        mock_set_name.assert_called_once()
        assert result["collected_info"]["purpose"] == "Test purpose"
        assert result["collected_info"]["name"] == "TestBot"

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.saver.add_participant")
    async def test_saves_participants(self, mock_add_participant):
        state = make_state(
            current_stage="participants",
            stage_result={
                "status": "complete",
                "data": {"participants": ["a@example.com", "b@example.com"]},
            },
        )
        config = {"configurable": {"db": MagicMock()}}

        result = await saver_node(state, config)

        assert mock_add_participant.call_count == 2

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.saver.configure_memory")
    async def test_saves_memory(self, mock_configure_memory):
        state = make_state(
            current_stage="memory",
            stage_result={
                "status": "complete",
                "data": {"memory_type": "yes"},
            },
        )
        config = {"configurable": {"db": MagicMock()}}

        result = await saver_node(state, config)

        mock_configure_memory.assert_called_once()

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.saver.add_tools_and_apis")
    async def test_saves_tools(self, mock_add_tools):
        state = make_state(
            current_stage="tools",
            stage_result={
                "status": "complete",
                "data": {"tools": ["web_search", "database"]},
            },
        )
        config = {"configurable": {"db": MagicMock()}}

        result = await saver_node(state, config)

        assert mock_add_tools.call_count == 2

    @pytest.mark.asyncio
    async def test_no_db_returns_error(self):
        state = make_state(
            current_stage="purpose",
            stage_result={"status": "complete", "data": {"purpose": "test"}},
        )
        config = {"configurable": {}}  # No db

        result = await saver_node(state, config)

        assert result["stage_result"]["status"] == "error"
        assert "no database session" in result["stage_result"]["error_message"]

    @pytest.mark.asyncio
    @patch("foreman_v3.nodes.saver.define_purpose")
    async def test_exception_returns_error(self, mock_define_purpose):
        mock_define_purpose.side_effect = Exception("DB error")

        state = make_state(
            current_stage="purpose",
            stage_result={"status": "complete", "data": {"purpose": "test"}},
        )
        config = {"configurable": {"db": MagicMock()}}

        result = await saver_node(state, config)

        assert result["stage_result"]["status"] == "error"
        assert "DB error" in result["stage_result"]["error_message"]
