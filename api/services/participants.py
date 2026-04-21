"""
Participant Utilities

Helper functions for thread participant membership, addressing,
routing, and permissions. Centralizes participant-related queries
so they don't scatter across routes and services.
"""

import logging
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy.orm import Session

from models import ThreadParticipant

if TYPE_CHECKING:
    from models import Thread

logger = logging.getLogger(__name__)

# Conversation modes (also used in conversation_service.py)
FOREMAN_BUILD = "foreman_build"
CONFAB_RUNTIME = "confab_runtime"
MULTI_AGENT = "multi_agent_workspace"


# ---------------------------------------------------------------------------
# Membership queries
# ---------------------------------------------------------------------------

def get_active_participants(db: Session, thread_id: int) -> List[ThreadParticipant]:
    """Get all active participants for a thread."""
    return (
        db.query(ThreadParticipant)
        .filter(
            ThreadParticipant.thread_id == thread_id,
            ThreadParticipant.is_active == True,
        )
        .all()
    )


def has_participant(db: Session, thread_id: int, *, participant_type: str,
                    participant_id: Optional[int] = None,
                    system_agent_name: Optional[str] = None) -> bool:
    """Check if a specific participant is active in a thread."""
    query = db.query(ThreadParticipant).filter(
        ThreadParticipant.thread_id == thread_id,
        ThreadParticipant.participant_type == participant_type,
        ThreadParticipant.is_active == True,
    )
    if participant_id is not None:
        query = query.filter(ThreadParticipant.participant_id == participant_id)
    if system_agent_name is not None:
        query = query.filter(ThreadParticipant.system_agent_name == system_agent_name)
    return query.first() is not None


def has_foreman(db: Session, thread_id: int) -> bool:
    """Check if the foreman system agent is active in a thread."""
    return has_participant(db, thread_id, participant_type="system", system_agent_name="foreman")


def has_confab(db: Session, thread_id: int, confab_id: Optional[int] = None) -> bool:
    """Check if any (or a specific) confab is active in a thread."""
    return has_participant(db, thread_id, participant_type="confab", participant_id=confab_id)


def get_confab_ids(db: Session, thread_id: int) -> List[int]:
    """Get all active confab participant IDs in a thread."""
    participants = (
        db.query(ThreadParticipant)
        .filter(
            ThreadParticipant.thread_id == thread_id,
            ThreadParticipant.participant_type == "confab",
            ThreadParticipant.is_active == True,
        )
        .all()
    )
    return [p.participant_id for p in participants if p.participant_id]


def is_user_in_thread(db: Session, thread_id: int, user_id: int) -> bool:
    """Check if a user is an active participant in a thread."""
    return has_participant(db, thread_id, participant_type="user", participant_id=user_id)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def infer_mode_from_participants(db: Session, thread_id: int) -> str:
    """
    Infer conversation mode from participant composition.

    Prefer reading thread.conversation_mode when available;
    use this as a fallback for threads created before the mode column.
    """
    from models import Confab

    participants = get_active_participants(db, thread_id)

    foreman_present = False
    confab_ids: List[int] = []

    for p in participants:
        if p.participant_type == "system" and p.system_agent_name == "foreman":
            foreman_present = True
        elif p.participant_type == "confab" and p.participant_id:
            confab_ids.append(p.participant_id)

    if foreman_present and confab_ids:
        confab = db.query(Confab).filter(Confab.id == confab_ids[0]).first()
        if confab and confab.status == "building":
            return FOREMAN_BUILD

    if confab_ids:
        return CONFAB_RUNTIME

    return CONFAB_RUNTIME


def get_conversation_mode(db: Session, thread: "Thread") -> str:
    """
    Get the conversation mode for a thread.

    Uses the explicit conversation_mode field if set,
    otherwise falls back to inference from participants.
    """
    if hasattr(thread, "conversation_mode") and thread.conversation_mode:
        return thread.conversation_mode
    return infer_mode_from_participants(db, thread.id)


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

def can_send_message(db: Session, thread_id: int, user_id: int) -> bool:
    """Check if a user can send messages in a thread (active participant or owner)."""
    from models import Thread
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if not thread:
        return False
    if thread.owner_user_id == user_id:
        return True
    return is_user_in_thread(db, thread_id, user_id)
