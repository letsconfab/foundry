# Deployment

## Local Development Setup

### Prerequisites

| Dependency | Purpose | Required |
|------------|---------|----------|
| Python 3.10+ | Backend runtime | Yes |
| Node.js (LTS) | Frontend runtime | Yes |
| npm | Frontend package manager | Yes |
| Docker & Docker Compose | PostgreSQL container | Yes |
| Git | Version control | Yes |
| Make | Task runner | Yes (or run commands manually) |

### Optional Dependencies

| Dependency | Purpose |
|------------|---------|
| GitHub OAuth App credentials | Full GitHub integration (login, repo operations) |

### Step-by-Step Setup

#### 1. Clone and Configure Environment

```bash
git clone <repository-url>
cd foundry

# Root environment (Docker Compose variables)
cp .env.sample .env
# Edit .env — set POSTGRES_PASSWORD

# API environment
cp api/.env.example api/.env
# Edit api/.env — set at minimum:
#   DATABASE_URL=postgresql://postgres:<password>@localhost:7432/confab_foundry_db
#   SECRET_KEY=<a-strong-random-string>
#   GITHUB_CLIENT_ID=<your-github-oauth-app-id>        (optional)
#   GITHUB_CLIENT_SECRET=<your-github-oauth-app-secret> (optional)
#   ALLOWED_ORIGINS=http://localhost:3002
```

#### 2. Install Dependencies

```bash
make dev-setup
```

This runs:
- `make install-api` — Creates `api/.venv/`, installs Python packages from `api/requirements.txt`.
- `make install-ui` — Runs `npm install` in `ui/`.

#### 3. Start Services

```bash
make all
```

This starts (in order):
1. **Database** (`make db`) — `docker compose up -d` to start PostgreSQL on port 7432.
2. **API** (`make api`) — Activates the virtualenv and runs `uvicorn main:app --reload --host 0.0.0.0 --port 8001`.
3. **UI** (`make ui`) — Runs `npm run dev` (Vite dev server on port 3002).

#### 4. Apply Database Migrations

```bash
cd api && . .venv/bin/activate && alembic upgrade head
```

#### 5. Verify

- Frontend: `http://localhost:3002`
- API Swagger docs: `http://localhost:8001/docs`
- Database: `psql -h localhost -p 7432 -U postgres -d confab_foundry_db`

### Individual Service Commands

```bash
make db       # Start only PostgreSQL
make api      # Start only the API
make ui       # Start only the UI
make stop     # Stop all services
make clean    # Stop all services and remove Docker volumes
make logs-db  # View database logs
make logs-api # View API logs
make logs-ui  # View UI logs
```

### Database Migration Commands

Run from `/api` with the virtualenv activated:

```bash
alembic revision --autogenerate -m "Description"  # Generate a migration
alembic upgrade head                               # Apply all pending migrations
alembic downgrade -1                               # Roll back one migration
```

---

## Cloud Deployment

> Cloud deployment infrastructure is not yet implemented. The following outlines the components that would need to be provisioned.

### Components to Deploy

| Component | Technology | Notes |
|-----------|-----------|-------|
| Database | PostgreSQL 18.1 | Managed service recommended (RDS, Cloud SQL, etc.) |
| API | FastAPI + Uvicorn | Should run behind Gunicorn with Uvicorn workers in production |
| UI | Static files (Vite build) | Serve via CDN or static file host |

### Build the Frontend for Production

```bash
cd ui && npm run build
```

This outputs static files to `ui/build/`. These can be served by any static file server, CDN, or reverse proxy.

### Run the API in Production

```bash
cd api && . .venv/bin/activate
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001
```

### Environment Variables for Production

All variables from `api/.env.example` apply, with these adjustments:

| Variable | Production Value |
|----------|-----------------|
| `SECRET_KEY` | A strong, randomly generated secret |
| `DEBUG` | `False` |
| `DATABASE_URL` | Connection string for the managed database |
| `ALLOWED_ORIGINS` | The production frontend domain |
| `GITHUB_BACKEND_REDIRECT_URI` | Production API callback URL |
| `GITHUB_FRONTEND_REDIRECT_URI` | Production frontend callback URL |
| `VITE_API_URL` (frontend build-time) | Production API base URL |
| `FOREMAN_V3_ENABLED` | `true` to enable LangGraph Foreman (default: `false`) |
| `REGISTRY_GITHUB_TOKEN` | Server-side GitHub PAT for email/password user registry commits |
| `REGISTRY_REPO_OWNER` | Registry repo owner (default: `letsconfab`) |
| `REGISTRY_REPO_NAME` | Registry repo name (default: `registry`) |
| `OPENWEBUI_URL` | Open WebUI URL for confab model wrappers, default `http://localhost:3001` |
| `OPENWEBUI_ADMIN_EMAIL` | Open WebUI admin account email |
| `OPENWEBUI_ADMIN_PASSWORD` | Open WebUI admin account password |
| `RAGANYTHING_URL` | RAGAnything REST API URL, default `http://localhost:8001` |
| `RAGANYTHING_WORKSPACE_PREFIX` | Workspace root for deployed confabs, default `confabs` |
| `HERMES_OPENWEBUI_BASE_MODEL` | Base Open WebUI model for confab wrappers, default `hermes-agent` |

## Hermes Platform Bridge

Foundry deploys published confabs into the local Hermes platform rather than provisioning cloud infrastructure in this pass.

Deploy flow:

1. Foundry collects the confab purpose, description, guardrails, tests/sample I/O, active uploaded documents, and approved learnings.
2. Foundry uploads active documents and generated markdown files (`PURPOSE.md`, `GUARDRAILS.md`, `TESTS.md`, `LEARNINGS.md`, `CONFAB.md`) to RAGAnything under `confabs/{confab_id}/`.
3. Foundry indexes that folder with both `/api/v1/folder/index` and `/api/v1/classical/folder/index`.
4. Foundry creates or updates an Open WebUI model wrapper with ID `confab-{confab_id}-{slug}` and base model `hermes-agent`.
5. Deploy status reports `running` when the Open WebUI model wrapper exists.

Local platform endpoints:

| Service | URL |
|---------|-----|
| Open WebUI | `http://localhost:3001` |
| RAGAnything | `http://localhost:8001` |

Deprecated for the Foundry deploy path:

| Legacy setting | Status |
|----------------|--------|
| `HERMES_AGENTS_URL=http://localhost:8022` | Deprecated realization API path |
| `CONFAB_RAG_URL=http://localhost:8099` | Deprecated confab-rag API path |
| `HERMES_WEBHOOK_SECRET` | Keep only if a webhook receiver is intentionally reintroduced |

RAGAnything workspace cleanup is not implemented because the observed API has no safe delete-workspace endpoint. Undeploy removes only the Open WebUI model wrapper and logs the skipped RAG cleanup.

Runtime answer grounding is still a separate verification item: Hermes must either invoke RAGAnything MCP tools through Open WebUI, or a follow-up runtime query layer must be added before generation.

### Infrastructure Considerations

- **Reverse proxy** — Place Nginx or a cloud load balancer in front of the API.
- **HTTPS** — Terminate TLS at the reverse proxy or load balancer.
- **Database** — Use a managed PostgreSQL service with automated backups.
- **Secrets** — Store `SECRET_KEY`, `GITHUB_CLIENT_SECRET`, and `DATABASE_URL` in a secrets manager (not environment files).
- **Logging** — Configure structured logging and forward to a log aggregation service.
- **Health checks** — The `GET /` endpoint returns `{"message": "Let's Confab API"}` and can be used for liveness probes.

### Currently Not Present

- No Dockerfile for the API or UI.
- No Kubernetes manifests or Helm charts.
- No CI/CD pipeline (GitHub Actions or equivalent).
- No Terraform or infrastructure-as-code definitions.
