from pathlib import Path

from fastapi.testclient import TestClient

from models import ConfabDeployment
from services import model_router_proxy


def _deployment(
    tmp_path: Path,
    model_id: str,
    status: str = "running",
    confab_id: int = 100,
    api_port: int = 8700,
) -> ConfabDeployment:
    profile_path = tmp_path / model_id
    profile_path.mkdir()
    (profile_path / ".env").write_text("API_SERVER_KEY=profile-secret\n", encoding="utf-8")
    return ConfabDeployment(
        confab_id=confab_id,
        user_id=1,
        status=status,
        profile_name=model_id,
        model_id=model_id,
        container_name=f"hermes-{model_id}",
        profile_host_path=str(profile_path),
        api_port=api_port,
        api_server_key_hash="hash",
        api_base_url_external=f"http://localhost:{api_port}/v1",
        api_base_url_internal=f"http://hermes-{model_id}:8642/v1",
        rag_workspace=f"confabs/{confab_id}",
        rag_prefix=f"confabs/{confab_id}/",
    )


def test_router_models_lists_only_running(client: TestClient, db, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(model_router_proxy, "HERMES_MODEL_ROUTER_API_KEY", "router-secret")
    db.add(_deployment(tmp_path, "confab-100-running", "running", 100, 8700))
    db.add(_deployment(tmp_path, "confab-101-stopped", "stopped", 101, 8701))
    db.commit()

    response = client.get("/router/v1/models", headers={"Authorization": "Bearer router-secret"})

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["data"]]
    assert ids == ["confab-100-running"]


def test_router_requires_api_key(client: TestClient, monkeypatch):
    monkeypatch.setattr(model_router_proxy, "HERMES_MODEL_ROUTER_API_KEY", "router-secret")

    response = client.get("/router/v1/models")

    assert response.status_code == 401


def test_router_unknown_model_returns_openai_error(client: TestClient, monkeypatch):
    monkeypatch.setattr(model_router_proxy, "HERMES_MODEL_ROUTER_API_KEY", "router-secret")

    response = client.post(
        "/router/v1/chat/completions",
        headers={"Authorization": "Bearer router-secret"},
        json={"model": "missing", "messages": []},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"


def test_router_non_streaming_chat_forwards_profile_key(client: TestClient, db, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(model_router_proxy, "HERMES_MODEL_ROUTER_API_KEY", "router-secret")
    db.add(_deployment(tmp_path, "confab-100-running", "running"))
    db.commit()
    calls = []

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def json(self):
            return {"id": "chatcmpl-test", "choices": []}

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def post(self, url, headers=None, json=None):
            calls.append((url, headers, json))
            return FakeResponse()

    monkeypatch.setattr(model_router_proxy.aiohttp, "ClientSession", FakeSession)

    response = client.post(
        "/router/v1/chat/completions",
        headers={"Authorization": "Bearer router-secret"},
        json={"model": "confab-100-running", "messages": [{"role": "user", "content": "Hi"}]},
    )

    assert response.status_code == 200
    assert calls[0][0] == "http://localhost:8700/v1/chat/completions"
    assert calls[0][1]["Authorization"] == "Bearer profile-secret"
    assert calls[0][1]["Authorization"] != "Bearer router-secret"
    forwarded_messages = calls[0][2]["messages"]
    assert forwarded_messages[-2]["role"] == "system"
    assert "mcp_raganything_knowledge_query_knowledge_base" in forwarded_messages[-2]["content"]
    assert "`confabs/100`" in forwarded_messages[-2]["content"]
    assert forwarded_messages[-1]["role"] == "user"


def test_router_grounding_instruction_ignores_stale_empty_history(client: TestClient, db, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(model_router_proxy, "HERMES_MODEL_ROUTER_API_KEY", "router-secret")
    db.add(_deployment(tmp_path, "confab-100-running", "running"))
    db.commit()
    calls = []

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def json(self):
            return {"id": "chatcmpl-test", "choices": []}

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def post(self, url, headers=None, json=None):
            calls.append(json)
            return FakeResponse()

    monkeypatch.setattr(model_router_proxy.aiohttp, "ClientSession", FakeSession)

    response = client.post(
        "/router/v1/chat/completions",
        headers={"Authorization": "Bearer router-secret"},
        json={
            "model": "confab-100-running",
            "messages": [
                {"role": "user", "content": "What is INTEGRATE?"},
                {"role": "assistant", "content": "I couldn't find any relevant material."},
                {"role": "user", "content": "What is INTEGRATE?"},
            ],
        },
    )

    assert response.status_code == 200
    messages = calls[0]["messages"]
    assert messages[-2]["role"] == "system"
    assert "If prior chat history says the knowledge base had no relevant material" in messages[-2]["content"]
    assert "Do not call `mcp_raganything_classical_classical_query` as the first search" in messages[-2]["content"]
    assert messages[-1]["content"] == "What is INTEGRATE?"
