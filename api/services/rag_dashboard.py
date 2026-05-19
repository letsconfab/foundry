"""LightRAG WebUI sidecar lifecycle and proxy helpers."""

import asyncio
import hashlib
import os
import secrets
import socket
from dataclasses import dataclass
from typing import Any

import aiohttp
from sqlalchemy.orm import Session

from models import ConfabDeployment

RAG_DASHBOARD_IMAGE = os.getenv("RAG_DASHBOARD_IMAGE", "hermes-agents-raganything")
RAG_DASHBOARD_NETWORK = os.getenv("RAG_DASHBOARD_NETWORK", "hermes-agents_hermes-net")
RAG_DASHBOARD_PORT_START = int(os.getenv("RAG_DASHBOARD_PORT_START", "9200"))
RAG_DASHBOARD_PORT_END = int(os.getenv("RAG_DASHBOARD_PORT_END", "9299"))
RAG_DASHBOARD_CONTAINER_PORT = int(os.getenv("RAG_DASHBOARD_CONTAINER_PORT", "9621"))
RAG_DASHBOARD_API_KEY_FILENAME = ".rag_dashboard_api_key"


@dataclass
class RagDashboardResult:
    ok: bool
    detail: str | None = None
    data: dict[str, Any] | None = None


def normalize_rag_working_dir(working_dir: str) -> str:
    return working_dir if working_dir.endswith("/") else f"{working_dir}/"


def lightrag_workspace_name(working_dir: str) -> str:
    normalized = normalize_rag_working_dir(working_dir)
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"ws_{digest}"


def rag_dashboard_container_name(deployment: ConfabDeployment) -> str:
    return f"rag-dashboard-{deployment.profile_name}"


def rag_dashboard_external_url(deployment: ConfabDeployment) -> str:
    return f"http://localhost:{deployment.rag_dashboard_port}/webui/"


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _api_key_path(deployment: ConfabDeployment) -> str:
    return os.path.join(deployment.profile_host_path, RAG_DASHBOARD_API_KEY_FILENAME)


def load_rag_dashboard_api_key(deployment: ConfabDeployment) -> str | None:
    try:
        with open(_api_key_path(deployment), "r", encoding="utf-8") as f:
            value = f.read().strip()
            return value or None
    except OSError:
        return None


def ensure_rag_dashboard_api_key(deployment: ConfabDeployment) -> str:
    existing = load_rag_dashboard_api_key(deployment)
    if existing:
        deployment.rag_dashboard_api_key_hash = _hash_key(existing)
        return existing

    os.makedirs(deployment.profile_host_path, exist_ok=True)
    api_key = f"foundry-rag-dashboard-{secrets.token_urlsafe(24)}"
    with open(_api_key_path(deployment), "w", encoding="utf-8") as f:
        f.write(api_key)
    deployment.rag_dashboard_api_key_hash = _hash_key(api_key)
    return api_key


def _is_host_port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


async def allocate_rag_dashboard_port(db: Session) -> int:
    used = {
        row[0]
        for row in db.query(ConfabDeployment.rag_dashboard_port)
        .filter(ConfabDeployment.rag_dashboard_port.isnot(None))
        .all()
    }
    for port in range(RAG_DASHBOARD_PORT_START, RAG_DASHBOARD_PORT_END + 1):
        if port not in used and not _is_host_port_listening(port):
            return port
    raise RuntimeError("No RAG dashboard ports available in configured range")


def load_rag_dashboard_env(deployment: ConfabDeployment, api_key: str | None = None) -> dict[str, str]:
    key = api_key or load_rag_dashboard_api_key(deployment) or ""
    return {
        "WORKSPACE": deployment.lightrag_workspace or lightrag_workspace_name(deployment.rag_workspace),
        "LIGHTRAG_KV_STORAGE": "PGKVStorage",
        "LIGHTRAG_VECTOR_STORAGE": "PGVectorStorage",
        "LIGHTRAG_GRAPH_STORAGE": "PGGraphStorage",
        "LIGHTRAG_DOC_STATUS_STORAGE": "PGDocStatusStorage",
        "POSTGRES_HOST": os.getenv("RAG_POSTGRES_HOST", "postgres"),
        "POSTGRES_PORT": os.getenv("RAG_POSTGRES_PORT", "5432"),
        "POSTGRES_USER": os.getenv("RAG_POSTGRES_USER", "raganything"),
        "POSTGRES_PASSWORD": os.getenv("RAG_POSTGRES_PASSWORD", "raganything"),
        "POSTGRES_DATABASE": os.getenv("RAG_POSTGRES_DATABASE", "raganything"),
        "LLM_BINDING": "openai",
        "LLM_BINDING_HOST": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        "LLM_BINDING_API_KEY": os.getenv("LLM_API_KEY", ""),
        "LLM_MODEL": os.getenv("CHAT_MODEL", "gpt-4o-mini"),
        "EMBEDDING_BINDING": "openai",
        "EMBEDDING_BINDING_HOST": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
        "EMBEDDING_BINDING_API_KEY": os.getenv("LLM_API_KEY", ""),
        "EMBEDDING_MODEL": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        "EMBEDDING_DIM": os.getenv("EMBEDDING_DIM", "1536"),
        "LIGHTRAG_API_KEY": key,
        "MAX_GRAPH_NODES": os.getenv("MAX_GRAPH_NODES", "1000"),
    }


def _docker_client():
    import docker

    return docker.from_env()


async def remove_rag_dashboard_container(deployment: ConfabDeployment) -> bool:
    name = deployment.rag_dashboard_container_name or rag_dashboard_container_name(deployment)

    def _remove() -> bool:
        client = _docker_client()
        try:
            container = client.containers.get(name)
        except Exception:
            return True
        try:
            container.remove(force=True)
            return True
        finally:
            client.close()

    return await asyncio.to_thread(_remove)


async def create_or_replace_rag_dashboard_container(deployment: ConfabDeployment) -> RagDashboardResult:
    await remove_rag_dashboard_container(deployment)
    api_key = ensure_rag_dashboard_api_key(deployment)
    name = deployment.rag_dashboard_container_name or rag_dashboard_container_name(deployment)

    def _create() -> RagDashboardResult:
        client = _docker_client()
        try:
            container = client.containers.create(
                image=RAG_DASHBOARD_IMAGE,
                name=name,
                network=RAG_DASHBOARD_NETWORK,
                ports={f"{RAG_DASHBOARD_CONTAINER_PORT}/tcp": ("127.0.0.1", deployment.rag_dashboard_port)},
                environment=load_rag_dashboard_env(deployment, api_key),
                command=[
                    "/app/.venv/bin/lightrag-server",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    str(RAG_DASHBOARD_CONTAINER_PORT),
                    "--key",
                    api_key,
                ],
                healthcheck={
                    "test": ["CMD", "curl", "-f", f"http://localhost:{RAG_DASHBOARD_CONTAINER_PORT}/health"],
                    "interval": 30_000_000_000,
                    "timeout": 10_000_000_000,
                    "retries": 3,
                    "start_period": 30_000_000_000,
                },
                restart_policy={"Name": "unless-stopped"},
                detach=True,
            )
            return RagDashboardResult(True, data={"id": container.id, "name": name})
        except Exception as e:
            return RagDashboardResult(False, detail=str(e))
        finally:
            client.close()

    return await asyncio.to_thread(_create)


async def start_rag_dashboard_container(deployment: ConfabDeployment) -> RagDashboardResult:
    name = deployment.rag_dashboard_container_name or rag_dashboard_container_name(deployment)

    def _start() -> RagDashboardResult:
        client = _docker_client()
        try:
            container = client.containers.get(name)
            container.start()
            return RagDashboardResult(True, data={"id": container.id, "name": name})
        except Exception as e:
            return RagDashboardResult(False, detail=str(e))
        finally:
            client.close()

    return await asyncio.to_thread(_start)


async def stop_rag_dashboard_container(deployment: ConfabDeployment) -> bool:
    name = deployment.rag_dashboard_container_name or rag_dashboard_container_name(deployment)

    def _stop() -> bool:
        client = _docker_client()
        try:
            container = client.containers.get(name)
            container.stop(timeout=10)
            return True
        except Exception:
            return True
        finally:
            client.close()

    return await asyncio.to_thread(_stop)


async def get_rag_dashboard_health(deployment: ConfabDeployment) -> dict:
    if not deployment.rag_dashboard_enabled or not deployment.rag_dashboard_port:
        return {"ok": False, "webui_available": False, "error": "RAG dashboard is not enabled"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://127.0.0.1:{deployment.rag_dashboard_port}/health", timeout=5) as resp:
                return {
                    "ok": resp.status == 200,
                    "status": resp.status,
                    "webui_available": resp.status == 200,
                }
    except Exception as e:
        return {"ok": False, "webui_available": False, "error": str(e)}
