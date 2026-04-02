"""
Foreman V3 Responder Node

Generates the response message to send back to the user.
Uses V2's templated response style (concise, declarative, no excessive praise).
"""

import logging
from typing import Dict, Any

from langchain_core.messages import AIMessage

from ..state import ForemanState, STAGE_ORDER

logger = logging.getLogger(__name__)


# Stage questions - the primary question for each stage (from V2)
STAGE_QUESTIONS = {
    "purpose": "What should this agent do? Describe its main job in a sentence or two.",
    "participants": "Who should have access to this agent? You can add email addresses or skip for now.",
    "memory": "Should this agent remember previous conversations? (yes, no, or limited)",
    "tools": "What external tools or APIs does this agent need? (e.g., web search, database, none)",
    "guardrails": "What safety boundaries should this agent follow? List any rules or restrictions.",
    "sample_io": "Can you provide an example interaction? (e.g., 'User asks X, agent responds Y')",
    "review": "Here's your agent configuration. Ready to save and deploy?",
}

# Clarification prompts when we need more info (from V2)
STAGE_CLARIFICATIONS = {
    "purpose": "I need a bit more detail. What specific task should this agent help with?",
    "participants": "Could you provide an email address, or say 'skip' to continue?",
    "memory": "Please specify: should it remember conversations? (yes/no/limited)",
    "tools": "Which tools specifically? For example: web search, calendar, database, or 'none'.",
    "guardrails": "What's one important rule this agent should follow?",
    "sample_io": "Can you give a quick example of what a user might ask and how the agent should respond?",
    "review": "Would you like to make any changes, or shall I save this configuration?",
}

# Acknowledgment templates (short, no praise) (from V2)
STAGE_ACKNOWLEDGMENTS = {
    "purpose": "Recorded the purpose.",
    "participants": "Added participant.",
    "memory": "Memory settings configured.",
    "tools": "Tools configured.",
    "guardrails": "Guardrails saved.",
    "sample_io": "Example recorded.",
    "review": "Configuration saved.",
}


def responder_node(state: ForemanState) -> Dict[str, Any]:
    """
    Generate response message based on stage result.

    Creates an AIMessage to append to the conversation.
    Follows V2's voice rules:
    - One question per turn
    - No exuberant praise
    - Concise, declarative tone
    """
    stage_result = state.get("stage_result", {})
    status = stage_result.get("status", "error")
    current_stage = state["current_stage"]
    is_update = state.get("is_update", False)
    update_target = state.get("update_target")

    # Determine which stage we're responding about
    responded_stage = update_target if is_update else current_stage

    logger.info(f"[V3] responder_node: status={status}, stage={responded_stage}, is_update={is_update}")

    response_text = _build_response(
        status=status,
        stage=responded_stage,
        current_stage=current_stage,
        stage_result=stage_result,
        is_update=is_update,
        state=state,
    )

    return {
        "messages": [AIMessage(content=response_text)],
    }


def _build_response(
    status: str,
    stage: str,
    current_stage: str,
    stage_result: dict,
    is_update: bool,
    state: ForemanState,
) -> str:
    """Build the response text based on status and stage."""

    if status == "complete":
        return _build_complete_response(stage, current_stage, stage_result, is_update)
    elif status == "clarify":
        return _build_clarify_response(stage, stage_result, state)
    elif status == "skip":
        return _build_skip_response(stage, current_stage)
    elif status == "error":
        return _build_error_response(stage, stage_result)
    else:
        return f"Something went wrong. {STAGE_QUESTIONS.get(current_stage, '')}"


def _build_complete_response(
    stage: str,
    current_stage: str,
    stage_result: dict,
    is_update: bool,
) -> str:
    """Build response for successful completion."""
    ack = STAGE_ACKNOWLEDGMENTS.get(stage, "Saved.")

    # Add summary if available
    summary = stage_result.get("summary")
    if summary:
        ack = summary

    # For updates, confirm and re-ask current stage
    if is_update and stage != current_stage:
        next_q = STAGE_QUESTIONS.get(current_stage, "")
        return f"{ack} {next_q}"

    # For normal flow, ask next stage question
    # Note: current_stage will have been advanced by advancer before responder
    next_q = STAGE_QUESTIONS.get(current_stage, "")

    if current_stage == "complete":
        return f"{ack} Your agent is ready to deploy!"

    return f"{ack} {next_q}"


def _build_clarify_response(
    stage: str,
    stage_result: dict,
    state: ForemanState,
) -> str:
    """Build response requesting clarification."""
    next_question = stage_result.get("next_question")

    # Handle special signals
    if next_question == "_show_config":
        return _build_config_summary(state)

    if next_question and next_question.startswith("_edit:"):
        edit_target = next_question.split(":")[1]
        return f"Sure, let's update the {edit_target}. What changes would you like to make?"

    # Use custom clarification or default
    if next_question:
        return next_question

    return STAGE_CLARIFICATIONS.get(stage, "Could you clarify that?")


def _build_skip_response(stage: str, current_stage: str) -> str:
    """Build response for skipping a stage."""
    # Note: current_stage will have been advanced by advancer
    next_q = STAGE_QUESTIONS.get(current_stage, "")

    if current_stage == "complete":
        return "Skipped. Your agent is ready to deploy!"

    return f"Skipped. {next_q}"


def _build_error_response(stage: str, stage_result: dict) -> str:
    """Build response for errors."""
    error_msg = stage_result.get("error_message", "Something went wrong.")
    retry_q = STAGE_QUESTIONS.get(stage, "Let's try again.")
    return f"Error: {error_msg}. {retry_q}"


def _build_config_summary(state: ForemanState) -> str:
    """
    Build a summary of the current configuration.

    Mirrors V2's _build_config_summary() method.
    """
    collected = state.get("collected_info", {})
    lines = ["\n\n---\n**Agent Configuration**\n---\n\n"]

    # Name
    name = collected.get("name")
    if name:
        lines.append(f"**Name:** {name}\n\n")

    # Purpose
    purpose = collected.get("purpose")
    if purpose:
        purpose_preview = purpose[:300] + "..." if len(purpose) > 300 else purpose
        lines.append(f"**Purpose:**\n{purpose_preview}\n\n")

    # Participants
    participants = collected.get("participants", [])
    if participants:
        lines.append(f"**Participants:** {', '.join(participants)}\n\n")

    # Memory
    memory_type = collected.get("memory_type")
    if memory_type:
        memory_label = {
            "yes": "Full memory enabled",
            "no": "Memory disabled",
            "limited": "Limited memory - recent conversations only",
        }.get(memory_type, memory_type)
        lines.append(f"**Memory:** {memory_label}\n\n")

    # Tools
    tools = collected.get("tools", [])
    if tools:
        lines.append(f"**Tools:** {', '.join(tools)}\n\n")

    # Guardrails
    guardrails = collected.get("guardrails")
    if guardrails:
        # Show first 5 rules
        rules = guardrails.split("\n")[:5]
        lines.append("**Guardrails:**\n")
        for rule in rules:
            if rule.strip():
                lines.append(f"  {rule}\n")
        if len(guardrails.split("\n")) > 5:
            lines.append("  ... and more\n")
        lines.append("\n")

    # Sample I/O
    sample_io = collected.get("sample_io")
    if sample_io:
        lines.append(f"**Sample Q&A:**\n{sample_io}\n\n")

    lines.append("---\n")
    lines.append(STAGE_QUESTIONS.get("review", "Ready to save?"))

    return "".join(lines)
