# Foundry UI/UX Ralph Loop Prompt

You are iteratively improving the Foundry repo on branch `foundry-april-9-evolution`. Each loop iteration, you pick up where you left off by reading git history, file state, and this prompt.

## Objective

The main objective is **UI/UX improvement across the product**, with all parts of the repo in scope. Do not limit work to the issues listed below, but use them as priority input.

## Priority Issues

### Foreman Chat Interview Flow
- [ ] Split foreman responses so the response to the previous turn is distinct from the call to action for the next step.
- [ ] Preserve the feeling that the Foreman is actively leading the interview.
- [ ] Add hints, affordances, and/or active CTA controls in the chat window to make progress easier.
- [ ] Evaluate whether step-specific actions such as file upload, suggestion chips, skip affordances, or guided input controls should appear inline in the Foreman flow.

### Broader UI/UX Improvement
- [ ] Audit the rest of the application for inconsistent UX, weak affordances, confusing state transitions, visual regressions, accessibility issues, and interaction friction.
- [ ] Improve any UX discovered during the audit, even if it was not explicitly listed up front.

## How to Work

1. **At the start of each iteration**, run `git log --oneline -20` and check what has already been done.
2. **Consult the phase tracker** below and take the next incomplete phase or the next meaningful chunk inside that phase.
3. **Do one focused unit of work per iteration**, but make multiple commits inside the iteration if that is the cleanest way to land the work.
4. **Update this prompt** as phases and priority issues are completed.
5. **Add tests as needed** for new behavior, especially where UX changes depend on backend contracts, orchestration behavior, or component logic.
6. **Prevent regressions**. Validate the changed area each iteration and run broader checks before declaring completion.
7. **Use good judgment** on architecture, tests, and commit granularity. No artificial constraints beyond preserving quality.
8. **If a UX issue is discovered during implementation**, you may add it to the relevant phase in this file before fixing it.

## Default Validation

Run the checks that match the changed area:

- **Backend changes**: `cd api && . .venv/bin/activate && python -m pytest tests/ -x -q 2>&1 | tail -30`
- **Frontend changes**: `cd ui && npx tsc --noEmit 2>&1 | tail -30`
- **UI pipeline / styling changes**: `cd ui && npm run build 2>&1 | tail -30`

Add narrower or broader tests where appropriate. If you change behavior and there is no test coverage around it, add coverage unless there is a strong reason not to.

## Key Files To Inspect Frequently

- `ui/src/components/AgentChat.tsx`
- `ui/src/components/ConfabChat.tsx`
- `ui/src/components/DocumentUploadDialog.tsx`
- `ui/src/components/Header.tsx`
- `ui/src/components/HeroSection.tsx`
- `ui/src/components/Login.tsx`
- `ui/src/components/Register.tsx`
- `ui/src/components/ThemeToggle.tsx`
- `ui/src/components/ui/`
- `ui/src/api/client.js`
- `ui/src/contexts/ThemeContext.tsx`
- `api/routes/conversation_routes.py`
- `api/services/conversation_service.py`
- `api/foreman_v3/`
- `api/tests/`

## Phase Tracker

### Phase 1 — Audit Current UX and Capture Issues `[ ]`
- [ ] Review the main user journeys: landing, auth, foreman build chat, confab runtime chat, dashboard, deployment, document flows
- [x] Capture UX issues discovered during review directly in this prompt
- [x] Confirm current Foreman interview UX behavior and identify where previous-turn response and next-step CTA are coupled
- [x] Identify supporting backend/frontend contracts that will need to change

#### Discovered Issues
- [ ] Foreman V3 currently concatenates acknowledgement and next-stage CTA into one assistant message in `api/foreman_v3/nodes/responder.py`
- [ ] `ForemanV2Metadata` already carries enough structure to support a split interaction, but the UI is not using it to render the interview as a guided sequence
- [ ] `AgentChat.tsx` already has suggestion chips, upload affordances, and UI-hint handling, but these are not organized as stage-aware CTA controls
- [ ] Resumed foreman conversations currently load raw message history only, so interview guidance is weaker after resume than during a live turn

### Phase 2 — Reshape the Foreman Chat Interaction Model `[ ]`
- [ ] Separate “answer to previous turn” from “prompt for next step” in the Foreman chat experience
- [ ] Preserve or improve progression clarity so the interview still feels guided and deliberate
- [ ] Decide whether this should be represented as multiple messages, structured metadata, or richer UI composition
- [ ] Keep backward compatibility where practical, or add compatibility shims if response shape changes

### Phase 3 — Add Guided CTAs and Input Affordances `[ ]`
- [ ] Add step-aware hints in the Foreman chat UI
- [ ] Add active CTA controls where they materially reduce friction
- [ ] Support optional guided actions such as skip, examples, structured suggestions, or file upload where appropriate
- [ ] Ensure these controls feel native to the interview rather than bolted on

### Phase 4 — Strengthen Supporting Backend and Tests `[ ]`
- [ ] Update backend or orchestration behavior if needed to support the improved Foreman UX
- [ ] Add or update tests for any changed Foreman/chat behavior
- [ ] Verify no regressions in conversation start, resume, message persistence, and progress synchronization

### Phase 5 — Broader UI/UX Improvement Sweep `[ ]`
- [ ] Fix additional UX issues found across the application
- [ ] Improve consistency of spacing, hierarchy, controls, empty states, and interaction feedback
- [ ] Improve accessibility and responsiveness where obvious issues exist
- [ ] Refine components that feel visually or behaviorally inconsistent with the rest of the product

### Phase 6 — Final Regression Pass and Cleanup `[ ]`
- [ ] Run relevant backend tests
- [ ] Run frontend typecheck
- [ ] Run frontend build
- [ ] Resolve any regressions introduced during the UI/UX work
- [ ] Confirm all issues captured in this prompt are either fixed or explicitly superseded by a better solution

## Completion

When all outstanding UI/UX issues and bug fixes tracked here have been applied, all tests/checks are passing, and there are no known regressions, output:

<promise>FOUNDRY UI UX LOOP COMPLETE</promise>

If work remains, commit progress and exit cleanly. You will be re-invoked with this same prompt.

## Important Rules

- You **may modify this PROMPT.md** to track progress, add discovered issues, and check off completed work.
- Everything in the repo is in scope.
- Nothing is out of scope.
- Use multiple commits per iteration if needed, but make at least one commit per iteration.
- Favor real product improvements over superficial visual tweaks.
- Do not accept regressions in core flows while improving UX.
