# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Foundry is a full-stack monorepo for Let's Confab - a platform for building, saving, and managing AI agent "confabs" (custom agent configurations). It consists of a FastAPI backend and React/TypeScript frontend.

## Development Commands

### Start All Services
```bash
make all          # Start db, api, and ui
```

### Individual Services
```bash
make db           # Start PostgreSQL (Docker)
make api          # Start FastAPI backend (port 8001)
make ui           # Start React frontend (port 3002)
make stop         # Stop all services
```

### Setup
```bash
make dev-setup    # Install both API and UI dependencies
make install-api  # Python venv + pip install
make install-ui   # npm install
```

### Database Migrations (run from /api directory)
```bash
cd api && . .venv/bin/activate
alembic revision --autogenerate -m "Description"  # Create migration
alembic upgrade head                               # Apply migrations
alembic downgrade -1                               # Rollback one migration
```

### API Documentation
When API is running: `http://localhost:8001/docs` (Swagger) or `/redoc`

## Architecture

### Backend (`/api`)
- **main.py**: FastAPI app with all route definitions
- **models.py**: SQLAlchemy ORM models (User, GitHubAccount, Confab)
- **schemas.py**: Pydantic validation schemas
- **auth.py**: JWT token generation and password hashing
- **github_oauth.py**: GitHub OAuth flow and token exchange
- **confab_manager.py**: GitHub repository operations (create repos, branches, PRs)
- **database.py**: PostgreSQL connection via SQLAlchemy

### Frontend (`/ui`)
- **src/App.tsx**: React Router configuration
- **src/contexts/AuthContext.tsx**: Global auth state (user, tokens, GitHub connection)
- **src/api/client.js**: API client with automatic token injection
- **src/components/**: React components using Radix UI + Tailwind CSS

### Key Data Flow
1. Auth: Email/password or GitHub OAuth → JWT token → stored in localStorage
2. Confabs: Created via API → stored in DB + synced to GitHub as structured files
3. GitHub Integration: OAuth token stored in GitHubAccount → used for repo operations

### Confab Storage Format (in GitHub)
Each confab is stored as a directory containing:
- `Confab.toml` - Configuration metadata
- `PURPOSE.md` - Purpose and objectives
- `GUARDRAILS.md` - Safety constraints
- `TESTS.md` - Test scenarios

## Port Configuration
- PostgreSQL: 7432 (mapped from container 5432)
- API: 8001
- UI: 3002

## Environment Variables
Copy `.env.sample` to `.env` at root and `api/.env.example` to `api/.env`. Key variables:
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT signing key
- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` - OAuth credentials
- `ALLOWED_ORIGINS` - CORS whitelist
