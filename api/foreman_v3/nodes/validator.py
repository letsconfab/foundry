"""
Foreman V3 Validator Node

Validates extraction results and determines routing:
- complete: Route to saver
- clarify: Route to responder (ask follow-up)
- skip: Route to advancer (skip stage)
- error: Route to responder (show error)
"""

import logging
from typing import Dict, Any, Literal

from ..state import ForemanState

logger = logging.getLogger(__name__)


def validator_node(state: ForemanState) -> Dict[str, Any]:
    """
    Validate the stage result and prepare for routing.

    This node doesn't modify state - it just validates that
    stage_result is present and has a valid status.
    """
    stage_result = state.get("stage_result")

    if not stage_result:
        logger.error("[V3] validator_node: No stage_result in state")
        return {
            "stage_result": {
                "status": "error",
                "error_message": "Internal error: no extraction result",
            }
        }

    status = stage_result.get("status")
    if status not in ("complete", "clarify", "skip", "error"):
        logger.error(f"[V3] validator_node: Invalid status '{status}'")
        return {
            "stage_result": {
                "status": "error",
                "error_message": f"Internal error: invalid status '{status}'",
            }
        }

    logger.info(f"[V3] validator_node: status={status}")

    # Pass through - routing handled by conditional edges
    return {}


def route_after_validation(state: ForemanState) -> str:
    """
    Conditional edge function to route based on validation result.

    Routes:
    - "complete" -> saver (persist data)
    - "clarify" -> responder (ask follow-up)
    - "skip" -> advancer (skip stage)
    - "error" -> responder (show error)
    """
    stage_result = state.get("stage_result", {})
    status = stage_result.get("status", "error")

    logger.info(f"[V3] route_after_validation: status={status}")

    if status == "complete":
        return "saver"
    elif status == "clarify":
        return "responder"
    elif status == "skip":
        return "advancer"
    else:  # error or unknown
        return "responder"
