# Conversation Architecture

## Status

- **Phase:** Defining contracts (Phase 1 of the Foundry April 9 Evolution)
- **Scope:** Covers conversation lifecycle, ownership boundaries, and request/response contracts

---

## Conversation Modes

Every conversation in Foundry operates in one of these modes:

| Mode | Description | Orchestrator | Entry Point |
|------|-------------|-------------|-------------|
| `foreman_build` | Build-time interview to create a confab. The Foreman agent walks the user through an 8-stage setup. | `ForemanV3` (LangGraph) | User starts a new confab or resumes a building one |
| `confab_runtime` | Chat with a published confab. The confab's purpose, guardrails, and context drive LLM responses. | Runtime LLM call (ad-hoc) | User opens chat with a published confab |
| `multi_agent_workspace` | _(Reserved)_ Multi-agent collaboration with multiple confabs and/or system agents in one thread. | TBD | TBD |

### Mode Inference

A conversation's mode is determined by its participants and their state:

1. If a `system` participant with `system_agent_name = "foreman"` is present **and** the linked confab has `status = "building"` → `foreman_build`
2. If a `confab` participant is present **and** the confab has `status = "published"` → `confab_runtime`
3. Otherwise → fall back to `confab_runtime` (default behavior)

**Goal:** Replace this inference-from-participants approach with an explicit `conversation_mode` field on the thread or an associated record (Phase 8).

---

## Ownership Boundaries

### Layer Diagram

```
┌─────────────────────────────────────────────┐
│  UI Layer                                   │
│  AgentChat.tsx, ConfabChat.tsx, client.js    │
│  Owns: rendering, local input state, UX     │
├─────────────────────────────────────────────┤
│  API Routers                                │
│  routes/conversation_routes.py, etc.        │
│  Owns: HTTP handling, auth, validation      │
├─────────────────────────────────────────────┤
│  ConversationService                        │
│  services/conversation_service.py           │
│  Owns: conversation lifecycle, bootstrap,   │
│        message persistence, routing         │
├─────────────────────────────────────────────┤
│  Agent Orchestrators                        │
│  ForemanV3, runtime LLM handler             │
│  Owns: domain logic, LLM calls, extraction  │
├─────────────────────────────────────────────┤
│  Persistence / Adapters                     │
│  models.py, database.py, checkpointer.py    │
│  Owns: DB schema, ORM, migrations           │
└─────────────────────────────────────────────┘
```

### What Each Layer Must NOT Do

| Layer | Must NOT |
|-------|----------|
| **UI** | Create threads, add participants, seed system messages, infer conversation mode |
| **API Routers** | Contain orchestration logic, directly call LLM services |
| **ConversationService** | Know about LLM prompts, extraction logic, or graph node internals |
| **Agent Orchestrators** | Create threads or manage participants (they receive context, return responses) |
| **Persistence** | Contain business logic beyond schema constraints |

---

## Interfaces / Protocols

### ConversationService

The central service that owns conversation lifecycle. All conversation operations flow through here.

```python
class ConversationService:
    """Owns conversation bootstrap, message routing, and persistence."""

    async def start_foreman_conversation(
        self, user_id: int, confab_id: int | None = None
    ) -> ConversationStartResponse:
        """
        Start a new foreman build conversation.
        - Creates confab if confab_id is None
        - Creates thread
        - Attaches foreman participant
        - Attaches confab participant
        - Seeds welcome message
        - Returns thread_id, confab_id, initial messages, mode
        """
        ...

    async def resume_foreman_conversation(
        self, user_id: int, confab_id: int
    ) -> ConversationStartResponse:
        """
        Resume an existing foreman build conversation.
        - Finds existing thread for the confab
        - Loads message history
        - Returns thread_id, confab_id, messages, current stage
        """
        ...

    async def start_runtime_conversation(
        self, user_id: int, confab_id: int
    ) -> ConversationStartResponse:
        """
        Start a chat with a published confab.
        - Creates thread
        - Attaches confab participant
        - Seeds system welcome message
        - Returns thread_id, confab_id, initial messages, mode
        """
        ...

    async def send_message(
        self, user_id: int, thread_id: int, content: str,
        addressed_to: list | None = None, in_reply_to: int | None = None
    ) -> ChatResponse:
        """
        Send a user message and get agent responses.
        - Persists user message
        - Infers conversation mode
        - Routes to correct orchestrator
        - Persists agent responses
        - Returns unified ChatResponse
        """
        ...

    def infer_conversation_mode(
        self, thread_id: int, db: Session
    ) -> str:
        """Returns 'foreman_build', 'confab_runtime', or 'multi_agent_workspace'."""
        ...
```

### ConversationRouter

Determines which orchestrator handles a message based on conversation mode.

```python
class ConversationRouter:
    """Routes messages to the correct orchestrator based on conversation mode."""

    async def route(
        self, mode: str, message: str, context: RoutingContext
    ) -> OrchestratorResponse:
        """
        Routes to:
        - ForemanV3 for foreman_build
        - Runtime LLM for confab_runtime
        - TBD for multi_agent_workspace
        """
        ...
```

### ConversationBootstrapper

Handles the mechanics of setting up a new conversation.

```python
class ConversationBootstrapper:
    """Creates threads, participants, and seed messages."""

    def create_thread_for_confab_build(
        self, user_id: int, confab_id: int, db: Session
    ) -> Thread:
        ...

    def attach_foreman_participant(
        self, thread_id: int, db: Session
    ) -> ThreadParticipant:
        ...

    def attach_confab_participant(
        self, thread_id: int, confab_id: int, db: Session
    ) -> ThreadParticipant:
        ...

    def seed_welcome_message(
        self, thread_id: int, content: str, sender_name: str, db: Session
    ) -> Message:
        ...
```

### AgentOrchestrator (Protocol)

Common interface for all agent orchestrators.

```python
from typing import Protocol

class AgentOrchestrator(Protocol):
    """Protocol for agent orchestrators (Foreman, runtime confab, future agents)."""

    async def initialize(self) -> None:
        """Load any required state."""
        ...

    async def process_message(
        self, content: str, *, thread_id: int, thread_history: list
    ) -> dict:
        """
        Process a user message and return a response dict.

        Returns:
            {
                "response": str,         # The agent's text response
                "metadata": dict | None, # Agent-specific metadata
            }
        """
        ...
```

---

## Request/Response Contracts

### ConversationStartResponse

Returned by `start_*` and `resume_*` methods:

```python
class ConversationStartResponse(BaseModel):
    thread_id: int
    confab_id: int | None
    conversation_mode: str                  # foreman_build | confab_runtime
    messages: list[MessageResponse]         # Pre-existing or seed messages
    participants: list[ParticipantResponse]  # Who's in the thread
    # Foreman-specific (present in foreman_build mode)
    setup_progress: SetupProgressResponse | None
    current_stage: str | None               # e.g., "purpose"
```

### ChatResponse (existing, unchanged)

The unified chat response remains the same:

```python
class ChatResponse(BaseModel):
    thread_id: int
    user_message: MessageResponse
    agent_responses: list[MessageResponse]
    timestamp: datetime
    foreman_metadata: ForemanChatResponse | None
```

No changes to `ChatResponse` shape — backward compatibility is preserved.

---

## Source-of-Truth Policy

| Data | Source of Truth | Notes |
|------|----------------|-------|
| **LangGraph execution state** | LangGraph checkpoint (when enabled) / graph invocation | Ephemeral within a graph run; not persisted between sessions yet |
| **Confab setup progress** | `confab.setup_progress` (JSON column) | Persisted UI summary snapshot. Written by the Advancer node after each stage completion. Used for resume flows. |
| **Collected confab data** | `confab.*` ORM fields (`purpose`, `guardrails`, `tests`, etc.) | Written by the Saver node. The actual persisted configuration. |
| **Conversation history** | `messages` table | All messages (user + agent) are persisted here. LangGraph rebuilds its message list from this on resume. |
| **Thread membership** | `thread_participants` table | Who is in the conversation. Currently also used to infer conversation mode (to be replaced by explicit mode field). |

### Key Invariant

`confab.setup_progress` is a **derived snapshot** of graph state, not the canonical execution state. The graph produces it; the UI consumes it. No code outside the Advancer/Saver nodes should write to `setup_progress` directly.

---

## Migration Path

### Current State (Pre-Refactor)

- UI (`AgentChat.tsx`) performs 5 API calls to bootstrap a conversation: create confab, create thread, add foreman participant, add confab participant, save welcome message
- `main.py` contains all route handlers including the 190-line `chat()` endpoint that inlines orchestration logic
- Both `Foreman` (V2) and `ForemanV3` are active, selected by feature flag
- Conversation mode is inferred implicitly from participant types

### Target State (Post-Refactor)

- UI calls a single `POST /conversations/foreman/start` endpoint
- `ConversationService` handles all bootstrap internally
- Route handlers are thin and delegate to the service
- `ForemanV3` is the only production orchestrator
- Conversation mode is explicit (inferred server-side, returned to client)

---

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Keep current DB schema | The schema is sound; the problem is in the orchestration layer, not the data model |
| Keep `ChatResponse` shape unchanged | Frontend depends on `foreman_metadata.v2_metadata.*` fields; changing shape is a Phase 6 concern |
| Use Python Protocol for `AgentOrchestrator` | Structural subtyping — `ForemanV3` and future orchestrators don't need to inherit from a base class |
| `ConversationService` as a plain class, not a FastAPI dependency | Easier to test; injected into route handlers via constructor or factory |
