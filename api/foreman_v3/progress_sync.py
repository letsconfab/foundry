"""
Foreman V3 Progress Synchronization

Single source of truth for mapping between LangGraph graph state
and confab.setup_progress (the database-persisted progress snapshot).

All reads and writes to setup_progress should go through this module.
"""

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from .state import STAGE_ORDER

if TYPE_CHECKING:
    from models import Confab
    from sqlalchemy.orm import Session
    from schemas import SetupProgressResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage ↔ step number conversion
# ---------------------------------------------------------------------------

def stages_to_steps(stages: List[str]) -> List[int]:
    """Convert stage names to 1-indexed step numbers."""
    return sorted(
        STAGE_ORDER.index(s) + 1
        for s in stages
        if s in STAGE_ORDER
    )


def steps_to_stages(steps: List[int]) -> List[str]:
    """Convert 1-indexed step numbers to stage names."""
    return [
        STAGE_ORDER[n - 1]
        for n in sorted(steps)
        if 1 <= n <= len(STAGE_ORDER)
    ]


# ---------------------------------------------------------------------------
# Graph state → setup_progress (write to DB)
# ---------------------------------------------------------------------------

def graph_state_to_progress(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a setup_progress dict from the current LangGraph state.

    This is the canonical mapping used by the advancer node and
    any other code that needs to persist graph state to the DB.
    """
    completed_stages = list(state.get("completed_stages", []))
    current_stage = state.get("current_stage", "purpose")
    collected_info = state.get("collected_info", {})

    progress: Dict[str, Any] = {
        "current_stage": current_stage,
        "completed_steps": stages_to_steps(completed_stages),
    }

    # Persist collected data fields (only if present)
    if collected_info.get("participants"):
        progress["participants"] = collected_info["participants"]
    if collected_info.get("memory_type"):
        progress["memory_notes"] = collected_info["memory_type"]
    if collected_info.get("tools"):
        progress["integrations"] = {
            "apis": [{"name": t} for t in collected_info["tools"]]
        }
    if collected_info.get("guardrails"):
        progress["guardrails_text"] = collected_info["guardrails"]
    if collected_info.get("sample_io"):
        progress["sample_io"] = collected_info["sample_io"]

    return progress


def save_progress_to_db(
    db: "Session",
    confab_id: int,
    current_stage: str,
    completed_stages: List[str],
    extra_fields: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Persist stage progress to confab.setup_progress in the database.

    This is the single write path for stage/step progress updates.
    Additional data fields (participants, memory, etc.) can be passed
    via extra_fields and are merged into the existing progress dict.
    """
    try:
        from models import Confab
        from sqlalchemy.orm.attributes import flag_modified

        confab = db.query(Confab).filter(Confab.id == confab_id).first()
        if not confab:
            logger.warning(f"[progress_sync] Confab {confab_id} not found")
            return

        progress = confab.setup_progress or {}
        progress["current_stage"] = current_stage
        progress["completed_steps"] = stages_to_steps(completed_stages)

        if extra_fields:
            progress.update(extra_fields)

        confab.setup_progress = progress
        flag_modified(confab, "setup_progress")
        db.commit()

        logger.info(
            f"[progress_sync] Saved progress for confab {confab_id}: "
            f"stage={current_stage}, steps={progress['completed_steps']}"
        )
    except Exception as e:
        logger.error(f"[progress_sync] Failed to save progress: {e}")


# ---------------------------------------------------------------------------
# setup_progress → Graph state (read from DB)
# ---------------------------------------------------------------------------

def progress_to_graph_fields(setup_progress: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract graph-relevant fields from a setup_progress dict.

    Returns a dict with keys matching ForemanState fields:
    - current_stage
    - completed_stages
    - collected_info (partial)

    Used by the orchestrator's _build_state to reconstruct graph state
    from the database on resume.
    """
    current_stage = setup_progress.get("current_stage", "purpose")
    completed_steps = setup_progress.get("completed_steps", [])
    completed_stages = steps_to_stages(completed_steps)

    collected_info = {
        "participants": setup_progress.get("participants", []),
        "memory_type": _normalize_memory_type(setup_progress.get("memory_notes")),
        "tools": _extract_tools(setup_progress),
        "sample_io": setup_progress.get("sample_io"),
    }

    return {
        "current_stage": current_stage,
        "completed_stages": completed_stages,
        "collected_info": collected_info,
    }


# ---------------------------------------------------------------------------
# Helpers (moved from orchestrator)
# ---------------------------------------------------------------------------

def _normalize_memory_type(memory_notes: Optional[str]) -> Optional[str]:
    """Convert memory notes to memory type."""
    if not memory_notes:
        return None
    lower = memory_notes.lower()
    if "disabled" in lower or "no memory" in lower:
        return "no"
    if "limited" in lower:
        return "limited"
    if "enabled" in lower or "full" in lower:
        return "yes"
    return None


def to_setup_progress_response(setup_progress: Optional[Dict[str, Any]]) -> Optional["SetupProgressResponse"]:
    """
    Convert a raw setup_progress dict to a SetupProgressResponse schema.

    Returns None if setup_progress is empty/None. This is the single
    conversion point used by conversation_service and route handlers.
    """
    if not setup_progress:
        return None

    from schemas import SetupProgressResponse

    completed_steps = setup_progress.get("completed_steps", [])
    total = len(STAGE_ORDER)
    remaining = [i for i in range(1, total + 1) if i not in completed_steps]

    return SetupProgressResponse(
        completed_steps=completed_steps,
        current_stage=setup_progress.get("current_stage", "purpose"),
        total_steps=total,
        remaining_steps=remaining,
    )


def _extract_tools(setup_progress: dict) -> list:
    """Extract tool names from setup_progress integrations."""
    integrations = setup_progress.get("integrations", {})
    apis = integrations.get("apis", [])
    return [api.get("name", "") for api in apis if api.get("name")]
