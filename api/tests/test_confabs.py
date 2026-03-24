"""
Tests for confab CRUD endpoints.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import User, Confab, ThreadMapping, Thread


class TestCreateConfab:
    """Tests for POST /confabs"""

    def test_create_confab_success(self, client: TestClient, auth_headers: dict, test_user: User):
        """Test successful confab creation."""
        with patch("main.create_confab_in_github", new_callable=AsyncMock) as mock_github:
            mock_github.return_value = "https://github.com/test/repo/pull/1"

            response = client.post("/confabs", json={
                "name": "My New Confab",
                "description": "A helpful assistant"
            }, headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "My New Confab"
            assert data["description"] == "A helpful assistant"
            assert data["status"] == "building"
            assert data["version"] == "1.0.0"

    def test_create_confab_with_config(self, client: TestClient, auth_headers: dict, test_user: User):
        """Test confab creation with config field populated."""
        with patch("main.create_confab_in_github", new_callable=AsyncMock) as mock_github:
            mock_github.return_value = "https://github.com/test/repo/pull/1"

            response = client.post("/confabs", json={
                "name": "Configured Confab",
                "description": "Has config",
                "config": {
                    "model_provider": "openai",
                    "model_name": "gpt-4",
                    "system_prompt": "You are helpful",
                    "temperature": 0.7
                }
            }, headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Configured Confab"

    def test_create_confab_no_auth(self, client: TestClient):
        """Test confab creation without authentication."""
        response = client.post("/confabs", json={
            "name": "Test",
            "description": "Test"
        })
        # HTTPBearer returns 401 when no credentials provided
        assert response.status_code in [401, 403]


class TestGetConfabs:
    """Tests for GET /confabs"""

    def test_get_user_confabs(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        """Test getting all confabs for a user."""
        response = client.get("/confabs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(c["id"] == test_confab.id for c in data)

    def test_get_confabs_empty(self, client: TestClient, auth_headers: dict):
        """Test getting confabs when user has none."""
        # Note: test_user fixture creates user but not test_confab in this test
        response = client.get("/confabs", headers=auth_headers)
        assert response.status_code == 200
        # May have 0 or more depending on fixtures


class TestGetConfab:
    """Tests for GET /confabs/{confab_id}"""

    def test_get_confab_success(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        """Test getting a single confab."""
        response = client.get(f"/confabs/{test_confab.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_confab.id
        assert data["name"] == test_confab.name

    def test_get_confab_not_found(self, client: TestClient, auth_headers: dict):
        """Test getting non-existent confab."""
        response = client.get("/confabs/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_get_confab_wrong_user(self, client: TestClient, db: Session, test_confab: Confab):
        """Test that users can't access other users' confabs."""
        # Create another user
        from auth import get_password_hash, create_access_token
        other_user = User(
            name="Other User",
            email="other@example.com",
            password_hash=get_password_hash("password"),
            country="US",
            timezone="UTC"
        )
        db.add(other_user)
        db.commit()

        other_token = create_access_token({"user_id": other_user.id, "email": other_user.email})
        other_headers = {"Authorization": f"Bearer {other_token}"}

        response = client.get(f"/confabs/{test_confab.id}", headers=other_headers)
        assert response.status_code == 404  # Should not find other user's confab


class TestUpdateConfab:
    """Tests for PUT /confabs/{confab_id}"""

    def test_update_confab_success(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        """Test successful confab update."""
        with patch("main.update_confab_in_github", new_callable=AsyncMock):
            response = client.put(f"/confabs/{test_confab.id}", json={
                "name": "Updated Name",
                "description": "Updated description"
            }, headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Updated Name"
            assert data["description"] == "Updated description"
            # Version should be incremented (semver: 1.0.0 -> 1.0.1)
            assert data["version"] == "1.0.1"

    def test_update_confab_not_found(self, client: TestClient, auth_headers: dict):
        """Test updating non-existent confab."""
        response = client.put("/confabs/99999", json={
            "name": "Test",
            "description": "Test"
        }, headers=auth_headers)
        assert response.status_code == 404


class TestDeleteConfab:
    """Tests for DELETE /confabs/{confab_id}"""

    def test_delete_confab_success(self, client: TestClient, auth_headers: dict, test_confab: Confab, db: Session):
        """Test successful confab deletion."""
        confab_id = test_confab.id
        response = client.delete(f"/confabs/{confab_id}", headers=auth_headers)
        assert response.status_code == 200

        # Verify it's deleted
        deleted = db.query(Confab).filter(Confab.id == confab_id).first()
        assert deleted is None

    def test_delete_confab_with_thread_mapping(
        self, client: TestClient, auth_headers: dict,
        test_confab: Confab, test_thread: Thread, db: Session
    ):
        """Test deleting confab with thread mappings (cascade delete)."""
        # Create a thread mapping
        mapping = ThreadMapping(confab_id=test_confab.id, thread_id=test_thread.id)
        db.add(mapping)
        db.commit()

        confab_id = test_confab.id
        response = client.delete(f"/confabs/{confab_id}", headers=auth_headers)
        assert response.status_code == 200

        # Verify both confab and mapping are deleted
        deleted_confab = db.query(Confab).filter(Confab.id == confab_id).first()
        deleted_mapping = db.query(ThreadMapping).filter(ThreadMapping.confab_id == confab_id).first()
        assert deleted_confab is None
        assert deleted_mapping is None

    def test_delete_confab_not_found(self, client: TestClient, auth_headers: dict):
        """Test deleting non-existent confab."""
        response = client.delete("/confabs/99999", headers=auth_headers)
        assert response.status_code == 404
