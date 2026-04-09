"""
ConversationService — owns conversation bootstrap, message routing, and persistence.

Centralizes logic that was previously split between AgentChat.tsx (frontend)
and main.py (inline in route handlers). The UI should call high-level
conversation endpoints; this service handles thread creation, participant
wiring, welcome messages, orchestrator dispatch, and response persistence.
"""

import datetime
import logging
from typing import Optional, List

from sqlalchemy.orm import Session

from models import User, Confab, Thread, ThreadParticipant, Message
from schemas import (
    MessageResponse,
    ChatResponse,
    ParticipantResponse,
    SetupProgressResponse,
    ForemanChatResponse,
    ForemanV2Metadata,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conversation modes
# ---------------------------------------------------------------------------

FOREMAN_BUILD = "foreman_build"
CONFAB_RUNTIME = "confab_runtime"
MULTI_AGENT_WORKSPACE = "multi_agent_workspace"  # reserved


# ---------------------------------------------------------------------------
# Foreman welcome message
# ---------------------------------------------------------------------------

FOREMAN_WELCOME = (
    "Hi, I'm the Foreman. I'll help you build your agent through a quick conversation.\n\n"
    "Let's start with the basics: **What should this agent do?**\n\n"
    "Here are some examples:\n"
    '- "A customer support bot that handles refund requests and tracks order status"\n'
    '- "An internal assistant that answers questions about company policies"\n'
    '- "A code reviewer that checks for security issues and suggests fixes"\n\n'
    "What's your agent's main job?"
)

FOREMAN_RESUME = (
    "Welcome back! Let's pick up where we left off building your agent."
)


# ---------------------------------------------------------------------------
# Data classes for service responses
# ---------------------------------------------------------------------------

class ConversationStartResult:
    """Returned by start/resume methods."""

    def __init__(
        self,
        thread_id: int,
        confab_id: int | None,
        conversation_mode: str,
        messages: list[MessageResponse],
        participants: list[ParticipantResponse],
        setup_progress: SetupProgressResponse | None = None,
        current_stage: str | None = None,
    ):
        self.thread_id = thread_id
        self.confab_id = confab_id
        self.conversation_mode = conversation_mode
        self.messages = messages
        self.participants = participants
        self.setup_progress = setup_progress
        self.current_stage = current_stage


# ---------------------------------------------------------------------------
# ConversationService
# ---------------------------------------------------------------------------

class ConversationService:
    """
    Central service for conversation lifecycle.

    All conversation operations (start, resume, send message) flow through
    this class. Route handlers should be thin wrappers that delegate here.
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Bootstrap helpers
    # ------------------------------------------------------------------

    def create_thread_for_confab_build(self, user_id: int, confab_id: int) -> Thread:
        """Create a thread wired for a foreman build conversation."""
        confab = self.db.query(Confab).filter(Confab.id == confab_id).first()
        name_part = confab.name if confab else "New Confab"
        thread_name = f"Build: {name_part} – {datetime.datetime.now().strftime('%b %d %H:%M')}"

        thread = Thread(name=thread_name, owner_user_id=user_id)
        self.db.add(thread)
        self.db.commit()
        self.db.refresh(thread)

        # Owner participant
        owner_p = ThreadParticipant(
            thread_id=thread.id,
            participant_type="user",
            participant_id=user_id,
            role="owner",
        )
        self.db.add(owner_p)
        self.db.commit()

        return thread

    def attach_foreman_participant(self, thread_id: int) -> ThreadParticipant:
        """Add the Foreman system agent as a participant."""
        participant = ThreadParticipant(
            thread_id=thread_id,
            participant_type="system",
            system_agent_name="foreman",
            role="participant",
        )
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        return participant

    def attach_confab_participant(self, thread_id: int, confab_id: int) -> ThreadParticipant:
        """Add a confab as a participant."""
        participant = ThreadParticipant(
            thread_id=thread_id,
            participant_type="confab",
            participant_id=confab_id,
            role="participant",
        )
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        return participant

    def persist_message(
        self,
        thread_id: int,
        content: str,
        role: str = "assistant",
        sender_type: str = "system",
        sender_name: str = "Foreman",
        sender_id: int | None = None,
        in_reply_to: int | None = None,
        depth: int = 0,
        addressed_to: list | None = None,
    ) -> Message:
        """Save a message to the messages table."""
        msg = Message(
            thread_id=thread_id,
            sender_type=sender_type,
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            role=role,
            in_reply_to=in_reply_to,
            depth=depth,
            addressed_to=addressed_to,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    # ------------------------------------------------------------------
    # Mode inference
    # ------------------------------------------------------------------

    def infer_conversation_mode(self, thread_id: int) -> str:
        """
        Determine conversation mode from thread participants.

        Rules:
        1. If foreman system agent is present AND the linked confab is building → foreman_build
        2. If a published confab participant is present → confab_runtime
        3. Default → confab_runtime
        """
        participants = (
            self.db.query(ThreadParticipant)
            .filter(ThreadParticipant.thread_id == thread_id, ThreadParticipant.is_active == True)
            .all()
        )

        has_foreman = False
        confab_ids = []

        for p in participants:
            if p.participant_type == "system" and p.system_agent_name == "foreman":
                has_foreman = True
            elif p.participant_type == "confab" and p.participant_id:
                confab_ids.append(p.participant_id)

        if has_foreman and confab_ids:
            # Check if the confab is in building status
            confab = self.db.query(Confab).filter(Confab.id == confab_ids[0]).first()
            if confab and confab.status == "building":
                return FOREMAN_BUILD

        if confab_ids:
            return CONFAB_RUNTIME

        return CONFAB_RUNTIME

    # ------------------------------------------------------------------
    # Start / Resume
    # ------------------------------------------------------------------

    async def start_foreman_conversation(
        self, user: User, confab_id: int | None = None
    ) -> ConversationStartResult:
        """
        Start a new foreman build conversation.

        If confab_id is None, creates a new confab in 'building' status.
        Creates thread, attaches participants, seeds welcome message.
        """
        # Create confab if not provided
        if confab_id is None:
            confab = Confab(
                name="New Confab",
                status="building",
                user_id=user.id,
                version="1.0.0",
                oasf_schema_version="1.0.0",
            )
            self.db.add(confab)
            self.db.commit()
            self.db.refresh(confab)
            confab_id = confab.id
        else:
            confab = self.db.query(Confab).filter(
                Confab.id == confab_id, Confab.user_id == user.id
            ).first()
            if not confab:
                raise ValueError(f"Confab {confab_id} not found or not owned by user")

        # Create thread
        thread = self.create_thread_for_confab_build(user.id, confab_id)

        # Attach participants
        self.attach_foreman_participant(thread.id)
        self.attach_confab_participant(thread.id, confab_id)

        # Seed welcome message
        welcome_msg = self.persist_message(
            thread_id=thread.id,
            content=FOREMAN_WELCOME,
            role="assistant",
            sender_type="system",
            sender_name="Foreman",
        )

        # Build response
        participants = (
            self.db.query(ThreadParticipant)
            .filter(ThreadParticipant.thread_id == thread.id)
            .all()
        )

        setup_progress = None
        current_stage = None
        if confab.setup_progress:
            sp = confab.setup_progress
            setup_progress = SetupProgressResponse(
                completed_steps=sp.get("completed_steps", []),
                current_stage=sp.get("current_stage", "purpose"),
                total_steps=8,
                remaining_steps=sp.get("remaining_steps", list(range(1, 9))),
            )
            current_stage = sp.get("current_stage", "purpose")
        else:
            current_stage = "purpose"

        return ConversationStartResult(
            thread_id=thread.id,
            confab_id=confab_id,
            conversation_mode=FOREMAN_BUILD,
            messages=[MessageResponse.model_validate(welcome_msg)],
            participants=[ParticipantResponse.model_validate(p) for p in participants],
            setup_progress=setup_progress,
            current_stage=current_stage,
        )

    async def resume_foreman_conversation(
        self, user: User, confab_id: int
    ) -> ConversationStartResult:
        """
        Resume an existing foreman build conversation.

        Finds the thread for this confab (has foreman + confab participants),
        loads message history, and returns current state.
        """
        confab = self.db.query(Confab).filter(
            Confab.id == confab_id, Confab.user_id == user.id
        ).first()
        if not confab:
            raise ValueError(f"Confab {confab_id} not found or not owned by user")

        # Find the thread with both foreman and this confab
        thread = self._find_thread_for_confab(confab_id, require_foreman=True)

        if not thread:
            # No existing thread — start a new one (with resume message)
            result = await self.start_foreman_conversation(user, confab_id)
            return result

        # Load messages
        messages = (
            self.db.query(Message)
            .filter(Message.thread_id == thread.id)
            .order_by(Message.created_at)
            .all()
        )

        participants = (
            self.db.query(ThreadParticipant)
            .filter(ThreadParticipant.thread_id == thread.id)
            .all()
        )

        # Build setup progress
        setup_progress = None
        current_stage = None
        if confab.setup_progress:
            sp = confab.setup_progress
            setup_progress = SetupProgressResponse(
                completed_steps=sp.get("completed_steps", []),
                current_stage=sp.get("current_stage", "purpose"),
                total_steps=8,
                remaining_steps=sp.get("remaining_steps", list(range(1, 9))),
            )
            current_stage = sp.get("current_stage", "purpose")

        return ConversationStartResult(
            thread_id=thread.id,
            confab_id=confab_id,
            conversation_mode=FOREMAN_BUILD,
            messages=[MessageResponse.model_validate(m) for m in messages],
            participants=[ParticipantResponse.model_validate(p) for p in participants],
            setup_progress=setup_progress,
            current_stage=current_stage,
        )

    async def start_runtime_conversation(
        self, user: User, confab_id: int
    ) -> ConversationStartResult:
        """Start a chat with a published confab."""
        confab = self.db.query(Confab).filter(
            Confab.id == confab_id, Confab.user_id == user.id
        ).first()
        if not confab:
            raise ValueError(f"Confab {confab_id} not found or not owned by user")

        # Create thread
        thread_name = f"Chat: {confab.name} – {datetime.datetime.now().strftime('%b %d %H:%M')}"
        thread = Thread(name=thread_name, owner_user_id=user.id)
        self.db.add(thread)
        self.db.commit()
        self.db.refresh(thread)

        # Owner participant
        owner_p = ThreadParticipant(
            thread_id=thread.id,
            participant_type="user",
            participant_id=user.id,
            role="owner",
        )
        self.db.add(owner_p)
        self.db.commit()

        # Confab participant
        self.attach_confab_participant(thread.id, confab_id)

        # Welcome message from the confab
        welcome_content = f"Hi! I'm {confab.name}."
        if confab.purpose:
            welcome_content += f" {confab.purpose[:200]}"
        welcome_content += "\n\nHow can I help you?"

        welcome_msg = self.persist_message(
            thread_id=thread.id,
            content=welcome_content,
            role="assistant",
            sender_type="confab",
            sender_name=confab.name,
            sender_id=confab_id,
        )

        participants = (
            self.db.query(ThreadParticipant)
            .filter(ThreadParticipant.thread_id == thread.id)
            .all()
        )

        return ConversationStartResult(
            thread_id=thread.id,
            confab_id=confab_id,
            conversation_mode=CONFAB_RUNTIME,
            messages=[MessageResponse.model_validate(welcome_msg)],
            participants=[ParticipantResponse.model_validate(p) for p in participants],
        )

    # ------------------------------------------------------------------
    # Send message
    # ------------------------------------------------------------------

    async def send_message(
        self,
        user: User,
        thread_id: int,
        content: str,
        addressed_to: list | None = None,
        in_reply_to: int | None = None,
    ) -> ChatResponse:
        """
        Send a user message and dispatch to the correct orchestrator.

        This is the core routing method. It:
        1. Validates thread ownership
        2. Persists the user message
        3. Infers conversation mode
        4. Routes to ForemanV3 or runtime LLM
        5. Persists agent responses
        6. Returns unified ChatResponse
        """
        thread = self.db.query(Thread).filter(
            Thread.id == thread_id, Thread.owner_user_id == user.id
        ).first()
        if not thread:
            raise ValueError("Thread not found")

        # Calculate depth for subthreading
        depth = 0
        if in_reply_to:
            parent = self.db.query(Message).filter(Message.id == in_reply_to).first()
            if parent:
                depth = parent.depth + 1

        # Persist user message
        user_message = self.persist_message(
            thread_id=thread_id,
            content=content,
            role="user",
            sender_type="user",
            sender_name=user.name,
            sender_id=user.id,
            in_reply_to=in_reply_to,
            depth=depth,
            addressed_to=[a if isinstance(a, dict) else a.model_dump() for a in addressed_to] if addressed_to else None,
        )

        # Infer mode and route
        mode = self.infer_conversation_mode(thread_id)
        agent_responses: list[MessageResponse] = []
        foreman_metadata = None

        if mode == FOREMAN_BUILD:
            foreman_metadata, agent_responses = await self._handle_foreman_build(
                user, thread_id, content, user_message
            )
        elif mode == CONFAB_RUNTIME:
            agent_responses = await self._handle_confab_runtime(
                thread_id, content, user_message
            )

        return ChatResponse(
            thread_id=thread_id,
            user_message=MessageResponse.model_validate(user_message),
            agent_responses=agent_responses,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            foreman_metadata=foreman_metadata,
        )

    # ------------------------------------------------------------------
    # Private: orchestrator dispatch
    # ------------------------------------------------------------------

    async def _handle_foreman_build(
        self,
        user: User,
        thread_id: int,
        content: str,
        user_message: Message,
    ) -> tuple[ForemanChatResponse | None, list[MessageResponse]]:
        """Route to ForemanV3 for build-time conversation."""
        from foreman_v3 import FOREMAN_V3_ENABLED, ForemanV3
        from foreman import Foreman

        # Find the building confab for this user
        confab = (
            self.db.query(Confab)
            .filter(Confab.user_id == user.id, Confab.status == "building")
            .order_by(Confab.created_at.desc())
            .first()
        )

        if not confab:
            # No building confab — send a fallback message
            fallback = self.persist_message(
                thread_id=thread_id,
                content="No confab is currently being built. Please start a new confab to begin.",
                sender_name="Foreman",
            )
            return None, [MessageResponse.model_validate(fallback)]

        # Get thread history for context
        thread_messages = (
            self.db.query(Message)
            .filter(Message.thread_id == thread_id)
            .order_by(Message.created_at)
            .limit(20)
            .all()
        )

        # V3 (LangGraph) is canonical; legacy Foreman only via explicit flag
        if FOREMAN_V3_ENABLED:
            logger.info(f"[ConversationService] Using Foreman V3 for confab {confab.id}")
            foreman = ForemanV3(confab.id, self.db)
            await foreman.initialize()
            result = await foreman.process_message(
                content, thread_id=thread_id, thread_history=thread_messages
            )
        else:
            logger.warning(f"[ConversationService] Falling back to legacy Foreman for confab {confab.id}")
            foreman = Foreman(confab.id, self.db)
            await foreman.initialize()
            result = await foreman.process_message(content)

        response_content = result.get("response", "")

        # Persist Foreman's response
        agent_msg = self.persist_message(
            thread_id=thread_id,
            content=response_content,
            role="assistant",
            sender_type="system",
            sender_name="Foreman",
            in_reply_to=user_message.id,
            depth=user_message.depth,
        )

        # Build foreman metadata
        foreman_metadata = self._build_foreman_metadata(result, thread_id)

        return foreman_metadata, [MessageResponse.model_validate(agent_msg)]

    async def _handle_confab_runtime(
        self,
        thread_id: int,
        content: str,
        user_message: Message,
    ) -> list[MessageResponse]:
        """Route to runtime LLM for published confab chat."""
        from llm_service import ask_llm

        # Find confab participants
        confab_participants = (
            self.db.query(ThreadParticipant)
            .filter(
                ThreadParticipant.thread_id == thread_id,
                ThreadParticipant.is_active == True,
                ThreadParticipant.participant_type == "confab",
            )
            .all()
        )

        thread_messages = (
            self.db.query(Message)
            .filter(Message.thread_id == thread_id)
            .order_by(Message.created_at)
            .limit(20)
            .all()
        )

        responses = []
        for cp in confab_participants:
            confab = self.db.query(Confab).filter(Confab.id == cp.participant_id).first()
            if not confab or confab.status == "building":
                continue

            # Build context prompt
            context = f"You are {confab.name}. "
            if confab.purpose:
                context += f"Your purpose: {confab.purpose}\n"
            if confab.guardrails:
                context += f"Guardrails: {confab.guardrails}\n"
            context += "\nConversation:\n"
            for msg in thread_messages[-10:]:
                role_label = "User" if msg.role == "user" else "Assistant"
                context += f"{role_label}: {msg.content}\n"
            context += f"User: {content}\n"

            try:
                response_content = await ask_llm(prompt=context, temperature=confab.temperature)

                agent_msg = self.persist_message(
                    thread_id=thread_id,
                    content=response_content,
                    role="assistant",
                    sender_type="confab",
                    sender_name=confab.name,
                    sender_id=confab.id,
                    in_reply_to=user_message.id,
                    depth=user_message.depth,
                )
                responses.append(MessageResponse.model_validate(agent_msg))
            except Exception as e:
                logger.error(f"Error generating runtime response for confab {confab.id}: {e}")

        return responses

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_thread_for_confab(
        self, confab_id: int, require_foreman: bool = False
    ) -> Thread | None:
        """Find the thread that links to a specific confab (and optionally has Foreman)."""
        # Get all threads that have this confab as participant
        confab_threads = (
            self.db.query(ThreadParticipant.thread_id)
            .filter(
                ThreadParticipant.participant_type == "confab",
                ThreadParticipant.participant_id == confab_id,
                ThreadParticipant.is_active == True,
            )
            .all()
        )
        thread_ids = [t[0] for t in confab_threads]

        if not thread_ids:
            return None

        if require_foreman:
            # Also needs a foreman participant
            foreman_threads = (
                self.db.query(ThreadParticipant.thread_id)
                .filter(
                    ThreadParticipant.thread_id.in_(thread_ids),
                    ThreadParticipant.participant_type == "system",
                    ThreadParticipant.system_agent_name == "foreman",
                    ThreadParticipant.is_active == True,
                )
                .all()
            )
            thread_ids = [t[0] for t in foreman_threads]

        if not thread_ids:
            return None

        # Return the most recently created matching thread
        return (
            self.db.query(Thread)
            .filter(Thread.id.in_(thread_ids))
            .order_by(Thread.created_at.desc())
            .first()
        )

    def _build_foreman_metadata(
        self, result: dict, thread_id: int
    ) -> ForemanChatResponse | None:
        """Build ForemanChatResponse from orchestrator result dict."""
        setup_progress_data = result.get("setup_progress")
        v2_data = result.get("v2_metadata")

        is_v3 = result.get("is_v3", False)
        is_v2 = result.get("is_v2", v2_data is not None and not is_v3)

        setup_progress = None
        if setup_progress_data:
            setup_progress = SetupProgressResponse(**setup_progress_data)

        v2_metadata = None
        if v2_data:
            v2_metadata = ForemanV2Metadata(
                stage=v2_data.get("stage", ""),
                stage_status=v2_data.get("stage_status"),
                saved_fields=v2_data.get("saved_fields"),
                next_question=v2_data.get("next_question"),
                next_stage=setup_progress_data.get("current_stage") if setup_progress_data else None,
                clarification_needed=v2_data.get("stage_status") == "clarify",
                ui_hint=v2_data.get("ui_hint"),
            )

        return ForemanChatResponse(
            response=result.get("response", ""),
            confab_id=result.get("confab_id", 0),
            thread_id=thread_id,
            setup_progress=setup_progress,
            tool_calls=result.get("tool_calls", []),
            timestamp=datetime.datetime.fromisoformat(
                result.get("timestamp", datetime.datetime.now().isoformat())
            ),
            v2_metadata=v2_metadata,
            is_v2=is_v2,
            is_v3=is_v3,
        )
