# Foundry

A full-stack platform for building, configuring, and managing AI agents (confabs). Features an intelligent guided creation process powered by the Foreman agent, GitHub integration for version control, and RAG-enabled document storage.

## Features

- **Guided Agent Creation** - 7-step interview process led by the Foreman system agent
- **GitHub Sync** - Automatic version control of agent configurations as markdown files
- **Document Store** - Upload documents for RAG-enabled knowledge bases (ChromaDB)
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

## License

MIT
