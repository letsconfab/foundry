"""
Foreman V3 Saver Node

Persists extracted data to the database using V2 tool functions.
This is the critical save-gating node - stage only advances after successful save.
"""

import logging
from typing import Dict, Any, TYPE_CHECKING, Optional

from langgraph.types import RunnableConfig

from ..state import ForemanState

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Import tool functions (reuse from V2)
from agent_tools import (
    define_purpose,
    set_confab_name,
    add_participant,
    configure_memory,
    add_tools_and_apis,
    guardrails,
    sample_io,
    review_and_save,
)

logger = logging.getLogger(__name__)


async def saver_node(state: ForemanState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Persist extracted data to the database.

    This node is called when stage_result.status == "complete".
    It invokes the appropriate tool function based on current stage.

    The db session is passed via config["configurable"]["db"].
    """
    # Get database session from config
    db = config.get("configurable", {}).get("db")
    if not db:
        logger.error("[V3] saver_node: No database session in config")
        return {
            "stage_result": {
                "status": "error",
                "error_message": "Internal error: no database session",
            },
            "last_error": "No database session in config",
        }

    confab_id = state["confab_id"]
    stage = state.get("update_target") if state.get("is_update") else state["current_stage"]
    stage_result = state.get("stage_result", {})
    data = stage_result.get("data", {})

    logger.info(f"[V3] saver_node: stage={stage}, confab_id={confab_id}, data_keys={list(data.keys())}")

    try:
        if stage == "purpose":
            await _save_purpose(db, confab_id, data)
        elif stage == "participants":
            await _save_participants(db, confab_id, data)
        elif stage == "memory":
            await _save_memory(db, confab_id, data)
        elif stage == "tools":
            await _save_tools(db, confab_id, data)
        elif stage == "guardrails":
            await _save_guardrails(db, confab_id, data)
        elif stage == "sample_io":
            await _save_sample_io(db, confab_id, data)
        elif stage == "review":
            await _save_review(db, confab_id, data)
        else:
            logger.warning(f"[V3] saver_node: Unknown stage '{stage}', skipping save")

        # Update collected_info with saved data
        collected_info = dict(state.get("collected_info", {}))
        collected_info.update(data)

        logger.info(f"[V3] saver_node: Save successful for stage={stage}")
        return {
            "collected_info": collected_info,
        }

    except Exception as e:
        logger.error(f"[V3] saver_node: Save failed for stage={stage}: {e}")
        return {
            "stage_result": {
                "status": "error",
                "error_message": f"Failed to save: {str(e)}",
            },
            "last_error": str(e),
        }


async def _save_purpose(db: "Session", confab_id: int, data: Dict[str, Any]) -> None:
    """Save purpose and optionally set confab name."""
    purpose_text = data.get("purpose")
    if purpose_text:
        define_purpose(db=db, confab_id=confab_id, purpose_text=purpose_text)
        logger.info(f"[V3] Saved purpose for confab {confab_id}")

    # Set name if suggested
    name = data.get("name")
    if name:
        set_confab_name(db=db, confab_id=confab_id, name=name)
        logger.info(f"[V3] Set name '{name}' for confab {confab_id}")


async def _save_participants(db: "Session", confab_id: int, data: Dict[str, Any]) -> None:
    """Save participant emails."""
    participants = data.get("participants", [])
    for email in participants:
        add_participant(db=db, confab_id=confab_id, email=email)
    logger.info(f"[V3] Added {len(participants)} participant(s) to confab {confab_id}")


async def _save_memory(db: "Session", confab_id: int, data: Dict[str, Any]) -> None:
    """Save memory configuration."""
    memory_type = data.get("memory_type", "no")

    # Convert V3 format to V2 tool parameters
    enable = memory_type != "no"
    notes = {
        "yes": "Full memory enabled",
        "no": "Memory disabled",
        "limited": "Limited memory - recent conversations only",
    }.get(memory_type, memory_type)

    configure_memory(db=db, confab_id=confab_id, memory_notes=notes, enable=enable)
    logger.info(f"[V3] Configured memory for confab {confab_id}: {memory_type}")


async def _save_tools(db: "Session", confab_id: int, data: Dict[str, Any]) -> None:
    """Save tool/API configurations."""
    tools = data.get("tools", [])
    for tool in tools:
        # V2 tool expects tool_name and api_key (empty string for now)
        add_tools_and_apis(db=db, confab_id=confab_id, tool_name=tool, api_key="")
    logger.info(f"[V3] Added {len(tools)} tool(s) to confab {confab_id}")


async def _save_guardrails(db: "Session", confab_id: int, data: Dict[str, Any]) -> None:
    """Save guardrails text."""
    guardrails_text = data.get("guardrails")
    if guardrails_text:
        guardrails(db=db, confab_id=confab_id, guardrails_text=guardrails_text)
        logger.info(f"[V3] Saved guardrails for confab {confab_id}")


async def _save_sample_io(db: "Session", confab_id: int, data: Dict[str, Any]) -> None:
    """Save sample input/output text."""
    sample_text = data.get("sample_io")
    if sample_text:
        sample_io(db=db, confab_id=confab_id, sample_text=sample_text)
        logger.info(f"[V3] Saved sample I/O for confab {confab_id}")


async def _save_review(db: "Session", confab_id: int, data: Dict[str, Any]) -> None:
    """Finalize and save the confab configuration."""
    if data.get("confirmed"):
        review_and_save(db=db, confab_id=confab_id)
        logger.info(f"[V3] Review complete for confab {confab_id}")
