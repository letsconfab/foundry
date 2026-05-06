# Foundry

A full-stack platform for building, configuring, and managing AI agents (confabs). Features an intelligent guided creation process powered by the Foreman agent, GitHub integration for version control, and RAG-enabled document storage.

## Features

- **Guided Agent Creation** - 7-step interview process led by the Foreman system agent
- **GitHub Sync** - Automatic version control of agent configurations as markdown files
- **Document Store** - Upload documents for RAG-enabled knowledge bases (ChromaDB)
- **Hermes Platform Deploy** - Published confabs deploy into Open WebUI with RAGAnything-backed knowledge
- **Chat Interface** - Conversation threading with message history
- **OASF Export** - Open Agent Specification Format for portability

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite, Radix UI, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL |
| LLM | Groq API (Qwen-3 32B) |
| Vector Store | ChromaDB + Sentence Transformers |
| Auth | JWT + GitHub OAuth |

## Quick Start

### Prerequisites

- Python 3.8+
- Node.js 18+
- Docker (for PostgreSQL)
- Groq API key
- GitHub OAuth app (for GitHub integration)

### Setup

1. **Clone and configure environment**
   ```bash
   git clone https://github.com/letsconfab/foundry.git
   cd foundry
   cp .env.sample .env
   cp api/.env.example api/.env
   ```

2. **Edit `.env` and `api/.env`** with your credentials:
   ```
   DATABASE_URL=postgresql://postgres:password@localhost:7432/foundry
   SECRET_KEY=your-secret-key
   GROQ_API_KEY=your-groq-api-key
   GITHUB_CLIENT_ID=your-github-client-id
   GITHUB_CLIENT_SECRET=your-github-client-secret
   ```

3. **Install dependencies**
   ```bash
   make dev-setup
   ```

4. **Start all services**
   ```bash
   make all
   ```

   This starts:
   - PostgreSQL on port 7432
   - FastAPI backend on port 8001
   - React frontend on port 3002

5. **Open the app**
   
   Visit [http://localhost:3002](http://localhost:3002)

## Development Commands

```bash
make all          # Start all services (db, api, ui)
make db           # Start PostgreSQL only
make api          # Start FastAPI backend only
make ui           # Start React frontend only
make stop         # Stop all services
make dev-setup    # Install all dependencies
```

### Database Migrations

```bash
cd api && . .venv/bin/activate
alembic revision --autogenerate -m "Description"
alembic upgrade head
alembic downgrade -1
```

### API Documentation

When the API is running:
- Swagger UI: http://localhost:8001/docs
- ReDoc: http://localhost:8001/redoc

## Project Structure

```
foundry/
├── api/                    # FastAPI backend
│   ├── main.py             # Route definitions
│   ├── models.py           # SQLAlchemy models
│   ├── foreman.py          # Foreman agent (guided creation)
│   ├── llm_service.py      # Groq API integration
│   ├── github_service.py   # GitHub operations
│   ├── document_store/     # RAG document management
│   └── alembic/            # Database migrations
│
├── ui/                     # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── contexts/       # Auth context
│   │   └── api/            # API client
│   └── package.json
│
├── spec/                   # Documentation
├── docker-compose.yml      # Service orchestration
└── Makefile                # Development commands
```

## The Foreman Agent

The Foreman is a system agent that guides users through creating AI agents via a structured 7-step interview:

1. **Define Purpose** - What should the agent do?
2. **Add Participants** - Who can access it?
3. **Configure Memory** - Should it remember conversations?
4. **Set Up Tools** - What external APIs/capabilities?
5. **Establish Guardrails** - Safety boundaries & rules
6. **Sample I/O** - Example interactions
7. **Review** - Finalize configuration & deploy

The Foreman uses deterministic stage progression with LLM-powered extraction at low temperature for reliable, consistent results.

## GitHub Integration

Confabs are automatically synced to GitHub as structured files:

```
confabs/{agent-name}/
├── Confab.toml       # Metadata
├── PURPOSE.md        # Agent purpose
├── GUARDRAILS.md     # Safety rules
└── TESTS.md          # Test scenarios
```

To enable GitHub sync:
1. Create a GitHub OAuth app
2. Configure `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`
3. Connect your GitHub account in the app settings

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key |
| `GROQ_API_KEY` | Groq API key for LLM |
| `GROQ_MODEL_NAME` | Model name (default: `qwen/qwen3-32b`) |
| `GITHUB_CLIENT_ID` | GitHub OAuth client ID |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth client secret |
| `GITHUB_REDIRECT_URI` | OAuth callback URL |
| `ALLOWED_ORIGINS` | CORS whitelist |
| `FOREMAN_V2_ENABLED` | Enable V2 deterministic interview flow |
| `OPENWEBUI_URL` | Open WebUI URL shown for deployed confabs, default `http://localhost:3001` |
| `RAGANYTHING_URL` | RAGAnything REST API URL, default `http://localhost:8001` |
| `RAGANYTHING_WORKSPACE_PREFIX` | Workspace/prefix root for deployed confabs, default `confabs` |
| `HERMES_PROFILE_IMAGE` | Hermes Agent Docker image for profile runtimes |
| `HERMES_PROFILE_NETWORK` | Docker network where Hermes profile containers run |
| `HERMES_PROFILE_DATA_DIR` | Host root for generated Hermes profile directories; local default is `api/data/hermes-profiles` |
| `HERMES_PROFILE_PORT_START` / `HERMES_PROFILE_PORT_END` | Persistent host port allocation range |
| `HERMES_PLATFORM_PROFILE_SOURCE` | Platform default Hermes profile directory to inherit model settings from |
| `HERMES_PLATFORM_PROFILE_CONTAINER` | Optional running Hermes container to copy platform model config/auth from when the profile source is not host-readable |
| `HERMES_MODEL_ROUTER_API_KEY` | Shared bearer key Open WebUI uses for the Foundry model router |
| `HERMES_MODEL_ROUTER_PROXY_BASE` | `external` for host-local routing, `internal` for Docker-network routing |
| `HERMES_OPENWEBUI_BASE_MODEL` | Deprecated for the profile runtime deploy path |

## Deployment Bridge

Foundry remains the source of truth for confab definitions, uploaded documents, and approved learnings. Deploying a published confab now syncs deployable knowledge into RAGAnything under `confabs/{confab_id}/`, indexes that folder, renders a Hermes profile, starts one dedicated Hermes container, and exposes the confab as model `confab-{confab_id}-{slug}` through the Foundry model router.

Open WebUI should be configured with one OpenAI-compatible backend pointing at the router, for example `http://localhost:8011/router/v1` from the host or the equivalent Foundry API service URL inside Docker. The old Open WebUI wrapper-only model path, the old hermes-agents realization API on `:8022`, and the old confab-rag API on `:8099` are deprecated for the Foundry deploy path. Undeploy removes the dedicated runtime and preserves profile files and RAG workspace data.

For local GitHub OAuth, set the GitHub OAuth app callback URL to `http://localhost:8011/auth/github/callback`. The Hermes RAGAnything service owns `localhost:8001` in the local stack, so Foundry uses `8011` for its API.

## License

MIT
