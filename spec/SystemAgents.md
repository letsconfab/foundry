# System Agents

## Overview

System agents are built-in AI assistants that perform specialized platform functions. Unlike user-created confabs, system agents are pre-configured and always available.

---

## Foreman

The Foreman is the lead orchestrator for confab creation. It guides users through a structured 7-step process to configure their AI agents.

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
- **Step-by-step guidance** — Walks users through 7 sequential steps to configure a confab.
- **Progress persistence** — Tracks completed steps in `confab.setup_progress` so users can resume later.
- **Tool integration** — Uses internal tools to save configuration incrementally to the database.
- **Context awareness** — Loads full confab state, thread history, and progress before each response.

### Initial Greeting

When starting a new confab build:

> "Welcome to the Agent Foundry. I am the Foreman, and will walk you through the creation of this confab (Collaborative Agent).
>
> I'll guide you through a simple 7-step process to configure your agent:
> 1. **Define purpose** — What should your agent do?
> 2. **Add participants** — Who can access it?
> 3. **Configure memory** — Should it remember conversations?
> 4. **Set up tools** — What external capabilities does it need?
> 5. **Establish guardrails** — What are its safety boundaries?
> 6. **Sample I/O** — Provide example interactions
> 7. **Review** — Finalize your configuration
>
> Let's start with the most important part: **What would you like this agent to do?** Describe its main purpose and objectives."

### The 7 Steps

| Step | Stage Key | Description | Tool |
|------|-----------|-------------|------|
| 1 | `purpose` | What should the agent do? | `define_purpose` |
| 2 | `participants` | Who can access it? | `add_participant` |
| 3 | `memory` | Should it remember conversations? | `configure_memory` |
| 4 | `tools` | What external capabilities does it need? | `add_tools_and_apis` |
| 5 | `guardrails` | What are its safety boundaries? | `guardrails` |
| 6 | `sample_io` | Provide example interactions | `sample_io` |
| 7 | `review` | Finalize configuration | `review_and_save` |

### Tools Available

| Tool | Purpose | Marks Step Complete |
|------|---------|---------------------|
| `define_purpose` | Save purpose text to confab | Step 1 |
| `add_participant` | Add email to participant list | Step 2 |
| `configure_memory` | Toggle memory settings | Step 3 |
| `add_tools_and_apis` | Record external API configuration | Step 4 |
| `guardrails` | Write guardrail rules | Step 5 |
| `sample_io` | Save example input/output scenarios | Step 6 |
| `review_and_save` | Finalize confab, set status to `draft` | Step 7 |
| `update_purpose` | Modify existing purpose | (No step) |

### Progress Tracking

Progress is stored in `confab.setup_progress`:

```json
{
  "completed_steps": [1, 2],
  "current_stage": "memory"
}
```

**Stage values:** `purpose`, `participants`, `memory`, `tools`, `guardrails`, `sample_io`, `review`

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
| `api/foreman.py` | Main Foreman class with message processing |
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
