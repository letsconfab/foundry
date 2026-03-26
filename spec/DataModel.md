# Data Model

## Overview

The system persists core entities for user management, confab configuration, and threaded conversations. A relational database (PostgreSQL) is used for storage, with schema migrations managed by Alembic.

---

## Entities

### User

Represents a registered platform user.

| Attribute | Type | Required | Unique | Notes |
|-----------|------|----------|--------|-------|
| id | integer | auto | yes | Primary identifier |
| name | string | yes | no | Display name |
| email | string | yes | yes | Must be a valid email, indexed for lookup |
| password_hash | string | yes | no | Hashed password (never stored in plain text) |
| country | string | yes | no | |
| timezone | string | yes | no | |
| created_at | timestamp | auto | no | Set on creation |
| updated_at | timestamp | auto | no | Set on every update |

### GitHub Account

Represents a linked GitHub identity. Each user may have at most one.

| Attribute | Type | Required | Unique | Notes |
|-----------|------|----------|--------|-------|
| id | integer | auto | yes | Primary identifier |
| user_id | integer | yes | yes | References User. Unique constraint enforces one-to-one. |
| github_id | integer | yes | no | GitHub's numeric user ID |
| github_username | string | yes | no | GitHub login handle |
| access_token | string | yes | no | GitHub OAuth token |
| selected_org | string | no | no | Optional GitHub organization |
| selected_repo | string | yes | no | Repository name for storing confabs |
| created_at | timestamp | auto | no | Set on creation |
| updated_at | timestamp | auto | no | Set on every update |

### Confab

Represents a single AI agent configuration owned by a user.

| Attribute | Type | Required | Unique | Notes |
|-----------|------|----------|--------|-------|
| id | integer | auto | yes | Primary identifier |
| name | string | yes | no | Confab display name |
| description | text | no | no | Free-form description |
| version | string | yes | no | Defaults to `"1.0.0"`. Incremented by 0.1 on each update. |
| status | string | yes | no | One of: `building`, `draft`, `published`, `archived`. Defaults to `building`. |
| config | JSON | no | no | Stores the full or simple confab configuration (see Features.md) |
| setup_progress | JSON | no | no | Foreman setup state: `{"completed_steps": [1,2], "current_stage": "memory"}` |
| purpose | text | no | no | PURPOSE.md content (denormalized for quick access) |
| guardrails | JSON | no | no | Structured list of guardrail rules |
| tests | JSON | no | no | Structured test scenarios |
| model_provider | string | no | no | LLM provider. Defaults to `"groq"` |
| model_name | string | no | no | Model identifier. Defaults to `"qwen/qwen3-32b"` |
| temperature | float | yes | no | LLM temperature. Defaults to `0.7` |
| oasf_schema_version | string | yes | no | OASF schema version. Defaults to `"1.0.0"` |
| skills | JSON | no | no | List of OASF skill IDs |
| domains | JSON | no | no | List of domain strings |
| oasf_yaml | text | no | no | Cached full OASF export |
| github_url | string | no | no | URL to the GitHub pull request, if synced |
| github_path | string | no | no | Folder name in GitHub repo |
| github_synced_at | timestamp | no | no | When last synced to GitHub |
| github_sync_version | string | no | no | Version that was synced |
| user_id | integer | yes | no | References User |
| created_at | timestamp | auto | no | Set on creation |
| updated_at | timestamp | auto | no | Set on every update |

### Thread

Represents a conversation container with multiple participants.

| Attribute | Type | Required | Unique | Notes |
|-----------|------|----------|--------|-------|
| id | integer | auto | yes | Primary identifier |
| name | string | yes | no | Thread display name |
| owner_user_id | integer | yes | no | References User (denormalized for quick lookup) |
| created_at | timestamp | auto | no | Set on creation |

### ThreadParticipant

Links participants (users, confabs, or system agents) to threads. Supports polymorphic participant references.

| Attribute | Type | Required | Unique | Notes |
|-----------|------|----------|--------|-------|
| id | integer | auto | yes | Primary identifier |
| thread_id | integer | yes | no | References Thread |
| participant_type | string | yes | no | One of: `user`, `confab`, `system` |
| participant_id | integer | no | no | References User or Confab; NULL for system agents |
| system_agent_name | string | no | no | e.g., `"foreman"`; only if type is `system` |
| role | string | yes | no | One of: `owner`, `participant`, `observer`. Defaults to `participant`. |
| is_active | boolean | yes | no | Defaults to `true`; set to `false` on leave |
| joined_at | timestamp | auto | no | Set on creation |
| left_at | timestamp | no | no | Set when participant leaves |

### Message

Individual message in a thread with sender info and threading support.

| Attribute | Type | Required | Unique | Notes |
|-----------|------|----------|--------|-------|
| id | integer | auto | yes | Primary identifier |
| thread_id | integer | yes | no | References Thread |
| sender_type | string | yes | no | One of: `user`, `confab`, `system` |
| sender_id | integer | no | no | User or Confab ID; NULL for system agents |
| sender_name | string | no | no | Cached display name |
| content | text | yes | no | Message text |
| role | string | yes | no | One of: `user`, `assistant` (for LLM context) |
| in_reply_to | integer | no | no | References parent Message; NULL = main thread |
| depth | integer | yes | no | 0 = main thread, 1+ = subthread depth |
| addressed_to | JSON | no | no | Explicit recipients: `[{"type": "confab", "id": 5}]`; NULL = broadcast |
| created_at | timestamp | auto | no | Set on creation |

### ConfabLearning

Knowledge learned during confab operation, synced to GitHub.

| Attribute | Type | Required | Unique | Notes |
|-----------|------|----------|--------|-------|
| id | integer | auto | yes | Primary identifier |
| confab_id | integer | yes | no | References Confab |
| content | text | yes | no | Learning content |
| summary | string(500) | no | no | One-line summary |
| tags | JSON | no | no | List of tag strings |
| status | string | yes | no | One of: `draft`, `approved`. Defaults to `draft`. |
| author_type | string | yes | no | One of: `user`, `confab`, `system` |
| author_id | integer | no | no | User or Confab ID |
| source | string | yes | no | One of: `conversation`, `manual`, `import` |
| source_thread_id | integer | no | no | References Thread |
| github_filename | string | no | no | e.g., `"learning-001.md"` |
| github_synced_at | timestamp | no | no | When last synced |
| created_at | timestamp | auto | no | Set on creation |

### ConfabDocument

Document uploaded to a confab's document store for RAG retrieval. Stored locally (not synced to GitHub).

| Attribute | Type | Required | Unique | Notes |
|-----------|------|----------|--------|-------|
| id | integer | auto | yes | Primary identifier |
| confab_id | integer | yes | no | References Confab |
| filename | string(500) | yes | no | Original filename |
| content_type | string(100) | yes | no | MIME type: `text/plain`, `text/markdown`, `application/pdf` |
| source | string(50) | yes | no | One of: `upload`, `url`, `manual`. Defaults to `upload`. |
| source_url | string(2000) | no | no | URL if imported from web |
| content_hash | string(64) | yes | no | SHA-256 hash for deduplication |
| raw_content | text | no | no | Full content for text/markdown |
| file_path | string(500) | no | no | Path to PDF file on disk |
| chunk_count | integer | yes | no | Number of chunks generated |
| status | string(20) | yes | no | One of: `pending`, `indexed`, `failed`. Defaults to `pending`. |
| error_message | text | no | no | Error details if status is `failed` |
| metadata_json | JSON | no | no | Custom metadata (author, date, tags) |
| created_at | timestamp | auto | no | Set on creation |
| updated_at | timestamp | auto | no | Set on update |

### DocumentChunk

Individual chunk of a document with reference to vector embedding in ChromaDB.

| Attribute | Type | Required | Unique | Notes |
|-----------|------|----------|--------|-------|
| id | integer | auto | yes | Primary identifier |
| document_id | integer | yes | no | References ConfabDocument |
| chunk_index | integer | yes | no | Position in document (0-indexed) |
| content | text | yes | no | Chunk text content |
| start_char | integer | no | no | Start position in original document |
| end_char | integer | no | no | End position in original document |
| vector_id | string(100) | yes | no | ID in ChromaDB collection |
| created_at | timestamp | auto | no | Set on creation |

---

## Relationships

```
User (1) ──── (0..1) GitHub Account
User (1) ──── (0..*)  Confab
User (1) ──── (0..*)  Thread (ownership)
Confab (1) ──── (0..*) ConfabLearning
Confab (1) ──── (0..*) ConfabDocument
ConfabDocument (1) ──── (0..*) DocumentChunk
Thread (1) ──── (0..*) ThreadParticipant
Thread (1) ──── (0..*) Message
Message (1) ──── (0..*) Message (replies)
```

- A user may optionally have one linked GitHub account.
- A user may own zero or more confabs.
- A user may own zero or more threads.
- A confab may have zero or more learnings.
- A thread has one or more participants (owner is always a participant).
- A message may be a reply to another message (self-referential).
- Deleting a user should cascade to their GitHub account, confabs, and owned threads.
- Deleting a thread should cascade to its participants and messages.
- Deleting a confab should cascade to its learnings.

---

## Confab Configuration Shapes

A confab's `config` field accepts one of two shapes:

### Full Configuration

| Section | Purpose |
|---------|---------|
| Capabilities | Which agent abilities are enabled (text generation, code generation, web search, etc.) |
| Model | LLM provider, model name, temperature, max tokens, sampling parameters |
| Knowledge Base | Optional: source type, indexing method, chunk settings |
| Conversation | System prompt, memory settings, context window, greeting/error messages |
| Security | Content filtering, domain allowlists, keyword blocklists, rate limiting |
| Integrations | External APIs, webhooks, databases, storage |
| Deployment | Environment, scaling, monitoring, logging level |
| Custom Settings | Arbitrary key-value pairs |

### Simple Configuration

A lightweight alternative with just: model provider, model name, system prompt, temperature, and max tokens.

---

## Constraints and Invariants

1. User email must be unique across the system.
2. Each user can have at most one GitHub account (enforced by unique constraint on user_id).
3. Confab version starts at `"1.0.0"` and increments by 0.1 on each update.
4. Confab status must be one of the allowed values: `building`, `draft`, `published`, `archived`.
5. Passwords must not exceed 72 bytes when UTF-8 encoded (bcrypt limit).
6. ThreadParticipant must have either `participant_id` (for user/confab) or `system_agent_name` (for system), but not both.
7. Message `in_reply_to` must reference a message in the same thread.
