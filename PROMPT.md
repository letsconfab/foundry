# Foundry April 9 Evolution — Ralph Loop Prompt

You are iteratively refactoring the Foundry repo on branch `foundry-april-9-evolution`. Each loop iteration, you pick up where you left off by reading git history, file state, and this prompt.

## How to Work

1. **At the start of each iteration**, run `git log --oneline -20` and check what's been done.
2. **Consult the phase tracker** below to find the next incomplete phase.
3. **Do one focused unit of work** per iteration — a single phase step or a meaningful chunk within a phase. Commit after each meaningful change with a clear message.
4. **Update the phase tracker** in this file after completing a phase (change `[ ]` to `[x]`).
5. **Run tests** after backend changes: `cd api && . .venv/bin/activate && python -m pytest tests/ -x -q 2>&1 | tail -30`
6. **Run type/lint checks** after frontend changes: `cd ui && npx tsc --noEmit 2>&1 | tail -30`
7. **Never break existing functionality.** If unsure, keep the old code path and add the new one alongside it.
8. **Commit early and often.** Small, focused commits. Use conventional-ish messages: `refactor: ...`, `feat: ...`, `fix: ...`, `docs: ...`.
9. **Bump versions on bugfixes**: patch version in `api/main.py` and/or `ui/package.json` as appropriate.

## Key Files Reference

- **Backend monolith**: `api/main.py` (1672 lines — needs splitting)
- **Legacy Foreman**: `api/foreman.py` (1424 lines — to be deprecated)
- **Foreman V3**: `api/foreman_v3/` (canonical orchestrator)
- **Models/Schemas**: `api/models.py`, `api/schemas.py`
- **Frontend chat**: `ui/src/components/AgentChat.tsx`, `ui/src/components/ConfabChat.tsx`
- **API client**: `ui/src/api/client.js`
- **Spec docs**: `spec/`
- **Tests**: `api/tests/`

## Phase Tracker

### Phase 1 — Freeze architecture and define contracts `[x]`
- [x] Create `spec/ConversationArchitecture.md` with conversation modes, ownership boundaries, request/response contracts
- [x] Define interfaces: `ConversationService`, `ConversationRouter`, `ConversationBootstrapper`, `AgentOrchestrator`
- [x] Define conversation modes: `foreman_build`, `confab_runtime`, reserve `multi_agent_workspace`
- [x] Document source-of-truth policy (LangGraph checkpoint = execution state, `confab.setup_progress` = UI summary snapshot)

### Phase 2 — Introduce ConversationService on the backend `[x]`
- [x] Create `api/services/__init__.py` and `api/services/conversation_service.py`
- [x] Implement: start foreman conversation (create confab, thread, participants, seed message)
- [x] Implement: resume foreman conversation
- [x] Implement: start runtime conversation for published confab
- [x] Implement: persist messages, route to orchestrator, return unified ChatResponse
- [x] Add helpers: `create_thread_for_confab_build`, `attach_foreman_participant`, `attach_confab_participant`, `persist_message`, `infer_conversation_mode`

### Phase 3 — Make foreman_v3 canonical `[x]`
- [x] Promote `api/foreman_v3/` as the only production Foreman runtime
- [x] Convert `api/foreman.py` to thin compatibility shim or deprecated wrapper
- [x] Remove legacy V1 production path from `main.py`
- [x] Simplify feature flags

### Phase 4 — Split main.py into routers `[x]`
- [x] Create `api/routes/auth_routes.py`
- [x] Create `api/routes/confab_routes.py`
- [x] Create `api/routes/conversation_routes.py`
- [x] Create `api/routes/github_sync_routes.py`
- [x] Create `api/routes/learning_routes.py`
- [x] Create `api/routes/document_routes.py`
- [x] Slim `main.py` to app creation, middleware, router registration, startup wiring

### Phase 5 — Introduce high-level conversation endpoints `[x]`
- [x] `POST /conversations/foreman/start`
- [x] `POST /conversations/foreman/{confab_id}/resume`
- [x] `POST /conversations/runtime/{confab_id}/start`
- [x] `POST /conversations/{thread_id}/messages`
- [x] Keep legacy `/threads/*` endpoints for backward compatibility

### Phase 6 — Refactor frontend to use high-level conversation APIs `[x]`
- [x] Add conversation methods to `ui/src/api/client.js`
- [x] Refactor `AgentChat.tsx` — remove manual thread/participant/message creation
- [x] Refactor `ConfabChat.tsx` — use `startRuntimeConversation`
- [x] Keep raw thread/message APIs for review/admin tooling only

### Phase 7 — Normalize progress/state synchronization `[x]`
- [x] Add adapter to sync LangGraph graph state to `confab.setup_progress`
- [x] Ensure `setup_progress` writes go through a single mapping function
- [x] Ensure resume flows use this mapping consistently

### Phase 8 — Clarify participant semantics and routing `[x]`
- [x] Add helper utilities for membership, addressing, routing, permissions
- [x] Add explicit conversation mode field (not just participant presence)
- [x] Document participant semantics

### Phase 9 — Prepare external chat/collaboration provider seam `[ ]`
- [ ] Define interfaces: `ConversationStore`, `MessagePublisher`, `ParticipantDirectory`
- [ ] Current Postgres model = default implementation
- [ ] No external provider integration yet — just the seam

### Phase 10 — Testing and migration hardening `[ ]`
- [ ] Tests for starting/resuming foreman conversations
- [ ] Tests for runtime confab conversations
- [ ] Tests for participant bootstrap correctness
- [ ] Tests for setup_progress synchronization
- [ ] Tests for backward compatibility with current chat payload shape

### Phase 11 — UI/UX Polish and Dark Mode `[ ]`
- [ ] Add dark mode support: configure Tailwind `darkMode: 'class'`, add theme toggle component
- [ ] Create a `ThemeProvider` context with localStorage persistence
- [ ] Audit all page components for dark mode compatibility (backgrounds, text, borders, shadows)
- [ ] Polish `AgentChat.tsx` — improve message bubbles, loading states, scroll behavior, input UX
- [ ] Polish `ConfabChat.tsx` — consistent styling with AgentChat
- [ ] Polish `AgentDashboard.tsx` — card layouts, empty states, responsive grid
- [ ] Polish `Header.tsx` — add theme toggle, improve nav responsiveness
- [ ] Polish `Footer.tsx` — dark mode compatible
- [ ] Polish `DocumentUploadDialog.tsx` — drag-and-drop visual feedback, progress indicators
- [ ] Polish `Login.tsx` and `Register.tsx` — form validation UX, consistent styling
- [ ] Polish `HeroSection.tsx` — responsive layout, dark mode hero
- [ ] Add subtle animations/transitions (page transitions, hover effects, loading skeletons)
- [ ] Ensure all Radix UI primitive components (`ui/src/components/ui/`) have proper dark: variants

## Completion

When ALL phases (1-11) are checked off and tests pass, output:

<promise>FOUNDRY EVOLUTION COMPLETE</promise>

If you finish an iteration but more work remains, just commit your progress and exit cleanly. You will be re-invoked with this same prompt.

## Important Rules

- **Do not modify this PROMPT.md** except to check off completed phases.
- **Read CLAUDE.md** for project conventions (ports, commands, structure).
- **Read spec/ docs** before making architectural decisions.
- **Keep backward compatibility** — never remove an endpoint without a replacement in place.
- **Small commits** — one logical change per commit.
- **Test after every backend change.**
