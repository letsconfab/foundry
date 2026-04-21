"""
Foreman V3 Advancer Node

Advances to the next stage after successful save or skip.
Updates completed_stages and current_stage.
Persists stage progress to the database via progress_sync.
"""

import logging
from typing import Dict, Any, TYPE_CHECKING

from langgraph.types import RunnableConfig

from ..state import ForemanState, STAGE_ORDER, get_next_stage
from ..progress_sync import save_progress_to_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def advancer_node(state: ForemanState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Advance to the next stage in the interview flow.

    Called after:
    - Successful save (from saver node)
    - Skip (from validator routing)

    For out-of-order updates, does NOT advance - just confirms the update.
    """
    current_stage = state["current_stage"]
    completed_stages = list(state.get("completed_stages", []))
    is_update = state.get("is_update", False)
    update_target = state.get("update_target")

    # For updates, don't advance stage
    if is_update and update_target:
        logger.info(f"[V3] advancer_node: Update to {update_target} complete, staying at {current_stage}")
        return {
            "is_update": False,
            "update_target": None,
        }

    # Mark current stage as completed (if not already)
    if current_stage not in completed_stages and current_stage in STAGE_ORDER:
        completed_stages.append(current_stage)
        logger.info(f"[V3] advancer_node: Marked {current_stage} as complete")

    # Get next stage
    next_stage = get_next_stage(current_stage)

    is_complete = next_stage == "complete" or current_stage == "review"
    final_stage = "complete" if is_complete else next_stage

    # Persist stage progress to database
    _save_stage_progress(
        config=config,
        confab_id=state["confab_id"],
        current_stage=final_stage,
        completed_stages=completed_stages,
    )

    if is_complete:
        logger.info(f"[V3] advancer_node: Interview complete!")
        return {
            "current_stage": "complete",
            "completed_stages": completed_stages,
            "is_complete": True,
        }

    logger.info(f"[V3] advancer_node: Advancing from {current_stage} to {next_stage}")
    return {
        "current_stage": next_stage,
        "completed_stages": completed_stages,
        "is_update": False,
        "update_target": None,
    }


def _save_stage_progress(
    config: RunnableConfig,
    confab_id: int,
    current_stage: str,
    completed_stages: list,
) -> None:
    """Persist stage progress to the database via progress_sync."""
    db = config.get("configurable", {}).get("db")
    if not db:
        logger.warning("[V3] advancer_node: No db session, skipping progress save")
        return

    save_progress_to_db(db, confab_id, current_stage, completed_stages)
