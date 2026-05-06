import asyncio
import hashlib

from sqlalchemy.orm import Session

from document_store_v2.compression import compress
from models import Confab, ConfabDocumentV2, ConfabLearning, DocumentVersion
from services import rag_sync


def _add_document(db: Session, confab: Confab, filename: str, content: bytes, status: str = "active", version: int = 1):
    doc = ConfabDocumentV2(
        confab_id=confab.id,
        filename=filename,
        original_content_type="text/plain",
        status=status,
    )
    db.add(doc)
    db.commit()
    blob = compress(content) if content is not None else b"not-zstd"
    doc_version = DocumentVersion(
        document_id=doc.id,
        version_number=version,
        content_blob=blob,
        content_hash=hashlib.sha256(content or b"bad").hexdigest(),
        original_size=len(content or b"bad"),
        compressed_size=len(blob),
    )
    db.add(doc_version)
    db.commit()
    return doc


def test_sync_uploads_active_latest_documents_and_synthetic_files(monkeypatch, db: Session, test_confab: Confab):
    test_confab.status = "published"
    test_confab.guardrails = [{"rule": "Never reveal secrets", "enabled": True}]
    test_confab.tests = [{"name": "Greeting", "input": "Hi", "expected_behavior": "Greet clearly"}]
    db.commit()
    active = _add_document(db, test_confab, "active.txt", b"old", version=1)
    db.add(DocumentVersion(
        document_id=active.id,
        version_number=2,
        content_blob=compress(b"latest"),
        content_hash=hashlib.sha256(b"latest").hexdigest(),
        original_size=6,
        compressed_size=len(compress(b"latest")),
    ))
    _add_document(db, test_confab, "archived.txt", b"skip", status="archived")
    db.add(ConfabLearning(
        confab_id=test_confab.id,
        content="Approved fact",
        summary="Approved",
        tags=["fact"],
        status="approved",
        author_type="user",
        source="manual",
    ))
    db.add(ConfabLearning(
        confab_id=test_confab.id,
        content="Draft fact",
        status="draft",
        author_type="user",
        source="manual",
    ))
    db.commit()

    uploads = []
    indexes = []

    async def fake_upload(_session, prefix, filename, content, content_type):
        uploads.append((prefix, filename, content, content_type))

    async def fake_index(_session, endpoint, workspace):
        indexes.append((endpoint, workspace))
        return True

    class FakeSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(rag_sync.aiohttp, "ClientSession", lambda: FakeSession())
    monkeypatch.setattr(rag_sync, "_upload_file", fake_upload)
    monkeypatch.setattr(rag_sync, "_index_folder", fake_index)

    result = asyncio.run(rag_sync.sync_documents_to_raganything(db, test_confab))

    filenames = [item[1] for item in uploads]
    contents = {filename: content for _, filename, content, _ in uploads}
    assert result["workspace"] == f"confabs/{test_confab.id}"
    assert result["uploaded"] == 6
    assert result["indexed"] is True
    assert result["classical_indexed"] is True
    assert "active.txt" in filenames
    assert contents["active.txt"] == b"latest"
    assert "archived.txt" not in filenames
    assert "PURPOSE.md" in filenames
    assert "GUARDRAILS.md" in filenames
    assert "Approved fact" in contents["LEARNINGS.md"].decode("utf-8")
    assert "Draft fact" not in contents["LEARNINGS.md"].decode("utf-8")
    assert ("/api/v1/folder/index", f"confabs/{test_confab.id}") in indexes
    assert ("/api/v1/classical/folder/index", f"confabs/{test_confab.id}") in indexes


def test_sync_decompression_failure_is_partial(monkeypatch, db: Session, test_confab: Confab):
    _add_document(db, test_confab, "good.txt", b"good")
    bad = ConfabDocumentV2(
        confab_id=test_confab.id,
        filename="bad.txt",
        original_content_type="text/plain",
        status="active",
    )
    db.add(bad)
    db.commit()
    db.add(DocumentVersion(
        document_id=bad.id,
        version_number=1,
        content_blob=b"not-zstd",
        content_hash=hashlib.sha256(b"bad").hexdigest(),
        original_size=3,
        compressed_size=8,
    ))
    db.commit()

    uploads = []

    async def fake_upload(_session, prefix, filename, content, content_type):
        uploads.append(filename)

    async def fake_index(_session, endpoint, workspace):
        return True

    class FakeSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(rag_sync.aiohttp, "ClientSession", lambda: FakeSession())
    monkeypatch.setattr(rag_sync, "_upload_file", fake_upload)
    monkeypatch.setattr(rag_sync, "_index_folder", fake_index)

    result = asyncio.run(rag_sync.sync_documents_to_raganything(db, test_confab))

    assert "good.txt" in uploads
    assert "bad.txt" not in uploads
    assert any("bad.txt: decompression failed" in error for error in result["errors"])


def test_sync_returns_upload_and_index_errors(monkeypatch, db: Session, test_confab: Confab):
    _add_document(db, test_confab, "good.txt", b"good")

    async def fake_upload(_session, prefix, filename, content, content_type):
        if filename == "good.txt":
            raise RuntimeError("good.txt upload exploded")

    async def fake_index(_session, endpoint, workspace):
        if endpoint == "/api/v1/classical/folder/index":
            raise RuntimeError("classical failed")
        return True

    class FakeSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(rag_sync.aiohttp, "ClientSession", lambda: FakeSession())
    monkeypatch.setattr(rag_sync, "_upload_file", fake_upload)
    monkeypatch.setattr(rag_sync, "_index_folder", fake_index)

    result = asyncio.run(rag_sync.sync_documents_to_raganything(db, test_confab))

    assert result["indexed"] is True
    assert result["classical_indexed"] is False
    assert any("good.txt upload exploded" in error for error in result["errors"])
    assert any("classical failed" in error for error in result["errors"])
