"""
Sync deployed Foundry confab knowledge into RAGAnything.
"""

import io
import logging
import os
from typing import Any

import aiohttp
from sqlalchemy.orm import Session

from document_store_v2.compression import decompress
from models import Confab, ConfabDocumentV2, ConfabLearning, DocumentVersion

logger = logging.getLogger(__name__)

RAGANYTHING_URL = os.getenv("RAGANYTHING_URL", "http://localhost:8001").rstrip("/")
RAGANYTHING_WORKSPACE_PREFIX = os.getenv("RAGANYTHING_WORKSPACE_PREFIX", "confabs").strip("/")


def get_raganything_workspace(confab: Confab) -> str:
    return f"{RAGANYTHING_WORKSPACE_PREFIX}/{confab.id}"


def _markdown_for_json_list(title: str, value: Any, empty: str) -> str:
    lines = [f"# {title}\n\n"]
    if not value:
        lines.append(f"{empty}\n")
        return "".join(lines)
    if isinstance(value, str):
        lines.append(value)
        lines.append("\n")
        return "".join(lines)
    if isinstance(value, list):
        for idx, item in enumerate(value, 1):
            if isinstance(item, dict):
                enabled = item.get("enabled", True)
                if enabled is False:
                    continue
                if item.get("input") or item.get("expected_behavior"):
                    lines.append(f"## {item.get('name') or f'Test {idx}'}\n\n")
                    if item.get("input"):
                        lines.append(f"Input:\n\n{item['input']}\n\n")
                    if item.get("expected_behavior"):
                        lines.append(f"Expected behavior:\n\n{item['expected_behavior']}\n\n")
                else:
                    lines.append(f"{idx}. {item.get('rule') or item.get('content') or item}\n")
            else:
                lines.append(f"{idx}. {item}\n")
        return "".join(lines) if len(lines) > 1 else f"# {title}\n\n{empty}\n"
    lines.append(str(value))
    lines.append("\n")
    return "".join(lines)


def _synthetic_files(confab: Confab, learnings: list[ConfabLearning]) -> list[tuple[str, bytes, str]]:
    guardrails = _markdown_for_json_list(
        f"{confab.name} Guardrails",
        confab.guardrails,
        "No guardrails defined.",
    )
    tests = _markdown_for_json_list(
        f"{confab.name} Tests and Sample I/O",
        confab.tests,
        "No tests or sample I/O defined.",
    )

    learnings_md = [f"# {confab.name} Approved Learnings\n\n"]
    if learnings:
        for idx, learning in enumerate(learnings, 1):
            learnings_md.append(f"## Learning {idx}\n\n")
            if learning.summary:
                learnings_md.append(f"Summary: {learning.summary}\n\n")
            learnings_md.append(f"{learning.content}\n\n")
            if learning.tags:
                tags = ", ".join(learning.tags) if isinstance(learning.tags, list) else str(learning.tags)
                learnings_md.append(f"Tags: {tags}\n\n")
    else:
        learnings_md.append("No approved learnings yet.\n")

    confab_md = "\n".join([
        f"# {confab.name}",
        "",
        confab.description or "No description provided.",
        "",
        f"Version: {confab.version}",
        f"Status: {confab.status}",
        "",
    ])

    return [
        ("PURPOSE.md", f"# {confab.name} Purpose\n\n{confab.purpose or 'No purpose provided.'}\n".encode("utf-8"), "text/markdown"),
        ("GUARDRAILS.md", guardrails.encode("utf-8"), "text/markdown"),
        ("TESTS.md", tests.encode("utf-8"), "text/markdown"),
        ("LEARNINGS.md", "".join(learnings_md).encode("utf-8"), "text/markdown"),
        ("CONFAB.md", confab_md.encode("utf-8"), "text/markdown"),
    ]


async def _upload_file(
    session: aiohttp.ClientSession,
    prefix: str,
    filename: str,
    content: bytes,
    content_type: str,
) -> None:
    form = aiohttp.FormData()
    form.add_field("prefix", prefix)
    form.add_field("file", io.BytesIO(content), filename=filename, content_type=content_type)
    async with session.post(
        f"{RAGANYTHING_URL}/api/v1/files/upload",
        data=form,
        timeout=aiohttp.ClientTimeout(total=120),
    ) as resp:
        if resp.status not in (200, 201):
            raise RuntimeError(f"{filename}: upload failed with {resp.status} {await resp.text()}")


async def _index_folder(session: aiohttp.ClientSession, endpoint: str, workspace: str) -> bool:
    indexing_workspace = workspace if workspace.endswith("/") else f"{workspace}/"
    async with session.post(
        f"{RAGANYTHING_URL}{endpoint}",
        json={"working_dir": indexing_workspace, "recursive": True},
        timeout=aiohttp.ClientTimeout(total=600),
    ) as resp:
        if resp.status in (200, 201, 202):
            return True
        raise RuntimeError(f"{endpoint}: indexing failed with {resp.status} {await resp.text()}")


async def sync_documents_to_raganything(db: Session, confab: Confab) -> dict:
    """
    Upload active documents, approved learnings, and definition markdown to RAGAnything.
    """
    workspace = get_raganything_workspace(confab)
    result = {
        "workspace": workspace,
        "uploaded": 0,
        "indexed": False,
        "classical_indexed": False,
        "errors": [],
    }

    documents = (
        db.query(ConfabDocumentV2)
        .filter(ConfabDocumentV2.confab_id == confab.id, ConfabDocumentV2.status == "active")
        .all()
    )
    learnings = (
        db.query(ConfabLearning)
        .filter(ConfabLearning.confab_id == confab.id, ConfabLearning.status == "approved")
        .all()
    )

    upload_items: list[tuple[str, bytes, str]] = []
    for doc in documents:
        latest_version = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )
        if not latest_version or not latest_version.content_blob:
            result["errors"].append(f"{doc.filename}: no deployable content")
            continue
        try:
            content = decompress(latest_version.content_blob)
        except Exception as e:
            result["errors"].append(f"{doc.filename}: decompression failed: {e}")
            logger.warning("Skipping document %s during RAGAnything sync: %s", doc.filename, e)
            continue
        upload_items.append((doc.filename, content, doc.original_content_type or "application/octet-stream"))

    upload_items.extend(_synthetic_files(confab, learnings))

    try:
        async with aiohttp.ClientSession() as session:
            for filename, content, content_type in upload_items:
                try:
                    await _upload_file(session, workspace, filename, content, content_type)
                    result["uploaded"] += 1
                except Exception as e:
                    result["errors"].append(str(e))
                    logger.error("RAGAnything upload error for confab %s: %s", confab.id, e)

            try:
                result["indexed"] = await _index_folder(session, "/api/v1/folder/index", workspace)
            except Exception as e:
                result["errors"].append(str(e))
                logger.error("RAGAnything folder index error for confab %s: %s", confab.id, e)

            try:
                result["classical_indexed"] = await _index_folder(session, "/api/v1/classical/folder/index", workspace)
            except Exception as e:
                result["errors"].append(str(e))
                logger.error("RAGAnything classical index error for confab %s: %s", confab.id, e)
    except aiohttp.ClientError as e:
        result["errors"].append(f"RAGAnything connection failed: {e}")
        logger.warning("Could not connect to RAGAnything at %s: %s", RAGANYTHING_URL, e)

    return result


async def cleanup_raganything_on_undeploy(confab_id: int) -> bool:
    """
    RAGAnything has no observed safe delete-workspace endpoint; cleanup is deferred.
    """
    logger.info(
        "RAGAnything workspace cleanup for confab %s skipped; no safe delete endpoint is available.",
        confab_id,
    )
    return True
