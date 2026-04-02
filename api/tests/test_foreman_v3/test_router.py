"""
Tests for foreman_v3.nodes.router module.

Tests skip detection, update intent detection, and stage routing.
"""

import pytest
from langchain_core.messages import HumanMessage

from foreman_v3.nodes.router import (
    router_node,
    route_to_extractor,
    _detect_skip_intent,
    _detect_update_intent,
)
from foreman_v3.state import create_initial_state


class TestDetectSkipIntent:
    """Tests for _detect_skip_intent function."""

    def test_skip_is_detected(self):
        assert _detect_skip_intent("skip") is True

    def test_skip_this_is_detected(self):
        assert _detect_skip_intent("skip this") is True

    def test_next_is_detected(self):
        assert _detect_skip_intent("next") is True

    def test_move_on_is_detected(self):
        assert _detect_skip_intent("move on") is True

    def test_none_is_detected(self):
        assert _detect_skip_intent("none") is True

    def test_nothing_is_detected(self):
        assert _detect_skip_intent("nothing") is True

    def test_pass_is_detected(self):
        assert _detect_skip_intent("pass") is True

    def test_na_is_detected(self):
        assert _detect_skip_intent("n/a") is True
        assert _detect_skip_intent("na") is True

    def test_case_insensitive(self):
        assert _detect_skip_intent("SKIP") is True
        assert _detect_skip_intent("Skip") is True
        assert _detect_skip_intent("NONE") is True

    def test_normal_message_not_detected(self):
        assert _detect_skip_intent("I want to help customers") is False

    def test_partial_match_not_detected(self):
        assert _detect_skip_intent("I'll skip breakfast") is False

    def test_skip_this_with_trailing_text_is_detected(self):
        # "skip this" at start with trailing text is still a skip
        assert _detect_skip_intent("skip this one please") is True

    def test_skip_in_sentence_not_detected(self):
        # "skip" not at start should not be detected
        assert _detect_skip_intent("I'll skip breakfast") is False


class TestDetectUpdateIntent:
    """Tests for _detect_update_intent function."""

    def test_update_purpose_detected(self):
        stage, content = _detect_update_intent(
            "Update the purpose: New purpose text",
            completed_stages=["purpose"]
        )
        assert stage == "purpose"
        assert content == "New purpose text"

    def test_change_guardrails_detected(self):
        stage, content = _detect_update_intent(
            "Change the guardrails to add no profanity rule",
            completed_stages=["purpose", "guardrails"]
        )
        assert stage == "guardrails"

    def test_modify_tools_detected(self):
        stage, content = _detect_update_intent(
            "Modify the tools list",
            completed_stages=["purpose", "tools"]
        )
        assert stage == "tools"

    def test_edit_participants_detected(self):
        stage, content = _detect_update_intent(
            "Edit the participants to add user@example.com",
            completed_stages=["purpose", "participants"]
        )
        assert stage == "participants"

    def test_add_to_guardrails_detected(self):
        stage, content = _detect_update_intent(
            "Add to the guardrails: No personal advice",
            completed_stages=["purpose", "guardrails"]
        )
        assert stage == "guardrails"

    def test_uncompleted_stage_not_detected(self):
        stage, content = _detect_update_intent(
            "Update the guardrails: New rule",
            completed_stages=["purpose"]  # guardrails not completed
        )
        assert stage is None

    def test_no_update_trigger_not_detected(self):
        stage, content = _detect_update_intent(
            "The purpose should be customer support",
            completed_stages=["purpose"]
        )
        assert stage is None

    def test_case_insensitive_trigger(self):
        stage, content = _detect_update_intent(
            "UPDATE the purpose: New text",
            completed_stages=["purpose"]
        )
        assert stage == "purpose"


class TestRouterNode:
    """Tests for router_node function."""

    def _make_state(self, message: str, current_stage: str = "purpose", completed_stages: list = None):
        """Helper to create state with a message."""
        state = create_initial_state(confab_id=1)
        state["messages"] = [HumanMessage(content=message)]
        state["current_stage"] = current_stage
        state["completed_stages"] = completed_stages or []
        return state

    def test_skip_intent_sets_skip_status(self):
        state = self._make_state("skip")
        result = router_node(state)
        assert result.get("stage_result", {}).get("status") == "skip"
        assert result["is_update"] is False

    def test_normal_message_no_update(self):
        state = self._make_state("I want to build a support agent")
        result = router_node(state)
        assert result["is_update"] is False
        assert result["update_target"] is None

    def test_update_intent_sets_update_flags(self):
        state = self._make_state(
            "Update the purpose: New purpose",
            current_stage="participants",
            completed_stages=["purpose"]
        )
        result = router_node(state)
        assert result["is_update"] is True
        assert result["update_target"] == "purpose"


class TestRouteToExtractor:
    """Tests for route_to_extractor function."""

    def _make_state(self, current_stage: str, is_update: bool = False, update_target: str = None, skip: bool = False):
        """Helper to create state for routing."""
        state = create_initial_state(confab_id=1)
        state["current_stage"] = current_stage
        state["is_update"] = is_update
        state["update_target"] = update_target
        if skip:
            state["stage_result"] = {"status": "skip"}
        return state

    def test_routes_to_purpose(self):
        state = self._make_state("purpose")
        assert route_to_extractor(state) == "purpose"

    def test_routes_to_participants(self):
        state = self._make_state("participants")
        assert route_to_extractor(state) == "participants"

    def test_routes_to_memory(self):
        state = self._make_state("memory")
        assert route_to_extractor(state) == "memory"

    def test_routes_to_tools(self):
        state = self._make_state("tools")
        assert route_to_extractor(state) == "tools"

    def test_routes_to_guardrails(self):
        state = self._make_state("guardrails")
        assert route_to_extractor(state) == "guardrails"

    def test_routes_to_sample_io(self):
        state = self._make_state("sample_io")
        assert route_to_extractor(state) == "sample_io"

    def test_routes_to_review(self):
        state = self._make_state("review")
        assert route_to_extractor(state) == "review"

    def test_routes_to_complete(self):
        state = self._make_state("complete")
        assert route_to_extractor(state) == "complete"

    def test_skip_routes_to_validator_skip(self):
        state = self._make_state("purpose", skip=True)
        assert route_to_extractor(state) == "validator_skip"

    def test_update_routes_to_target_stage(self):
        state = self._make_state("participants", is_update=True, update_target="purpose")
        assert route_to_extractor(state) == "purpose"
