"""Inspect deployed RAGAnything workspace contents for a confab."""

import logging
from typing import Any

import aiohttp
from sqlalchemy.orm import Session

from models import Confab, ConfabDeployment, ConfabDocumentV2, ConfabLearning
from services.deployment_naming import rag_workspace
from services.rag_sources import display_name_from_file_path, normalize_file_path
from services.rag_sync import RAGANYTHING_URL, _synthetic_files

logger = logging.getLogger(__name__)


def _file_path_from_item(item: Any, prefix: str) -> tuple[str, dict]:
    metadata = {}
    if isinstance(item, str):
        path = item
    elif isinstance(item, dict):
        metadata = dict(item)
        path = (
            item.get("file_path")
            or item.get("path")
            or item.get("object_path")
            or item.get("object_name")
            or item.get("key")
            or item.get("id")
            or item.get("name")
            or ""
        )
    else:
        return "", {}

    path = normalize_file_path(str(path))
    if path and "/" not in path and prefix:
        path = f"{prefix.rstrip('/')}/{path}"
    return path, metadata


def _items_from_payload(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("files", "items", "objects", "data", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("files", "items", "objects", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _normalize_rag_files(items: list[Any], prefix: str) -> list[dict]:
    files = []
    seen: set[str] = set()
    for item in items:
        path, metadata = _file_path_from_item(item, prefix)
        if not path or path in seen:
            continue
        seen.add(path)
        files.append(
            {
                "id": path,
                "path": path,
                "name": display_name_from_file_path(path),
                "type": "file",
                "size": metadata.get("size") or metadata.get("bytes"),
                "content_type": metadata.get("content_type") or metadata.get("mime_type"),
                "updated_at": metadata.get("updated_at") or metadata.get("last_modified"),
            }
        )
    return files


def _expected_documents(db: Session, confab: Confab) -> list[dict]:
    expected = []
    active_docs = (
        db.query(ConfabDocumentV2)
        .filter(ConfabDocumentV2.confab_id == confab.id, ConfabDocumentV2.status == "active")
        .order_by(ConfabDocumentV2.id.asc())
        .all()
    )
    for doc in active_docs:
        expected.append(
            {
                "name": doc.filename,
                "source_type": "uploaded_document",
                "document_id": doc.id,
                "status": doc.status,
            }
        )

    learnings = (
        db.query(ConfabLearning)
        .filter(ConfabLearning.confab_id == confab.id, ConfabLearning.status == "approved")
        .all()
    )
    for filename, _content, _content_type in _synthetic_files(confab, learnings):
        expected.append(
            {
                "name": filename,
                "source_type": "synthetic_document",
                "document_id": None,
                "status": "generated",
            }
        )
    return expected


async def _list_raganything_files(prefix: str) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{RAGANYTHING_URL}/api/v1/files/list",
            params={"prefix": prefix},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status >= 400:
                raise RuntimeError(f"RAGAnything file list failed with {resp.status} {await resp.text()}")
            return _normalize_rag_files(_items_from_payload(await resp.json()), prefix)


async def list_rag_pipeline_documents(db: Session, confab: Confab) -> dict:
    deployment = db.query(ConfabDeployment).filter(ConfabDeployment.confab_id == confab.id).first()
    workspace = deployment.rag_workspace if deployment else rag_workspace(confab)
    prefix = (deployment.rag_prefix if deployment else f"{workspace}/").rstrip("/")
    sync = deployment.last_sync_result if deployment and deployment.last_sync_result else {}
    expected = _expected_documents(db, confab)
    errors = []
    rag_files = []
    raganything_available = True

    try:
        rag_files = await _list_raganything_files(prefix)
    except Exception as e:
        raganything_available = False
        errors.append(str(e))
        logger.warning("Could not list RAGAnything files for %s: %s", prefix, e)

    expected_names = {item["name"] for item in expected}
    for file in rag_files:
        file["expected"] = file["name"] in expected_names

    rag_file_names = {file["name"] for file in rag_files}
    for item in expected:
        item["present_in_raganything"] = item["name"] in rag_file_names

    return {
        "confab_id": confab.id,
        "deployment_status": deployment.status if deployment else "not_deployed",
        "rag_workspace": workspace,
        "rag_prefix": prefix,
        "raganything_url": RAGANYTHING_URL,
        "raganything_available": raganything_available,
        "files": rag_files,
        "file_count": len(rag_files),
        "expected_documents": expected,
        "expected_document_count": len(expected),
        "last_sync": {
            "uploaded": sync.get("uploaded", 0),
            "indexed": sync.get("indexed", False),
            "classical_indexed": sync.get("classical_indexed", False),
            "errors": sync.get("errors", []),
        },
        "evaluation": sync.get("evaluation"),
        "errors": errors,
    }
