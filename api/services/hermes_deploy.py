"""
Legacy Open WebUI wrapper deploy service.

The active Foundry deploy path now provisions a dedicated Hermes profile runtime
through services.deploy_orchestrator. Keep this module only for legacy callers
and compatibility tests.
"""

import logging
import os
import re
from typing import Any, Optional

import aiohttp

from models import Confab

logger = logging.getLogger(__name__)

OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "http://localhost:3001").rstrip("/")
OPENWEBUI_ADMIN_EMAIL = os.getenv("OPENWEBUI_ADMIN_EMAIL", "")
OPENWEBUI_ADMIN_PASSWORD = os.getenv("OPENWEBUI_ADMIN_PASSWORD", "")
HERMES_OPENWEBUI_BASE_MODEL = os.getenv("HERMES_OPENWEBUI_BASE_MODEL", "hermes-agent")


def normalize_agent_name(name: str) -> str:
    """Normalize a confab name to a deterministic URL-safe slug."""
    slug = (name or "").lower().replace("_", "-")
    slug = re.sub(r"[^a-z0-9-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "unnamed"


def _model_id(confab: Confab) -> str:
    return f"confab-{confab.id}-{normalize_agent_name(confab.name)}"


def _format_structured_list(value: Any, empty: str) -> str:
    if not value:
        return empty
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                text = (
                    item.get("rule")
                    or item.get("expected_behavior")
                    or item.get("input")
                    or item.get("name")
                    or str(item)
                )
                if item.get("input") and item.get("expected_behavior"):
                    text = f"{item.get('name') or 'Sample'}: input={item.get('input')} expected={item.get('expected_behavior')}"
                enabled = item.get("enabled", True)
                if enabled is False:
                    continue
                lines.append(f"- {text}")
            else:
                lines.append(f"- {item}")
        return "\n".join(lines) if lines else empty
    return str(value)


def render_confab_system_prompt(confab: Confab, rag_workspace: str) -> str:
    """Render the Open WebUI system prompt for a deployed confab."""
    description = confab.description or "No description provided."
    purpose = confab.purpose or "No purpose provided."
    guardrails = _format_structured_list(confab.guardrails, "No guardrails defined.")
    tests = _format_structured_list(confab.tests, "No sample I/O expectations defined.")

    return "\n".join([
        f"You are {confab.name}.",
        "",
        "Description:",
        description,
        "",
        "Purpose:",
        purpose,
        "",
        "Guardrails:",
        guardrails,
        "",
        "Sample and test expectations:",
        tests,
        "",
        f"Ground answers in the deployed RAGAnything workspace `{rag_workspace}` whenever relevant.",
        "If deployed knowledge has no relevant result, say that clearly instead of inventing supporting facts.",
    ])


async def _get_admin_token(session: aiohttp.ClientSession) -> Optional[str]:
    try:
        async with session.post(
            f"{OPENWEBUI_URL}/api/v1/auths/signin",
            json={"email": OPENWEBUI_ADMIN_EMAIL, "password": OPENWEBUI_ADMIN_PASSWORD},
            timeout=10,
        ) as resp:
            if resp.status != 200:
                logger.error("Open WebUI auth failed: %s %s", resp.status, await resp.text())
                return None
            data = await resp.json()
            return data.get("token")
    except aiohttp.ClientError as e:
        logger.warning("Could not connect to Open WebUI at %s: %s", OPENWEBUI_URL, e)
        return None


def _model_payload(confab: Confab, rag_workspace: str) -> dict:
    return {
        "id": _model_id(confab),
        "name": confab.name,
        "base_model_id": HERMES_OPENWEBUI_BASE_MODEL,
        "meta": {
            "description": confab.description or f"Confab model wrapper for {confab.name}",
            "rag_workspace": rag_workspace,
        },
        "params": {
            "system": render_confab_system_prompt(confab, rag_workspace),
        },
    }


async def deploy_confab_to_openwebui(confab: Confab, rag_workspace: str) -> Optional[dict]:
    """Create or update an Open WebUI model wrapper for a confab."""
    payload = _model_payload(confab, rag_workspace)

    try:
        async with aiohttp.ClientSession() as session:
            token = await _get_admin_token(session)
            if not token:
                return None
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

            async with session.post(
                f"{OPENWEBUI_URL}/api/v1/models/model/update",
                headers=headers,
                json={"id": payload["id"], **payload},
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    logger.info("Updated Open WebUI model %s", payload["id"])
                    return {
                        "status": "running",
                        "model_id": payload["id"],
                        "openwebui_url": OPENWEBUI_URL,
                        "workspace": rag_workspace,
                    }
                update_error = await resp.text()

            async with session.post(
                f"{OPENWEBUI_URL}/api/v1/models/create",
                headers=headers,
                json=payload,
                timeout=10,
            ) as resp:
                if resp.status in (200, 201):
                    logger.info("Created Open WebUI model %s", payload["id"])
                    return {
                        "status": "running",
                        "model_id": payload["id"],
                        "openwebui_url": OPENWEBUI_URL,
                        "workspace": rag_workspace,
                    }
                logger.error(
                    "Open WebUI model create failed for %s after update failed (%s): %s %s",
                    payload["id"],
                    update_error,
                    resp.status,
                    await resp.text(),
                )
                return None
    except Exception as e:
        logger.error("Open WebUI deploy error for confab %s: %s", confab.id, e)
        return None


async def undeploy_confab_from_openwebui(confab: Confab) -> bool:
    """Delete the Open WebUI model wrapper for a confab."""
    model_id = _model_id(confab)
    try:
        async with aiohttp.ClientSession() as session:
            token = await _get_admin_token(session)
            if not token:
                return False
            async with session.post(
                f"{OPENWEBUI_URL}/api/v1/models/model/delete",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"id": model_id},
                timeout=10,
            ) as resp:
                if resp.status in (200, 204, 404):
                    logger.info("Deleted Open WebUI model wrapper %s", model_id)
                    return True
                logger.error("Open WebUI model delete failed: %s %s", resp.status, await resp.text())
                return False
    except Exception as e:
        logger.error("Open WebUI undeploy error for confab %s: %s", confab.id, e)
        return False


def _find_model(models: Any, model_id: str) -> Optional[dict]:
    if isinstance(models, dict):
        for key in ("data", "models"):
            found = _find_model(models.get(key), model_id)
            if found:
                return found
        if models.get("id") == model_id:
            return models
    if isinstance(models, list):
        for model in models:
            if isinstance(model, dict) and model.get("id") == model_id:
                return model
    return None


async def get_openwebui_deploy_status(confab: Confab) -> Optional[dict]:
    """Return running status if the Open WebUI model wrapper exists."""
    model_id = _model_id(confab)
    try:
        async with aiohttp.ClientSession() as session:
            token = await _get_admin_token(session)
            if not token:
                return None
            headers = {"Authorization": f"Bearer {token}"}
            async with session.get(f"{OPENWEBUI_URL}/api/v1/models", headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    logger.warning("Open WebUI model list failed: %s %s", resp.status, await resp.text())
                    return None
                model = _find_model(await resp.json(), model_id)
                if not model:
                    return None
                workspace = (model.get("meta") or {}).get("rag_workspace")
                return {
                    "status": "running",
                    "model_id": model_id,
                    "openwebui_url": OPENWEBUI_URL,
                    "rag_workspace": workspace,
                }
    except Exception as e:
        logger.error("Open WebUI status error for confab %s: %s", confab.id, e)
        return None
