"""Naming helpers shared by legacy agent runtime modules."""

import re


def slugify(text: str) -> str:
    """
    Convert text to a clean, URL-friendly slug.

    This preserves the legacy Foreman/GitHub folder behavior used by
    agent_runner and agent_tools.
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", "", text)
    text = text.strip()
    text = text.replace(" ", "-")
    return re.sub(r"-+", "-", text)
