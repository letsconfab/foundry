"""Post-deployment checks for RAG source grounding."""

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass

import aiohttp
from sqlalchemy.orm import Session

from document_store_v2.compression import decompress
from models import Confab, ConfabDocumentV2, ConfabLearning, DocumentVersion
from services import rag_sync
from services.rag_sources import display_name_from_file_path, normalize_file_path, sources_from_chunks

logger = logging.getLogger(__name__)

MAX_EVALUATED_DOCUMENTS = 50
RAG_EVALUATION_WAIT_SECONDS = float(os.getenv("RAG_EVALUATION_WAIT_SECONDS", "180"))
RAG_EVALUATION_RETRY_INTERVAL_SECONDS = float(os.getenv("RAG_EVALUATION_RETRY_INTERVAL_SECONDS", "5"))


@dataclass
class RagGroundingCandidate:
    filename: str
    content: bytes
    document_id: int | None = None
    source_type: str = "document"


def _latest_version(db: Session, document_id: int) -> DocumentVersion | None:
    return (
        db.query(DocumentVersion)
        .filter(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
        .first()
    )


def _deployed_rag_candidates(db: Session, confab: Confab) -> tuple[list[RagGroundingCandidate], list[dict]]:
    candidates: list[RagGroundingCandidate] = []
    skipped: list[dict] = []

    documents = (
        db.query(ConfabDocumentV2)
        .filter(ConfabDocumentV2.confab_id == confab.id, ConfabDocumentV2.status == "active")
        .order_by(ConfabDocumentV2.id.asc())
        .all()
    )
    for doc in documents:
        latest = _latest_version(db, doc.id)
        if not latest or not latest.content_blob:
            skipped.append({"filename": doc.filename, "document_id": doc.id, "reason": "no deployable content"})
            continue
        try:
            content = decompress(latest.content_blob)
        except Exception as e:
            skipped.append({"filename": doc.filename, "document_id": doc.id, "reason": f"decompression failed: {e}"})
            continue
        if content.startswith(b"%PDF"):
            skipped.append(
                {
                    "filename": doc.filename,
                    "document_id": doc.id,
                    "reason": "binary PDF content is validated through RAG document inventory",
                }
            )
            continue
        candidates.append(
            RagGroundingCandidate(
                filename=doc.filename,
                content=content,
                document_id=doc.id,
                source_type="uploaded_document",
            )
        )

    learnings = (
        db.query(ConfabLearning)
        .filter(ConfabLearning.confab_id == confab.id, ConfabLearning.status == "approved")
        .all()
    )
    for filename, content, _content_type in rag_sync._synthetic_files(confab, learnings):
        candidates.append(RagGroundingCandidate(filename=filename, content=content, source_type="synthetic_document"))

    return candidates[:MAX_EVALUATED_DOCUMENTS], skipped


def _query_for_candidate(candidate: RagGroundingCandidate) -> str:
    if candidate.content.startswith(b"%PDF"):
        return f'Retrieve the deployed source document named "{candidate.filename}" and cite it as the source.'
    text = candidate.content.decode("utf-8", errors="ignore")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    printable = sum(1 for char in text if char.isprintable() or char.isspace())
    if not text or printable / max(len(text), 1) < 0.85:
        return f'Retrieve the deployed source document named "{candidate.filename}" and cite it as the source.'
    if len(text) >= 80:
        excerpt = text[:500]
        return (
            "Which deployed source document contains the following passage? "
            f'Passage: "{excerpt}"'
        )
    return f'Retrieve the deployed source document named "{candidate.filename}" and cite it as the source.'


def _source_matches_filename(source: dict, filename: str) -> bool:
    source_info = source.get("source") if isinstance(source, dict) else {}
    metadata = source.get("metadata") if isinstance(source, dict) else []
    candidates = []
    if isinstance(source_info, dict):
        candidates.extend([source_info.get("id"), source_info.get("name")])
    if isinstance(metadata, list):
        for item in metadata:
            if isinstance(item, dict):
                candidates.extend([item.get("source"), item.get("name")])

    for value in candidates:
        if not value:
            continue
        normalized = normalize_file_path(str(value))
        if normalized.endswith(f"/{filename}") or normalized == filename:
            return True
        if display_name_from_file_path(normalized) == filename:
            return True
    return False


async def _query_sources(
    session: aiohttp.ClientSession,
    working_dir: str,
    query: str,
    mode: str,
) -> list[dict]:
    async with session.post(
        f"{rag_sync.RAGANYTHING_URL}/api/v1/query",
        json={
            "working_dir": working_dir,
            "query": query,
            "mode": mode,
            "top_k": 10,
        },
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"RAGAnything query failed with {resp.status} {await resp.text()}")
        payload = await resp.json()

    chunks = []
    if isinstance(payload, list):
        chunks = [item for item in payload if isinstance(item, dict)]
    elif isinstance(payload, dict):
        for key in ("chunks", "results", "documents", "items", "sources"):
            value = payload.get(key)
            if isinstance(value, list):
                chunks = [item for item in value if isinstance(item, dict)]
                break
        data = payload.get("data")
        if not chunks and isinstance(data, list):
            chunks = [item for item in data if isinstance(item, dict)]
        if not chunks and isinstance(data, dict):
            for key in ("chunks", "results", "documents", "items"):
                value = data.get(key)
                if isinstance(value, list):
                    chunks = [item for item in value if isinstance(item, dict)]
                    break
    return sources_from_chunks(chunks)


async def _evaluate_candidate(
    session: aiohttp.ClientSession,
    candidate: RagGroundingCandidate,
    working_dir: str,
    attempt: int,
) -> dict:
    query = _query_for_candidate(candidate)
    modes_tried = []
    sources = []
    error = None
    for mode in ("naive", "hybrid"):
        modes_tried.append(mode)
        try:
            sources = await _query_sources(session, working_dir, query, mode)
        except Exception as e:
            error = str(e)
            logger.warning(
                "RAG grounding evaluation query failed for %s in %s: %s",
                candidate.filename,
                working_dir,
                e,
            )
            break
        if any(_source_matches_filename(source, candidate.filename) for source in sources):
            break

    matched_sources = [
        source["source"]["id"]
        for source in sources
        if isinstance(source, dict)
        and isinstance(source.get("source"), dict)
        and _source_matches_filename(source, candidate.filename)
    ]
    return {
        "filename": candidate.filename,
        "document_id": candidate.document_id,
        "source_type": candidate.source_type,
        "query": query,
        "status": "passed" if matched_sources else "failed",
        "attempt": attempt,
        "modes_tried": modes_tried,
        "matched_source_ids": matched_sources,
        "returned_source_ids": [
            source["source"]["id"]
            for source in sources
            if isinstance(source, dict) and isinstance(source.get("source"), dict)
        ],
        "error": error,
    }


async def evaluate_rag_grounding(
    db: Session,
    confab: Confab,
    working_dir: str,
    max_wait_seconds: float | None = None,
    retry_interval_seconds: float | None = None,
) -> dict:
    candidates, skipped = _deployed_rag_candidates(db, confab)
    tests_by_key: dict[tuple[str, int | None, str], dict] = {}
    max_wait = RAG_EVALUATION_WAIT_SECONDS if max_wait_seconds is None else max_wait_seconds
    retry_interval = (
        RAG_EVALUATION_RETRY_INTERVAL_SECONDS
        if retry_interval_seconds is None
        else retry_interval_seconds
    )
    deadline = time.monotonic() + max_wait
    attempt = 0

    try:
        async with aiohttp.ClientSession() as session:
            while True:
                attempt += 1
                pending = [
                    candidate
                    for candidate in candidates
                    if tests_by_key.get(
                        (candidate.filename, candidate.document_id, candidate.source_type),
                        {},
                    ).get("status")
                    != "passed"
                ]
                if not pending:
                    break

                for candidate in pending:
                    key = (candidate.filename, candidate.document_id, candidate.source_type)
                    tests_by_key[key] = await _evaluate_candidate(session, candidate, working_dir, attempt)

                if all(test["status"] == "passed" for test in tests_by_key.values()):
                    break
                if time.monotonic() >= deadline:
                    break
                await asyncio.sleep(min(retry_interval, max(0, deadline - time.monotonic())))
    except Exception as e:
        logger.warning("RAG grounding evaluation failed for workspace %s: %s", working_dir, e)
        tests = list(tests_by_key.values())
        return {
            "status": "failed",
            "workspace": working_dir,
            "total_documents": len(candidates),
            "passed": 0,
            "failed": len(candidates),
            "skipped": len(skipped),
            "tests": tests,
            "skipped_documents": skipped,
            "errors": [str(e)],
        }

    tests = list(tests_by_key.values())
    passed = sum(1 for test in tests if test["status"] == "passed")
    failed = sum(1 for test in tests if test["status"] == "failed")
    status = "passed" if failed == 0 else "failed"
    if not tests and skipped:
        status = "skipped"

    return {
        "status": status,
        "workspace": working_dir,
        "total_documents": len(candidates),
        "passed": passed,
        "failed": failed,
        "skipped": len(skipped),
        "attempts": attempt,
        "tests": tests,
        "skipped_documents": skipped,
        "errors": [],
    }
