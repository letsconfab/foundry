"""Render and write Hermes profile files for a deployed confab."""

import os
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any

import yaml

from models import Confab, ConfabDeployment

HERMES_PLATFORM_PROFILE_SOURCE = os.getenv("HERMES_PLATFORM_PROFILE_SOURCE", "/opt/data")
HERMES_PLATFORM_PROFILE_CONTAINER = os.getenv("HERMES_PLATFORM_PROFILE_CONTAINER", "hermes-agent")

_PLATFORM_CONFIG_KEYS = (
    "model",
    "models",
    "providers",
    "fallback_providers",
    "credential_pool_strategies",
    "llm",
    "provider",
    "model_provider",
    "model_name",
)

_PLATFORM_ENV_KEYS = (
    "HERMES_INFERENCE_PROVIDER",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_TOKEN",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
    "GEMINI_BASE_URL",
    "OLLAMA_API_KEY",
    "OLLAMA_BASE_URL",
    "GLM_API_KEY",
    "GLM_BASE_URL",
    "KIMI_API_KEY",
    "KIMI_BASE_URL",
    "KIMI_CN_API_KEY",
    "ARCEEAI_API_KEY",
    "ARCEE_BASE_URL",
    "MINIMAX_API_KEY",
    "MINIMAX_BASE_URL",
    "MINIMAX_CN_API_KEY",
    "MINIMAX_CN_BASE_URL",
    "OPENCODE_ZEN_API_KEY",
    "OPENCODE_ZEN_BASE_URL",
    "OPENCODE_GO_API_KEY",
    "OPENCODE_GO_BASE_URL",
    "HF_TOKEN",
    "HERMES_QWEN_BASE_URL",
    "XIAOMI_API_KEY",
    "XIAOMI_BASE_URL",
)


def _format_markdown_list(value: Any, empty: str) -> str:
    if not value:
        return empty
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        lines = []
        for idx, item in enumerate(value, 1):
            if isinstance(item, dict):
                if item.get("enabled", True) is False:
                    continue
                if item.get("input") or item.get("expected_behavior"):
                    name = item.get("name") or f"Sample {idx}"
                    lines.append(f"## {name}")
                    if item.get("input"):
                        lines.append("")
                        lines.append(f"Input: {item['input']}")
                    if item.get("expected_behavior"):
                        lines.append("")
                        lines.append(f"Expected behavior: {item['expected_behavior']}")
                    lines.append("")
                else:
                    text = item.get("rule") or item.get("content") or item.get("name") or str(item)
                    lines.append(f"- {text}")
            else:
                lines.append(f"- {item}")
        return "\n".join(lines).strip() or empty
    return str(value)


def render_soul_md(confab: Confab, rag_workspace: str) -> str:
    guardrails = _format_markdown_list(confab.guardrails, "No guardrails defined.")
    tests = _format_markdown_list(confab.tests, "No sample I/O expectations defined.")
    return "\n\n".join([
        "# Identity",
        f"You are {confab.name}.",
        "# Purpose",
        confab.purpose or "No purpose provided.",
        "# Description",
        confab.description or "No description provided.",
        "# Guardrails",
        guardrails,
        "# Sample I/O Expectations",
        tests,
        "# Knowledge Grounding",
        (
            f"Use deployed knowledge from RAGAnything workspace `{rag_workspace}` when a user asks "
            "questions that may depend on confab documents or approved learnings.\n\n"
            "For knowledge questions, first call `mcp_raganything_knowledge_query_knowledge_base` with "
            f"`working_dir` set exactly to `{rag_workspace}`, the user's question as `query`, `mode` set to "
            "`naive`, and `top_k` set to 10. If that returns no useful result, retry "
            "`mcp_raganything_knowledge_query_knowledge_base` with `mode` set to `hybrid+` and `top_k` set to 10. "
            "Use `mcp_raganything_classical_classical_query` only as a supplemental fallback, and do not treat one "
            "empty classical result as proof that deployed knowledge is absent.\n\n"
            "If deployed knowledge has no relevant result after those retries, say that clearly instead of "
            "inventing supporting facts."
        ),
    ]) + "\n"


def _read_platform_file(filename: str) -> str | None:
    source = Path(HERMES_PLATFORM_PROFILE_SOURCE) / filename
    if source.exists():
        try:
            return source.read_text(encoding="utf-8")
        except OSError:
            return None

    if not HERMES_PLATFORM_PROFILE_CONTAINER:
        return None

    try:
        import docker

        client = docker.from_env()
        try:
            container = client.containers.get(HERMES_PLATFORM_PROFILE_CONTAINER)
            bits, _stat = container.get_archive(f"/opt/data/{filename}")
            archive = BytesIO(b"".join(bits))
            with tarfile.open(fileobj=archive) as tar:
                member = tar.getmember(filename)
                extracted = tar.extractfile(member)
                if extracted is None:
                    return None
                return extracted.read().decode("utf-8")
        finally:
            client.close()
    except Exception:
        return None


def _load_platform_model_config() -> dict:
    text = _read_platform_file("config.yaml")
    if not text:
        return {}
    try:
        data = yaml.safe_load(text) or {}
    except Exception:
        return {}
    return {key: data[key] for key in _PLATFORM_CONFIG_KEYS if key in data}


def _load_platform_provider_env() -> dict[str, str]:
    values = {
        key: value
        for key in _PLATFORM_ENV_KEYS
        if (value := os.getenv(key, "").strip())
    }
    text = _read_platform_file(".env")
    if not text:
        return values
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in _PLATFORM_ENV_KEYS and value:
            values.setdefault(key, value)
    return values


def render_profile_config(confab: Confab, deployment: ConfabDeployment) -> str:
    config = _load_platform_model_config()
    config.update({
        "mcp_servers": {
            "raganything_knowledge": {
                "url": "http://raganything:8000/rag/mcp",
                "timeout": 180,
            },
            "raganything_files": {
                "url": "http://raganything:8000/files/mcp",
                "timeout": 120,
            },
            "raganything_classical": {
                "url": "http://raganything:8000/classical/mcp",
                "timeout": 180,
            },
        },
        "agent": {
            **(config.get("agent") if isinstance(config.get("agent"), dict) else {}),
            "tool_use_enforcement": "required",
        },
    })
    return yaml.safe_dump(config, sort_keys=False)


def render_profile_env(confab: Confab, deployment: ConfabDeployment, api_key: str) -> str:
    lines = [
        "# Generated by Foundry. Redeploy overwrites this file.",
        "API_SERVER_ENABLED=true",
        "API_SERVER_HOST=0.0.0.0",
        "API_SERVER_PORT=8642",
        f"API_SERVER_KEY={api_key}",
        f"API_SERVER_MODEL_NAME={deployment.model_id}",
        "API_SERVER_CORS_ORIGINS=*",
    ]
    provider_env = _load_platform_provider_env()
    if provider_env:
        lines.extend(["", "# Platform default inference provider"])
        lines.extend(f"{key}={value}" for key, value in sorted(provider_env.items()))
    lines.append("")
    return "\n".join(lines)


async def write_profile_files(confab: Confab, deployment: ConfabDeployment, api_key: str) -> None:
    path = Path(deployment.profile_host_path)
    path.mkdir(parents=True, exist_ok=True)
    (path / "SOUL.md").write_text(render_soul_md(confab, deployment.rag_workspace), encoding="utf-8")
    (path / "config.yaml").write_text(render_profile_config(confab, deployment), encoding="utf-8")
    (path / ".env").write_text(render_profile_env(confab, deployment, api_key), encoding="utf-8")
    auth_json = _read_platform_file("auth.json")
    if auth_json:
        (path / "auth.json").write_text(auth_json, encoding="utf-8")
