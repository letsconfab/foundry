"""
Service for deploying/undeploying confabs to hermes-agents.
"""

import os
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)

HERMES_AGENTS_URL = os.getenv("HERMES_AGENTS_URL", "http://localhost:8022")
HERMES_WEBHOOK_SECRET = os.getenv("HERMES_WEBHOOK_SECRET", "")


def _normalize_name(name: str) -> str:
    return name.lower().replace(" ", "-").replace("_", "-")


async def deploy_confab(confab_name: str) -> Optional[dict]:
    """
    Deploy a confab by creating and starting a realization in hermes-agents.
    Returns the realization details or None on failure.
    """
    agent_name = _normalize_name(confab_name)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Secret": HERMES_WEBHOOK_SECRET,
    }

    try:
        async with aiohttp.ClientSession() as session:
            # Create a realization
            create_url = f"{HERMES_AGENTS_URL}/agents/{agent_name}/realizations"
            async with session.post(
                create_url,
                json={"name": f"{agent_name}-default"},
                timeout=10,
            ) as resp:
                if resp.status not in (200, 201):
                    error = await resp.text()
                    logger.error(f"Failed to create realization: {resp.status} {error}")
                    return None
                realization = await resp.json()

            instance_id = realization["instance_id"]

            # Start the realization
            start_url = f"{HERMES_AGENTS_URL}/agents/{agent_name}/realizations/{instance_id}/start"
            async with session.post(start_url, timeout=30) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.error(f"Failed to start realization: {resp.status} {error}")
                    return None
                started = await resp.json()

            logger.info(f"Deployed {agent_name} on port {started.get('port')}")
            return started

    except aiohttp.ClientConnectorError as e:
        logger.warning(f"Could not connect to hermes-agents: {e}")
        return None
    except Exception as e:
        logger.error(f"Deploy error: {e}")
        return None


async def undeploy_confab(confab_name: str) -> bool:
    """
    Undeploy a confab by stopping and deleting all realizations.
    Returns True on success.
    """
    agent_name = _normalize_name(confab_name)

    try:
        async with aiohttp.ClientSession() as session:
            # List realizations
            list_url = f"{HERMES_AGENTS_URL}/agents/{agent_name}/realizations"
            async with session.get(list_url, timeout=10) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()

            for r in data.get("realizations", []):
                instance_id = r["instance_id"]

                # Stop if running
                if r["status"] == "running":
                    stop_url = f"{HERMES_AGENTS_URL}/agents/{agent_name}/realizations/{instance_id}/stop"
                    async with session.post(stop_url, timeout=15) as resp:
                        pass

                # Delete
                del_url = f"{HERMES_AGENTS_URL}/agents/{agent_name}/realizations/{instance_id}"
                async with session.delete(del_url, timeout=10) as resp:
                    pass

            logger.info(f"Undeployed all realizations for {agent_name}")
            return True

    except Exception as e:
        logger.error(f"Undeploy error: {e}")
        return False


async def get_deploy_status(confab_name: str) -> Optional[dict]:
    """
    Get deployment status for a confab.
    Returns dict with status info or None if not deployed.
    """
    agent_name = _normalize_name(confab_name)

    try:
        async with aiohttp.ClientSession() as session:
            list_url = f"{HERMES_AGENTS_URL}/agents/{agent_name}/realizations"
            async with session.get(list_url, timeout=10) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()

            realizations = data.get("realizations", [])
            if not realizations:
                return {"status": "not_deployed", "realizations": []}

            running = [r for r in realizations if r["status"] == "running"]
            return {
                "status": "running" if running else "stopped",
                "realizations": realizations,
                "api_url": running[0].get("api_url") if running else None,
            }

    except Exception:
        return None
