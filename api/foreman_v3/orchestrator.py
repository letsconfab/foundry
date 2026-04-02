"""
Foreman V3 Orchestrator

Main entry point for V3 Foreman interactions.
Wraps graph invocation with checkpointing and message handling.
"""

import logging
from typing import Dict, Any, Optional, TYPE_CHECKING

from langchain_core.messages import HumanMessage

from .state import ForemanState, create_initial_state
from .graph import get_foreman_graph
from .checkpointer import get_checkpointer, get_thread_config
from .compat import format_v3_response, format_error_response
from .adapters import orm_to_langgraph

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from models import Confab, Message

logger = logging.getLogger(__name__)


class ForemanV3:
    """
    Foreman V3 Orchestrator using LangGraph StateGraph.

    Provides the same interface as V2 Foreman for easy integration.
    """

    def __init__(self, confab_id: int, db: "Session"):
        """
        Initialize Foreman V3 for a specific confab.

        Args:
            confab_id: The confab being configured
            db: SQLAlchemy database session
        """
        self.confab_id = confab_id
        self.db = db
        self.graph = get_foreman_graph()
        self._confab: Optional["Confab"] = None
        self._thread_id: Optional[int] = None

    async def initialize(self) -> None:
        """
        Initialize context (mirrors V2 Foreman.initialize()).

        Loads confab and prepares for message processing.
        """
        from models import Confab

        self._confab = self.db.query(Confab).filter(Confab.id == self.confab_id).first()
        if not self._confab:
            raise ValueError(f"Confab {self.confab_id} not found")

        logger.info(f"[V3] ForemanV3 initialized for confab {self.confab_id}")

    @property
    def confab(self) -> "Confab":
        """Get the confab being configured."""
        if not self._confab:
            raise RuntimeError("ForemanV3 not initialized. Call initialize() first.")
        return self._confab

    async def process_message(
        self,
        user_message: str,
        thread_id: Optional[int] = None,
        thread_history: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Process a user message through the V3 graph.

        Args:
            user_message: The user's input message
            thread_id: Optional thread ID for checkpointing
            thread_history: Optional list of previous Message ORM objects

        Returns:
            V2-compatible response dict
        """
        logger.info(
            f"[V3] Processing message [confab={self.confab_id}, "
            f"thread={thread_id}, msg='{user_message[:50]}...']"
        )

        self._thread_id = thread_id or 0

        try:
            # Build initial state or load from checkpoint
            state = await self._build_state(user_message, thread_history)

            # Build graph config
            config = get_thread_config(self.confab_id, self._thread_id)
            config["configurable"]["db"] = self.db

            # Get checkpointer (may be None if not configured)
            checkpointer = await get_checkpointer()

            # Invoke graph
            if checkpointer:
                # With checkpointing
                graph_with_checkpointer = self.graph.with_config(
                    configurable={"checkpointer": checkpointer}
                )
                result = await graph_with_checkpointer.ainvoke(state, config)
            else:
                # Without checkpointing (fallback)
                result = await self.graph.ainvoke(state, config)

            logger.info(
                f"[V3] Graph execution complete [stage={result.get('current_stage')}, "
                f"status={result.get('stage_result', {}).get('status')}]"
            )

            # Format response
            return format_v3_response(result, self._thread_id)

        except Exception as e:
            logger.error(f"[V3] Error processing message: {e}", exc_info=True)
            return format_error_response(
                confab_id=self.confab_id,
                thread_id=self._thread_id,
                error_message=str(e),
                current_stage=self._get_current_stage(),
            )

    async def _build_state(
        self,
        user_message: str,
        thread_history: Optional[list] = None,
    ) -> ForemanState:
        """
        Build initial state for graph invocation.

        Loads existing progress from confab if available.
        """
        # Get current progress from confab
        setup_progress = self.confab.setup_progress or {}
        current_stage = setup_progress.get("current_stage", "purpose")
        completed_steps = setup_progress.get("completed_steps", [])

        # Convert step numbers to stage names
        stage_order = ["purpose", "participants", "memory", "tools", "guardrails", "sample_io", "review"]
        completed_stages = [
            stage_order[step - 1] for step in completed_steps
            if 1 <= step <= len(stage_order)
        ]

        # Build collected_info from confab data
        collected_info = self._extract_collected_info(setup_progress)

        # Convert thread history to LangGraph messages
        messages = []
        if thread_history:
            messages = orm_to_langgraph(thread_history)

        # Add current user message
        messages.append(HumanMessage(content=user_message))

        return {
            "messages": messages,
            "collected_info": collected_info,
            "current_stage": current_stage if current_stage in stage_order + ["complete"] else "purpose",
            "completed_stages": completed_stages,
            "confab_id": self.confab_id,
            "thread_id": self._thread_id,
            "is_complete": current_stage == "complete",
            "stage_result": None,
            "is_update": False,
            "update_target": None,
            "last_error": None,
        }

    def _extract_collected_info(self, setup_progress: dict) -> dict:
        """Extract collected info from confab's setup_progress."""
        return {
            "purpose": self.confab.purpose,
            "name": self.confab.name,
            "participants": setup_progress.get("participants", []),
            "memory_type": self._normalize_memory_type(setup_progress.get("memory_notes")),
            "tools": self._extract_tools(setup_progress),
            "guardrails": self._extract_guardrails(),
            "sample_io": setup_progress.get("sample_io"),
        }

    def _normalize_memory_type(self, memory_notes: Optional[str]) -> Optional[str]:
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

    def _extract_tools(self, setup_progress: dict) -> list:
        """Extract tool names from setup_progress."""
        integrations = setup_progress.get("integrations", {})
        apis = integrations.get("apis", [])
        return [api.get("name", "") for api in apis if api.get("name")]

    def _extract_guardrails(self) -> Optional[str]:
        """Extract guardrails as markdown text."""
        if not self.confab.guardrails:
            return None
        rules = self.confab.guardrails
        if isinstance(rules, list):
            lines = []
            for i, rule in enumerate(rules, 1):
                if isinstance(rule, dict):
                    lines.append(f"{i}. {rule.get('rule', '')}")
                else:
                    lines.append(f"{i}. {rule}")
            return "\n".join(lines)
        return str(rules)

    def _get_current_stage(self) -> str:
        """Get current stage from confab, with fallback."""
        if self._confab:
            setup_progress = self._confab.setup_progress or {}
            return setup_progress.get("current_stage", "purpose")
        return "purpose"
