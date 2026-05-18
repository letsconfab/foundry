import asyncio
from pathlib import Path
from types import SimpleNamespace

from models import Confab, ConfabDeployment
from services import deploy_orchestrator, hermes_runtime
from services.deployment_naming import (
    container_name,
    deployment_model_id,
    normalize_agent_name,
    profile_name,
    rag_workspace,
)
from services.hermes_profile import render_profile_config, render_profile_env, render_soul_md, write_profile_files
from services.hermes_runtime import (
    RuntimeResult,
    allocate_dashboard_port,
    allocate_port,
    create_or_replace_container,
    get_runtime_health,
    load_profile_env,
)


def test_deployment_naming_rules(test_confab: Confab):
    test_confab.id = 123
    test_confab.name = " Policy_Coach!! 2026 "
    assert normalize_agent_name(test_confab.name) == "policy-coach-2026"
    assert deployment_model_id(test_confab) == "confab-123-policy-coach-2026"
    assert profile_name(test_confab) == "confab-123-policy-coach-2026"
    assert container_name(test_confab) == "hermes-confab-123-policy-coach-2026"
    assert rag_workspace(test_confab) == "confabs/123"
    assert normalize_agent_name("!!!") == "unnamed"


def test_soul_md_rendering_includes_confab_fields(test_confab: Confab):
    test_confab.guardrails = [{"rule": "Never invent citations.", "enabled": True}]
    test_confab.tests = [{"name": "Greeting", "input": "Hi", "expected_behavior": "Say hello"}]
    soul = render_soul_md(test_confab, "confabs/1")
    assert "You are Test Confab." in soul
    assert "Test purpose" in soul
    assert "A test confab for testing" in soul
    assert "Never invent citations." in soul
    assert "Greeting" in soul
    assert "confabs/1" in soul
    assert "mcp_raganything_knowledge_query_knowledge_base" in soul
    assert "`working_dir` set exactly to `confabs/1`" in soul
    assert "`mode` set to `naive`" in soul
    assert "`mode` set to `hybrid+`" in soul


def test_profile_config_and_env_rendering(test_confab: Confab):
    deployment = ConfabDeployment(
        confab_id=1,
        user_id=1,
        profile_name="confab-1-test-confab",
        model_id="confab-1-test-confab",
        container_name="hermes-confab-1-test-confab",
        profile_host_path="/tmp/confab-1-test-confab",
        api_port=8700,
        api_server_key_hash="hash",
        api_base_url_external="http://localhost:8700/v1",
        api_base_url_internal="http://hermes-confab-1-test-confab:8642/v1",
        rag_workspace="confabs/1",
        rag_prefix="confabs/1/",
    )
    config = render_profile_config(test_confab, deployment)
    env = render_profile_env(test_confab, deployment, "secret-key")
    assert "raganything_knowledge" in config
    assert "raganything_files" in config
    assert "raganything_classical" in config
    assert "tool_use_enforcement: required" in config
    assert "API_SERVER_ENABLED=true" in env
    assert "API_SERVER_MODEL_NAME=confab-1-test-confab" in env
    assert "API_SERVER_KEY=secret-key" in env


def test_write_profile_files_overwrites(tmp_path: Path, test_confab: Confab):
    deployment = ConfabDeployment(
        confab_id=1,
        user_id=1,
        profile_name="confab-1-test-confab",
        model_id="confab-1-test-confab",
        container_name="hermes-confab-1-test-confab",
        profile_host_path=str(tmp_path),
        api_port=8700,
        api_server_key_hash="hash",
        api_base_url_external="http://localhost:8700/v1",
        api_base_url_internal="http://hermes-confab-1-test-confab:8642/v1",
        rag_workspace="confabs/1",
        rag_prefix="confabs/1/",
    )
    (tmp_path / "SOUL.md").write_text("old", encoding="utf-8")
    asyncio.run(write_profile_files(test_confab, deployment, "secret-key"))
    assert "You are Test Confab." in (tmp_path / "SOUL.md").read_text(encoding="utf-8")
    assert "API_SERVER_KEY=secret-key" in (tmp_path / ".env").read_text(encoding="utf-8")
    assert "raganything_knowledge" in (tmp_path / "config.yaml").read_text(encoding="utf-8")
    profile_env = load_profile_env(deployment)
    assert profile_env["API_SERVER_KEY"] == "secret-key"
    assert profile_env["API_SERVER_MODEL_NAME"] == "confab-1-test-confab"
    assert profile_env["HERMES_HOME"] == "/opt/data"


def test_allocate_port_skips_existing(db):
    db.add(
        ConfabDeployment(
            confab_id=999,
            user_id=1,
            profile_name="confab-999-used",
            model_id="confab-999-used",
            container_name="hermes-confab-999-used",
            profile_host_path="/tmp/confab-999-used",
            api_port=8700,
            api_server_key_hash="hash",
            api_base_url_external="http://localhost:8700/v1",
            api_base_url_internal="http://hermes-confab-999-used:8642/v1",
            rag_workspace="confabs/999",
            rag_prefix="confabs/999/",
        )
    )
    db.commit()
    assert asyncio.run(allocate_port(db)) == 8701


def test_allocate_dashboard_port_skips_existing(db, monkeypatch):
    monkeypatch.setattr(hermes_runtime, "HERMES_PROFILE_DASHBOARD_PORT_START", 9100)
    monkeypatch.setattr(hermes_runtime, "HERMES_PROFILE_DASHBOARD_PORT_END", 9101)
    monkeypatch.setattr(hermes_runtime, "_is_host_port_listening", lambda _port: False)
    db.add(
        ConfabDeployment(
            confab_id=999,
            user_id=1,
            profile_name="confab-999-used",
            model_id="confab-999-used",
            container_name="hermes-confab-999-used",
            profile_host_path="/tmp/confab-999-used",
            api_port=8700,
            api_server_key_hash="hash",
            api_base_url_external="http://localhost:8700/v1",
            api_base_url_internal="http://hermes-confab-999-used:8642/v1",
            dashboard_port=9100,
            rag_workspace="confabs/999",
            rag_prefix="confabs/999/",
        )
    )
    db.commit()

    assert asyncio.run(allocate_dashboard_port(db)) == 9101


def test_allocate_dashboard_port_ignores_nulls(db, monkeypatch):
    monkeypatch.setattr(hermes_runtime, "HERMES_PROFILE_DASHBOARD_PORT_START", 9100)
    monkeypatch.setattr(hermes_runtime, "HERMES_PROFILE_DASHBOARD_PORT_END", 9100)
    monkeypatch.setattr(hermes_runtime, "_is_host_port_listening", lambda _port: False)
    db.add(
        ConfabDeployment(
            confab_id=999,
            user_id=1,
            profile_name="confab-999-used",
            model_id="confab-999-used",
            container_name="hermes-confab-999-used",
            profile_host_path="/tmp/confab-999-used",
            api_port=8700,
            api_server_key_hash="hash",
            api_base_url_external="http://localhost:8700/v1",
            api_base_url_internal="http://hermes-confab-999-used:8642/v1",
            dashboard_port=None,
            rag_workspace="confabs/999",
            rag_prefix="confabs/999/",
        )
    )
    db.commit()

    assert asyncio.run(allocate_dashboard_port(db)) == 9100


def test_deployment_payload_includes_dashboard_fields(monkeypatch):
    monkeypatch.setattr(deploy_orchestrator, "HERMES_PROFILE_DASHBOARD_ENABLED", True)
    deployment = ConfabDeployment(
        confab_id=1,
        user_id=1,
        status="running",
        profile_name="confab-1-test-confab",
        model_id="confab-1-test-confab",
        container_name="hermes-confab-1-test-confab",
        profile_host_path="/tmp/confab-1-test-confab",
        api_port=8700,
        api_server_key_hash="hash",
        api_base_url_external="http://localhost:8700/v1",
        api_base_url_internal="http://hermes-confab-1-test-confab:8642/v1",
        dashboard_enabled=True,
        dashboard_port=9100,
        dashboard_url_external="http://localhost:9100",
        dashboard_url_internal="http://hermes-confab-1-test-confab:9119",
        rag_workspace="confabs/1",
        rag_prefix="confabs/1/",
    )

    payload = deploy_orchestrator._deployment_payload(deployment)
    assert payload["dashboard_enabled"] is True
    assert payload["dashboard_url"] == "http://localhost:9100"
    assert payload["dashboard_port"] == 9100

    deployment.dashboard_enabled = False
    deployment.dashboard_url_external = None
    payload = deploy_orchestrator._deployment_payload(deployment)
    assert payload["dashboard_enabled"] is False
    assert payload["dashboard_url"] is None
    assert payload["dashboard_port"] is None


def test_deploy_runs_post_deployment_rag_evaluation(db, test_confab: Confab, tmp_path: Path, monkeypatch):
    test_confab.status = "published"
    db.commit()
    evaluation = {
        "status": "failed",
        "workspace": f"confabs/{test_confab.id}",
        "total_documents": 2,
        "passed": 1,
        "failed": 1,
        "skipped": 0,
        "tests": [],
        "skipped_documents": [],
        "errors": [],
    }

    async def fake_sync(_db, confab):
        return {
            "workspace": f"confabs/{confab.id}",
            "uploaded": 2,
            "indexed": True,
            "classical_indexed": True,
            "errors": [],
        }

    async def fake_write(_confab, _deployment, _api_key):
        return None

    async def fake_runtime_ok(_deployment):
        return RuntimeResult(True)

    async def fake_health(_deployment):
        return {"healthy": True, "models_ok": True}

    async def fake_register(deployment):
        deployment.router_registered = True
        return {"model_id": deployment.model_id}

    async def fake_evaluate(_db, confab, workspace):
        assert workspace == f"confabs/{confab.id}"
        return evaluation

    monkeypatch.setattr(deploy_orchestrator, "HERMES_PROFILE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(deploy_orchestrator, "allocate_port", lambda _db: asyncio.sleep(0, result=8700))
    monkeypatch.setattr(deploy_orchestrator, "sync_documents_to_raganything", fake_sync)
    monkeypatch.setattr(deploy_orchestrator, "write_profile_files", fake_write)
    monkeypatch.setattr(deploy_orchestrator, "create_or_replace_container", fake_runtime_ok)
    monkeypatch.setattr(deploy_orchestrator, "start_container", fake_runtime_ok)
    monkeypatch.setattr(deploy_orchestrator, "wait_for_runtime_healthy", fake_health)
    monkeypatch.setattr(deploy_orchestrator, "register_deployment_model", fake_register)
    monkeypatch.setattr(deploy_orchestrator, "evaluate_rag_grounding", fake_evaluate)

    result = asyncio.run(deploy_orchestrator.deploy_confab(db, test_confab))

    deployment = db.query(ConfabDeployment).filter(ConfabDeployment.confab_id == test_confab.id).first()
    assert result["deployment"]["status"] == "running"
    assert result["rag_evaluation"] == evaluation
    assert deployment.last_sync_result["evaluation"] == evaluation
    assert deployment.status_detail == "RAG grounding evaluation failed for 1 of 2 documents"


def test_runtime_health_includes_dashboard_state(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(hermes_runtime, "HERMES_PROFILE_DASHBOARD_ENABLED", True)
    profile_path = tmp_path / "profile"
    profile_path.mkdir()
    (profile_path / ".env").write_text("API_SERVER_KEY=secret\n", encoding="utf-8")
    deployment = ConfabDeployment(
        confab_id=1,
        user_id=1,
        profile_name="confab-1-test-confab",
        model_id="confab-1-test-confab",
        container_name="hermes-confab-1-test-confab",
        profile_host_path=str(profile_path),
        api_port=8700,
        api_server_key_hash="hash",
        api_base_url_external="http://localhost:8700/v1",
        api_base_url_internal="http://hermes-confab-1-test-confab:8642/v1",
        dashboard_enabled=True,
        dashboard_port=9100,
        rag_workspace="confabs/1",
        rag_prefix="confabs/1/",
    )

    class FakeResponse:
        def __init__(self, status: int, data: dict | None = None):
            self.status = status
            self._data = data or {}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        async def json(self):
            return self._data

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def get(self, url, **_kwargs):
            if url.endswith("/health"):
                return FakeResponse(200)
            if url.endswith("/v1/models"):
                return FakeResponse(200, {"data": [{"id": "confab-1-test-confab"}]})
            if url == "http://localhost:9100/":
                return FakeResponse(200)
            return FakeResponse(404)

    monkeypatch.setattr(hermes_runtime.aiohttp, "ClientSession", FakeSession)

    health = asyncio.run(get_runtime_health(deployment))
    assert health["healthy"] is True
    assert health["models_ok"] is True
    assert health["dashboard_enabled"] is True
    assert health["dashboard_ok"] is True
    assert health["dashboard_status"] == 200


def test_container_spec_publishes_dashboard_when_enabled(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(hermes_runtime, "HERMES_PROFILE_DASHBOARD_ENABLED", True)
    monkeypatch.setattr(hermes_runtime, "HERMES_PROFILE_DASHBOARD_CONTAINER_PORT", 9119)
    monkeypatch.setattr(hermes_runtime, "remove_container", lambda _deployment: asyncio.sleep(0))
    created = {}

    class FakeContainers:
        def create(self, **kwargs):
            created.update(kwargs)
            return SimpleNamespace(id="container-id")

    class FakeClient:
        containers = FakeContainers()

        def close(self):
            pass

    monkeypatch.setattr(hermes_runtime, "_docker_client", lambda: FakeClient())
    deployment = ConfabDeployment(
        confab_id=1,
        user_id=1,
        profile_name="confab-1-test-confab",
        model_id="confab-1-test-confab",
        container_name="hermes-confab-1-test-confab",
        profile_host_path=str(tmp_path),
        api_port=8700,
        api_server_key_hash="hash",
        api_base_url_external="http://localhost:8700/v1",
        api_base_url_internal="http://hermes-confab-1-test-confab:8642/v1",
        dashboard_enabled=True,
        dashboard_port=9100,
        rag_workspace="confabs/1",
        rag_prefix="confabs/1/",
    )

    result = asyncio.run(create_or_replace_container(deployment))
    assert result.ok is True
    assert created["ports"]["8642/tcp"] == 8700
    assert created["ports"]["9119/tcp"] == ("127.0.0.1", 9100)
    assert "hermes dashboard" in created["command"][0]


def test_container_spec_omits_dashboard_when_disabled(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(hermes_runtime, "HERMES_PROFILE_DASHBOARD_ENABLED", False)
    monkeypatch.setattr(hermes_runtime, "remove_container", lambda _deployment: asyncio.sleep(0))
    created = {}

    class FakeContainers:
        def create(self, **kwargs):
            created.update(kwargs)
            return SimpleNamespace(id="container-id")

    class FakeClient:
        containers = FakeContainers()

        def close(self):
            pass

    monkeypatch.setattr(hermes_runtime, "_docker_client", lambda: FakeClient())
    deployment = ConfabDeployment(
        confab_id=1,
        user_id=1,
        profile_name="confab-1-test-confab",
        model_id="confab-1-test-confab",
        container_name="hermes-confab-1-test-confab",
        profile_host_path=str(tmp_path),
        api_port=8700,
        api_server_key_hash="hash",
        api_base_url_external="http://localhost:8700/v1",
        api_base_url_internal="http://hermes-confab-1-test-confab:8642/v1",
        dashboard_enabled=False,
        dashboard_port=9100,
        rag_workspace="confabs/1",
        rag_prefix="confabs/1/",
    )

    result = asyncio.run(create_or_replace_container(deployment))
    assert result.ok is True
    assert created["ports"] == {"8642/tcp": 8700}
    assert "hermes dashboard" not in created["command"][0]
