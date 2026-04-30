"""
Service for syncing confab documents to the confab-rag MCP service.

On deploy:
  1. Queries all active documents for the confab
  2. Decompresses content blobs (zstd)
  3. Posts base64-encoded documents to the confab-rag REST API
  4. confab-rag extracts text, builds KG + vector index via LightRAG

On undeploy:
  - Deletes the confab's RAG index
"""

import os
import base64
import logging
from typing import Optional

import aiohttp
from sqlalchemy.orm import Session

from models import Confab, ConfabDocumentV2, DocumentVersion, ConfabLearning
from document_store_v2.compression import decompress

logger = logging.getLogger(__name__)

CONFAB_RAG_URL = os.getenv("CONFAB_RAG_URL", "http://localhost:8099")


async def sync_documents_to_rag(
    db: Session,
    confab: Confab,
) -> Optional[dict]:
    """
    Push all confab documents and approved learnings to the confab-rag service.

    Called during the deploy flow. Returns the ingestion result or None on failure.
    """
    # 1. Collect documents
    documents = (
        db.query(ConfabDocumentV2)
        .filter(
            ConfabDocumentV2.confab_id == confab.id,
            ConfabDocumentV2.status == "active",
        )
        .all()
    )

    payloads = []

    for doc in documents:
        latest_version = (
            db.query(DocumentVersion)
            .filter(DocumentVersion.document_id == doc.id)
            .order_by(DocumentVersion.version_number.desc())
            .first()
        )
        if not latest_version or not latest_version.content_blob:
            logger.debug(f"Skipping document {doc.filename}: no content")
            continue

        try:
            content = decompress(latest_version.content_blob)
        except Exception as e:
            logger.error(f"Failed to decompress {doc.filename}: {e}")
            continue

        payloads.append({
            "filename": doc.filename,
            "content_base64": base64.b64encode(content).decode("ascii"),
            "content_type": doc.original_content_type or "application/octet-stream",
        })

    # 2. Collect approved learnings as a markdown document
    learnings = (
        db.query(ConfabLearning)
        .filter(
            ConfabLearning.confab_id == confab.id,
            ConfabLearning.status == "approved",
        )
        .all()
    )

    if learnings:
        learnings_md = f"# {confab.name} — Learned Knowledge\n\n"
        for i, learning in enumerate(learnings, 1):
            learnings_md += f"## Learning {i}\n\n"
            learnings_md += f"{learning.content}\n\n"
            if learning.tags:
                tags = ", ".join(learning.tags) if isinstance(learning.tags, list) else str(learning.tags)
                learnings_md += f"*Tags: {tags}*\n\n"
            learnings_md += "---\n\n"

        payloads.append({
            "filename": "learnings.md",
            "content_base64": base64.b64encode(learnings_md.encode("utf-8")).decode("ascii"),
            "content_type": "text/markdown",
        })

    # 3. Include confab purpose and guardrails as documents too
    if confab.purpose:
        purpose_md = f"# {confab.name} — Purpose\n\n{confab.purpose}"
        payloads.append({
            "filename": "PURPOSE.md",
            "content_base64": base64.b64encode(purpose_md.encode("utf-8")).decode("ascii"),
            "content_type": "text/markdown",
        })

    if not payloads:
        logger.info(f"No documents to sync for confab {confab.id} ({confab.name})")
        return {"confab_id": confab.id, "total_indexed": 0, "results": []}

    # 4. Post to confab-rag service
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CONFAB_RAG_URL}/api/ingest",
                json={
                    "confab_id": confab.id,
                    "documents": payloads,
                },
                timeout=aiohttp.ClientTimeout(total=600),  # 10min — LightRAG KG extraction is LLM-heavy
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    logger.info(
                        f"RAG sync for confab {confab.id}: "
                        f"{result.get('total_indexed', 0)} documents indexed"
                    )
                    return result
                else:
                    error = await resp.text()
                    logger.error(
                        f"RAG sync failed for confab {confab.id}: "
                        f"{resp.status} {error}"
                    )
                    return None

    except aiohttp.ClientConnectorError as e:
        logger.warning(f"Could not connect to confab-rag at {CONFAB_RAG_URL}: {e}")
        return None
    except Exception as e:
        logger.error(f"RAG sync error for confab {confab.id}: {e}")
        return None


async def cleanup_rag_on_undeploy(confab_id: int) -> bool:
    """
    Delete the RAG index for a confab. Called during undeploy.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{CONFAB_RAG_URL}/api/confab/{confab_id}",
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 200:
                    logger.info(f"Cleaned up RAG index for confab {confab_id}")
                    return True
                else:
                    error = await resp.text()
                    logger.warning(
                        f"RAG cleanup for confab {confab_id}: {resp.status} {error}"
                    )
                    return False

    except aiohttp.ClientConnectorError:
        logger.warning("confab-rag service not reachable — skipping RAG cleanup")
        return False
    except Exception as e:
        logger.error(f"RAG cleanup error: {e}")
        return False
