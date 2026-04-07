"""
Foreman V3 Router Node

Routes user messages to the appropriate extractor based on:
1. Current stage (normal flow)
2. Update intent detection (out-of-order updates)
"""

import re
import logging
from typing import Dict, Any, Literal

from ..state import ForemanState
from ..adapters import get_last_user_message

logger = logging.getLogger(__name__)


# Update trigger patterns (ported from V2 _detect_update_intent)
UPDATE_PATTERNS = [
    r"^update\s+(the\s+)?",
    r"^change\s+(the\s+)?",
    r"^modify\s+(the\s+)?",
    r"^edit\s+(the\s+)?",
    r"^revise\s+(the\s+)?",
    r"^fix\s+(the\s+)?",
    r"^add\s+to\s+(the\s+)?",
]

# Stage keyword mappings for update detection
STAGE_KEYWORDS = {
    "purpose": ["purpose", "goal", "objective", "main job", "what it does"],
    "participants": ["participant", "user", "email", "access", "who can"],
    "memory": ["memory", "remember", "conversation", "context"],
    "tools": ["tool", "api", "capability", "integration"],
    "guardrails": ["guardrail", "rule", "safety", "boundary", "restriction"],
    "sample_io": ["sample", "example", "interaction", "input", "output"],
}


def _detect_skip_intent(message: str) -> bool:
    """Check if user wants to skip the current stage."""
    # Normalize: lowercase, strip whitespace and trailing punctuation
    lower = message.lower().strip().rstrip('.,!?;:')
    skip_phrases = [
        "skip", "skip this", "skip it", "next", "move on",
        "don't need", "not needed", "no thanks", "n/a", "na",
        "none", "nothing", "pass",
        # Participants-specific skip phrases
        "only me", "just me", "me only", "just myself",
        "no one else", "nobody else", "no others", "private",
    ]
    return any(phrase == lower or lower.startswith(phrase + " ") for phrase in skip_phrases)


def _detect_update_intent(message: str, completed_stages: list) -> tuple:
    """
    Detect if user is trying to update a previously completed stage.

    Returns:
        (target_stage, extracted_content) if update detected
        (None, None) otherwise
    """
    lower = message.lower()

    # Check for update trigger patterns
    for pattern in UPDATE_PATTERNS:
        if re.match(pattern, lower):
            # Look for stage keywords
            for stage, keywords in STAGE_KEYWORDS.items():
                if stage in completed_stages:
                    if any(kw in lower for kw in keywords):
                        # Extract content after the stage reference
                        # Try to find content after colon or stage keyword
                        content = None
                        if ":" in message:
                            content = message.split(":", 1)[1].strip()
                        else:
                            # Find the last keyword and take everything after
                            for kw in keywords:
                                idx = lower.find(kw)
                                if idx != -1:
                                    after_kw = message[idx + len(kw):].strip()
                                    if after_kw:
                                        content = after_kw
                                        break

                        logger.info(f"[V3] Update intent detected: stage={stage}, content={content[:50] if content else None}...")
                        return (stage, content)

    return (None, None)


def router_node(state: ForemanState) -> Dict[str, Any]:
    """
    Route to appropriate extractor based on message analysis.

    Handles:
    - Skip intent: Sets stage_result with skip status
    - Update intent: Routes to target stage extractor
    - Normal flow: Routes to current stage extractor
    """
    last_msg = get_last_user_message(state["messages"])
    current_stage = state["current_stage"]
    completed_stages = state.get("completed_stages", [])

    logger.info(f"[V3] router_node: current_stage={current_stage}, msg='{last_msg[:50]}...'")

    # Check for skip intent first
    if _detect_skip_intent(last_msg):
        logger.info(f"[V3] Skip intent detected for stage {current_stage}")
        return {
            "stage_result": {
                "status": "skip",
                "data": {},
            },
            "is_update": False,
            "update_target": None,
        }

    # Check for update intent (out-of-order updates)
    target_stage, extracted_content = _detect_update_intent(last_msg, completed_stages)

    if target_stage:
        logger.info(f"[V3] Update intent: routing to {target_stage} instead of {current_stage}")
        return {
            "is_update": True,
            "update_target": target_stage,
            # Route will use update_target instead of current_stage
        }

    # Normal flow: route to current stage
    return {
        "is_update": False,
        "update_target": None,
    }


def route_to_extractor(state: ForemanState) -> str:
    """
    Conditional edge function to determine which extractor to call.

    Returns the name of the extractor node to route to.
    """
    # Check if skip was detected in router
    stage_result = state.get("stage_result")
    logger.info(f"[V3] route_to_extractor: stage_result={stage_result}, current_stage={state.get('current_stage')}")
    if stage_result and stage_result.get("status") == "skip":
        # Skip detected, go directly to validator
        logger.info("[V3] route_to_extractor: Routing to validator_skip")
        return "validator_skip"

    # Check for update routing
    if state.get("is_update") and state.get("update_target"):
        target = state["update_target"]
        logger.info(f"[V3] Routing to update extractor: {target}")
        return target

    # Normal routing by current stage
    current = state["current_stage"]

    if current == "complete":
        return "complete"

    logger.info(f"[V3] Routing to extractor: {current}")
    return current
