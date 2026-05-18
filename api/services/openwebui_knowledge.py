"""
Legacy service for syncing confab documents and learnings to OpenWebUI's knowledge base.

The current Foundry deploy bridge uses RAGAnything as the deployed knowledge
source and creates only an Open WebUI model wrapper. Keep this module for older
internal callers, but do not call it from the confab deploy path.

On deploy, this service:
1. Authenticates with OpenWebUI as admin
2. Creates a knowledge collection for the confab
3. Uploads all confab documents and approved learnings
4. Creates/updates an OpenWebUI model wrapper that links the knowledge
"""

import os
import io
import base64
import logging
from typing import Optional

import aiohttp
from sqlalchemy.orm import Session

from models import Confab, ConfabDocumentV2, DocumentVersion, ConfabLearning
from document_store_v2.compression import decompress

logger = logging.getLogger(__name__)

OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "http://localhost:3080")
OPENWEBUI_ADMIN_EMAIL = os.getenv("OPENWEBUI_ADMIN_EMAIL", "test@test.com")
OPENWEBUI_ADMIN_PASSWORD = os.getenv("OPENWEBUI_ADMIN_PASSWORD", "admin123")


async def _get_admin_token() -> Optional[str]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OPENWEBUI_URL}/api/v1/auths/signin",
                json={"email": OPENWEBUI_ADMIN_EMAIL, "password": OPENWEBUI_ADMIN_PASSWORD},
                timeout=10,
            ) as resp:
                if resp.status != 200:
                    logger.error(f"OpenWebUI auth failed: {resp.status}")
                    return None
                data = await resp.json()
                return data.get("token")
    except aiohttp.ClientError as e:
        logger.warning(f"Could not connect to OpenWebUI: {e}")
        return None
    except Exception as e:
        logger.error(f"OpenWebUI auth error: {e}")
        return None


async def _upload_file(
    session: aiohttp.ClientSession,
    token: str,
    filename: str,
    content: bytes,
    content_type: str,
) -> Optional[str]:
    """Upload a file to OpenWebUI, return file ID."""
    form = aiohttp.FormData()
    form.add_field(
        "file",
        io.BytesIO(content),
        filename=filename,
        content_type=content_type,
    )

    async with session.post(
        f"{OPENWEBUI_URL}/api/v1/files/",
        headers={"Authorization": f"Bearer {token}"},
        data=form,
        timeout=30,
    ) as resp:
        if resp.status != 200:
            error = await resp.text()
            logger.error(f"File upload failed for {filename}: {resp.status} {error}")
            return None
        data = await resp.json()
        return data.get("id")


async def sync_knowledge_on_deploy(
    db: Session,
    confab: Confab,
    agent_name: str,
) -> Optional[str]:
    """
    Sync confab documents and learnings to OpenWebUI as a knowledge collection.

    Returns the knowledge collection ID, or None on failure.
    """
    token = await _get_admin_token()
    if not token:
        logger.warning("Could not authenticate with OpenWebUI — skipping knowledge sync")
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        # 1. Create knowledge collection
        kb_name = f"{confab.name} Knowledge"
        kb_description = confab.description or f"Knowledge base for {confab.name}"

        async with session.post(
            f"{OPENWEBUI_URL}/api/v1/knowledge/create",
            headers=headers,
            json={"name": kb_name, "description": kb_description},
            timeout=10,
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                logger.error(f"Knowledge creation failed: {resp.status} {error}")
                return None
            kb_data = await resp.json()
            kb_id = kb_data["id"]

        logger.info(f"Created knowledge collection {kb_id} for {confab.name}")

        # 2. Upload confab documents
        documents = (
            db.query(ConfabDocumentV2)
            .filter(
                ConfabDocumentV2.confab_id == confab.id,
                ConfabDocumentV2.status == "active",
            )
            .all()
        )

        for doc in documents:
            latest_version = (
                db.query(DocumentVersion)
                .filter(DocumentVersion.document_id == doc.id)
                .order_by(DocumentVersion.version_number.desc())
                .first()
            )
            if not latest_version or not latest_version.content_blob:
                continue

            content = decompress(latest_version.content_blob)
            file_id = await _upload_file(
                session, token, doc.filename, content, doc.original_content_type,
            )
            if not file_id:
                continue

            # Add file to knowledge collection
            async with session.post(
                f"{OPENWEBUI_URL}/api/v1/knowledge/{kb_id}/file/add",
                headers=headers,
                json={"file_id": file_id},
                timeout=30,
            ) as resp:
                if resp.status == 200:
                    logger.info(f"Added document {doc.filename} to knowledge {kb_id}")
                else:
                    logger.warning(f"Failed to add {doc.filename} to knowledge: {resp.status}")

        # 3. Upload approved learnings as a single markdown file
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
            for learning in learnings:
                summary = f"**{learning.summary}**\n\n" if learning.summary else ""
                tags = f"Tags: {', '.join(learning.tags)}\n\n" if learning.tags else ""
                learnings_md += f"## Learning\n\n{summary}{learning.content}\n\n{tags}---\n\n"

            file_id = await _upload_file(
                session, token, "learnings.md", learnings_md.encode("utf-8"), "text/markdown",
            )
            if file_id:
                async with session.post(
                    f"{OPENWEBUI_URL}/api/v1/knowledge/{kb_id}/file/add",
                    headers=headers,
                    json={"file_id": file_id},
                    timeout=30,
                ) as resp:
                    if resp.status == 200:
                        logger.info(f"Added {len(learnings)} learnings to knowledge {kb_id}")

        # 4. Create/update OpenWebUI model with knowledge association
        model_payload = {
            "id": agent_name,
            "name": confab.name,
            "base_model_id": agent_name,
            "meta": {
                "description": confab.description or f"Chat with {confab.name}",
                "knowledge": [
                    {
                        "collection_name": kb_id,
                        "name": kb_name,
                        "type": "collection",
                    }
                ],
            },
            "params": {},
        }

        # Try update first, then create
        async with session.post(
            f"{OPENWEBUI_URL}/api/v1/models/model/update",
            headers=headers,
            json={"id": agent_name, **model_payload},
            timeout=10,
        ) as resp:
            if resp.status == 200:
                logger.info(f"Updated OpenWebUI model {agent_name} with knowledge")
            else:
                async with session.post(
                    f"{OPENWEBUI_URL}/api/v1/models/create",
                    headers=headers,
                    json=model_payload,
                    timeout=10,
                ) as create_resp:
                    if create_resp.status == 200:
                        logger.info(f"Created OpenWebUI model {agent_name} with knowledge")
                    else:
                        error = await create_resp.text()
                        logger.warning(f"Failed to create model in OpenWebUI: {error}")

        return kb_id


async def cleanup_knowledge_on_undeploy(agent_name: str) -> bool:
    """Remove knowledge collection and model from OpenWebUI on undeploy."""
    token = await _get_admin_token()
    if not token:
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    async with aiohttp.ClientSession() as session:
        # Delete the model wrapper
        async with session.post(
            f"{OPENWEBUI_URL}/api/v1/models/model/delete",
            headers=headers,
            json={"id": agent_name},
            timeout=10,
        ) as resp:
            if resp.status == 200:
                logger.info(f"Deleted OpenWebUI model {agent_name}")

    return True
