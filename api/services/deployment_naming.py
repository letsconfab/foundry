"""Deterministic names for confab profile deployments."""

import re

from models import Confab


def normalize_agent_name(name: str) -> str:
    slug = (name or "").strip().lower().replace("_", "-")
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "unnamed"


def deployment_model_id(confab: Confab) -> str:
    return f"confab-{confab.id}-{normalize_agent_name(confab.name)}"


def profile_name(confab: Confab) -> str:
    return deployment_model_id(confab)


def container_name(confab: Confab) -> str:
    return f"hermes-confab-{confab.id}-{normalize_agent_name(confab.name)}"


def rag_workspace(confab: Confab) -> str:
    return f"confabs/{confab.id}"
