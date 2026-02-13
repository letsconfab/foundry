# Packaging

## Current Packaging Model

Foundry does not have a single packaged artifact. Each component is packaged and deployed independently:

| Component | Packaging | Output |
|-----------|-----------|--------|
| Frontend (UI) | Vite production build | Static files in `ui/build/` |
| Backend (API) | Python virtualenv + source | `api/` directory with `.venv/` |
| Database | Docker container image | `postgres:18.1` from Docker Hub |

---

## Frontend Packaging

### Build Command

```bash
cd ui && npm run build
```

### Output

Vite produces optimized static assets in `ui/build/`:

```
ui/build/
├── index.html          # Entry point
└── assets/
    ├── *.js            # Bundled, minified JavaScript (code-split chunks)
    └── *.css           # Compiled Tailwind CSS
```

### Build Configuration

- **Tool:** Vite 6.3.5 with SWC
- **Target:** ESNext
- **Output directory:** `ui/build/`
- **Code splitting:** Automatic (Vite default)
- **Minification:** Enabled (Vite default for production)
- **Source maps:** Vite default (hidden in production)

### Build-Time Environment Variables

Variables prefixed with `VITE_` are embedded at build time:

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_URL` | `http://localhost:8001` | Backend API base URL |

This value is baked into the built JS, so it must be set correctly before running `npm run build` for each target environment.

### Serving the Build

The output is a standard static site. It can be served by:

- Any static file server (e.g., `npx serve ui/build`)
- A CDN (CloudFront, Cloudflare Pages, Vercel, Netlify)
- Nginx or Apache as a reverse proxy
- An S3 bucket with static website hosting

Since the app uses client-side routing, the server must be configured to serve `index.html` for all paths (SPA fallback).

---

## Backend Packaging

### Current Model

The API is run directly from source using a Python virtual environment:

```bash
cd api
. .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001
```

### Dependencies

All Python dependencies are listed in `api/requirements.txt` and installed into `api/.venv/`.

### No Containerization (Yet)

There is no Dockerfile for the API. To containerize it, a Dockerfile would need to:

1. Use a Python base image.
2. Copy `api/requirements.txt` and install dependencies.
3. Copy the source files (`main.py`, `models.py`, `schemas.py`, `auth.py`, `github_oauth.py`, `confab_manager.py`, `database.py`).
4. Copy the `alembic/` directory and `alembic.ini`.
5. Expose port 8001.
6. Run with Gunicorn + Uvicorn workers.

### No Python Package

The API is not packaged as a distributable Python package (no `setup.py`, `pyproject.toml`, or `setup.cfg` for packaging). It is intended to be run from source.

---

## Database Packaging

### Container Image

PostgreSQL runs as a Docker container defined in `docker-compose.yml`:

```yaml
image: postgres:18.1
container_name: confab-foundry-db
```

### Persistent Storage

Data is stored in a named Docker volume:

```yaml
volumes:
  postgres_data:
    driver: local
```

Volume mount: `postgres_data:/var/lib/postgresql/18/docker`

### Schema Management

The database schema is managed by Alembic migrations in `api/alembic/versions/`. Migrations must be applied after the database container starts:

```bash
cd api && . .venv/bin/activate && alembic upgrade head
```

---

## Deployment Artifacts Summary

For a full deployment, the following artifacts are needed:

1. **`ui/build/`** — Static frontend files, built with the correct `VITE_API_URL`.
2. **`api/`** — Backend source code + `requirements.txt` + `alembic/` directory.
3. **`docker-compose.yml`** — PostgreSQL container definition (or equivalent managed database).
4. **`api/.env`** — Backend environment configuration (or equivalent secrets injection).

There is no single deployable package or container that bundles all components together. Each is deployed to its own host or service.
