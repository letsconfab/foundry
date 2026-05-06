# Hermes Profile Deployment Plan

## Goal

When a published Foundry confab is deployed, Foundry should create a real Hermes Agent runtime for that confab, not only an Open WebUI model wrapper.

A deployed confab should become a Hermes profile-backed agent with:

- its own `SOUL.md`
- its own `config.yaml`
- its own `.env`
- its own memory, sessions, skills, logs, cron state, and gateway state
- its own OpenAI-compatible API endpoint
- its own Open WebUI model entry
- its own RAGAnything workspace/prefix

The Open WebUI model dropdown should expose real deployed Hermes agents, where each model points to a distinct Hermes profile/gateway process.

## Current State

The May 6 bridge commit deploys confabs as Open WebUI model wrappers over one shared Hermes backend:

- Foundry syncs deployable knowledge to RAGAnything under `confabs/{confab_id}`.
- Foundry creates an Open WebUI model wrapper with ID `confab-{confab_id}-{slug}`.
- The wrapper uses base model `hermes-agent`.
- The wrapper injects confab purpose, guardrails, tests, and workspace instructions into `params.system`.

This is not a real Hermes agent boundary. Hermes still runs as one default profile and one gateway process. The request `model` field is cosmetic in Hermes API server mode; the real model/provider/runtime is configured server-side.

## Hermes Runtime Finding

Hermes Agent supports real multi-agent separation through profiles.

A Hermes profile is a separate `HERMES_HOME` directory containing its own:

- `config.yaml`
- `.env`
- `SOUL.md`
- memories
- sessions
- skills
- cron jobs
- logs
- gateway state
- state database

Each profile runs its own gateway/API server process. Each profile API server advertises its profile name as the model ID unless `API_SERVER_MODEL_NAME` overrides it.

Therefore, Foundry deploy must provision a profile and process per confab.

## Target Architecture

### Deploy Flow

1. User publishes a confab in Foundry.
2. User clicks deploy.
3. Foundry syncs knowledge into RAGAnything:
   - active latest document versions
   - `PURPOSE.md`
   - `GUARDRAILS.md`
   - `TESTS.md`
   - `LEARNINGS.md`
   - `CONFAB.md`
4. Foundry creates or updates a Hermes profile for the confab.
5. Foundry writes generated profile files:
   - `SOUL.md`
   - `config.yaml`
   - `.env`
   - optional profile-local `AGENTS.md` or `.hermes.md` context
6. Foundry starts or restarts that profile gateway/API server.
7. Foundry registers or updates an Open WebUI model/connection entry for the profile endpoint.
8. Foundry stores deployment metadata.
9. Deploy status checks the actual profile gateway health plus Open WebUI model existence.

### Runtime Shape

For confab ID `123` named `Policy Coach`:

- Foundry slug: `policy-coach`
- Hermes profile name: `confab-123-policy-coach`
- Hermes profile home: `/opt/data/profiles/confab-123-policy-coach`
- Hermes API port: allocated, for example `8701`
- Hermes API base URL: `http://hermes-confab-123-policy-coach:8642/v1` inside Docker, or `http://localhost:8701/v1` from host
- Open WebUI model ID: `confab-123-policy-coach`
- RAGAnything workspace: `confabs/123`
- RAGAnything prefix: `confabs/123/`

## Key Product Decision

There are two viable deployment modes.

### Option A: One Hermes Container, Many Profile Processes

Run multiple `hermes -p <profile> gateway run` processes inside one `hermes-agent` container.

Pros:

- smallest infrastructure change
- profile directories stay under one `hermes_data` volume
- can use Hermes profile CLI directly

Cons:

- process supervision becomes Foundry's responsibility or requires a supervisor
- per-profile API ports must be allocated and exposed
- a single container failure stops every profile
- Docker Compose static port mapping is awkward for dynamic profiles

### Option B: One Hermes Container Per Deployed Confab

Foundry creates a container per confab profile from `nousresearch/hermes-agent:latest`, with its own mounted profile volume and API port.

Pros:

- clean runtime isolation
- container health maps directly to deploy status
- easy undeploy semantics
- logs/restarts are per confab
- aligns with “real agent per confab”

Cons:

- requires Docker API access or an internal provisioning service
- more containers to manage
- requires naming, port allocation, volume lifecycle, and cleanup policy

Recommendation: use **Option B** for the product path. It best matches the user-facing promise that each deployed confab is a real Hermes Agent.

## Required Foundry Changes

### 1. Add Deployment Metadata

Add a table such as `confab_deployments`:

```text
id
confab_id
user_id
status                  # provisioning, running, stopped, failed, deleting
runtime                 # hermes_profile
profile_name            # confab-123-policy-coach
model_id                # confab-123-policy-coach
container_name          # hermes-confab-123-policy-coach
api_base_url_internal   # http://hermes-confab-123-policy-coach:8642/v1
api_base_url_external   # http://localhost:8701/v1
api_port
rag_workspace           # confabs/123
rag_prefix              # confabs/123/
openwebui_model_id
last_sync_result        # JSON
last_health             # JSON
last_error
created_at
updated_at
deployed_at
stopped_at
```

Add a unique constraint on `confab_id`.

### 2. Split Services by Responsibility

Create new services:

```text
api/services/hermes_profile.py
api/services/hermes_runtime.py
api/services/openwebui_models.py
api/services/deploy_orchestrator.py
```

Responsibilities:

- `rag_sync.py`: only RAGAnything upload/index.
- `hermes_profile.py`: render and write profile files.
- `hermes_runtime.py`: create/start/stop/restart/health-check Hermes runtime containers or processes.
- `openwebui_models.py`: register/remove Open WebUI model entries that point to the profile endpoint.
- `deploy_orchestrator.py`: sequence the deploy/undeploy/status workflows and persist state.

### 3. Generate Hermes `SOUL.md`

Foundry should generate a profile-specific `SOUL.md` from confab source of truth.

The file should include durable agent identity and behavioral style:

```markdown
# Identity

You are {confab.name}.

# Purpose

{confab.purpose}

# Description

{confab.description}

# Guardrails

{guardrails}

# Sample I/O Expectations

{tests}

# Knowledge Grounding

Use deployed knowledge from RAGAnything workspace `confabs/{confab.id}` when a user asks questions that may depend on confab documents or approved learnings.

If deployed knowledge has no relevant result, say that clearly instead of inventing supporting facts.
```

Important: Hermes docs describe `SOUL.md` as identity/personality, not project workflow. Keep operational details minimal. Put heavy procedural/tool instructions into profile-local `.hermes.md` or `AGENTS.md` if needed.

### 4. Generate Profile `config.yaml`

The profile config must include:

- same LLM provider/model defaults as the platform or Foundry confab runtime settings
- API server enabled
- API server host `0.0.0.0`
- API server port `8642` inside the container
- API server model name equal to the profile/model ID
- MCP servers for RAGAnything
- API server toolsets including MCP
- tool-use enforcement where appropriate

Example:

```yaml
model:
  default: gpt-5.4-mini
  provider: openai-codex
  base_url: https://chatgpt.com/backend-api/codex

platforms:
  api_server:
    enabled: true
    extra:
      host: 0.0.0.0
      port: 8642
      key: ${API_SERVER_KEY}
      model_name: confab-123-policy-coach

mcp_servers:
  raganything_knowledge:
    url: http://raganything:8000/rag/mcp
    timeout: 180
  raganything_files:
    url: http://raganything:8000/files/mcp
    timeout: 120
  raganything_classical:
    url: http://raganything:8000/classical/mcp
    timeout: 180

agent:
  tool_use_enforcement: required
```

Validate exact config keys against the Hermes version in use before implementation because the API server docs currently emphasize environment variables for this surface.

### 5. Generate Profile `.env`

Each profile needs at least:

```env
API_SERVER_ENABLED=true
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=8642
API_SERVER_KEY=<per-profile secret>
API_SERVER_MODEL_NAME=confab-123-policy-coach
API_SERVER_CORS_ORIGINS=*
```

Provider credentials can be:

- cloned from the base Hermes runtime, or
- injected from Foundry-managed platform secrets, or
- selected per confab if Foundry later supports that.

Initial implementation should clone the platform provider config and only vary the API server key/model/profile identity.

### 6. Provision Runtime Container

For Option B, add a service that can call Docker:

```python
async def create_or_update_confab_runtime(deployment: ConfabDeployment) -> RuntimeResult
async def start_confab_runtime(deployment: ConfabDeployment) -> RuntimeResult
async def stop_confab_runtime(deployment: ConfabDeployment) -> bool
async def remove_confab_runtime(deployment: ConfabDeployment) -> bool
async def get_confab_runtime_health(deployment: ConfabDeployment) -> dict | None
```

Container requirements:

- image: `nousresearch/hermes-agent:latest`
- name: `hermes-confab-{id}-{slug}`
- network: same Docker network as RAGAnything/Open WebUI
- mounted profile volume or directory at `/opt/data`
- port mapping: host allocated port -> container `8642`
- command: `hermes gateway run`
- health check: `GET /health` or `GET /v1/models`

Avoid shelling out long-term. Use Docker SDK or a small internal runtime-control API. Shelling out can be acceptable for a spike but should not be the production path.

### 7. Register Open WebUI Model

Current Open WebUI wrapper code sets `base_model_id=hermes-agent`, which still routes to the shared default backend.

For real profiles, Foundry must ensure Open WebUI routes the model to the profile endpoint. There are two possible approaches:

1. Add a separate Open WebUI OpenAI connection for each profile endpoint.
2. Run a Foundry/Hermes model-router API that exposes many model IDs from one `/v1/models` endpoint and forwards each request to the correct profile endpoint.

Recommendation for first robust implementation: **model-router API**.

Reason:

- Open WebUI connection management APIs are less stable than OpenAI-compatible routing.
- Hermes API server advertises one model per profile endpoint.
- A router can aggregate all profile `/v1/models` results and route `/v1/chat/completions` by request `model`.
- Open WebUI needs only one connection to the router.

Router responsibilities:

- `GET /v1/models`: list all running deployed confab model IDs.
- `POST /v1/chat/completions`: inspect `model`, forward to that profile API.
- `POST /v1/responses`: same for Responses API if enabled.
- `GET /health`: report aggregate status.

This router can live in Foundry API only if security and long-running streaming behavior are acceptable. Otherwise, implement it as a small separate service.

### 8. Update Deploy Endpoint

New deploy endpoint sequence:

```python
deployment = get_or_create_deployment(confab)
deployment.status = "provisioning"

rag_result = await sync_documents_to_raganything(db, confab)
profile_files = render_hermes_profile_files(confab, rag_result["workspace"])
runtime = await create_or_update_confab_runtime(deployment, profile_files)
health = await wait_for_runtime_health(runtime)
openwebui = await register_model_or_router_entry(deployment)

deployment.status = "running"
deployment.last_sync_result = rag_result
deployment.last_health = health
```

Return:

```json
{
  "message": "Deployed",
  "deployment": {
    "status": "running",
    "profile_name": "confab-123-policy-coach",
    "model_id": "confab-123-policy-coach",
    "api_base_url": "http://localhost:8701/v1",
    "openwebui_url": "http://localhost:3001",
    "rag_workspace": "confabs/123"
  },
  "knowledge_synced": true,
  "rag_indexed": 5,
  "rag_workspace": "confabs/123"
}
```

### 9. Update Undeploy Endpoint

Undeploy should:

1. remove or disable the Open WebUI model/router entry
2. stop and remove the Hermes profile container
3. mark deployment as `stopped` or `deleted`
4. skip RAGAnything workspace cleanup until a safe delete endpoint exists

Do not delete the profile volume by default. Preserve it for redeploy/debug unless the user asks for destructive cleanup.

### 10. Update Status Endpoint

Status should check:

- deployment row exists
- runtime container exists
- runtime health endpoint responds
- `/v1/models` advertises expected model ID
- Open WebUI/router exposes expected model ID
- latest RAG sync metadata

Return:

```json
{
  "status": "running",
  "profile_name": "confab-123-policy-coach",
  "model_id": "confab-123-policy-coach",
  "api_base_url": "http://localhost:8701/v1",
  "openwebui_url": "http://localhost:3001",
  "rag_workspace": "confabs/123",
  "runtime": {
    "container": "hermes-confab-123-policy-coach",
    "healthy": true
  },
  "knowledge": {
    "last_uploaded": 5,
    "indexed": true,
    "classical_indexed": true,
    "errors": []
  }
}
```

## Open Questions

1. Should profile containers share one provider credential, or should Foundry manage per-user/per-confab LLM credentials?
2. Should undeploy preserve profile state by default?
3. Should redeploy overwrite `SOUL.md` every time, or preserve manual Hermes-side edits?
4. Should approved learnings be injected into `SOUL.md`, RAG only, or both?
5. Should runtime RAG be forced through a model-router pre-query layer if Hermes MCP invocation remains unreliable?
6. Should each confab get its own RAGAnything database namespace beyond prefix/workspace, or is `confabs/{id}` sufficient?

## Implementation Phases

### Phase 1: Data Model and File Rendering

- Add `ConfabDeployment` SQLAlchemy model and migration.
- Add schemas for deployment status.
- Implement deterministic profile/model/container naming.
- Implement `SOUL.md`, `config.yaml`, `.env`, and optional `.hermes.md` rendering.
- Unit-test rendering with purpose, guardrails, tests, workspace, and approved learnings.

Acceptance:

- Deploy metadata persists.
- Generated `SOUL.md` exactly reflects Foundry source-of-truth fields.

### Phase 2: Runtime Provisioning Spike

- Implement container provisioning behind `hermes_runtime.py`.
- Allocate host ports deterministically or from a configured range.
- Start one profile container from a test confab.
- Verify `/v1/models` returns the confab model ID.
- Verify `/health` returns OK.

Acceptance:

- A deployed confab starts a distinct Hermes process/container.
- The profile has its own `/opt/data/SOUL.md`.

### Phase 3: Open WebUI Routing

- Decide between per-profile Open WebUI connections and a model-router API.
- Prefer model-router API for stable dropdown behavior.
- Implement `GET /v1/models` aggregation.
- Implement streaming-safe forwarding for `/v1/chat/completions`.
- Point Open WebUI at the router.

Acceptance:

- Open WebUI dropdown shows deployed confabs.
- Selecting a confab routes chat to that confab profile endpoint.

### Phase 4: RAG Runtime Grounding

- Verify whether the profile runtime invokes RAGAnything MCP tools naturally.
- If not reliable, add explicit router-side RAG pre-query:
  - detect model/confab
  - query `/api/v1/query` and `/api/v1/classical/query`
  - inject retrieved snippets into request instructions/system context
  - label grounding source and no-result cases

Acceptance:

- Asking about an uploaded document produces a grounded answer or an explicit no-result response.
- Runtime grounding status is surfaced separately from indexing status.

### Phase 5: UI and Operations

- Dashboard shows:
  - profile name
  - runtime health
  - Open WebUI link
  - RAG sync/index status
  - last deploy error
- Add redeploy/restart controls if needed.
- Add logs link or last error display.
- Add cleanup policy for stopped profile containers/volumes.

Acceptance:

- Non-technical users can publish, deploy, verify running status, chat, and undeploy without understanding profiles/ports.

## Test Plan

### Unit Tests

- profile name normalization
- `SOUL.md` rendering includes purpose, guardrails, tests, and workspace
- generated `.env` includes per-profile API settings
- generated config includes RAGAnything MCP servers
- deploy orchestration calls RAG sync before runtime start
- undeploy stops runtime and skips RAG cleanup
- status reports not deployed, provisioning, running, failed

### Integration Tests

- create a sample published confab
- upload a document during Foreman document stage
- approve one learning
- deploy
- assert a profile container exists
- assert profile `/opt/data/SOUL.md` contains confab identity
- assert profile `/v1/models` returns model ID
- assert RAGAnything files list includes `confabs/{id}/PURPOSE.md`, `GUARDRAILS.md`, and uploaded document
- assert Open WebUI/router model list includes confab model
- undeploy and assert runtime stopped

### Manual Acceptance

1. Build a confab through Foreman.
2. Upload a document during the document stage.
3. Add guardrails and sample I/O.
4. Publish.
5. Deploy.
6. Confirm Open WebUI model dropdown shows the confab name/model.
7. Ask a question requiring the uploaded document.
8. Confirm answer is grounded or no-result is explicit.
9. Undeploy.
10. Confirm model disappears or is disabled and runtime stops.

## Migration From Current Bridge

Keep the current RAG sync service. Replace the OpenWebUI wrapper-only deploy service with profile runtime provisioning.

Temporary compatibility:

- Existing deployed wrappers can be treated as legacy deployments.
- On next deploy, create a real profile deployment and overwrite the Open WebUI entry to point to the profile/router model.
- Status endpoint should identify `runtime: "openwebui_wrapper"` vs `runtime: "hermes_profile"` during transition.

## Risks

- Dynamic Docker/container management from Foundry may need extra permissions.
- Open WebUI connection/model APIs may change; a router reduces that dependency.
- Hermes API server tool invocation through MCP remains unproven for RAG grounding.
- Many profile containers can exhaust host resources without concurrency limits.
- Port allocation must avoid collisions and survive restarts.

## Recommended Next Implementation Step

Implement Phase 1 and a Phase 2 spike together:

1. Add deployment table.
2. Render profile files.
3. Provision one profile container for a deployed confab.
4. Verify `SOUL.md` and `/v1/models`.

Do not redesign the UI first. The runtime boundary must be proven before polishing dashboard status.
