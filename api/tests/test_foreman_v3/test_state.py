"""
Tests for foreman_v3.state module.

Tests state schema, initial state creation, and helper functions.
"""

import pytest
from foreman_v3.state import (
    ForemanState,
    InformationSchema,
    StageResultDict,
    STAGE_ORDER,
    create_initial_state,
    get_stage_index,
    get_next_stage,
)


class TestStageOrder:
    """Tests for STAGE_ORDER constant."""

    def test_stage_order_has_seven_stages(self):
        assert len(STAGE_ORDER) == 7

    def test_stage_order_starts_with_purpose(self):
        assert STAGE_ORDER[0] == "purpose"

    def test_stage_order_ends_with_review(self):
        assert STAGE_ORDER[-1] == "review"

    def test_stage_order_contains_all_stages(self):
        expected = ["purpose", "participants", "memory", "tools", "guardrails", "sample_io", "review"]
        assert STAGE_ORDER == expected


class TestCreateInitialState:
    """Tests for create_initial_state function."""

    def test_creates_state_with_confab_id(self):
        state = create_initial_state(confab_id=123)
        assert state["confab_id"] == 123

    def test_creates_state_with_thread_id(self):
        state = create_initial_state(confab_id=1, thread_id=456)
        assert state["thread_id"] == 456

    def test_creates_state_without_thread_id(self):
        state = create_initial_state(confab_id=1)
        assert state["thread_id"] is None

    def test_initial_stage_is_purpose(self):
        state = create_initial_state(confab_id=1)
        assert state["current_stage"] == "purpose"

    def test_initial_completed_stages_is_empty(self):
        state = create_initial_state(confab_id=1)
        assert state["completed_stages"] == []

    def test_initial_messages_is_empty(self):
        state = create_initial_state(confab_id=1)
        assert state["messages"] == []

    def test_initial_is_complete_is_false(self):
        state = create_initial_state(confab_id=1)
        assert state["is_complete"] is False

    def test_initial_stage_result_is_none(self):
        state = create_initial_state(confab_id=1)
        assert state["stage_result"] is None

    def test_initial_is_update_is_false(self):
        state = create_initial_state(confab_id=1)
        assert state["is_update"] is False

    def test_initial_collected_info_has_all_fields(self):
        state = create_initial_state(confab_id=1)
        info = state["collected_info"]
        assert "purpose" in info
        assert "name" in info
        assert "participants" in info
        assert "memory_type" in info
        assert "tools" in info
        assert "guardrails" in info
        assert "sample_io" in info

    def test_initial_collected_info_values_are_empty(self):
        state = create_initial_state(confab_id=1)
        info = state["collected_info"]
        assert info["purpose"] is None
        assert info["name"] is None
        assert info["participants"] == []
        assert info["memory_type"] is None
        assert info["tools"] == []
        assert info["guardrails"] is None
        assert info["sample_io"] is None


class TestGetStageIndex:
    """Tests for get_stage_index function."""

    def test_purpose_is_index_1(self):
        assert get_stage_index("purpose") == 1

    def test_participants_is_index_2(self):
        assert get_stage_index("participants") == 2

    def test_memory_is_index_3(self):
        assert get_stage_index("memory") == 3

    def test_tools_is_index_4(self):
        assert get_stage_index("tools") == 4

    def test_guardrails_is_index_5(self):
        assert get_stage_index("guardrails") == 5

    def test_sample_io_is_index_6(self):
        assert get_stage_index("sample_io") == 6

    def test_review_is_index_7(self):
        assert get_stage_index("review") == 7

    def test_invalid_stage_returns_0(self):
        assert get_stage_index("invalid") == 0

    def test_complete_stage_returns_0(self):
        assert get_stage_index("complete") == 0


class TestGetNextStage:
    """Tests for get_next_stage function."""

    def test_purpose_next_is_participants(self):
        assert get_next_stage("purpose") == "participants"

    def test_participants_next_is_memory(self):
        assert get_next_stage("participants") == "memory"

    def test_memory_next_is_tools(self):
        assert get_next_stage("memory") == "tools"

    def test_tools_next_is_guardrails(self):
        assert get_next_stage("tools") == "guardrails"

    def test_guardrails_next_is_sample_io(self):
        assert get_next_stage("guardrails") == "sample_io"

    def test_sample_io_next_is_review(self):
        assert get_next_stage("sample_io") == "review"

    def test_review_next_is_complete(self):
        assert get_next_stage("review") == "complete"

    def test_invalid_stage_returns_none(self):
        assert get_next_stage("invalid") is None

    def test_complete_stage_returns_none(self):
        assert get_next_stage("complete") is None


class TestInformationSchema:
    """Tests for InformationSchema TypedDict."""

    def test_can_create_empty_schema(self):
        info: InformationSchema = {
            "purpose": None,
            "name": None,
            "participants": [],
            "memory_type": None,
            "tools": [],
            "guardrails": None,
            "sample_io": None,
        }
        assert info["purpose"] is None

    def test_can_create_populated_schema(self):
        info: InformationSchema = {
            "purpose": "Help with customer support",
            "name": "SupportBot",
            "participants": ["user@example.com"],
            "memory_type": "yes",
            "tools": ["web_search"],
            "guardrails": "1. Be polite\n2. No profanity",
            "sample_io": "User: Hello\nAgent: Hi!",
        }
        assert info["purpose"] == "Help with customer support"
        assert info["name"] == "SupportBot"
        assert len(info["participants"]) == 1
        assert info["memory_type"] == "yes"
        assert len(info["tools"]) == 1


class TestStageResultDict:
    """Tests for StageResultDict TypedDict."""

    def test_complete_status(self):
        result: StageResultDict = {
            "status": "complete",
            "data": {"purpose": "Test purpose"},
            "summary": "Purpose saved",
        }
        assert result["status"] == "complete"

    def test_clarify_status(self):
        result: StageResultDict = {
            "status": "clarify",
            "next_question": "Can you clarify?",
        }
        assert result["status"] == "clarify"
        assert result["next_question"] == "Can you clarify?"

    def test_skip_status(self):
        result: StageResultDict = {
            "status": "skip",
            "data": {},
        }
        assert result["status"] == "skip"

    def test_error_status(self):
        result: StageResultDict = {
            "status": "error",
            "error_message": "Something went wrong",
        }
        assert result["status"] == "error"
        assert result["error_message"] == "Something went wrong"
