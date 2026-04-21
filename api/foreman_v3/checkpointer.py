"""
Foreman V3 Checkpointer Integration

Provides PostgreSQL-backed conversation persistence using LangGraph's
PostgresSaver checkpointer.
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Global checkpointer instance
_checkpointer = None
_checkpointer_initialized = False


async def get_checkpointer():
    """
    Get the PostgreSQL checkpointer instance (singleton).

    Creates tables on first call using LangGraph's built-in setup.

    NOTE: Checkpointing is currently disabled until we resolve state
    persistence issues. The orchestrator manages state via database
    (confab.setup_progress) instead.

    Returns:
        None (checkpointing disabled)
    """
    # Checkpointing is disabled for now - state is managed via DB
    # The langgraph-checkpoint-postgres 3.x API uses async context managers
    # which requires different lifecycle management. For now, we rely on
    # the database-based state persistence in the advancer node.
    logger.info("[V3] Checkpointing disabled, using DB-based state persistence")
    return None


def get_thread_config(confab_id: int, thread_id: int) -> Dict[str, Any]:
    """
    Build configuration dict for graph invocation with thread tracking.

    Args:
        confab_id: The confab being configured
        thread_id: The conversation thread ID

    Returns:
        Config dict with thread_id for checkpointing
    """
    return {
        "configurable": {
            "thread_id": f"foreman-{confab_id}-{thread_id}",
        }
    }


async def cleanup_checkpoints(confab_id: int) -> bool:
    """
    Delete checkpoints for a confab when it's deployed.

    Called when confab status changes from 'building' to 'deployed'.

    Args:
        confab_id: The confab ID to clean up

    Returns:
        True if cleanup successful, False otherwise
    """
    checkpointer = await get_checkpointer()
    if not checkpointer:
        logger.warning(f"[V3] No checkpointer available for cleanup of confab {confab_id}")
        return False

    try:
        # LangGraph checkpointer stores by thread_id
        # We need to find and delete all threads for this confab
        # Pattern: foreman-{confab_id}-*

        # Note: PostgresSaver doesn't have built-in pattern deletion
        # This would need custom SQL or iteration through known threads
        # For now, log intent - actual cleanup requires thread tracking

        logger.info(f"[V3] Checkpoint cleanup requested for confab {confab_id}")

        # TODO: Implement actual cleanup when we track thread IDs
        # Options:
        # 1. Store thread IDs in confab.setup_progress["v3_threads"]
        # 2. Use raw SQL to delete by thread_id pattern
        # 3. Track in separate table

        return True

    except Exception as e:
        logger.error(f"[V3] Checkpoint cleanup failed for confab {confab_id}: {e}")
        return False


async def get_checkpoint_state(confab_id: int, thread_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve the latest checkpoint state for a conversation.

    Args:
        confab_id: The confab ID
        thread_id: The thread ID

    Returns:
        Checkpoint state dict if found, None otherwise
    """
    checkpointer = await get_checkpointer()
    if not checkpointer:
        return None

    config = get_thread_config(confab_id, thread_id)

    try:
        checkpoint = await checkpointer.aget(config)
        if checkpoint:
            logger.info(f"[V3] Retrieved checkpoint for confab {confab_id}, thread {thread_id}")
            return checkpoint
        return None
    except Exception as e:
        logger.error(f"[V3] Failed to retrieve checkpoint: {e}")
        return None
