"""
Foreman V3 State Schema

Defines the TypedDict state structure for the LangGraph Information Collector.
"""

from typing import TypedDict, List, Optional, Dict, Any, Annotated, Literal
from langgraph.graph.message import add_messages


# Stage order constant (shared with V2)
STAGE_ORDER = ["purpose", "participants", "memory", "documents", "tools", "guardrails", "sample_io", "review"]


class InformationSchema(TypedDict):
    """
    Collected information across all interview stages.

    Each field corresponds to data gathered from a specific stage.
    Fields are Optional because stages may be skipped or incomplete.
    """
    # Purpose stage
    purpose: Optional[str]
    name: Optional[str]  # Auto-extracted from purpose, saved via set_confab_name()

    # Participants stage
    participants: List[str]  # Email addresses

    # Memory stage
    memory_type: Optional[Literal["yes", "no", "limited"]]

    # Documents stage
    documents: List[Dict[str, Any]]  # Uploaded document metadata
    documents_skipped: bool

    # Tools stage
    tools: List[str]  # Tool/API names

    # Guardrails stage
    guardrails: Optional[str]  # Markdown text

    # Sample I/O stage
    sample_io: Optional[str]  # Markdown text with example interactions


class StageResultDict(TypedDict, total=False):
    """
    Result from a stage extraction/handler.

    Mirrors V2's StageResult dataclass but as a TypedDict for LangGraph state.
    """
    status: Literal["complete", "clarify", "skip", "error"]
    data: Optional[Dict[str, Any]]  # Extracted/saved data
    summary: Optional[str]  # What was saved (for response)
    next_question: Optional[str]  # What to ask next (for clarify)
    error_message: Optional[str]  # If status == "error"
    ui_hint: Optional[str]  # Frontend hint for stage-specific UX
    response_ack: Optional[str]  # Short acknowledgement for the previous turn
    interview_prompt: Optional[str]  # Next explicit call to action for the interview


class ForemanState(TypedDict):
    """
    LangGraph state for Foreman V3 Information Collector.

    This state flows through all nodes in the graph and accumulates
    collected information until the interview is complete.
    """
    # Message history with add_messages reducer for proper accumulation
    messages: Annotated[list, add_messages]

    # Collected information (accumulates across stages)
    collected_info: InformationSchema

    # Current position in the interview
    current_stage: Literal[
        "purpose", "participants", "memory", "documents", "tools",
        "guardrails", "sample_io", "review", "complete"
    ]
    completed_stages: List[str]

    # Context identifiers
    confab_id: int
    thread_id: Optional[int]

    # Completion flag
    is_complete: bool

    # Current turn result (from extractor)
    stage_result: Optional[StageResultDict]

    # Out-of-order update tracking
    is_update: bool  # True if updating a previous stage
    update_target: Optional[str]  # Target stage for update

    # Error tracking
    last_error: Optional[str]


def create_initial_state(confab_id: int, thread_id: Optional[int] = None) -> ForemanState:
    """
    Create initial state for a new Foreman conversation.

    Args:
        confab_id: The ID of the confab being configured
        thread_id: Optional thread ID for conversation tracking

    Returns:
        Initial ForemanState with empty collected_info and purpose as first stage
    """
    return {
        "messages": [],
        "collected_info": {
            "purpose": None,
            "name": None,
            "participants": [],
            "memory_type": None,
            "documents": [],
            "documents_skipped": False,
            "tools": [],
            "guardrails": None,
            "sample_io": None,
        },
        "current_stage": "purpose",
        "completed_stages": [],
        "confab_id": confab_id,
        "thread_id": thread_id,
        "is_complete": False,
        "stage_result": None,
        "is_update": False,
        "update_target": None,
        "last_error": None,
    }


def get_stage_index(stage: str) -> int:
    """Get the 1-based index of a stage (for completed_steps)."""
    if stage in STAGE_ORDER:
        return STAGE_ORDER.index(stage) + 1
    return 0


def get_next_stage(current: str) -> Optional[str]:
    """Get the next stage after the current one, or None if at review."""
    if current not in STAGE_ORDER:
        return None
    idx = STAGE_ORDER.index(current)
    if idx + 1 < len(STAGE_ORDER):
        return STAGE_ORDER[idx + 1]
    return "complete"
