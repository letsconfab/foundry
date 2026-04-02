# Foreman V2 — Deterministic Interview Orchestrator

## Status
- **Phase**: 0 (Baseline and Feature Flag)
- **Feature Flag**: `FOREMAN_V2_ENABLED`
- **Target**: Deterministic, interview-style setup flow

---

## Current Foreman Flow (V1)

### Architecture
1. User sends message to `/chat` endpoint
2. `Foreman.process_message()` builds a contextual prompt with:
   - Full system prompt (~100 lines) describing all 7 steps and tools
   - Last 10 messages of conversation history
   - Current stage and completed steps
   - Document context
3. LLM generates free-form response with embedded JSON tool calls
4. `_parse_tool_calls()` extracts JSON objects from prose using brace-matching
5. `_execute_tools_and_respond()` runs discovered tools
6. `_update_progress_from_response()` advances stage based on phrase detection

### Tool Parsing (V1)
```python
# Current approach: find {"tool": ...} in prose
start = response.find('{"tool"', search_start)
# ... brace matching ...
tool_call = json.loads(normalized)
```

### Stage Progression (V1)
```python
completion_signals = [
    "got it", "understood", "perfect", "great", "recorded",
    "saved", "moving on", "next step", "let's continue"
]
if any(signal in response_lower for signal in completion_signals):
    # Advance stage
```

---

## Current Failure Modes

### 1. Non-Deterministic Responses
- **Cause**: Temperature 0.7 produces varied outputs
- **Symptom**: Same user input yields different Foreman responses
- **Impact**: Inconsistent UX, difficult to test

### 2. Unreliable Tool Parsing
- **Cause**: JSON embedded in prose, brace-matching heuristics
- **Symptom**: Malformed JSON, missed tool calls, duplicate extraction
- **Impact**: Data not saved, user must repeat information

### 3. Phrase-Based Stage Progression
- **Cause**: Stage advancement triggered by LLM saying "got it" or "saved"
- **Symptom**: Stage advances without actual data persistence
- **Impact**: User sees progress but nothing is saved

### 4. LLM-Driven Flow Control
- **Cause**: One giant prompt lets LLM decide what to do next
- **Symptom**: Foreman may skip steps, ask multiple questions, or ramble
- **Impact**: Unpredictable interview flow

### 5. UI Keyword Detection
- **Cause**: Frontend detects step via message keywords, not backend state
- **Symptom**: UI step indicator diverges from actual backend progress
- **Impact**: Confusing progress display

### 6. Verbose Responses
- **Cause**: No response length constraints, LLM defaults to chatty style
- **Symptom**: Multi-paragraph responses with excessive praise/brainstorming
- **Impact**: Feels like assistant chat, not focused interview

---

## Target Architecture (V2)

### Core Principles
1. **Foreman owns transitions** — Stage changes happen in Python code only
2. **Structured extraction** — Low-temperature LLM calls return strict JSON
3. **Direct tool binding** — Python calls tools directly per stage
4. **Save-gated progression** — Stage advances only after successful persistence
5. **Templated responses** — Predictable, concise Foreman voice

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│  ConfigureConfabWithThreads.tsx                             │
│  - Renders current_stage from API response                  │
│  - Shows one active question                                │
│  - Displays saved summaries for completed stages            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      API Response                            │
│  {                                                          │
│    response: "...",                                         │
│    current_stage: "purpose",                                │
│    next_stage: "participants",                              │
│    stage_status: "complete" | "clarify" | "skip" | "error", │
│    saved_fields: {...},                                     │
│    suggested_question: "..."                                │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Foreman (foreman.py)                       │
│                                                             │
│  process_message()                                          │
│    ├─ Dispatch by current_stage                             │
│    ├─ _handle_purpose()                                     │
│    ├─ _handle_participants()                                │
│    ├─ _handle_memory()                                      │
│    ├─ _handle_tools()                                       │
│    ├─ _handle_guardrails()                                  │
│    ├─ _handle_sample_io()                                   │
│    └─ _handle_review()                                      │
│                                                             │
│  Each handler:                                              │
│    1. Calls LLM extractor (low temp, JSON output)           │
│    2. Validates extracted data                              │
│    3. Calls tool function directly                          │
│    4. Returns structured result                             │
│    5. Foreman advances stage if save succeeded              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 LLM Service (llm_service.py)                 │
│                                                             │
│  ask_llm_json()                                             │
│    - Temperature: 0.0–0.2                                   │
│    - Stage-specific extractor prompt                        │
│    - Strict JSON output contract                            │
│    - One retry on malformed JSON                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Tool Functions (agent_tools.py)            │
│                                                             │
│  define_purpose(), set_confab_name(), add_participant(),    │
│  configure_memory(), add_tools_and_apis(), guardrails(),    │
│  sample_io(), review_and_save()                             │
│                                                             │
│  Called directly from stage handlers — no prose parsing     │
└─────────────────────────────────────────────────────────────┘
```

### Stage Order
1. `purpose` — What should the agent do?
2. `participants` — Who can access it?
3. `memory` — Should it remember conversations?
4. `tools` — What external capabilities?
5. `guardrails` — Safety boundaries?
6. `sample_io` — Example interactions?
7. `review` — Finalize and save

### Internal Result Shape
```python
@dataclass
class StageResult:
    status: Literal["complete", "clarify", "skip", "error"]
    data: Optional[Dict[str, Any]]      # Extracted/saved data
    summary: Optional[str]              # What was saved
    next_question: Optional[str]        # What to ask next
    error_message: Optional[str]        # If status == "error"
```

### Response Voice Rules
- One question per turn
- No exuberant praise ("Great!", "Awesome!")
- No brainstorming unless user is stuck
- No "what would you like to do next?" during staged flow
- Concise, declarative tone

Example responses:
- "Recorded the purpose. Who should have access initially?"
- "I need one detail: what is the main job of the confab in one sentence?"
- "Noted. Should it remember prior conversations: yes, no, or limited?"

### Out-of-Order Updates

Users can update previously completed stages at any time using natural language:

```
User: "Update the guardrails: Add a rule about no profanity"
```

The `_detect_update_intent()` method detects:
- Update triggers: "update", "change", "modify", "edit", "revise", "fix", "add to"
- Stage keywords: maps "guardrails", "rule", "safety" → `guardrails` stage

When detected:
1. Extract content after the stage reference
2. Dispatch to target stage handler (not current stage)
3. Do NOT advance current stage after update
4. Confirm update and re-ask current stage question

### Configuration Summary

At the review stage, users can view their full configuration:

```
User: "Show the configuration"
```

The `_build_config_summary()` method displays:
- Name, Purpose, Participants, Memory settings
- Tools, Guardrails (first 5 rules)
- Sample Q&A

This is also shown automatically when transitioning to the review stage.

---

## Rollout Plan

### Phase 0 — Baseline and Feature Flag ✅ COMPLETE
- [x] Design spec (this document)
- [x] Add `FOREMAN_V2_ENABLED` feature flag
- [x] Add logging for stage, tool execution, parse failures, progress
- [x] Preserve V1 flow behind flag

### Phase 1 — Deterministic Stage Machine ✅ COMPLETE
- [x] Refactor `process_message()` to dispatch by stage
- [x] Add stage handlers: `_handle_{purpose,participants,memory,tools,guardrails,sample_io,review}`
- [x] Remove phrase-based stage progression (V2 path)
- [x] Add `_next_stage_after()`, `_complete_stage()`, `_render_foreman_reply()`

### Phase 2 — Structured LLM Extraction ✅ COMPLETE
- [x] Add `ask_llm_json()` helper in `llm_service.py`
- [x] Use temperature 0.1 for extraction
- [x] Build per-stage extractor prompts
- [x] Add JSON retry with repair prompt

### Phase 3 — Direct Tool Binding ✅ COMPLETE
- [x] Call tools directly from stage handlers
- [x] V2 path does not use `_parse_tool_calls()`
- [x] Gate stage advancement on successful save

### Phase 4 — Stable Foreman Voice ✅ COMPLETE
- [x] Implement response templating (STAGE_QUESTIONS, STAGE_ACKNOWLEDGMENTS)
- [x] Enforce one-question-per-turn via `_render_foreman_reply()`
- [x] Apply style rules (concise, declarative templates)

### Phase 5 — API Response Contract ✅ COMPLETE
- [x] Extend Pydantic schemas: `ForemanV2Metadata`, updated `ForemanChatResponse`
- [x] Return `current_stage`, `stage_status`, `saved_fields`, `next_question`
- [x] Maintain backward compatibility via optional fields

### Phase 6 — UI Guided Interview ✅ COMPLETE
- [x] Refactor `ConfigureConfabWithThreads.tsx`
- [x] Use backend stage metadata via `foreman_metadata`
- [x] Show current stage prominently with completion indicators
- [x] Add "Skip this step" button

### Phase 6.5 — Bug Fixes and Enhancements ✅ COMPLETE
- [x] Fix: Pass conversation context to `extract_purpose()` for multi-turn synthesis
- [x] Fix: Skip status now properly advances stage (`_complete_stage` call added)
- [x] Fix: Guardrails extraction handles list-to-string conversion
- [x] Fix: `_build_config_summary()` reads from `setup_progress` JSON field
- [x] Feature: `_detect_update_intent()` for out-of-order updates (e.g., "Update the guardrails:")
- [x] Feature: `_build_config_summary()` displays full agent configuration at review stage
- [x] Feature: "Show configuration" request handling in review stage
- [x] Cleanup: `_guardrails_to_markdown()` outputs clean rules without severity/status metadata

### Phase 7 — Optional Internal Workers
- [ ] Extract complex stages to worker modules (if needed)
- [ ] Workers return structured data only
- [ ] Foreman remains sole visible speaker

### Phase 8 — Tests
- [ ] Backend: stage progression, clarification, skip, save-gating
- [ ] Frontend: stage rendering, clarification handling
- [ ] Evaluation harness: compare V1 vs V2 metrics

### Phase 9 — Cutover and Cleanup
- [ ] Enable `FOREMAN_V2_ENABLED` by default
- [ ] Remove V1 code paths
- [ ] Update CLAUDE.md

---

## Migration Notes

### Backward Compatibility
- Existing confabs in `building` status continue working
- V1 remains available via `FOREMAN_V2_ENABLED=false`
- API response shape extends (additive), not replaces

### Feature Flag Behavior
```python
FOREMAN_V2_ENABLED = os.getenv("FOREMAN_V2_ENABLED", "false").lower() == "true"

if FOREMAN_V2_ENABLED:
    # New deterministic path
else:
    # Legacy V1 path
```

---

## Success Metrics

| Metric | V1 Baseline | V2 Target |
|--------|-------------|-----------|
| Response variance (same input) | High | Near-zero |
| Tool execution success rate | ~70% | >95% |
| Stage progression accuracy | ~80% | 100% |
| Avg turns to complete setup | 15+ | <10 |
| User re-entry rate (repeat info) | ~30% | <5% |
