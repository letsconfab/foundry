# Document Store

## Overview

PostgreSQL-native versioned document storage with compression. Each confab can store reference documents (PDFs, text files, office documents, images) with append-only version history and zstd compression.

Replaces V1 (ChromaDB-based RAG with embeddings and chunking), which was removed in migration `8538d84e49b6`.

---

## Architecture

### Storage

All document data lives in PostgreSQL — no external vector store or embedding service:

- **`confab_documents_v2`** — Document metadata, identity, and status
- **`document_versions`** — Immutable, append-only version records with compressed binary content

Content is stored as `LargeBinary` (`content_blob`) compressed with zstd. Each version includes a SHA-256 hash for deduplication checks.

### Compression

Uses the `zstandard` library (zstd) at compression level 3:

- All uploaded content is compressed before storage
- Decompressed on retrieval
- Compression ratio tracked per version (`original_size` / `compressed_size`)

### Encryption (Phase 2 — not yet active)

Schema includes fields for AES-256-GCM encryption (`encryption_key_id`, `encryption_iv`, `encryption_tag`) but these are nullable and unused in Phase 1.

---

## Supported Document Types

Validated via magic bytes (not file extension) using `python-magic`:

| Category | Types |
|----------|-------|
| Text | plain text, markdown, CSV |
| Structured | JSON, YAML, TOML |
| PDF | application/pdf |
| Office | DOCX, XLSX |
| Images | PNG, JPEG, GIF, WebP, TIFF (for future OCR) |

### Validation Rules

- **Max file size:** 50 MB
- **Empty files:** Rejected
- **MIME detection:** Magic bytes first, extension fallback for `text/plain`
- **Filename sanitization:** Path traversal prevention, unsafe character removal, unicode normalization (NFC), length truncation to 255 characters

---

## Versioning

Each document has an append-only history of `DocumentVersion` records:

- Versions are numbered sequentially (1, 2, 3, ...)
- Content is never modified after creation — new versions are appended
- Each version stores: compressed content blob, SHA-256 hash, original/compressed sizes
- Text extraction status tracked per version (`pending`, `completed`, `failed`)

---

## API Endpoints

9 endpoints replacing V1's 6:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/confabs/{id}/documents` | Upload document (JSON body with base64 content) |
| `GET` | `/confabs/{id}/documents` | List active documents |
| `GET` | `/confabs/{id}/documents/{doc_id}` | Get document metadata |
| `DELETE` | `/confabs/{id}/documents/{doc_id}` | Archive (soft delete) |
| `GET` | `/confabs/{id}/documents/{doc_id}/versions` | List all versions |
| `GET` | `/confabs/{id}/documents/{doc_id}/versions/latest` | Get latest version content |
| `GET` | `/confabs/{id}/documents/{doc_id}/versions/{num}` | Get specific version content |
| `POST` | `/confabs/{id}/documents/{doc_id}/versions` | Create new version |
| `GET` | `/documents/accepted-formats` | Get accepted formats and UI hints |

### Key Differences from V1

- Upload accepts JSON body with `content_base64` (not multipart/form-data)
- Delete is a soft-delete (archives the document, preserves data)
- Semantic search and stats endpoints removed (no vector store)
- Version management endpoints added

---

## Request/Response Schemas

### Upload Request

```json
{
  "filename": "report.pdf",
  "content_base64": "JVBERi0xLjQ...",
  "content_type": "application/pdf",
  "metadata": {"author": "Jane", "tags": ["quarterly"]}
}
```

### Document Response

```json
{
  "id": 1,
  "document_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "confab_id": 42,
  "filename": "report.pdf",
  "content_type": "application/pdf",
  "source": "upload",
  "status": "active",
  "version_count": 2,
  "latest_version": {
    "id": 3,
    "version_number": 2,
    "content_hash": "a1b2c3...",
    "original_size": 45000,
    "compressed_size": 12000,
    "compression_ratio": 0.267,
    "text_extraction_status": "pending",
    "created_at": "2026-04-07T12:00:00Z"
  },
  "created_at": "2026-04-06T10:00:00Z"
}
```

### Version Content Response

```json
{
  "document_id": 1,
  "document_uuid": "550e8400-...",
  "version_number": 2,
  "filename": "report.pdf",
  "content_type": "application/pdf",
  "content_base64": "JVBERi0xLjQ...",
  "original_size": 45000,
  "extracted_text": null
}
```

---

## Foreman Integration

Foreman V3 includes a **documents** stage (step 4 of 8) that integrates with the upload UI:

1. When Foreman reaches the documents stage, the responder sends `ui_hint: "show_upload_panel"` in the response metadata
2. The frontend's `DocumentUploadDialog` component auto-opens (drag-and-drop UI)
3. User uploads files via `POST /confabs/{id}/documents` (V2 API)
4. User says "done" or "skip" to continue to the next stage

The `DocumentStageHint` schema provides accepted formats and size limits to the frontend.

---

## Implementation Files

| File | Purpose |
|------|---------|
| `api/document_store_v2/__init__.py` | Package init and exports |
| `api/document_store_v2/service.py` | `DocumentServiceV2` class — upload, version, list, archive |
| `api/document_store_v2/schemas.py` | Pydantic request/response schemas |
| `api/document_store_v2/validation.py` | Upload validation, MIME detection, filename sanitization |
| `api/document_store_v2/compression.py` | zstd compress/decompress utilities |

---

## Migration from V1

V1 used ChromaDB vector collections, embedding providers (Sentence Transformers, Ollama, OpenAI), and chunking via LangChain's `RecursiveCharacterTextSplitter`. It was removed because:

- External vector store dependency (ChromaDB) added operational complexity
- Embedding model management was brittle (model switch required full reindex)
- The platform's current needs are document storage and versioning, not semantic search

V1 tables (`confab_documents`, `document_chunks`) were dropped in Alembic migration `8538d84e49b6`. V1 dependencies (chromadb, sentence-transformers, pypdf) were removed from `requirements.txt`.

Semantic search may be re-added in a future phase with a different approach.
