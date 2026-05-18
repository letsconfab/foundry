"""Retrieve RAGAnything source documents for OpenWebUI source events."""

import html
import logging
import os
import posixpath
from typing import Any
from urllib.parse import unquote

import aiohttp

logger = logging.getLogger(__name__)

RAGANYTHING_URL = os.getenv("RAGANYTHING_URL", "http://localhost:8001").rstrip("/")

MAX_DISPLAYED_SOURCES = 10
MAX_CONTEXT_CHUNKS = 10
MAX_CHARS_PER_CHUNK = 2_000
MAX_TOTAL_CONTEXT_CHARS = 12_000


def normalize_file_path(file_path: str) -> str:
    raw = str(file_path or "").strip().replace("\\", "/")
    if not raw:
        return ""
    if "confabs/" in raw:
        raw = raw[raw.index("confabs/") :]
    return raw.lstrip("./")


def display_name_from_file_path(file_path: str) -> str:
    basename = posixpath.basename(normalize_file_path(file_path).rstrip("/"))
    if not basename:
        return "Unknown document"
    try:
        decoded = unquote(basename)
    except Exception:
        decoded = basename
    return decoded or "Unknown document"


def sources_from_chunks(chunks: list[dict]) -> list[dict]:
    sources = []
    seen: set[str] = set()
    for chunk in chunks:
        file_path = normalize_file_path(chunk.get("file_path") or "")
        if not file_path or file_path in seen:
            continue
        seen.add(file_path)
        display_name = display_name_from_file_path(file_path)
        sources.append(
            {
                "source": {
                    "id": file_path,
                    "name": display_name,
                    "type": "file",
                },
                "document": [""],
                "metadata": [
                    {
                        "source": file_path,
                        "name": display_name,
                    }
                ],
            }
        )
        if len(sources) >= MAX_DISPLAYED_SOURCES:
            break
    return sources


def _chunk_text(chunk: dict) -> str:
    for key in ("content", "text", "chunk", "document", "page_content"):
        value = chunk.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    metadata = chunk.get("metadata")
    if isinstance(metadata, dict):
        for key in ("content", "text", "chunk", "document", "page_content"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _context_from_chunks(chunks: list[dict]) -> str:
    parts = []
    total_chars = 0
    for index, chunk in enumerate(chunks[:MAX_CONTEXT_CHUNKS], 1):
        file_path = normalize_file_path(chunk.get("file_path") or "")
        text = _chunk_text(chunk)
        if not file_path or not text:
            continue
        display_name = display_name_from_file_path(file_path)
        text = text[:MAX_CHARS_PER_CHUNK]
        part = (
            f'<source id="{index}" name="{html.escape(display_name, quote=True)}" '
            f'resource-type="file" resource-id="{html.escape(file_path, quote=True)}">\n'
            f"{text.replace('</source>', '&lt;/source&gt;')}\n"
            "</source>"
        )
        if total_chars + len(part) > MAX_TOTAL_CONTEXT_CHARS:
            available = MAX_TOTAL_CONTEXT_CHARS - total_chars
            text_budget = available - (len(part) - len(text))
            if text_budget <= 0:
                break
            text = text[:text_budget]
            part = (
                f'<source id="{index}" name="{html.escape(display_name, quote=True)}" '
                f'resource-type="file" resource-id="{html.escape(file_path, quote=True)}">\n'
                f"{text.replace('</source>', '&lt;/source&gt;')}\n"
                "</source>"
            )
        parts.append(part)
        total_chars += len(part)
        if total_chars >= MAX_TOTAL_CONTEXT_CHARS:
            break
    return "\n\n".join(parts)


def _chunks_from_payload(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    for key in ("chunks", "results", "documents", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("chunks", "results", "documents", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    sources = payload.get("sources")
    if isinstance(sources, list):
        return [item for item in sources if isinstance(item, dict)]

    return []


async def _query_raganything(
    session: aiohttp.ClientSession,
    working_dir: str,
    query: str,
    mode: str,
) -> list[dict]:
    async with session.post(
        f"{RAGANYTHING_URL}/api/v1/query",
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
        return _chunks_from_payload(await resp.json())


async def retrieve_rag_sources(working_dir: str, query: str) -> tuple[list[dict], str]:
    if not working_dir or not query.strip():
        return [], ""

    try:
        async with aiohttp.ClientSession() as session:
            chunks = await _query_raganything(session, working_dir, query, "naive")
            if not chunks:
                chunks = await _query_raganything(session, working_dir, query, "hybrid+")
    except Exception as e:
        logger.warning("RAGAnything source retrieval failed for workspace %s: %s", working_dir, e)
        return [], ""

    if not chunks:
        return [], ""
    return sources_from_chunks(chunks), _context_from_chunks(chunks)
