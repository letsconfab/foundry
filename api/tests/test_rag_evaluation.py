import hashlib

import pytest
from sqlalchemy.orm import Session

from document_store_v2.compression import compress
from models import Confab, ConfabDocumentV2, DocumentVersion
from services import rag_evaluation


def _add_document(db: Session, confab: Confab, filename: str, content: bytes, status: str = "active"):
    doc = ConfabDocumentV2(
        confab_id=confab.id,
        filename=filename,
        original_content_type="text/plain",
        status=status,
    )
    db.add(doc)
    db.commit()
    blob = compress(content)
    db.add(
        DocumentVersion(
            document_id=doc.id,
            version_number=1,
            content_blob=blob,
            content_hash=hashlib.sha256(content).hexdigest(),
            original_size=len(content),
            compressed_size=len(blob),
        )
    )
    db.commit()
    return doc


def test_deployed_rag_candidates_cover_uploaded_and_synthetic_documents(db: Session, test_confab: Confab):
    active = _add_document(db, test_confab, "active.txt", b"Active document grounding text")
    _add_document(db, test_confab, "archived.txt", b"Archived text", status="archived")

    candidates, skipped = rag_evaluation._deployed_rag_candidates(db, test_confab)

    filenames = [candidate.filename for candidate in candidates]
    assert "active.txt" in filenames
    assert "archived.txt" not in filenames
    assert "PURPOSE.md" in filenames
    assert "GUARDRAILS.md" in filenames
    active_candidate = next(candidate for candidate in candidates if candidate.filename == "active.txt")
    assert active_candidate.document_id == active.id
    assert skipped == []


@pytest.mark.asyncio
async def test_evaluate_rag_grounding_passes_each_candidate(monkeypatch, db: Session, test_confab: Confab):
    candidates = [
        rag_evaluation.RagGroundingCandidate(filename="doc1.txt", content=b"short"),
        rag_evaluation.RagGroundingCandidate(filename="doc2.txt", content=b"short"),
    ]

    monkeypatch.setattr(rag_evaluation, "_deployed_rag_candidates", lambda _db, _confab: (candidates, []))

    async def fake_query_sources(_session, _working_dir, query, mode):
        if "doc1.txt" in query:
            return [{"source": {"id": "confabs/1/doc1.txt", "name": "doc1.txt", "type": "file"}, "metadata": []}]
        if "doc2.txt" in query and mode == "hybrid+":
            return [{"source": {"id": "confabs/1/doc2.txt", "name": "doc2.txt", "type": "file"}, "metadata": []}]
        return []

    monkeypatch.setattr(rag_evaluation, "_query_sources", fake_query_sources)

    result = await rag_evaluation.evaluate_rag_grounding(db, test_confab, "confabs/1", max_wait_seconds=0)

    assert result["status"] == "passed"
    assert result["total_documents"] == 2
    assert result["passed"] == 2
    assert result["failed"] == 0
    assert result["tests"][1]["modes_tried"] == ["naive", "hybrid+"]


@pytest.mark.asyncio
async def test_evaluate_rag_grounding_reports_missing_source(monkeypatch, db: Session, test_confab: Confab):
    candidates = [rag_evaluation.RagGroundingCandidate(filename="missing.txt", content=b"short")]
    monkeypatch.setattr(rag_evaluation, "_deployed_rag_candidates", lambda _db, _confab: (candidates, []))

    async def fake_query_sources(_session, _working_dir, _query, _mode):
        return [{"source": {"id": "confabs/1/other.txt", "name": "other.txt", "type": "file"}, "metadata": []}]

    monkeypatch.setattr(rag_evaluation, "_query_sources", fake_query_sources)

    result = await rag_evaluation.evaluate_rag_grounding(db, test_confab, "confabs/1", max_wait_seconds=0)

    assert result["status"] == "failed"
    assert result["passed"] == 0
    assert result["failed"] == 1
    assert result["tests"][0]["returned_source_ids"] == ["confabs/1/other.txt"]


@pytest.mark.asyncio
async def test_evaluate_rag_grounding_retries_until_source_is_searchable(monkeypatch, db: Session, test_confab: Confab):
    candidates = [rag_evaluation.RagGroundingCandidate(filename="delayed.txt", content=b"short")]
    calls = 0
    monkeypatch.setattr(rag_evaluation, "_deployed_rag_candidates", lambda _db, _confab: (candidates, []))

    async def fake_query_sources(_session, _working_dir, _query, _mode):
        nonlocal calls
        calls += 1
        if calls < 3:
            return []
        return [{"source": {"id": "confabs/1/delayed.txt", "name": "delayed.txt", "type": "file"}, "metadata": []}]

    monkeypatch.setattr(rag_evaluation, "_query_sources", fake_query_sources)

    result = await rag_evaluation.evaluate_rag_grounding(
        db,
        test_confab,
        "confabs/1",
        max_wait_seconds=1,
        retry_interval_seconds=0.01,
    )

    assert result["status"] == "passed"
    assert result["attempts"] == 2


def test_source_match_accepts_encoded_file_path():
    source = {
        "source": {
            "id": "confabs/3911/A%20Loving%20Organization%20Self-Assessment%20%28INTEGRATE%20Framework%29.pdf",
            "name": "A Loving Organization Self-Assessment (INTEGRATE Framework).pdf",
            "type": "file",
        },
        "metadata": [],
    }

    assert rag_evaluation._source_matches_filename(
        source,
        "A Loving Organization Self-Assessment (INTEGRATE Framework).pdf",
    )
