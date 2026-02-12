# Conventions

## Repository Structure

```
foundry/
├── api/          # FastAPI backend (Python)
├── ui/           # React frontend (TypeScript)
├── spec/         # Project specifications
├── Makefile      # Development task runner
├── docker-compose.yml
├── .env.sample
└── CLAUDE.md
```

The project is a monorepo. The backend and frontend each have their own dependency files, environment configs, and gitignore rules. Shared orchestration lives at the root level via the Makefile and Docker Compose.

---

## Backend Conventions (`/api`)

### Language & Runtime

- **Python** (no explicit version pin; compatible with 3.10+)
- Virtual environment managed via `python -m venv .venv`

### Framework & Libraries

| Package | Version | Role |
|---------|---------|------|
| FastAPI | 0.128.0 | Web framework |
| Uvicorn | 0.40.0 | ASGI server (with `standard` extras) |
| SQLAlchemy | 2.0.45 | ORM |
| Alembic | 1.17.2 | Database migrations |
| Pydantic | 2.12.5 | Request/response validation |
| pydantic-settings | 2.1.0 | Environment-based settings |
| psycopg2-binary | 2.9.9 | PostgreSQL adapter |
| python-jose | 3.3.0 | JWT token handling (with `cryptography` extras) |
| passlib | 1.7.4 | Password hashing (with `bcrypt` extras) |
| bcrypt | 3.2.2 | Bcrypt algorithm |
| httpx | 0.25.2 | Async HTTP client (GitHub API calls) |
| python-dotenv | 1.0.0 | `.env` file loading |
| python-multipart | 0.0.6 | Form data parsing |
| email-validator | 2.3.0 | Email validation |

### Code Organization

All backend code lives in flat Python modules at the top of `/api`:

| File | Responsibility |
|------|---------------|
| `main.py` | FastAPI app instance, all route definitions, CORS config |
| `models.py` | SQLAlchemy ORM models (`User`, `GitHubAccount`, `Confab`) |
| `schemas.py` | Pydantic schemas for request/response validation |
| `auth.py` | JWT token generation/verification, password hashing |
| `github_oauth.py` | GitHub OAuth flow, GitHub API client functions |
| `confab_manager.py` | GitHub repository operations (create repos, branches, PRs, files) |
| `database.py` | Engine, session factory, `get_db()` dependency |

### Authentication Pattern

- JWT tokens signed with HS256, configurable expiry (default 30 minutes).
- Passwords hashed with bcrypt via passlib. Passwords exceeding 72 bytes are rejected.
- Protected endpoints use `Depends(security)` + `Depends(get_current_user)`.
- GitHub OAuth uses the authorization code flow with `public_repo user:email` scope.

### Database Migrations

- Managed via Alembic, configured in `alembic.ini` and `alembic/env.py`.
- Migrations stored in `alembic/versions/`.
- Always run from the `/api` directory with the virtualenv activated.

### API Design

- Routes are defined directly in `main.py` (no separate router modules, except the GitHub OAuth router).
- Standard HTTP status codes: 400 (bad input), 401 (unauthorized), 404 (not found), 500 (server error), 502 (upstream failure).
- Swagger docs at `/docs`, ReDoc at `/redoc`.

### Environment Variables

Defined in `api/.env` (copied from `api/.env.example`):

- `DATABASE_URL` — PostgreSQL connection string
- `SECRET_KEY` — JWT signing key
- `ACCESS_TOKEN_EXPIRE_MINUTES` — Token lifetime (default: 30)
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` — OAuth credentials
- `GITHUB_BACKEND_REDIRECT_URI`, `GITHUB_FRONTEND_REDIRECT_URI` — OAuth redirect URLs
- `APP_NAME`, `APP_VERSION`, `DEBUG` — Application metadata
- `ALLOWED_ORIGINS` — Comma-separated CORS whitelist
- `DEFAULT_CONFAB_REPO_OWNER`, `DEFAULT_CONFAB_REPO_NAME` — Default GitHub org/repo

---

## Frontend Conventions (`/ui`)

### Language & Runtime

- **TypeScript** with React 18
- Built with **Vite 6.3.5** using the SWC compiler plugin (`@vitejs/plugin-react-swc`)

### Framework & Key Libraries

| Package | Version | Role |
|---------|---------|------|
| React | 18.3.1 | UI framework |
| React Router DOM | 6.30.2 | Client-side routing |
| Radix UI | Various ^1.x/^2.x | Headless, accessible component primitives (28 packages) |
| Tailwind CSS | 4.0.0 | Utility-first CSS framework |
| Lucide React | 0.487.0 | Icon library |
| class-variance-authority | 0.7.1 | Component variant management |
| clsx + tailwind-merge | * | Classname merging utilities |
| React Hook Form | 7.55.0 | Form state management |
| Zod | 3.23.8 | Schema-based form validation |
| @hookform/resolvers | 3.9.1 | Zod integration for React Hook Form |
| Zustand | 5.0.2 | Lightweight state management |
| Sonner | 2.0.3 | Toast notifications |
| Recharts | 2.15.2 | Data visualization |
| Motion | 11.14.4 | Animations |
| Vaul | 1.1.2 | Drawer component |
| cmdk | 1.1.1 | Command palette |
| next-themes | 0.4.6 | Dark/light theme switching |
| react-day-picker | 8.10.1 | Date picker |
| react-resizable-panels | 2.1.7 | Resizable panel layouts |
| embla-carousel-react | 8.6.0 | Carousel/slider |
| input-otp | 1.4.2 | OTP input |
| react-markdown | 9.0.1 | Markdown rendering |
| remark-gfm | 4.0.0 | GitHub Flavored Markdown support |
| date-fns | 4.1.0 | Date formatting utilities |
| nanoid | 5.0.8 | ID generation |

### Dev Dependencies

| Package | Version | Role |
|---------|---------|------|
| Vite | 6.3.5 | Build tool and dev server |
| @vitejs/plugin-react-swc | 3.10.2 | SWC-based React plugin |
| ESLint | 9.17.0 | Linting |
| eslint-plugin-react-hooks | 5.1.0 | React hooks lint rules |
| eslint-plugin-react-refresh | 0.4.16 | HMR lint rules |
| autoprefixer | 10.4.20 | CSS vendor prefixes |
| @types/node, @types/react, @types/react-dom, @types/react-router-dom | Various | TypeScript type definitions |

### Code Organization

```
ui/src/
├── api/
│   └── client.js         # Singleton API client with token injection
├── components/
│   ├── ui/               # 40+ reusable Radix-based UI primitives
│   ├── Header.tsx         # Navigation header
│   ├── HeroSection.tsx    # Landing page
│   ├── Login.tsx          # Login form
│   ├── Register.tsx       # Registration form
│   ├── AgentChat.tsx      # Chat-based agent creation wizard
│   ├── AgentDashboard.tsx # Confab listing dashboard
│   ├── DeploymentPanel.tsx # Deployment configuration
│   ├── ConfabChat.tsx     # Chat with a deployed confab
│   ├── ConfigureConfabWithThreads.tsx # Threaded confab configuration
│   ├── MultiAgentBuilder.tsx # Multi-agent orchestration
│   └── GitHubCallback.tsx # OAuth callback handler
├── contexts/
│   └── AuthContext.tsx    # Global auth state (user, tokens, GitHub status)
├── styles/
│   └── globals.css        # CSS variables, theme definitions
├── App.tsx                # Root component with routing
├── main.tsx               # Entry point
└── index.css              # Compiled Tailwind CSS
```

### Routing

Navigation uses a view-based state model managed in `App.tsx`:

```
Views: home | create | dashboard | deploy | multi-agent |
       login | register | confab-chat | configure
```

The GitHub OAuth callback is handled by a dedicated React Router route at `/auth/github/callback`.

### Styling

- Tailwind CSS v4 with a custom OKLch color palette defined as CSS variables in `globals.css`.
- Dark mode via the `.dark` class (toggled by `next-themes`).
- Component variants use `class-variance-authority` (CVA).
- Classnames merged with `cn()` utility (`clsx` + `tailwind-merge`).
- Base border radius: `0.625rem` (10px).

### UI Component Library

The `ui/src/components/ui/` directory contains 40+ pre-built components wrapping Radix UI primitives with Tailwind styling. These include: button, card, input, textarea, label, select, checkbox, radio-group, badge, avatar, dialog, dropdown-menu, accordion, tabs, progress, tooltip, popover, sheet, sidebar, skeleton, table, form, calendar, command, and more.

### Auth State

Managed by `AuthContext` which:
- Reads the JWT token from `localStorage` (`access_token` key).
- Validates on mount by calling `GET /auth/me`.
- Exposes `login()`, `register()`, `logout()`, `githubLogin()`, `refreshUser()`.
- Automatically clears token on auth errors.

### API Client

`ApiClient` in `src/api/client.js` is a singleton that:
- Reads `VITE_API_URL` (default: `http://localhost:8001`).
- Injects the Bearer token from localStorage into every request.
- Provides methods for all auth and confab endpoints.
- Parses error responses for `detail` or `message` fields.

---

## Shared Conventions

### Port Assignments

| Service | Port |
|---------|------|
| PostgreSQL | 7432 (host) → 5432 (container) |
| API | 8001 |
| UI | 3002 |

### Environment Files

- Root `.env` — Docker Compose variables (`POSTGRES_PASSWORD`).
- `api/.env` — Backend-specific variables (database, JWT, GitHub OAuth, CORS).
- Frontend reads `VITE_API_URL` from Vite's environment.

### Git Workflow

- Feature branches with descriptive names.
- Confabs stored in GitHub repos via branch + pull request workflow.
- No CI/CD pipeline currently configured.
