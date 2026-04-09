"""
Foreman V3 API Compatibility Layer

Formats V3 graph state into V2-compatible API response shape.
Critical for frontend compatibility - must match exact V2 field structure.
"""

from datetime import datetime
from typing import Dict, Any, List

from langchain_core.messages import AIMessage

from .state import ForemanState, STAGE_ORDER
from .progress_sync import stages_to_steps


def format_v3_response(state: ForemanState, thread_id: int) -> Dict[str, Any]:
    """
    Format V3 graph state to EXACT V2 response shape.

    Frontend (ConfigureConfabWithThreads.tsx) depends on:
    - response.foreman_metadata.setup_progress.current_stage
    - response.foreman_metadata.v2_metadata.stage_status
    - response.foreman_metadata.v2_metadata.saved_fields

    Args:
        state: ForemanState from graph execution
        thread_id: Thread ID for this conversation

    Returns:
        V2-compatible response dict
    """
    # Get last AI message as response text
    response_text = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage):
            response_text = msg.content
            break

    # Get stage result
    stage_result = state.get("stage_result") or {}
    status = stage_result.get("status", "complete") if stage_result else None

    # Build completed_steps as 1-indexed integers
    completed_stages = state.get("completed_stages", [])
    completed_steps = stages_to_steps(completed_stages)

    # Build remaining_steps
    remaining_steps = [i for i in range(1, len(STAGE_ORDER) + 1) if i not in completed_steps]

    # Current stage (may be "complete" after interview finishes)
    current_stage = state.get("current_stage", "purpose")

    return {
        # Core response
        "response": response_text,
        "confab_id": state["confab_id"],
        "thread_id": thread_id,

        # Required for V2 compatibility
        "is_resume": False,

        # Setup progress (V2 format)
        "setup_progress": {
            "completed_steps": completed_steps,
            "current_stage": current_stage,
            "total_steps": len(STAGE_ORDER),
            "remaining_steps": remaining_steps,
        },

        # Tool calls (V2 doesn't expose, but field required)
        "tool_calls": [],

        # Timestamp
        "timestamp": datetime.now().isoformat(),

        # V2 metadata (critical for frontend)
        "v2_metadata": {
            "stage": current_stage,
            "stage_status": status,
            "is_update": state.get("is_update", False),
            "updated_stage": state.get("update_target"),
            "saved_fields": stage_result.get("data"),
            "next_question": stage_result.get("next_question"),
            "ui_hint": stage_result.get("ui_hint"),
        },

        # Version flags
        "is_v2": False,
        "is_v3": True,
        "is_langgraph": True,
    }


def format_error_response(
    confab_id: int,
    thread_id: int,
    error_message: str,
    current_stage: str = "purpose",
) -> Dict[str, Any]:
    """
    Format an error response in V2-compatible shape.

    Args:
        confab_id: The confab ID
        thread_id: The thread ID
        error_message: Error description
        current_stage: Current stage when error occurred

    Returns:
        V2-compatible error response dict
    """
    return {
        "response": f"An error occurred: {error_message}",
        "confab_id": confab_id,
        "thread_id": thread_id,
        "is_resume": False,
        "setup_progress": {
            "completed_steps": [],
            "current_stage": current_stage,
            "total_steps": len(STAGE_ORDER),
            "remaining_steps": list(range(1, len(STAGE_ORDER) + 1)),
        },
        "tool_calls": [],
        "timestamp": datetime.now().isoformat(),
        "v2_metadata": {
            "stage": current_stage,
            "stage_status": "error",
            "is_update": False,
            "updated_stage": None,
            "saved_fields": None,
            "next_question": None,
        },
        "is_v2": False,
        "is_v3": True,
        "is_langgraph": True,
    }
