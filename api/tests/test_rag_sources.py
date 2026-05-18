import logging

import aiohttp
import pytest

from services import rag_sources


def test_display_name_url_decodes_basename():
    assert (
        rag_sources.display_name_from_file_path(
            "confabs/3911/A%20Loving%20Organization%20Self-Assessment%20%28INTEGRATE%20Framework%29.pdf"
        )
        == "A Loving Organization Self-Assessment (INTEGRATE Framework).pdf"
    )


def test_display_name_preserves_unicode():
    assert (
        rag_sources.display_name_from_file_path("confabs/3911/%E2%9D%A4%EF%B8%8F%20INTEGRATE.pdf")
        == "❤️ INTEGRATE.pdf"
    )


def test_sources_from_chunks_deduplicates_file_paths():
    chunks = [
        {"file_path": "confabs/3911/doc.pdf", "content": "one"},
        {"file_path": "confabs/3911/doc.pdf", "content": "two"},
        {"file_path": "confabs/3911/other.pdf", "content": "three"},
    ]

    sources = rag_sources.sources_from_chunks(chunks)

    assert [source["source"]["id"] for source in sources] == [
        "confabs/3911/doc.pdf",
        "confabs/3911/other.pdf",
    ]


@pytest.mark.asyncio
async def test_retrieve_rag_sources_empty_retrieval(monkeypatch):
    calls = []

    async def fake_query(_session, _working_dir, _query, mode):
        calls.append(mode)
        return []

    monkeypatch.setattr(rag_sources, "_query_raganything", fake_query)

    sources, context = await rag_sources.retrieve_rag_sources("confabs/3911", "missing")

    assert sources == []
    assert context == ""
    assert calls == ["naive", "hybrid+"]


@pytest.mark.asyncio
async def test_retrieve_rag_sources_fallback_mode(monkeypatch):
    calls = []

    async def fake_query(_session, _working_dir, _query, mode):
        calls.append(mode)
        if mode == "naive":
            return []
        return [{"file_path": "confabs/3911/doc.pdf", "content": "grounding text"}]

    monkeypatch.setattr(rag_sources, "_query_raganything", fake_query)

    sources, context = await rag_sources.retrieve_rag_sources("confabs/3911", "question")

    assert calls == ["naive", "hybrid+"]
    assert sources[0]["source"]["name"] == "doc.pdf"
    assert "<source" in context
    assert "grounding text" in context


@pytest.mark.asyncio
async def test_retrieve_rag_sources_failure_returns_empty(monkeypatch, caplog):
    async def fake_query(_session, _working_dir, _query, _mode):
        raise aiohttp.ClientError("offline")

    monkeypatch.setattr(rag_sources, "_query_raganything", fake_query)

    with caplog.at_level(logging.WARNING):
        sources, context = await rag_sources.retrieve_rag_sources("confabs/3911", "question")

    assert sources == []
    assert context == ""
    assert "RAGAnything source retrieval failed" in caplog.text
