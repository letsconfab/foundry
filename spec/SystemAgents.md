# System Agents

## Overview

System agents are built-in AI assistants that perform specialized platform functions. Unlike user-created confabs, system agents are pre-configured and always available.

---

## Foreman

The Foreman is the lead orchestrator for confab creation. It guides users through a structured interview process to configure their AI agents (7 steps in V2, 8 steps in V3).

### Identity

| Attribute | Value |
|-----------|-------|
| participant_type | `system` |
| system_agent_name | `foreman` |
| Display name | Foreman |
| UI Icon | HardHat (lucide-react) |
| UI Color | Amber/orange gradient (`from-amber-500 to-orange-600`) |

### Behavior

- **Directive conversation style** — Actively leads conversations rather than passively waiting. Every response ends with a clear question for the next step.
- **Step-by-step guidance** — Walks users through 7 (V2) or 8 (V3) sequential steps to configure a confab.
- **Progress persistence** — Tracks completed steps in `confab.setup_progress` so users can resume later.
- **Tool integration** — Uses internal tools to save configuration incrementally to the database.
- **Context awareness** — Loads full confab state, thread history, and progress before each response.
- **Out-of-order updates** — Users can update previous stages mid-flow (e.g., "Update the guardrails: ...").
- **Configuration review** — Displays full agent configuration at review stage or on request ("Show the configuration").

### V2 Deterministic Flow

When `FOREMAN_V2_ENABLED=true`, the Foreman uses a deterministic stage machine:

- **Stage handlers** — Each stage has a dedicated handler (`_handle_purpose`, `_handle_guardrails`, etc.)
- **Structured extraction** — Low-temperature LLM calls (0.1) return strict JSON
- **Save-gated progression** — Stage advances only after successful data persistence
- **Templated responses** — Consistent, concise voice via `STAGE_QUESTIONS` and `STAGE_ACKNOWLEDGMENTS`

See [ForemanV2.md](ForemanV2.md) for full architecture details.

### V3 LangGraph Flow

When `FOREMAN_V3_ENABLED=true`, the Foreman uses a LangGraph StateGraph with discrete nodes (Router → Extractors → Validator → Saver → Advancer → Responder). V3 adds a **documents** stage and produces V2-compatible responses via a compatibility layer.

See [ForemanV3.md](ForemanV3.md) for full architecture details.

### Initial Greeting (Interview Style)

When starting a new confab build, the Foreman uses an interview-style approach with examples at each step, rather than showing the full process upfront:

> "Hi, I'm the Foreman. I'll help you build your agent through a quick conversation.
>
> Let's start with the basics: **What should this agent do?**
>
> Here are some examples:
> - "A customer support bot that handles refund requests and tracks order status"
> - "An internal assistant that answers questions about company policies"
> - "A code reviewer that checks for security issues and suggests fixes"
>
> What's your agent's main job?"

Each subsequent stage also includes relevant examples to guide the user. See `STAGE_QUESTIONS` in `foreman.py` for the full set.

### The 8 Steps (V3) / 7 Steps (V2)

| Step | Stage Key | Description | Tool | V2 | V3 |
|------|-----------|-------------|------|----|----|
| 1 | `purpose` | What should the agent do? | `define_purpose` | yes | yes |
| 2 | `participants` | Who can access it? | `add_participant` | yes | yes |
| 3 | `memory` | Should it remember conversations? | `configure_memory` | yes | yes |
| 4 | `documents` | Upload reference documents | Document Store V2 API | — | yes |
| 5 | `tools` | What external capabilities does it need? | `add_tools_and_apis` | yes (step 4) | yes |
| 6 | `guardrails` | What are its safety boundaries? | `guardrails` | yes (step 5) | yes |
| 7 | `sample_io` | Provide example interactions | `sample_io` | yes (step 6) | yes |
| 8 | `review` | Finalize configuration | `review_and_save` | yes (step 7) | yes |

### Tools Available

**Setup Tools:**

| Tool | Purpose | Marks Step Complete |
|------|---------|---------------------|
| `define_purpose` | Save purpose text to confab | Step 1 |
| `add_participant` | Add email to participant list | Step 2 |
| `configure_memory` | Toggle memory settings | Step 3 |
| `add_tools_and_apis` | Record external API configuration | Step 5 (V3) / Step 4 (V2) |
| `guardrails` | Write guardrail rules | Step 6 (V3) / Step 5 (V2) |
| `sample_io` | Save example input/output scenarios | Step 7 (V3) / Step 6 (V2) |
| `review_and_save` | Finalize confab, set status to `draft` | Step 8 (V3) / Step 7 (V2) |
| `update_purpose` | Modify existing purpose | (No step) |

**Document Operations (V3 documents stage):**

Document uploads during confab building use the Document Store V2 REST API (`POST /confabs/{id}/documents`), not Foreman tools. The Foreman sends `ui_hint: "show_upload_panel"` to trigger the frontend's `DocumentUploadDialog` component. See `DocumentStore.md` for API details.

### Progress Tracking

Progress is stored in `confab.setup_progress`:

```json
{
  "completed_steps": [1, 2],
  "current_stage": "memory"
}
```

**Stage values (V2):** `purpose`, `participants`, `memory`, `tools`, `guardrails`, `sample_io`, `review`

**Stage values (V3):** `purpose`, `participants`, `memory`, `documents`, `tools`, `guardrails`, `sample_io`, `review`

### Resume Behavior

When a user returns to continue building a confab, the Foreman:

1. Loads the confab's current `setup_progress`
2. Checks thread history for the last message
3. Generates a contextual resume prompt:
   - If last message was assistant asking a question → reminds user of the pending question
   - If last message was user (no response) → offers to process it or start fresh
   - Otherwise → summarizes progress and suggests the next step

### Routing Logic

When a message is sent to `POST /threads/{id}/chat`:

1. Check if thread has a system participant with `system_agent_name='foreman'`
2. If yes, find the user's most recent confab with `status='building'`
3. Initialize Foreman with that confab's context
4. Process message and return response
5. Confabs in the thread do NOT respond while `status='building'`

### Implementation Files

| File | Purpose |
|------|---------|
| `api/foreman.py` | V2 Foreman class with message processing |
| `api/foreman_v3/` | V3 LangGraph implementation (see `ForemanV3.md`) |
| `api/context_loader.py` | Loads full context (confab, thread, progress, GitHub files) |
| `api/resume_generator.py` | Generates contextual resume prompts |
| `api/agent_tools.py` | Tool function implementations |
| `api/llm_service.py` | Groq API integration |

---

## Future System Agents

The following system agents are planned but not yet implemented:

### Moderator
- Facilitates multi-agent conversations
- Enforces turn-taking rules
- Resolves conflicts between confabs

### Reviewer
- Audits confab configurations for best practices
- Suggests improvements to guardrails
- Validates test scenarios

### Deployer
- Manages deployment workflows
- Monitors deployed confab health
- Handles scaling and rollback
