# Foreman V3 — LangGraph Information Collector

## Status

- **Feature flag:** `FOREMAN_V3_ENABLED` (default: `false`)
- **Architecture:** LangGraph StateGraph (Information Collector pattern)
- **Frontend compatibility:** V2-compatible response format via `compat.py`
- **Predecessor:** Foreman V2 (monolithic handler-per-stage in `foreman.py`); see `ForemanV2.md`

When enabled, new confabs use V3; existing confabs continue with their original version.

---

## Architecture

V3 replaces V2's monolithic orchestrator with a LangGraph `StateGraph` composed of discrete nodes. The graph implements a **gather → verify → save → advance** loop:

```
START → ROUTER → [EXTRACTOR_*] → VALIDATOR → SAVER → ADVANCER → RESPONDER → END
                      ↑                                    │
                      └────────── (loop back) ─────────────┘
```

### 8-Stage Interview Order

| Step | Stage | Description |
|------|-------|-------------|
| 1 | `purpose` | What the agent does |
| 2 | `participants` | Who has access (emails) |
| 3 | `memory` | Conversation memory (yes/no/limited) |
| 4 | `documents` | Reference document uploads (new in V3) |
| 5 | `tools` | External tools and APIs |
| 6 | `guardrails` | Safety rules and restrictions |
| 7 | `sample_io` | Example interactions |
| 8 | `review` | Configuration summary and finalization |

V3 adds the **documents** stage (step 4) between memory and tools. V2 has 7 stages.

---

## State Schema

### ForemanState

The graph's TypedDict state flows through all nodes and accumulates collected information.

| Field | Type | Description |
|-------|------|-------------|
| `messages` | `Annotated[list, add_messages]` | Message history with LangGraph reducer |
| `collected_info` | `InformationSchema` | Accumulated data across stages |
| `current_stage` | string | Current position in interview |
| `completed_stages` | list[str] | Stages that have been completed |
| `confab_id` | int | Confab being configured |
| `thread_id` | int | Thread for conversation tracking |
| `is_complete` | bool | True when interview is finished |
| `stage_result` | `StageResultDict` | Result from current extractor |
| `is_update` | bool | True if updating a previous stage |
| `update_target` | string | Target stage for out-of-order update |
| `last_error` | string | Last error message |

### InformationSchema

| Field | Type | Stage |
|-------|------|-------|
| `purpose` | string | purpose |
| `name` | string | purpose (auto-extracted) |
| `participants` | list[str] | participants (email addresses) |
| `memory_type` | "yes" / "no" / "limited" | memory |
| `documents` | list[dict] | documents (uploaded metadata) |
| `documents_skipped` | bool | documents |
| `tools` | list[str] | tools (tool/API names) |
| `guardrails` | string | guardrails (markdown) |
| `sample_io` | string | sample_io (markdown) |

### StageResultDict

Returned by extractors to indicate outcome:

| Field | Values | Description |
|-------|--------|-------------|
| `status` | `complete`, `clarify`, `skip`, `error` | Extraction result |
| `data` | dict | Extracted/saved data |
| `summary` | string | What was saved (for acknowledgment) |
| `next_question` | string | What to ask next (for clarify) |
| `error_message` | string | Error details |

---

## Graph Nodes

### Router (`nodes/router.py`)

Entry point for every user message. Determines routing based on:

1. **Skip intent** — Detects phrases like "skip", "next", "only me", "just me", "none", etc. Sets `stage_result.status = "skip"` and routes to `validator_skip`.
2. **Update intent** — Matches `UPDATE_PATTERNS` (update/change/modify/edit/revise/fix/add to) combined with `STAGE_KEYWORDS` to detect out-of-order updates to completed stages. Sets `is_update = True` and `update_target` to the target stage.
3. **Normal flow** — Routes to the current stage's extractor.

### Extractors (`nodes/extractors.py`)

Eight extractor nodes, one per stage. Each wraps V2's extraction functions from `llm_service.py` (low-temperature structured JSON extraction). Each returns a `StageResultDict` with status and extracted data.

| Node | Function | Description |
|------|----------|-------------|
| `extract_purpose_node` | `extract_purpose()` | Extracts purpose text and agent name |
| `extract_participants_node` | `extract_participants()` | Extracts email addresses |
| `extract_memory_node` | `extract_memory_preference()` | Extracts yes/no/limited |
| `extract_documents_node` | `extract_documents_intent()` | Detects upload/skip intent |
| `extract_tools_node` | `extract_tools()` | Extracts tool/API names |
| `extract_guardrails_node` | `extract_guardrails()` | Extracts safety rules |
| `extract_sample_io_node` | `extract_sample_io()` | Extracts example interactions |
| `extract_review_node` | — | Shows config summary, handles save/edit |

### Validator (`nodes/validator.py`)

Validates `stage_result` presence and routes based on status:

- `complete` → **Saver** (persist data)
- `clarify` or `error` → **Responder** (ask for more info)
- `skip` → **Advancer** (skip to next stage)

### Saver (`nodes/saver.py`)

Persists data using V2's tool functions from `agent_tools.py`: `define_purpose`, `set_confab_name`, `add_participant`, `configure_memory`, `add_tools_and_apis`, `guardrails`, `sample_io`, `review_and_save`. Gets the DB session from `config["configurable"]["db"]`.

### Advancer (`nodes/advancer.py`)

Advances `current_stage` to the next stage in `STAGE_ORDER`, appends the completed stage to `completed_stages`, and persists progress to `confab.setup_progress` via direct DB write with `flag_modified` (fixes the SQLAlchemy session caching bug from V2).

### Responder (`nodes/responder.py`)

Generates the `AIMessage` response using templated prompts:

- **`STAGE_QUESTIONS`** — Primary question per stage
- **`STAGE_CLARIFICATIONS`** — Follow-up when more info needed
- **`STAGE_ACKNOWLEDGMENTS`** — Short confirmation ("Recorded the purpose.", "Memory settings configured.", etc.)

Voice rules: one question per turn, no exuberant praise, concise declarative tone.

For the **documents** stage, the responder includes `ui_hint: "show_upload_panel"` in `stage_result`, which triggers the `DocumentUploadDialog` component in the frontend.

For the **review** stage, `_build_config_summary()` generates a formatted summary of all collected info.

---

## Orchestrator (`orchestrator.py`)

The `ForemanV3` class provides the same interface as V2's `Foreman` for easy integration.

### `process_message()` Flow

1. **Build state** — `_build_state()` loads `confab.setup_progress` from DB (with `db.refresh()` to avoid stale cache), reconstructs `collected_info` from ORM fields, converts thread history via `orm_to_langgraph()`, appends the new `HumanMessage`.
2. **Invoke graph** — Calls `graph.ainvoke(state, config)` with the DB session in config.
3. **Format response** — `format_v3_response(result, thread_id)` converts graph state to V2-compatible dict.

---

## Compatibility Layer (`compat.py`)

`format_v3_response()` converts V3 graph state to the exact V2 response shape that the frontend depends on:

```python
{
    "response": "...",           # Last AIMessage content
    "confab_id": 123,
    "thread_id": 456,
    "is_resume": False,
    "setup_progress": {
        "completed_steps": [1, 2, 3],
        "current_stage": "documents",
        "total_steps": 8,
        "remaining_steps": [4, 5, 6, 7, 8],
    },
    "tool_calls": [],
    "timestamp": "...",
    "v2_metadata": {
        "stage": "documents",
        "stage_status": "complete",
        "is_update": False,
        "updated_stage": None,
        "saved_fields": {...},
        "next_question": None,
        "ui_hint": "show_upload_panel",  # Triggers DocumentUploadDialog
    },
    "is_v2": False,
    "is_v3": True,
    "is_langgraph": True,
}
```

Frontend dependencies:
- `response.foreman_metadata.setup_progress.current_stage`
- `response.foreman_metadata.v2_metadata.stage_status`
- `response.foreman_metadata.v2_metadata.saved_fields`
- `response.foreman_metadata.v2_metadata.ui_hint`

---

## Adapters (`adapters.py`)

Bridges between V2's Message ORM objects and LangGraph's message types:

- `orm_to_langgraph()` — Converts `Message` ORM objects to `HumanMessage`/`AIMessage`
- `langgraph_to_context()` — Converts LangGraph messages to V2-style context string for extraction functions
- `get_last_user_message()` — Extracts the last `HumanMessage` content

---

## Checkpointing (`checkpointer.py`)

Designed for PostgreSQL checkpointing via `langgraph-checkpoint-postgres` but currently disabled (falls back to DB-based approach). State persistence is handled by the **advancer node** which writes directly to `confab.setup_progress`.

Thread config format: `foreman-{confab_id}-{thread_id}`

---

## Differences from V2

| Aspect | V2 | V3 |
|--------|----|----|
| Architecture | Monolithic `foreman.py` with handler methods | LangGraph StateGraph with discrete nodes |
| Stages | 7 (no documents) | 8 (adds documents between memory and tools) |
| State | Dataclass | TypedDict with `add_messages` reducer |
| Feature flag | `FOREMAN_V2_ENABLED` | `FOREMAN_V3_ENABLED` |
| Checkpointing | DB-only | Designed for PostgreSQL checkpointer (currently DB fallback) |
| Code reuse | Self-contained | Reuses V2 extraction functions and tool functions |

---

## Implementation Files

| File | Purpose |
|------|---------|
| `api/foreman_v3/__init__.py` | Package init, `FOREMAN_V3_ENABLED` flag |
| `api/foreman_v3/state.py` | `ForemanState` TypedDict, `InformationSchema`, `STAGE_ORDER` |
| `api/foreman_v3/graph.py` | StateGraph construction, singleton pattern |
| `api/foreman_v3/orchestrator.py` | `ForemanV3` class, `process_message()` entry point |
| `api/foreman_v3/compat.py` | V2-compatible response formatting |
| `api/foreman_v3/adapters.py` | ORM ↔ LangGraph message conversion |
| `api/foreman_v3/checkpointer.py` | PostgreSQL checkpointer (disabled, DB fallback) |
| `api/foreman_v3/nodes/__init__.py` | Node exports |
| `api/foreman_v3/nodes/router.py` | Router node, skip/update detection |
| `api/foreman_v3/nodes/extractors.py` | 8 extractor nodes |
| `api/foreman_v3/nodes/validator.py` | Validation and routing |
| `api/foreman_v3/nodes/saver.py` | DB persistence via V2 tools |
| `api/foreman_v3/nodes/advancer.py` | Stage advancement and progress persistence |
| `api/foreman_v3/nodes/responder.py` | Response generation with templates and UI hints |
