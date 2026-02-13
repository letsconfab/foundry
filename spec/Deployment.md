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
