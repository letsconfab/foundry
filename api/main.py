"""
Let's Confab API

App creation, middleware, and router registration.
Route handlers live in api/routes/*.
"""

import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from github_oauth import github_auth_router

# Route modules
from routes.auth_routes import router as auth_router
from routes.confab_routes import router as confab_router
from routes.learning_routes import router as learning_router
from routes.document_routes import router as document_router
from routes.conversation_routes import router as conversation_router
from routes.github_sync_routes import router as sync_router

# ---------------------------------------------------------------------------
# Create database tables
# ---------------------------------------------------------------------------

try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Warning: Could not connect to database: {e}")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Let's Confab API", version="2.0.5")

# CORS
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
allowed_origins = (
    [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
    if allowed_origins_env
    else ["http://localhost:3002"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

# GitHub OAuth callback router (has its own prefix handling)
app.include_router(github_auth_router, prefix="/auth/github", tags=["github"])

# Auth (register, login, me, github connect/login/repos)
app.include_router(auth_router, prefix="/auth")

# Confabs CRUD, export, definition files
app.include_router(confab_router)

# Confab learnings
app.include_router(learning_router)

# Document store V2
app.include_router(document_router)

# Threads, participants, messages, chat
app.include_router(conversation_router)

# Admin + GitHub sync + users list
app.include_router(sync_router)


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "Let's Confab API", "version": app.version}


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
