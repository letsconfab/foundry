# Data Model

## Overview

The system persists three core entities: Users, GitHub Accounts, and Confabs. A relational database is used for storage, with schema migrations managed separately.

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
| status | string | yes | no | One of: `draft`, `published`, `archived`. Defaults to `draft`. |
| config | JSON | no | no | Stores the full or simple confab configuration (see Features.md) |
| github_url | string | no | no | URL to the GitHub pull request, if synced |
| user_id | integer | yes | no | References User |
| created_at | timestamp | auto | no | Set on creation |
| updated_at | timestamp | auto | no | Set on every update |

---

## Relationships

```
User (1) ──── (0..1) GitHub Account
User (1) ──── (0..*)  Confab
```

- A user may optionally have one linked GitHub account.
- A user may own zero or more confabs.
- Deleting a user should cascade to their GitHub account and confabs.

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
4. Confab status must be one of the allowed values: `draft`, `published`, `archived`.
5. Passwords must not exceed 72 bytes when UTF-8 encoded (bcrypt limit).
