"""
Service for sending confab publications to hermes-agents.
"""

import os
import logging
import aiohttp
from typing import Optional

from models import Confab

logger = logging.getLogger(__name__)

HERMES_AGENTS_URL = os.getenv("HERMES_AGENTS_URL", "http://localhost:8022")
HERMES_WEBHOOK_SECRET = os.getenv("HERMES_WEBHOOK_SECRET", "")


def _format_guardrails(guardrails: list) -> str:
    """Format guardrails list to markdown."""
    if not guardrails:
        return ""

    lines = []
    for i, g in enumerate(guardrails, 1):
        if isinstance(g, dict):
            text = g.get("text", g.get("rule", str(g)))
        else:
            text = str(g)
        lines.append(f"{i}. {text}")

    return "\n".join(lines)


def _format_tests(tests: list) -> str:
    """Format tests list to markdown."""
    if not tests:
        return ""

    lines = []
    for i, t in enumerate(tests, 1):
        if isinstance(t, dict):
            scenario = t.get("scenario", t.get("name", f"Test {i}"))
            input_val = t.get("input", t.get("user_input", ""))
            output_val = t.get("expected_behavior", t.get("expected_output", t.get("output", "")))
            lines.append(f"## Scenario {i}: {scenario}")
            if input_val:
                lines.append(f"**User:** {input_val}")
            if output_val:
                lines.append(f"**Agent:** {output_val}")
            lines.append("")
        else:
            lines.append(str(t))

    return "\n".join(lines)


async def notify_hermes_agents(confab: Confab) -> bool:
    """
    Send confab publication to hermes-agents webhook.

    Returns True if successful, False otherwise.
    """
    if not HERMES_WEBHOOK_SECRET:
        logger.info("HERMES_WEBHOOK_SECRET not set, skipping webhook")
        return False

    url = f"{HERMES_AGENTS_URL}/webhook/confab-published"

    payload = {
        "confab_id": confab.id,
        "name": confab.name,
        "description": confab.description,
        "purpose_md": confab.purpose or "",
        "guardrails_md": _format_guardrails(confab.guardrails),
        "tests_md": _format_tests(confab.tests),
        "version": 1,  # Could parse from confab.version if needed
    }

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Secret": HERMES_WEBHOOK_SECRET,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    logger.info(f"Successfully notified hermes-agents of confab '{confab.name}' publication")
                    return True
                else:
                    error_text = await resp.text()
                    logger.error(f"Hermes webhook failed with status {resp.status}: {error_text}")
                    return False

    except aiohttp.ClientConnectorError as e:
        logger.warning(f"Could not connect to hermes-agents at {url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error notifying hermes-agents: {e}")
        return False
