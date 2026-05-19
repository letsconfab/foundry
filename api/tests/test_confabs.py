"""
Tests for confab CRUD endpoints.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import User, Confab, ConfabDeployment, Thread


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
        mock_deploy.return_value = {
            "message": "Deployed",
            "deployment": {
                "status": "running",
                "model_id": f"confab-{test_confab.id}-test-confab",
                "openwebui_url": "http://localhost:3001",
                "dashboard_enabled": True,
                "dashboard_url": "http://localhost:9100",
                "dashboard_port": 9100,
                "rag_workspace": f"confabs/{test_confab.id}",
            },
            "knowledge_synced": True,
            "rag_indexed": 5,
            "rag_workspace": f"confabs/{test_confab.id}",
            "rag_errors": [],
        }

        response = client.post(f"/confabs/{test_confab.id}/deploy", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Deployed"
        assert data["deployment"]["model_id"] == f"confab-{test_confab.id}-test-confab"
        assert data["deployment"]["dashboard_enabled"] is True
        assert data["deployment"]["dashboard_url"] == "http://localhost:9100"
        assert data["deployment"]["dashboard_port"] == 9100
        assert data["rag_workspace"] == f"confabs/{test_confab.id}"
        assert data["knowledge_synced"] is True
        assert data["rag_indexed"] == 5
        mock_deploy.assert_awaited_once()

    @patch("routes.confab_routes.deploy_confab", new_callable=AsyncMock)
    def test_deploy_runtime_unavailable(self, mock_deploy, client: TestClient, auth_headers: dict, test_confab: Confab, db: Session):
        test_confab.status = "published"
        db.commit()
        mock_deploy.side_effect = RuntimeError("runtime unavailable")

        response = client.post(f"/confabs/{test_confab.id}/deploy", headers=auth_headers)
        assert response.status_code == 502

    @patch("routes.confab_routes.undeploy_confab", new_callable=AsyncMock)
    def test_undeploy_success(self, mock_undeploy, client: TestClient, auth_headers: dict, test_confab: Confab):
        mock_undeploy.return_value = {
            "message": "Undeployed",
            "deployment": {
                "status": "stopped",
                "profile_name": "confab-1-test-confab",
                "model_id": "confab-1-test-confab",
                "profile_preserved": True,
                "rag_workspace": "confabs/1",
            },
        }
        response = client.post(f"/confabs/{test_confab.id}/undeploy", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["deployment"]["status"] == "stopped"
        mock_undeploy.assert_awaited_once()

    @patch("routes.confab_routes.get_deploy_status", new_callable=AsyncMock)
    def test_deploy_status_not_deployed(self, mock_status, client: TestClient, auth_headers: dict, test_confab: Confab):
        mock_status.return_value = {
            "status": "not_deployed",
            "runtime": "hermes_profile",
            "model_id": None,
            "rag_workspace": f"confabs/{test_confab.id}",
            "dashboard_enabled": False,
            "dashboard_url": None,
            "dashboard_port": None,
        }
        response = client.get(f"/confabs/{test_confab.id}/deploy-status", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "not_deployed"

    @patch("routes.confab_routes.get_deploy_status", new_callable=AsyncMock)
    def test_deploy_status_running(self, mock_status, client: TestClient, auth_headers: dict, test_confab: Confab):
        mock_status.return_value = {
            "status": "running",
            "runtime": "hermes_profile",
            "model_id": f"confab-{test_confab.id}-test-confab",
            "openwebui_url": "http://localhost:3001",
            "rag_workspace": f"confabs/{test_confab.id}",
            "dashboard_enabled": True,
            "dashboard_url": "http://localhost:9100",
            "dashboard_port": 9100,
        }
        response = client.get(f"/confabs/{test_confab.id}/deploy-status", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "running"
        assert response.json()["model_id"] == f"confab-{test_confab.id}-test-confab"
        assert response.json()["dashboard_url"] == "http://localhost:9100"

    @patch("routes.confab_routes.list_rag_pipeline_documents", new_callable=AsyncMock)
    def test_rag_documents(self, mock_documents, client: TestClient, auth_headers: dict, test_confab: Confab):
        mock_documents.return_value = {
            "confab_id": test_confab.id,
            "rag_workspace": f"confabs/{test_confab.id}",
            "files": [{"name": "PURPOSE.md", "path": f"confabs/{test_confab.id}/PURPOSE.md"}],
            "file_count": 1,
        }

        response = client.get(f"/confabs/{test_confab.id}/rag-documents", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["files"][0]["name"] == "PURPOSE.md"
        mock_documents.assert_awaited_once()

    def test_deploy_not_found(self, client: TestClient, auth_headers: dict):
        response = client.post("/confabs/99999/deploy", headers=auth_headers)
        assert response.status_code == 404

    def test_rag_documents_not_found(self, client: TestClient, auth_headers: dict):
        response = client.get("/confabs/99999/rag-documents", headers=auth_headers)
        assert response.status_code == 404

    def test_rag_dashboard_redirect_requires_owner(self, client: TestClient, auth_headers: dict, test_confab: Confab):
        response = client.get(
            f"/confabs/{test_confab.id}/rag-dashboard",
            headers=auth_headers,
            follow_redirects=False,
        )
        assert response.status_code == 307
        assert response.headers["location"] == f"/confabs/{test_confab.id}/rag-dashboard/webui/"

    def test_rag_dashboard_non_owner_receives_404(self, client: TestClient, db: Session, test_confab: Confab):
        from auth import create_access_token, get_password_hash

        other_user = User(
            name="Other User",
            email="other-rag@example.com",
            password_hash=get_password_hash("password"),
            country="US",
            timezone="UTC",
        )
        db.add(other_user)
        db.commit()
        other_token = create_access_token({"user_id": other_user.id, "email": other_user.email})

        response = client.get(
            f"/confabs/{test_confab.id}/rag-dashboard",
            headers={"Authorization": f"Bearer {other_token}"},
            follow_redirects=False,
        )
        assert response.status_code == 404

    def test_rag_dashboard_proxy_injects_api_key_and_rewrites_html(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        db: Session,
        tmp_path,
        monkeypatch,
    ):
        key_path = tmp_path / ".rag_dashboard_api_key"
        key_path.write_text("secret-rag-key", encoding="utf-8")
        deployment = ConfabDeployment(
            confab_id=test_confab.id,
            user_id=test_confab.user_id,
            status="running",
            profile_name=f"confab-{test_confab.id}-test-confab",
            model_id=f"confab-{test_confab.id}-test-confab",
            container_name=f"hermes-confab-{test_confab.id}-test-confab",
            profile_host_path=str(tmp_path),
            api_port=8700,
            api_server_key_hash="hash",
            api_base_url_external="http://localhost:8700/v1",
            api_base_url_internal="http://hermes:8642/v1",
            rag_workspace=f"confabs/{test_confab.id}",
            rag_prefix=f"confabs/{test_confab.id}/",
            lightrag_workspace="ws_test",
            rag_dashboard_enabled=True,
            rag_dashboard_port=9200,
            rag_dashboard_container_name=f"rag-dashboard-confab-{test_confab.id}-test-confab",
        )
        db.add(deployment)
        db.commit()
        captured = {}

        class FakeResponse:
            status = 200
            headers = {"content-type": "text/html; charset=utf-8"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def read(self):
                return b'<script src="/webui/app.js"></script><a href="/graphs">Graph</a><script>fetch("/documents");router.push("/login")</script>'

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            def request(self, method, url, headers=None, data=None, **_kwargs):
                captured["method"] = method
                captured["url"] = url
                captured["headers"] = headers
                captured["data"] = data
                return FakeResponse()

        monkeypatch.setattr("routes.confab_routes.aiohttp.ClientSession", FakeSession)

        response = client.get(
            f"/confabs/{test_confab.id}/rag-dashboard/webui/index.html?x=1",
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert captured["url"] == "http://127.0.0.1:9200/webui/index.html?x=1"
        assert captured["headers"]["X-API-Key"] == "secret-rag-key"
        assert f'"/confabs/{test_confab.id}/rag-dashboard/webui/app.js' in response.text
        assert f'"/confabs/{test_confab.id}/rag-dashboard/graphs' in response.text
        assert f'"/confabs/{test_confab.id}/rag-dashboard/documents' in response.text
        assert 'router.push("/login")' in response.text
        assert response.headers["cache-control"] == "no-store"

    def test_rag_dashboard_proxy_forwards_json_unchanged(
        self,
        client: TestClient,
        auth_headers: dict,
        test_confab: Confab,
        db: Session,
        tmp_path,
        monkeypatch,
    ):
        (tmp_path / ".rag_dashboard_api_key").write_text("secret-rag-key", encoding="utf-8")
        db.add(
            ConfabDeployment(
                confab_id=test_confab.id,
                user_id=test_confab.user_id,
                status="running",
                profile_name=f"confab-{test_confab.id}-test-confab-json",
                model_id=f"confab-{test_confab.id}-test-confab-json",
                container_name=f"hermes-confab-{test_confab.id}-test-confab-json",
                profile_host_path=str(tmp_path),
                api_port=8700,
                api_server_key_hash="hash",
                api_base_url_external="http://localhost:8700/v1",
                api_base_url_internal="http://hermes:8642/v1",
                rag_workspace=f"confabs/{test_confab.id}",
                rag_prefix=f"confabs/{test_confab.id}/",
                rag_dashboard_enabled=True,
                rag_dashboard_port=9200,
            )
        )
        db.commit()

        class FakeResponse:
            status = 200
            headers = {"content-type": "application/json"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def read(self):
                return b'{"path":"/graphs","ok":true}'

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            def request(self, *_args, **_kwargs):
                return FakeResponse()

        monkeypatch.setattr("routes.confab_routes.aiohttp.ClientSession", FakeSession)

        response = client.get(f"/confabs/{test_confab.id}/rag-dashboard/graphs", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"path": "/graphs", "ok": True}


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
