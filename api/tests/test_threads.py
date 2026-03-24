"""
Tests for thread and message endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import User, Thread, Message, Confab, ThreadMapping


class TestCreateThread:
    """Tests for POST /threads"""

    def test_create_thread_success(self, client: TestClient, auth_headers: dict):
        """Test successful thread creation."""
        response = client.post("/threads", json={
            "thread_name": "New Conversation"
        }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["thread_name"] == "New Conversation"
        assert "id" in data
        assert "created_at" in data

    def test_create_thread_no_auth(self, client: TestClient):
        """Test thread creation without auth fails."""
        response = client.post("/threads", json={
            "thread_name": "Test"
        })
        # HTTPBearer returns 401 when no credentials provided
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
        assert data["thread_name"] == test_thread.thread_name

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

    def test_post_thread_message(self, client: TestClient, auth_headers: dict, test_thread: Thread):
        """Test posting a message to a thread."""
        response = client.post(f"/threads/{test_thread.id}/messages", json={
            "content": "Hello, world!",
            "role": "user"
        }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Hello, world!"
        assert data["role"] == "user"
        assert data["thread_id"] == test_thread.id

    def test_get_thread_messages_with_messages(
        self, client: TestClient, auth_headers: dict, test_thread: Thread, db: Session
    ):
        """Test getting messages from thread with messages."""
        # Add a message
        msg = Message(
            thread_id=test_thread.id,
            content="Test message",
            role="user"
        )
        db.add(msg)
        db.commit()

        response = client.get(f"/threads/{test_thread.id}/messages", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(m["content"] == "Test message" for m in data)


class TestThreadMappings:
    """Tests for thread-confab mapping endpoints."""

    def test_create_thread_mapping(
        self, client: TestClient, auth_headers: dict,
        test_confab: Confab, test_thread: Thread
    ):
        """Test creating a thread-confab mapping."""
        response = client.post("/thread-mappings", json={
            "confab_id": test_confab.id,
            "thread_id": test_thread.id
        }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["confab_id"] == test_confab.id
        assert data["thread_id"] == test_thread.id

    def test_get_thread_mappings(
        self, client: TestClient, auth_headers: dict,
        test_confab: Confab, test_thread: Thread, db: Session
    ):
        """Test getting thread mappings."""
        # Create a mapping
        mapping = ThreadMapping(confab_id=test_confab.id, thread_id=test_thread.id)
        db.add(mapping)
        db.commit()

        response = client.get("/thread-mappings", headers=auth_headers)
        assert response.status_code == 200

    def test_get_confab_threads(
        self, client: TestClient, auth_headers: dict,
        test_confab: Confab, test_thread: Thread, db: Session
    ):
        """Test getting threads for a confab (using plural route)."""
        # Create a mapping
        mapping = ThreadMapping(confab_id=test_confab.id, thread_id=test_thread.id)
        db.add(mapping)
        db.commit()

        # Use the corrected plural route
        response = client.get(f"/confabs/{test_confab.id}/threads", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
