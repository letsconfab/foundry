"""
Foreman V3 StateGraph Construction

Assembles all nodes into a LangGraph StateGraph implementing
the Information Collector (gather-verify-loop) pattern.
"""

import logging
from typing import Optional

from langgraph.graph import StateGraph, END

from .state import ForemanState, STAGE_ORDER
from .nodes import (
    # Router
    router_node,
    route_to_extractor,
    # Extractors
    extract_purpose_node,
    extract_participants_node,
    extract_memory_node,
    extract_tools_node,
    extract_guardrails_node,
    extract_sample_io_node,
    extract_review_node,
    # Core flow
    validator_node,
    route_after_validation,
    saver_node,
    advancer_node,
    responder_node,
)

logger = logging.getLogger(__name__)


def build_foreman_graph() -> StateGraph:
    """
    Build the Foreman V3 StateGraph.

    Graph Flow:
    ```
    START → ROUTER → [EXTRACTOR_*] → VALIDATOR → SAVER/RESPONDER → ADVANCER → RESPONDER → END
                          ↑                                              │
                          └────────────────── (loop back) ───────────────┘
    ```

    Returns:
        Compiled StateGraph ready for invocation
    """
    logger.info("[V3] Building Foreman StateGraph")

    builder = StateGraph(ForemanState)

    # Add all nodes
    builder.add_node("router", router_node)

    # Extractor nodes - one per stage
    builder.add_node("purpose", extract_purpose_node)
    builder.add_node("participants", extract_participants_node)
    builder.add_node("memory", extract_memory_node)
    builder.add_node("tools", extract_tools_node)
    builder.add_node("guardrails", extract_guardrails_node)
    builder.add_node("sample_io", extract_sample_io_node)
    builder.add_node("review", extract_review_node)

    # Core flow nodes
    builder.add_node("validator", validator_node)
    builder.add_node("validator_skip", _validator_skip_node)  # For direct skip routing
    builder.add_node("saver", saver_node)
    builder.add_node("advancer", advancer_node)
    builder.add_node("responder", responder_node)

    # Set entry point
    builder.set_entry_point("router")

    # Router → Stage Extractors (conditional)
    builder.add_conditional_edges(
        "router",
        route_to_extractor,
        {
            "purpose": "purpose",
            "participants": "participants",
            "memory": "memory",
            "tools": "tools",
            "guardrails": "guardrails",
            "sample_io": "sample_io",
            "review": "review",
            "validator_skip": "validator_skip",  # Direct skip route
            "complete": END,
        }
    )

    # All extractors → Validator
    for stage in STAGE_ORDER:
        builder.add_edge(stage, "validator")

    # Validator skip → Advancer (skip detected in router)
    builder.add_edge("validator_skip", "advancer")

    # Validator → Saver/Responder (conditional based on status)
    builder.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "saver": "saver",
            "responder": "responder",
            "advancer": "advancer",
        }
    )

    # Saver → Advancer (after successful save)
    builder.add_edge("saver", "advancer")

    # Advancer → Responder (generate response after stage change)
    builder.add_edge("advancer", "responder")

    # Responder → END (return response to user)
    builder.add_edge("responder", END)

    logger.info("[V3] StateGraph built successfully")

    return builder.compile()


def _validator_skip_node(state: ForemanState) -> dict:
    """
    Pass-through node for skip routing.

    When router detects skip intent, it sets stage_result with skip status.
    This node just passes through to advancer.
    """
    return {}


# Global compiled graph instance (lazy initialization)
_foreman_graph: Optional[StateGraph] = None


def get_foreman_graph() -> StateGraph:
    """
    Get the compiled Foreman graph (singleton).

    Returns:
        Compiled StateGraph instance
    """
    global _foreman_graph
    if _foreman_graph is None:
        _foreman_graph = build_foreman_graph()
    return _foreman_graph
