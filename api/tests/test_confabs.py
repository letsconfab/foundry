"""
Tests for confab CRUD endpoints.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import User, Confab, Thread


class TestCreateConfab:
    """Tests for POST /confabs"""

    def test_create_confab_success(self, client: TestClient, auth_headers: dict, test_user: User):
        """Test successful confab creation."""
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

    def test_create_confab_with_runtime_config(self, client: TestClient, auth_headers: dict, test_user: User):
        """Test confab creation with runtime config fields."""
        response = client.post("/confabs", json={
            "name": "Configured Confab",
            "description": "Has config",
            "model_provider": "openai",
            "model_name": "gpt-4",
            "temperature": 0.9
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
        response = client.get("/confabs", headers=auth_headers)
        assert response.status_code == 200


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
        assert response.status_code == 404


class TestUpdateConfab:
    """Tests for PUT /confabs/{confab_id}"""

    def test_update_confab_success(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        """Test successful confab update."""
        response = client.put(f"/confabs/{test_confab.id}", json={
            "name": "Updated Name",
            "description": "Updated description"
        }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"
        assert data["version"] == "1.0.1"

    def test_update_confab_purpose(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        """Test updating confab purpose."""
        response = client.put(f"/confabs/{test_confab.id}", json={
            "purpose": "Help users with coding tasks"
        }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["purpose"] == "Help users with coding tasks"

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

        deleted = db.query(Confab).filter(Confab.id == confab_id).first()
        assert deleted is None

    def test_delete_confab_not_found(self, client: TestClient, auth_headers: dict):
        """Test deleting non-existent confab."""
        response = client.delete("/confabs/99999", headers=auth_headers)
        assert response.status_code == 404


class TestDeployConfab:
    """Tests for deploy/undeploy/status endpoints."""

    def test_deploy_requires_published(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        response = client.post(f"/confabs/{test_confab.id}/deploy", headers=auth_headers)
        assert response.status_code == 400
        assert "published" in response.json()["detail"].lower()

    @patch("routes.confab_routes.deploy_confab", new_callable=AsyncMock)
    def test_deploy_success(self, mock_deploy, client: TestClient, auth_headers: dict, test_confab: Confab, db: Session):
        test_confab.status = "published"
        db.commit()
        mock_deploy.return_value = {"status": "running", "port": 8642, "api_url": "http://localhost:8642/v1"}

        response = client.post(f"/confabs/{test_confab.id}/deploy", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Deployed"
        mock_deploy.assert_called_once_with(test_confab.name)

    @patch("routes.confab_routes.deploy_confab", new_callable=AsyncMock)
    def test_deploy_hermes_unavailable(self, mock_deploy, client: TestClient, auth_headers: dict, test_confab: Confab, db: Session):
        test_confab.status = "published"
        db.commit()
        mock_deploy.return_value = None

        response = client.post(f"/confabs/{test_confab.id}/deploy", headers=auth_headers)
        assert response.status_code == 502

    @patch("routes.confab_routes.undeploy_confab", new_callable=AsyncMock)
    def test_undeploy_success(self, mock_undeploy, client: TestClient, auth_headers: dict, test_confab: Confab):
        mock_undeploy.return_value = True
        response = client.post(f"/confabs/{test_confab.id}/undeploy", headers=auth_headers)
        assert response.status_code == 200

    @patch("routes.confab_routes.get_deploy_status", new_callable=AsyncMock)
    def test_deploy_status_not_deployed(self, mock_status, client: TestClient, auth_headers: dict, test_confab: Confab):
        mock_status.return_value = None
        response = client.get(f"/confabs/{test_confab.id}/deploy-status", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "not_deployed"

    @patch("routes.confab_routes.get_deploy_status", new_callable=AsyncMock)
    def test_deploy_status_running(self, mock_status, client: TestClient, auth_headers: dict, test_confab: Confab):
        mock_status.return_value = {
            "status": "running",
            "realizations": [{"instance_id": "abc", "status": "running", "port": 8642}],
            "api_url": "http://localhost:8642/v1",
        }
        response = client.get(f"/confabs/{test_confab.id}/deploy-status", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "running"

    def test_deploy_not_found(self, client: TestClient, auth_headers: dict):
        response = client.post("/confabs/99999/deploy", headers=auth_headers)
        assert response.status_code == 404


class TestConfabLearnings:
    """Tests for confab learnings CRUD."""

    def test_create_learning(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        """Test creating a learning."""
        response = client.post(f"/confabs/{test_confab.id}/learnings", json={
            "content": "Always greet users warmly",
            "summary": "Greeting behavior",
            "tags": ["behavior", "greetings"]
        }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Always greet users warmly"
        assert data["status"] == "draft"
        assert data["tags"] == ["behavior", "greetings"]

    def test_list_learnings(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        """Test listing learnings."""
        # Create a learning first
        client.post(f"/confabs/{test_confab.id}/learnings", json={
            "content": "Test learning",
            "summary": "Test"
        }, headers=auth_headers)

        response = client.get(f"/confabs/{test_confab.id}/learnings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_update_learning(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        """Test updating a learning."""
        # Create a learning
        create_response = client.post(f"/confabs/{test_confab.id}/learnings", json={
            "content": "Original content"
        }, headers=auth_headers)
        learning_id = create_response.json()["id"]

        # Update it
        response = client.put(f"/confabs/{test_confab.id}/learnings/{learning_id}", json={
            "content": "Updated content",
            "status": "approved"
        }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Updated content"
        assert data["status"] == "approved"

    def test_delete_learning(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        """Test deleting a learning."""
        # Create a learning
        create_response = client.post(f"/confabs/{test_confab.id}/learnings", json={
            "content": "To be deleted"
        }, headers=auth_headers)
        learning_id = create_response.json()["id"]

        # Delete it
        response = client.delete(f"/confabs/{test_confab.id}/learnings/{learning_id}", headers=auth_headers)
        assert response.status_code == 200
