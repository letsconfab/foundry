"""
Conversation Provider Interfaces

Abstract interfaces for conversation storage, message publishing,
and participant management. These define the seam for plugging in
external chat/collaboration providers (Slack, Discord, etc.) in the
future. The default implementation uses Postgres via SQLAlchemy.

Usage:
    The ConversationService accepts optional provider overrides.
    If none are provided, it uses the default Postgres implementations.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


# ---------------------------------------------------------------------------
# ConversationStore — thread and message persistence
# ---------------------------------------------------------------------------

class ConversationStore(ABC):
    """
    Abstraction over conversation persistence.

    Implementations handle creating/finding threads, persisting messages,
    and querying message history. The default Postgres implementation
    wraps SQLAlchemy Thread/Message models.
    """

    @abstractmethod
    def create_thread(
        self,
        name: str,
        owner_user_id: int,
        conversation_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new conversation thread.

        Returns a dict with at least: {"id": int, "name": str}
        """
        ...

    @abstractmethod
    def get_thread(self, thread_id: int) -> Optional[Dict[str, Any]]:
        """Get a thread by ID. Returns None if not found."""
        ...

    @abstractmethod
    def persist_message(
        self,
        thread_id: int,
        content: str,
        role: str,
        sender_type: str = "user",
        sender_name: Optional[str] = None,
        sender_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Persist a message in a thread.

        Returns a dict with at least: {"id": int, "content": str, "role": str}
        """
        ...

    @abstractmethod
    def get_messages(
        self,
        thread_id: int,
        limit: Optional[int] = None,
        before_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get messages for a thread, ordered by creation time."""
        ...


# ---------------------------------------------------------------------------
# MessagePublisher — real-time message delivery
# ---------------------------------------------------------------------------

class MessagePublisher(ABC):
    """
    Abstraction over real-time message delivery.

    Implementations handle broadcasting messages to connected clients.
    The default Postgres implementation is a no-op (clients poll).
    Future implementations could publish to WebSocket channels,
    Slack webhooks, etc.
    """

    @abstractmethod
    async def publish(
        self,
        thread_id: int,
        message: Dict[str, Any],
    ) -> None:
        """Publish a message to subscribers of a thread."""
        ...

    @abstractmethod
    async def subscribe(
        self,
        thread_id: int,
        callback: Any,
    ) -> None:
        """Subscribe to messages on a thread."""
        ...


# ---------------------------------------------------------------------------
# ParticipantDirectory — participant lookup and management
# ---------------------------------------------------------------------------

class ParticipantDirectory(ABC):
    """
    Abstraction over participant management.

    Implementations handle adding/removing participants,
    checking membership, and resolving participant identities.
    """

    @abstractmethod
    def add_participant(
        self,
        thread_id: int,
        participant_type: str,
        participant_id: Optional[int] = None,
        system_agent_name: Optional[str] = None,
        role: str = "participant",
    ) -> Dict[str, Any]:
        """Add a participant to a thread."""
        ...

    @abstractmethod
    def remove_participant(self, thread_id: int, participant_id: int) -> bool:
        """Remove a participant from a thread. Returns True if removed."""
        ...

    @abstractmethod
    def get_participants(self, thread_id: int) -> List[Dict[str, Any]]:
        """Get all active participants for a thread."""
        ...

    @abstractmethod
    def is_member(self, thread_id: int, user_id: int) -> bool:
        """Check if a user is an active participant."""
        ...


# ---------------------------------------------------------------------------
# Default Postgres implementations
# ---------------------------------------------------------------------------

class PostgresConversationStore(ConversationStore):
    """Default ConversationStore backed by SQLAlchemy/Postgres."""

    def __init__(self, db):
        self.db = db

    def create_thread(self, name, owner_user_id, conversation_mode=None):
        from models import Thread
        thread = Thread(
            name=name,
            owner_user_id=owner_user_id,
            conversation_mode=conversation_mode,
        )
        self.db.add(thread)
        self.db.commit()
        self.db.refresh(thread)
        return {"id": thread.id, "name": thread.name}

    def get_thread(self, thread_id):
        from models import Thread
        thread = self.db.query(Thread).filter(Thread.id == thread_id).first()
        if not thread:
            return None
        return {"id": thread.id, "name": thread.name, "conversation_mode": thread.conversation_mode}

    def persist_message(self, thread_id, content, role, sender_type="user",
                        sender_name=None, sender_id=None):
        from models import Message
        msg = Message(
            thread_id=thread_id,
            content=content,
            role=role,
            sender_type=sender_type,
            sender_name=sender_name,
            sender_id=sender_id,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return {
            "id": msg.id,
            "content": msg.content,
            "role": msg.role,
            "sender_name": msg.sender_name,
            "created_at": str(msg.created_at),
        }

    def get_messages(self, thread_id, limit=None, before_id=None):
        from models import Message
        query = self.db.query(Message).filter(Message.thread_id == thread_id)
        if before_id:
            query = query.filter(Message.id < before_id)
        query = query.order_by(Message.created_at)
        if limit:
            query = query.limit(limit)
        return [
            {"id": m.id, "content": m.content, "role": m.role,
             "sender_name": m.sender_name, "created_at": str(m.created_at)}
            for m in query.all()
        ]


class PostgresMessagePublisher(MessagePublisher):
    """Default no-op publisher. Clients poll for new messages."""

    async def publish(self, thread_id, message):
        pass  # No-op: clients poll via GET /threads/{id}/messages

    async def subscribe(self, thread_id, callback):
        pass  # No-op: polling-based


class PostgresParticipantDirectory(ParticipantDirectory):
    """Default ParticipantDirectory backed by SQLAlchemy/Postgres."""

    def __init__(self, db):
        self.db = db

    def add_participant(self, thread_id, participant_type, participant_id=None,
                        system_agent_name=None, role="participant"):
        from models import ThreadParticipant
        p = ThreadParticipant(
            thread_id=thread_id,
            participant_type=participant_type,
            participant_id=participant_id,
            system_agent_name=system_agent_name,
            role=role,
        )
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return {"id": p.id, "participant_type": p.participant_type, "role": p.role}

    def remove_participant(self, thread_id, participant_id):
        from models import ThreadParticipant
        p = self.db.query(ThreadParticipant).filter(
            ThreadParticipant.thread_id == thread_id,
            ThreadParticipant.id == participant_id,
        ).first()
        if not p:
            return False
        p.is_active = False
        self.db.commit()
        return True

    def get_participants(self, thread_id):
        from models import ThreadParticipant
        participants = self.db.query(ThreadParticipant).filter(
            ThreadParticipant.thread_id == thread_id,
            ThreadParticipant.is_active == True,
        ).all()
        return [
            {"id": p.id, "participant_type": p.participant_type,
             "participant_id": p.participant_id,
             "system_agent_name": p.system_agent_name, "role": p.role}
            for p in participants
        ]

    def is_member(self, thread_id, user_id):
        from models import ThreadParticipant
        return self.db.query(ThreadParticipant).filter(
            ThreadParticipant.thread_id == thread_id,
            ThreadParticipant.participant_type == "user",
            ThreadParticipant.participant_id == user_id,
            ThreadParticipant.is_active == True,
        ).first() is not None
