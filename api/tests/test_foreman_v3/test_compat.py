"""
Tests for foreman_v3.compat module.

Verifies V3 responses match V2 response shape for frontend compatibility.
"""

import pytest
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage

from foreman_v3.compat import (
    format_v3_response,
    format_error_response,
    _stages_to_steps,
    _get_remaining_steps,
)
from foreman_v3.state import create_initial_state


class TestStagesToSteps:
    """Tests for _stages_to_steps helper."""

    def test_empty_list_returns_empty(self):
        assert _stages_to_steps([]) == []

    def test_converts_purpose_to_1(self):
        assert _stages_to_steps(["purpose"]) == [1]

    def test_converts_multiple_stages(self):
        assert _stages_to_steps(["purpose", "participants", "memory"]) == [1, 2, 3]

    def test_returns_sorted_list(self):
        # Even if stages are out of order
        assert _stages_to_steps(["memory", "purpose"]) == [1, 3]

    def test_ignores_invalid_stages(self):
        assert _stages_to_steps(["purpose", "invalid", "memory"]) == [1, 3]


class TestGetRemainingSteps:
    """Tests for _get_remaining_steps helper."""

    def test_no_completed_returns_all(self):
        assert _get_remaining_steps([]) == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_all_completed_returns_empty(self):
        all_stages = ["purpose", "participants", "memory", "documents", "tools", "guardrails", "sample_io", "review"]
        assert _get_remaining_steps(all_stages) == []

    def test_partial_completion(self):
        assert _get_remaining_steps(["purpose", "participants"]) == [3, 4, 5, 6, 7, 8]


class TestFormatV3Response:
    """Tests for format_v3_response function."""

    def _make_state(self, **overrides):
        """Helper to create state with overrides."""
        state = create_initial_state(confab_id=1)
        state["messages"] = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
        ]
        state["stage_result"] = {"status": "complete", "data": {"purpose": "test"}}
        state.update(overrides)
        return state

    def test_includes_response_from_last_ai_message(self):
        state = self._make_state()
        result = format_v3_response(state, thread_id=1)

        assert result["response"] == "Hi there!"

    def test_includes_confab_id(self):
        state = self._make_state()
        result = format_v3_response(state, thread_id=1)

        assert result["confab_id"] == 1

    def test_includes_thread_id(self):
        state = self._make_state()
        result = format_v3_response(state, thread_id=42)

        assert result["thread_id"] == 42

    def test_includes_is_resume_field(self):
        state = self._make_state()
        result = format_v3_response(state, thread_id=1)

        assert "is_resume" in result
        assert result["is_resume"] is False

    def test_includes_setup_progress(self):
        state = self._make_state(
            current_stage="participants",
            completed_stages=["purpose"]
        )
        result = format_v3_response(state, thread_id=1)

        assert "setup_progress" in result
        assert result["setup_progress"]["current_stage"] == "participants"
        assert result["setup_progress"]["completed_steps"] == [1]
        assert result["setup_progress"]["total_steps"] == 8
        assert result["setup_progress"]["remaining_steps"] == [2, 3, 4, 5, 6, 7, 8]

    def test_includes_tool_calls_field(self):
        state = self._make_state()
        result = format_v3_response(state, thread_id=1)

        assert "tool_calls" in result
        assert result["tool_calls"] == []

    def test_includes_timestamp(self):
        state = self._make_state()
        result = format_v3_response(state, thread_id=1)

        assert "timestamp" in result
        # Should be ISO format
        datetime.fromisoformat(result["timestamp"])

    def test_includes_v2_metadata(self):
        state = self._make_state(
            current_stage="purpose",
            stage_result={"status": "clarify", "next_question": "What?"}
        )
        result = format_v3_response(state, thread_id=1)

        assert "v2_metadata" in result
        v2 = result["v2_metadata"]
        assert v2["stage"] == "purpose"
        assert v2["stage_status"] == "clarify"
        assert v2["next_question"] == "What?"

    def test_includes_saved_fields_in_v2_metadata(self):
        state = self._make_state(
            stage_result={"status": "complete", "data": {"purpose": "test purpose"}}
        )
        result = format_v3_response(state, thread_id=1)

        assert result["v2_metadata"]["saved_fields"] == {"purpose": "test purpose"}

    def test_includes_is_update_in_v2_metadata(self):
        state = self._make_state(is_update=True, update_target="purpose")
        result = format_v3_response(state, thread_id=1)

        assert result["v2_metadata"]["is_update"] is True
        assert result["v2_metadata"]["updated_stage"] == "purpose"

    def test_includes_version_flags(self):
        state = self._make_state()
        result = format_v3_response(state, thread_id=1)

        assert result["is_v2"] is False
        assert result["is_v3"] is True
        assert result["is_langgraph"] is True

    def test_handles_empty_messages(self):
        state = self._make_state(messages=[])
        result = format_v3_response(state, thread_id=1)

        assert result["response"] == ""

    def test_handles_no_stage_result(self):
        state = self._make_state(stage_result=None)
        result = format_v3_response(state, thread_id=1)

        assert result["v2_metadata"]["stage_status"] is None


class TestFormatErrorResponse:
    """Tests for format_error_response function."""

    def test_includes_error_message(self):
        result = format_error_response(
            confab_id=1,
            thread_id=1,
            error_message="Something went wrong"
        )

        assert "Something went wrong" in result["response"]

    def test_includes_confab_and_thread_ids(self):
        result = format_error_response(
            confab_id=42,
            thread_id=99,
            error_message="Error"
        )

        assert result["confab_id"] == 42
        assert result["thread_id"] == 99

    def test_has_error_status_in_v2_metadata(self):
        result = format_error_response(
            confab_id=1,
            thread_id=1,
            error_message="Error"
        )

        assert result["v2_metadata"]["stage_status"] == "error"

    def test_has_version_flags(self):
        result = format_error_response(
            confab_id=1,
            thread_id=1,
            error_message="Error"
        )

        assert result["is_v2"] is False
        assert result["is_v3"] is True
        assert result["is_langgraph"] is True

    def test_uses_provided_current_stage(self):
        result = format_error_response(
            confab_id=1,
            thread_id=1,
            error_message="Error",
            current_stage="guardrails"
        )

        assert result["v2_metadata"]["stage"] == "guardrails"
        assert result["setup_progress"]["current_stage"] == "guardrails"


class TestV2ResponseParity:
    """Tests to ensure V3 response matches V2 response shape exactly."""

    def test_has_all_required_v2_fields(self):
        """Verify all fields required by frontend are present."""
        state = create_initial_state(confab_id=1)
        state["messages"] = [AIMessage(content="Response")]
        state["stage_result"] = {"status": "complete"}

        result = format_v3_response(state, thread_id=1)

        # Required top-level fields
        required_fields = [
            "response", "confab_id", "thread_id", "is_resume",
            "setup_progress", "tool_calls", "timestamp",
            "v2_metadata", "is_v2"
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_setup_progress_has_all_fields(self):
        state = create_initial_state(confab_id=1)
        state["messages"] = [AIMessage(content="Response")]
        state["stage_result"] = {"status": "complete"}

        result = format_v3_response(state, thread_id=1)

        required_fields = [
            "completed_steps", "current_stage", "total_steps", "remaining_steps"
        ]
        for field in required_fields:
            assert field in result["setup_progress"], f"Missing setup_progress field: {field}"

    def test_v2_metadata_has_all_fields(self):
        state = create_initial_state(confab_id=1)
        state["messages"] = [AIMessage(content="Response")]
        state["stage_result"] = {"status": "complete", "data": {}}

        result = format_v3_response(state, thread_id=1)

        required_fields = [
            "stage", "stage_status", "is_update", "updated_stage",
            "saved_fields", "next_question"
        ]
        for field in required_fields:
            assert field in result["v2_metadata"], f"Missing v2_metadata field: {field}"
