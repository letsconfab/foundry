# Document Store

## Overview

The Document Store provides confab-specific RAG (Retrieval-Augmented Generation) capabilities. Each confab has an isolated document collection for storing and semantically searching uploaded documents and approved learnings.

## Purpose

Enable confabs to:
- Store reference documents (PDFs, text, markdown)
- Perform semantic search across their knowledge base
- Retrieve relevant context for answering user queries
- Build up domain-specific knowledge over time

## Supported Document Types

| Type | MIME Type | Storage | Notes |
|------|-----------|---------|-------|
| Plain Text | `text/plain` | Database | Raw content stored in `raw_content` column |
| Markdown | `text/markdown` | Database | YAML frontmatter stripped before chunking |
| PDF | `application/pdf` | File system | Extracted text stored, original file in `data/uploads/` |

## Architecture

### Storage Layers

1. **PostgreSQL (metadata)**
   - `confab_documents` - Document records and status
   - `document_chunks` - Chunk content and vector references

2. **ChromaDB (vectors)**
   - Per-confab collections: `confab_{id}_documents`
   - Stores embeddings for semantic search
   - Includes both document chunks and approved learnings

3. **File System (PDFs)**
   - Location: `api/data/uploads/confab_{id}/`
   - Original PDF files for re-processing if needed

### Isolation Model

Each confab gets a dedicated ChromaDB collection. This ensures:
- Complete data isolation between confabs
- Independent deletion/clearing per confab
- No cross-contamination of search results

## Chunking Strategy

Documents are split using LangChain's `RecursiveCharacterTextSplitter`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `chunk_size` | 500 | Target chunk size in characters |
| `chunk_overlap` | 50 | Overlap between consecutive chunks |
| Separators | `\n\n`, `\n`, `. `, ` `, `` | Hierarchy of split points |

Position tracking (`start_char`, `end_char`) enables locating chunks in source documents.

## Embedding Providers

### Sentence Transformers (Default)

Local embedding with no API dependencies.

| Model | Dimensions | Use Case |
|-------|------------|----------|
| `all-MiniLM-L6-v2` | 384 | Fast, general-purpose (default) |
| `all-mpnet-base-v2` | 768 | Higher quality, slower |

### Ollama

Local embedding via Ollama server.

| Model | Dimensions |
|-------|------------|
| `nomic-embed-text` | 768 |
| `mxbai-embed-large` | 1024 |

Requires `OLLAMA_BASE_URL` environment variable.

### OpenAI

External embedding via OpenAI API.

| Model | Dimensions |
|-------|------------|
| `text-embedding-3-small` | 1536 |
| `text-embedding-3-large` | 3072 |

Requires `OPENAI_API_KEY` environment variable.

## Configuration

### Environment Variables

```bash
DOCUMENT_STORE_ENABLED=true
CHROMADB_PERSIST_DIR=./data/chromadb
UPLOAD_DIR=./data/uploads
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHUNK_SIZE=500
CHUNK_OVERLAP=50
```

### Per-Confab Configuration

Stored in `Confab.config` JSON field:

```json
{
  "document_store": {
    "enabled": true,
    "embedding_provider": "sentence_transformers",
    "embedding_model": "all-MiniLM-L6-v2"
  }
}
```

## MCP Tools

Available to Foreman and deployed confabs:

| Tool | Description |
|------|-------------|
| `upload_document` | Upload and index a document |
| `list_documents` | List all documents in the store |
| `delete_document` | Remove a document |
| `search_documents` | Semantic search with top-k results |
| `get_context_for_query` | Get formatted RAG context |
| `reindex_documents` | Re-embed all documents |
| `sync_learnings` | Index approved learnings |
| `clear_document_store` | Delete all documents and vectors |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/confabs/{id}/documents` | Upload document (multipart) |
| GET | `/confabs/{id}/documents` | List documents |
| GET | `/confabs/{id}/documents/{doc_id}` | Get document details |
| DELETE | `/confabs/{id}/documents/{doc_id}` | Delete document |
| POST | `/confabs/{id}/documents/search` | Semantic search |
| GET | `/confabs/{id}/documents/stats` | Get store statistics |

## Learning Integration

Approved `ConfabLearning` records are automatically indexed:
- Stored in same ChromaDB collection as documents
- Metadata includes `type: "learning"` for filtering
- Indexed on approval status change
- Can be synced in bulk via `sync_learnings` tool

## Retrieval Flow

1. User query received
2. Generate query embedding
3. Search ChromaDB collection (documents + learnings)
4. Return top-k relevant chunks with scores
5. Optionally assemble into formatted context for LLM

## Limitations

- Maximum document size: 10 MB (configurable)
- PDF text extraction quality depends on document structure
- Embedding model switch requires full reindex
- No OCR for scanned PDFs (text-based extraction only)
