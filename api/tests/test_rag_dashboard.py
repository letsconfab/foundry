import asyncio
from types import SimpleNamespace

from models import ConfabDeployment
from services import rag_dashboard


def _deployment(tmp_path, **overrides):
    values = {
        "confab_id": 3911,
        "user_id": 1,
        "status": "running",
        "profile_name": "confab-3911-test",
        "model_id": "confab-3911-test",
        "container_name": "hermes-confab-3911-test",
        "profile_host_path": str(tmp_path),
        "api_port": 8700,
        "api_server_key_hash": "hash",
        "api_base_url_external": "http://localhost:8700/v1",
        "api_base_url_internal": "http://hermes-confab-3911-test:8642/v1",
        "rag_workspace": "confabs/3911",
        "rag_prefix": "confabs/3911/",
        "lightrag_workspace": "ws_196399baf97261eb",
        "rag_dashboard_enabled": True,
        "rag_dashboard_port": 9200,
        "rag_dashboard_container_name": "rag-dashboard-confab-3911-test",
    }
    values.update(overrides)
    return ConfabDeployment(**values)


def test_lightrag_workspace_name_normalizes_trailing_slash():
    assert rag_dashboard.lightrag_workspace_name("confabs/3911") == "ws_196399baf97261eb"
    assert rag_dashboard.lightrag_workspace_name("confabs/3911/") == "ws_196399baf97261eb"


def test_allocate_rag_dashboard_port_skips_existing(db, monkeypatch, tmp_path):
    monkeypatch.setattr(rag_dashboard, "RAG_DASHBOARD_PORT_START", 9200)
    monkeypatch.setattr(rag_dashboard, "RAG_DASHBOARD_PORT_END", 9201)
    monkeypatch.setattr(rag_dashboard, "_is_host_port_listening", lambda _port: False)
    db.add(_deployment(tmp_path, rag_dashboard_port=9200))
    db.commit()

    assert asyncio.run(rag_dashboard.allocate_rag_dashboard_port(db)) == 9201


def test_container_spec_uses_lightrag_server_and_pg_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(rag_dashboard, "remove_rag_dashboard_container", lambda _deployment: asyncio.sleep(0))
    created = {}

    class FakeContainers:
        def create(self, **kwargs):
            created.update(kwargs)
            return SimpleNamespace(id="container-id")

    class FakeClient:
        containers = FakeContainers()

        def close(self):
            pass

    monkeypatch.setattr(rag_dashboard, "_docker_client", lambda: FakeClient())
    deployment = _deployment(tmp_path)

    result = asyncio.run(rag_dashboard.create_or_replace_rag_dashboard_container(deployment))

    assert result.ok is True
    assert created["image"] == "hermes-agents-raganything"
    assert created["command"][:5] == ["/app/.venv/bin/lightrag-server", "--host", "0.0.0.0", "--port", "9621"]
    assert created["command"][5] == "--key"
    assert created["command"][6].startswith("foundry-rag-dashboard-")
    assert created["ports"]["9621/tcp"] == ("127.0.0.1", 9200)
    assert created["network"] == "hermes-agents_hermes-net"
    assert created["environment"]["WORKSPACE"] == "ws_196399baf97261eb"
    assert created["environment"]["LIGHTRAG_KV_STORAGE"] == "PGKVStorage"
    assert created["environment"]["LIGHTRAG_VECTOR_STORAGE"] == "PGVectorStorage"
    assert created["environment"]["LIGHTRAG_GRAPH_STORAGE"] == "PGGraphStorage"
    assert created["environment"]["LIGHTRAG_DOC_STATUS_STORAGE"] == "PGDocStatusStorage"
    assert created["environment"]["LIGHTRAG_API_KEY"].startswith("foundry-rag-dashboard-")
    assert deployment.rag_dashboard_api_key_hash


def test_health_check_available_and_unavailable(tmp_path, monkeypatch):
    deployment = _deployment(tmp_path)

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def get(self, url, **_kwargs):
            assert url == "http://127.0.0.1:9200/health"
            return FakeResponse()

    monkeypatch.setattr(rag_dashboard.aiohttp, "ClientSession", FakeSession)
    health = asyncio.run(rag_dashboard.get_rag_dashboard_health(deployment))
    assert health == {"ok": True, "status": 200, "webui_available": True}

    deployment.rag_dashboard_enabled = False
    health = asyncio.run(rag_dashboard.get_rag_dashboard_health(deployment))
    assert health["ok"] is False
