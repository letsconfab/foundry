"""
Foreman V3 Graph Nodes

Each node is a function that receives ForemanState and returns state updates.
Nodes are composed into a StateGraph in graph.py.
"""

from .router import router_node, route_to_extractor
from .extractors import (
    extract_purpose_node,
    extract_participants_node,
    extract_memory_node,
    extract_documents_node,
    extract_tools_node,
    extract_guardrails_node,
    extract_sample_io_node,
    extract_review_node,
)
from .validator import validator_node, route_after_validation
from .saver import saver_node
from .advancer import advancer_node
from .responder import responder_node

__all__ = [
    # Router
    "router_node",
    "route_to_extractor",
    # Extractors
    "extract_purpose_node",
    "extract_participants_node",
    "extract_memory_node",
    "extract_documents_node",
    "extract_tools_node",
    "extract_guardrails_node",
    "extract_sample_io_node",
    "extract_review_node",
    # Core flow
    "validator_node",
    "route_after_validation",
    "saver_node",
    "advancer_node",
    "responder_node",
]
