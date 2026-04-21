"""
Tests for ConversationService — Phase 10.

Covers conversation start/resume flows, participant bootstrap,
setup_progress synchronization, and backward compatibility.
"""

import pytest

from models import Confab, Thread, ThreadParticipant, Message
from services.conversation_service import (
    ConversationService,
    FOREMAN_BUILD,
    CONFAB_RUNTIME,
    FOREMAN_WELCOME,
)
from foreman_v3.progress_sync import (
    stages_to_steps,
    steps_to_stages,
    to_setup_progress_response,
)
from services.participants import (
    has_foreman,
    has_confab,
    get_confab_ids,
    get_conversation_mode,
    is_user_in_thread,
)


# ============================================================================
# Start foreman conversation
# ============================================================================

class TestStartForemanConversation:
    """Test starting a new foreman build conversation."""

    @pytest.fixture
    def service(self, db):
        return ConversationService(db)

    @pytest.mark.asyncio
    async def test_creates_confab_thread_and_participants(self, service, db, test_user):
        """Starting a foreman conversation should create a confab, thread, and wire participants."""
        result = await service.start_foreman_conversation(test_user)

        assert result.confab_id is not None
        assert result.thread_id is not None
        assert result.conversation_mode == FOREMAN_BUILD

        # Thread should exist with conversation_mode set
        thread = db.query(Thread).filter(Thread.id == result.thread_id).first()
        assert thread is not None
        assert thread.conversation_mode == FOREMAN_BUILD

        # Participants: user (owner) + foreman (system) + confab
        participants = db.query(ThreadParticipant).filter(
            ThreadParticipant.thread_id == result.thread_id
        ).all()
        types = {p.participant_type for p in participants}
        assert "user" in types
        assert "system" in types
        assert "confab" in types

    @pytest.mark.asyncio
    async def test_welcome_message_is_seeded(self, service, test_user):
        """Starting a foreman conversation should seed a welcome message."""
        result = await service.start_foreman_conversation(test_user)

        assert len(result.messages) >= 1
        assert result.messages[0].role == "assistant"

    @pytest.mark.asyncio
    async def test_with_existing_confab_id(self, service, db, test_user, test_confab):
        """Starting with an existing confab_id should use that confab."""
        result = await service.start_foreman_conversation(test_user, confab_id=test_confab.id)

        assert result.confab_id == test_confab.id


# ============================================================================
# Resume foreman conversation
# ============================================================================

class TestResumeForemanConversation:
    """Test resuming an existing foreman build conversation."""

    @pytest.fixture
    def service(self, db):
        return ConversationService(db)

    @pytest.mark.asyncio
    async def test_finds_existing_thread(self, service, db, test_user, test_confab):
        """Resuming should find the thread with foreman + confab participants."""
        # Start a conversation first
        start_result = await service.start_foreman_conversation(
            test_user, confab_id=test_confab.id
        )

        # Resume
        result = await service.resume_foreman_conversation(test_user, test_confab.id)

        assert result.thread_id == start_result.thread_id
        assert result.confab_id == test_confab.id
        assert result.conversation_mode == FOREMAN_BUILD

    @pytest.mark.asyncio
    async def test_loads_message_history(self, service, db, test_user, test_confab):
        """Resuming should return all messages from the thread."""
        start_result = await service.start_foreman_conversation(
            test_user, confab_id=test_confab.id
        )

        # Add a user message
        msg = Message(
            thread_id=start_result.thread_id,
            content="A customer support bot",
            role="user",
            sender_type="user",
        )
        db.add(msg)
        db.commit()

        result = await service.resume_foreman_conversation(test_user, test_confab.id)

        # Should have welcome + user message
        assert len(result.messages) >= 2

    @pytest.mark.asyncio
    async def test_returns_setup_progress(self, service, db, test_user, test_confab):
        """Resuming should include setup_progress from the confab."""
        test_confab.setup_progress = {
            "current_stage": "participants",
            "completed_steps": [1],
        }
        db.commit()

        await service.start_foreman_conversation(test_user, confab_id=test_confab.id)

        result = await service.resume_foreman_conversation(test_user, test_confab.id)

        assert result.setup_progress is not None
        assert result.setup_progress.current_stage == "participants"
        assert 1 in result.setup_progress.completed_steps

    @pytest.mark.asyncio
    async def test_no_existing_thread_creates_new(self, service, db, test_user, test_confab):
        """If no thread exists for the confab, resume should start a new conversation."""
        result = await service.resume_foreman_conversation(test_user, test_confab.id)

        assert result.thread_id is not None
        assert result.confab_id == test_confab.id


# ============================================================================
# Runtime conversation
# ============================================================================

class TestStartRuntimeConversation:
    """Test starting a runtime conversation with a published confab."""

    @pytest.fixture
    def service(self, db):
        return ConversationService(db)

    @pytest.fixture
    def published_confab(self, db, test_user):
        confab = Confab(
            name="Published Bot",
            description="A published confab",
            user_id=test_user.id,
            version="1.0.0",
            status="published",
            purpose="Help with testing",
        )
        db.add(confab)
        db.commit()
        db.refresh(confab)
        return confab

    @pytest.mark.asyncio
    async def test_creates_runtime_thread(self, service, db, test_user, published_confab):
        """Starting a runtime conversation should create a thread with confab_runtime mode."""
        result = await service.start_runtime_conversation(test_user, published_confab.id)

        assert result.thread_id is not None
        assert result.conversation_mode == CONFAB_RUNTIME

        thread = db.query(Thread).filter(Thread.id == result.thread_id).first()
        assert thread.conversation_mode == CONFAB_RUNTIME

    @pytest.mark.asyncio
    async def test_welcome_message_from_confab(self, service, test_user, published_confab):
        """Runtime conversation should have a welcome message from the confab."""
        result = await service.start_runtime_conversation(test_user, published_confab.id)

        assert len(result.messages) >= 1
        assert result.messages[0].role == "assistant"
        assert published_confab.name in result.messages[0].content


# ============================================================================
# Participant bootstrap
# ============================================================================

class TestParticipantBootstrap:
    """Test participant helper utilities."""

    def test_has_foreman_true(self, db, test_thread):
        """has_foreman should detect foreman participant."""
        p = ThreadParticipant(
            thread_id=test_thread.id,
            participant_type="system",
            system_agent_name="foreman",
            role="participant",
        )
        db.add(p)
        db.commit()

        assert has_foreman(db, test_thread.id) is True

    def test_has_foreman_false(self, db, test_thread):
        """has_foreman should return False when no foreman present."""
        assert has_foreman(db, test_thread.id) is False

    def test_has_confab(self, db, test_thread, test_confab):
        """has_confab should detect confab participant."""
        p = ThreadParticipant(
            thread_id=test_thread.id,
            participant_type="confab",
            participant_id=test_confab.id,
            role="participant",
        )
        db.add(p)
        db.commit()

        assert has_confab(db, test_thread.id) is True
        assert has_confab(db, test_thread.id, confab_id=test_confab.id) is True
        assert has_confab(db, test_thread.id, confab_id=99999) is False

    def test_get_confab_ids(self, db, test_thread, test_confab):
        """get_confab_ids should return all confab IDs in a thread."""
        p = ThreadParticipant(
            thread_id=test_thread.id,
            participant_type="confab",
            participant_id=test_confab.id,
            role="participant",
        )
        db.add(p)
        db.commit()

        ids = get_confab_ids(db, test_thread.id)
        assert test_confab.id in ids

    def test_is_user_in_thread(self, db, test_thread, test_user):
        """is_user_in_thread should check user membership."""
        assert is_user_in_thread(db, test_thread.id, test_user.id) is False

        p = ThreadParticipant(
            thread_id=test_thread.id,
            participant_type="user",
            participant_id=test_user.id,
            role="participant",
        )
        db.add(p)
        db.commit()

        assert is_user_in_thread(db, test_thread.id, test_user.id) is True

    def test_get_conversation_mode_explicit(self, db, test_user):
        """get_conversation_mode should use explicit field when set."""
        thread = Thread(
            name="Test",
            owner_user_id=test_user.id,
            conversation_mode=FOREMAN_BUILD,
        )
        db.add(thread)
        db.commit()
        db.refresh(thread)

        assert get_conversation_mode(db, thread) == FOREMAN_BUILD

    def test_get_conversation_mode_fallback(self, db, test_user, test_confab):
        """get_conversation_mode should fall back to participant inference."""
        thread = Thread(name="Test", owner_user_id=test_user.id)
        db.add(thread)
        db.commit()
        db.refresh(thread)

        # Add foreman + confab participants
        db.add(ThreadParticipant(
            thread_id=thread.id, participant_type="system",
            system_agent_name="foreman", role="participant",
        ))
        db.add(ThreadParticipant(
            thread_id=thread.id, participant_type="confab",
            participant_id=test_confab.id, role="participant",
        ))
        db.commit()

        assert get_conversation_mode(db, thread) == FOREMAN_BUILD


# ============================================================================
# Setup progress synchronization
# ============================================================================

class TestSetupProgressSync:
    """Test progress_sync mapping functions."""

    def test_stages_to_steps(self):
        assert stages_to_steps([]) == []
        assert stages_to_steps(["purpose"]) == [1]
        assert stages_to_steps(["purpose", "participants", "memory"]) == [1, 2, 3]
        assert stages_to_steps(["memory", "purpose"]) == [1, 3]  # sorted
        assert stages_to_steps(["purpose", "invalid"]) == [1]  # ignores invalid

    def test_steps_to_stages(self):
        assert steps_to_stages([]) == []
        assert steps_to_stages([1]) == ["purpose"]
        assert steps_to_stages([1, 2, 3]) == ["purpose", "participants", "memory"]
        assert steps_to_stages([3, 1]) == ["purpose", "memory"]  # sorted
        assert steps_to_stages([99]) == []  # out of range

    def test_to_setup_progress_response_none(self):
        assert to_setup_progress_response(None) is None
        assert to_setup_progress_response({}) is None

    def test_to_setup_progress_response_with_data(self):
        progress = {
            "current_stage": "memory",
            "completed_steps": [1, 2],
        }
        result = to_setup_progress_response(progress)
        assert result is not None
        assert result.current_stage == "memory"
        assert result.completed_steps == [1, 2]
        assert result.total_steps == 8
        assert 1 not in result.remaining_steps
        assert 2 not in result.remaining_steps
        assert 3 in result.remaining_steps


# ============================================================================
# Backward compatibility
# ============================================================================

class TestBackwardCompatibility:
    """Test that the chat payload shape hasn't changed."""

    @pytest.fixture
    def service(self, db):
        return ConversationService(db)

    @pytest.mark.asyncio
    async def test_start_result_has_expected_fields(self, service, test_user):
        """ConversationStartResult should have all fields the frontend expects."""
        result = await service.start_foreman_conversation(test_user)

        assert hasattr(result, "thread_id")
        assert hasattr(result, "confab_id")
        assert hasattr(result, "conversation_mode")
        assert hasattr(result, "messages")
        assert hasattr(result, "participants")
        assert hasattr(result, "setup_progress")
        assert hasattr(result, "current_stage")

    @pytest.mark.asyncio
    async def test_message_response_shape(self, service, test_user):
        """Messages in result should match MessageResponse schema."""
        result = await service.start_foreman_conversation(test_user)

        msg = result.messages[0]
        assert hasattr(msg, "id")
        assert hasattr(msg, "content")
        assert hasattr(msg, "role")

    @pytest.mark.asyncio
    async def test_participant_response_shape(self, service, test_user):
        """Participants in result should match ParticipantResponse schema."""
        result = await service.start_foreman_conversation(test_user)

        for p in result.participants:
            assert hasattr(p, "id")
            assert hasattr(p, "participant_type")


class TestForemanMetadata:
    """Tests for structured Foreman metadata used by the builder UI."""

    @pytest.fixture
    def service(self, db):
        return ConversationService(db)

    def test_build_foreman_metadata_preserves_ack_and_prompt(self, service):
        result = {
            "response": "Recorded the purpose.",
            "confab_id": 1,
            "setup_progress": {
                "completed_steps": [1],
                "current_stage": "participants",
                "total_steps": 8,
                "remaining_steps": [2, 3, 4, 5, 6, 7, 8],
            },
            "tool_calls": [],
            "timestamp": "2026-04-13T10:00:00",
            "v2_metadata": {
                "stage": "purpose",
                "stage_status": "complete",
                "saved_fields": {"purpose": "Test"},
                "next_question": None,
                "response_ack": "Recorded the purpose.",
                "interview_prompt": "Who should have access to this agent?",
                "ui_hint": None,
            },
            "is_v2": False,
            "is_v3": True,
        }

        metadata = service._build_foreman_metadata(result, thread_id=12)

        assert metadata is not None
        assert metadata.v2_metadata is not None
        assert metadata.v2_metadata.response_ack == "Recorded the purpose."
        assert metadata.v2_metadata.interview_prompt == "Who should have access to this agent?"
