"""
Foreman V3 — LangGraph Information Collector Implementation

This package implements the Foreman interview flow using LangGraph's
StateGraph pattern with PostgreSQL checkpointing for conversation
persistence and resumability.

Architecture:
- state.py: ForemanState TypedDict defining graph state
- adapters.py: Message format conversion (ORM <-> LangGraph)
- nodes/: Individual graph nodes (extractors, router, saver, etc.)
- graph.py: StateGraph construction
- checkpointer.py: PostgresSaver integration
- compat.py: V2-compatible response formatting
"""

import os
from dotenv import load_dotenv

# Load .env before reading env vars
load_dotenv()

# V3 is now the canonical Foreman implementation (default: true).
# Set FOREMAN_V3_ENABLED=false only for emergency rollback to legacy foreman.py.
FOREMAN_V3_ENABLED = os.getenv("FOREMAN_V3_ENABLED", "true").lower() == "true"

from .state import ForemanState, InformationSchema
from .graph import build_foreman_graph
from .checkpointer import get_checkpointer, get_thread_config
from .compat import format_v3_response
from .orchestrator import ForemanV3

__all__ = [
    "FOREMAN_V3_ENABLED",
    "ForemanV3",
    "ForemanState",
    "InformationSchema",
    "build_foreman_graph",
    "get_checkpointer",
    "get_thread_config",
    "format_v3_response",
]
