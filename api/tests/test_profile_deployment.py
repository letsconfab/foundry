import asyncio
from pathlib import Path

from models import Confab, ConfabDeployment
from services.deployment_naming import (
    container_name,
    deployment_model_id,
    normalize_agent_name,
    profile_name,
    rag_workspace,
)
from services.hermes_profile import render_profile_config, render_profile_env, render_soul_md, write_profile_files
from services.hermes_runtime import allocate_port, load_profile_env


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
