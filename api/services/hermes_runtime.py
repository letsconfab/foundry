"""Docker-backed Hermes profile runtime provisioning."""

import asyncio
import os
from dataclasses import dataclass
from typing import Any

import aiohttp
from sqlalchemy.orm import Session

from models import ConfabDeployment

HERMES_PROFILE_IMAGE = os.getenv("HERMES_PROFILE_IMAGE", "nousresearch/hermes-agent:latest")
HERMES_PROFILE_NETWORK = os.getenv("HERMES_PROFILE_NETWORK", "hermes-agents_hermes-net")
HERMES_PROFILE_PORT_START = int(os.getenv("HERMES_PROFILE_PORT_START", "8700"))
HERMES_PROFILE_PORT_END = int(os.getenv("HERMES_PROFILE_PORT_END", "8799"))


@dataclass
class RuntimeResult:
    ok: bool
    detail: str | None = None
    data: dict[str, Any] | None = None


async def allocate_port(db: Session) -> int:
    used = {
        row[0]
        for row in db.query(ConfabDeployment.api_port).filter(ConfabDeployment.api_port.isnot(None)).all()
    }
    for port in range(HERMES_PROFILE_PORT_START, HERMES_PROFILE_PORT_END + 1):
        if port not in used:
            return port
    raise RuntimeError("No Hermes profile ports available in configured range")


def _docker_client():
    import docker

    return docker.from_env()


async def remove_container(deployment: ConfabDeployment) -> bool:
    def _remove() -> bool:
        client = _docker_client()
        try:
            container = client.containers.get(deployment.container_name)
        except Exception:
            return True
        try:
            container.remove(force=True)
            return True
        finally:
            client.close()

    return await asyncio.to_thread(_remove)


async def create_or_replace_container(deployment: ConfabDeployment) -> RuntimeResult:
    await remove_container(deployment)

    def _create() -> RuntimeResult:
        client = _docker_client()
        try:
            container = client.containers.create(
                image=HERMES_PROFILE_IMAGE,
                name=deployment.container_name,
                network=HERMES_PROFILE_NETWORK,
                ports={"8642/tcp": deployment.api_port},
                environment=load_profile_env(deployment),
                volumes={
                    deployment.profile_host_path: {
                        "bind": "/opt/data",
                        "mode": "rw",
                    }
                },
                entrypoint=["/bin/sh", "-c"],
                command=["exec /opt/hermes/.venv/bin/hermes gateway run"],
                restart_policy={"Name": "unless-stopped"},
                detach=True,
            )
            return RuntimeResult(True, data={"id": container.id, "name": deployment.container_name})
        except Exception as e:
            return RuntimeResult(False, detail=str(e))
        finally:
            client.close()

    return await asyncio.to_thread(_create)


async def start_container(deployment: ConfabDeployment) -> RuntimeResult:
    def _start() -> RuntimeResult:
        client = _docker_client()
        try:
            container = client.containers.get(deployment.container_name)
            container.start()
            return RuntimeResult(True, data={"id": container.id, "name": deployment.container_name})
        except Exception as e:
            return RuntimeResult(False, detail=str(e))
        finally:
            client.close()

    return await asyncio.to_thread(_start)


async def stop_container(deployment: ConfabDeployment) -> bool:
    def _stop() -> bool:
        client = _docker_client()
        try:
            container = client.containers.get(deployment.container_name)
            container.stop(timeout=10)
            return True
        except Exception:
            return True
        finally:
            client.close()

    return await asyncio.to_thread(_stop)


def load_profile_api_key(deployment: ConfabDeployment) -> str | None:
    env_path = os.path.join(deployment.profile_host_path, ".env")
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("API_SERVER_KEY="):
                    return line.strip().split("=", 1)[1]
    except OSError:
        return None
    return None


def load_profile_env(deployment: ConfabDeployment) -> dict[str, str]:
    env_path = os.path.join(deployment.profile_host_path, ".env")
    values: dict[str, str] = {"HERMES_HOME": "/opt/data"}
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key] = value
    except OSError:
        pass
    return values


async def get_runtime_health(deployment: ConfabDeployment) -> dict | None:
    api_key = load_profile_api_key(deployment)
    health = {"healthy": False, "models_ok": False}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://localhost:{deployment.api_port}/health", timeout=5) as resp:
                health["healthy"] = resp.status == 200
                health["health_status"] = resp.status
            if not api_key:
                health["error"] = "Profile API key missing"
                return health
            async with session.get(
                f"http://localhost:{deployment.api_port}/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5,
            ) as resp:
                health["models_status"] = resp.status
                if resp.status == 200:
                    data = await resp.json()
                    ids = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
                    health["models_ok"] = deployment.model_id in ids
                    health["model_ids"] = ids
        return health
    except Exception as e:
        health["error"] = str(e)
        return health


async def wait_for_runtime_healthy(deployment: ConfabDeployment, timeout_seconds: int = 60) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    last = None
    while asyncio.get_event_loop().time() < deadline:
        last = await get_runtime_health(deployment)
        if last and last.get("healthy") and last.get("models_ok"):
            return last
        await asyncio.sleep(2)
    raise RuntimeError(f"Hermes runtime did not become healthy: {last}")
