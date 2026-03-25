"""
Tests for thread, participant, and message endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import User, Thread, Message, Confab, ThreadParticipant


class TestCreateThread:
    """Tests for POST /threads"""

    def test_create_thread_success(self, client: TestClient, auth_headers: dict):
        """Test successful thread creation."""
        response = client.post("/threads", json={
            "name": "New Conversation"
        }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Conversation"
        assert "id" in data
        assert "created_at" in data

    def test_create_thread_no_auth(self, client: TestClient):
        """Test thread creation without auth fails."""
        response = client.post("/threads", json={
            "name": "Test"
        })
        assert response.status_code in [401, 403]


class TestGetThreads:
    """Tests for GET /threads"""

    def test_get_threads(self, client: TestClient, auth_headers: dict, test_thread: Thread):
        """Test getting user's threads."""
        response = client.get("/threads", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(t["id"] == test_thread.id for t in data)


class TestGetThread:
    """Tests for GET /threads/{thread_id}"""

    def test_get_thread_success(self, client: TestClient, auth_headers: dict, test_thread: Thread):
        """Test getting a single thread."""
        response = client.get(f"/threads/{test_thread.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_thread.id
        assert data["name"] == test_thread.name

    def test_get_thread_not_found(self, client: TestClient, auth_headers: dict):
        """Test getting non-existent thread."""
        response = client.get("/threads/99999", headers=auth_headers)
        assert response.status_code == 404


class TestThreadMessages:
    """Tests for thread message endpoints."""

    def test_get_thread_messages_empty(self, client: TestClient, auth_headers: dict, test_thread: Thread):
        """Test getting messages from empty thread."""
        response = client.get(f"/threads/{test_thread.id}/messages", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_get_thread_messages_with_messages(
        self, client: TestClient, auth_headers: dict, test_thread: Thread, db: Session
    ):
        """Test getting messages from thread with messages."""
        msg = Message(
            thread_id=test_thread.id,
            content="Test message",
            role="user",
            sender_type="user",
        )
        db.add(msg)
        db.commit()

        response = client.get(f"/threads/{test_thread.id}/messages", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(m["content"] == "Test message" for m in data)


class TestThreadParticipants:
    """Tests for thread participant endpoints."""

    def test_add_user_participant(
        self, client: TestClient, auth_headers: dict,
        test_thread: Thread, test_user: User
    ):
        """Test adding a user as participant."""
        response = client.post(f"/threads/{test_thread.id}/participants", json={
            "participant_type": "user",
            "participant_id": test_user.id,
            "role": "participant"
        }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["participant_type"] == "user"
        assert data["participant_id"] == test_user.id
        assert data["role"] == "participant"

    def test_add_confab_participant(
        self, client: TestClient, auth_headers: dict,
        test_thread: Thread, test_confab: Confab
    ):
        """Test adding a confab as participant."""
        response = client.post(f"/threads/{test_thread.id}/participants", json={
            "participant_type": "confab",
            "participant_id": test_confab.id,
            "role": "participant"
        }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["participant_type"] == "confab"
        assert data["participant_id"] == test_confab.id

    def test_add_system_participant(
        self, client: TestClient, auth_headers: dict,
        test_thread: Thread
    ):
        """Test adding a system agent as participant."""
        response = client.post(f"/threads/{test_thread.id}/participants", json={
            "participant_type": "system",
            "system_agent_name": "foreman",
            "role": "participant"
        }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["participant_type"] == "system"
        assert data["system_agent_name"] == "foreman"

    def test_get_participants(
        self, client: TestClient, auth_headers: dict,
        test_thread: Thread, db: Session
    ):
        """Test getting thread participants."""
        # Add a participant
        participant = ThreadParticipant(
            thread_id=test_thread.id,
            participant_type="system",
            system_agent_name="foreman",
            role="participant"
        )
        db.add(participant)
        db.commit()

        response = client.get(f"/threads/{test_thread.id}/participants", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_remove_participant(
        self, client: TestClient, auth_headers: dict,
        test_thread: Thread, db: Session
    ):
        """Test removing a participant from thread."""
        # Add a participant
        participant = ThreadParticipant(
            thread_id=test_thread.id,
            participant_type="system",
            system_agent_name="foreman",
            role="participant"
        )
        db.add(participant)
        db.commit()
        db.refresh(participant)

        response = client.delete(
            f"/threads/{test_thread.id}/participants/{participant.id}",
            headers=auth_headers
        )
        assert response.status_code == 200

        # Verify participant is now inactive
        db.refresh(participant)
        assert participant.is_active == False
