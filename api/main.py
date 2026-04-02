"""
Let's Confab API - Simplified Route Structure

Routes:
- Auth: register, login, me, github/*
- Confabs: CRUD + learnings
- Threads: CRUD + participants + chat
- Admin: system-status, sync-to-github
"""

import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Tuple, Literal
import datetime
import logging
import re

logger = logging.getLogger(__name__)

from database import get_db, engine, Base
from models import User, Confab, ConfabLearning, GitHubAccount, Thread, ThreadParticipant, Message
from schemas import (
    # User
    UserCreate, UserLogin, UserResponse, UserListItem,
    # GitHub
    GitHubConnect, GitHubLogin,
    # Confab
    ConfabCreate, ConfabUpdate, ConfabResponse, ConfabListItem,
    # Learning
    LearningCreate, LearningUpdate, LearningResponse,
    # Thread
    ThreadCreate, ThreadResponse, ThreadWithParticipants,
    # Participant
    ParticipantAdd, ParticipantResponse,
    # Message & Chat
    MessageCreate, MessageResponse, ChatRequest, ChatResponse,
    # Admin
    SystemStatusResponse, GitHubSyncRequest, GitHubSyncResponse,
    # Definition files
    DefinitionFilesRefreshResponse, DefinitionFilesCommitRequest, DefinitionFilesCommitResponse,
)
from auth import create_access_token, verify_token, get_password_hash, verify_password
from github_oauth import github_auth_router, get_github_repos, get_github_primary_email
from github_service import GitHubService, GitHubServiceError, FileNotFoundError as GitHubFileNotFoundError
from llm_service import ask_llm
from foreman import Foreman
from oasf_export import export_confab_to_oasf_yaml, generate_all_export_files

# Create database tables
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Warning: Could not connect to database: {e}")

app = FastAPI(title="Let's Confab API", version="2.0.0")

# CORS middleware
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

security = HTTPBearer()
app.include_router(github_auth_router, prefix="/auth/github", tags=["github"])


# =============================================================================
# Auth Helper
# =============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = db.query(User).filter(User.id == payload.get("user_id")).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# =============================================================================
# Root
# =============================================================================

@app.get("/")
async def root():
    return {"message": "Let's Confab API", "version": "2.0.0"}


def _slugify(value: str) -> str:
    """Slugify text for stable folder names."""
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "untitled-confab"


def _normalize_repo_path(path: str) -> str:
    return "/".join([p for p in path.replace("\\", "/").split("/") if p not in ("", ".")])


def _is_path_within_prefix(path: str, prefix: str) -> bool:
    """Path guard to ensure writes stay in a user-owned confab folder."""
    normalized = _normalize_repo_path(path)
    normalized_prefix = _normalize_repo_path(prefix)
    if ".." in normalized.split("/"):
        return False
    return normalized == normalized_prefix or normalized.startswith(f"{normalized_prefix}/")


def _guardrails_to_markdown(confab_name: str, guardrails: Optional[List[Dict[str, Any]]]) -> str:
    """Render guardrails JSON into markdown."""
    title = f"# Guardrails for {confab_name}\n\n"
    if not guardrails:
        return title + "_No guardrails defined yet._\n"

    lines = [title, "## Rules\n"]
    for idx, rule in enumerate(guardrails, 1):
        if not isinstance(rule, dict):
            continue
        text = str(rule.get("rule", "")).strip()
        if not text:
            continue
        severity = str(rule.get("severity", "error")).strip() or "error"
        enabled = bool(rule.get("enabled", True))
        status = "enabled" if enabled else "disabled"
        lines.append(f"{idx}. {text}  \n")
        lines.append(f"   - severity: `{severity}`  \n")
        lines.append(f"   - status: `{status}`\n")
    return "".join(lines).strip() + "\n"


def _guardrails_from_markdown(markdown: str) -> List[Dict[str, Any]]:
    """
    Parse markdown into structured guardrail objects.
    Accepts ordered list items (`1. rule`) and bullet items (`- rule`).
    """
    rules: List[Dict[str, Any]] = []
    lines = (markdown or "").splitlines()
    for line in lines:
        stripped = line.strip()
        numbered = re.match(r"^\d+\.\s+(.*)$", stripped)
        bulleted = re.match(r"^[-*]\s+(.*)$", stripped)
        match = numbered or bulleted
        if not match:
            continue
        text = match.group(1).strip()
        if not text or text.startswith("severity:") or text.startswith("status:"):
            continue
        rules.append({
            "id": f"gr-{len(rules) + 1}",
            "rule": text,
            "severity": "error",
            "enabled": True,
        })

    # Fallback for freeform markdown with no list lines.
    if not rules and (markdown or "").strip():
        rules.append({
            "id": "gr-1",
            "rule": (markdown or "").strip(),
            "severity": "error",
            "enabled": True,
        })

    return rules


def _resolve_confab_namespace(current_user: User, github_account: Optional[GitHubAccount]) -> str:
    if github_account and github_account.github_username:
        return f"gh-{_slugify(github_account.github_username)}"
    return f"u-{current_user.id}"


def _resolve_or_set_confab_folder(
    confab: Confab,
    current_user: User,
    github_account: Optional[GitHubAccount],
    db: Session
) -> str:
    """Assign immutable confab folder path once and reuse forever."""
    if confab.github_path:
        return confab.github_path

    confab_slug = _slugify(confab.name)
    confab.github_path = f"{confab_slug}-c{confab.id}"
    db.commit()
    db.refresh(confab)
    return confab.github_path


def _resolve_github_target(
    current_user: User,
    confab: Confab,
    db: Session
) -> Tuple[GitHubService, Optional[GitHubAccount], bool]:
    """
    Resolve GitHub target/service.
    - GitHub-connected users: selected repo.
    - Email/password users: letsconfab/registry using service token.

    Returns: (service, github_account, is_registry)
    Note: Always commit to the default branch (main) - no confab-specific branches.
    """
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()

    if github_account:
        if not github_account.access_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub access token missing")
        repo_owner = github_account.selected_org or github_account.github_username
        repo_name = github_account.selected_repo
        service = GitHubService(
            access_token=github_account.access_token,
            repo_owner=repo_owner,
            repo_name=repo_name,
        )
        return service, github_account, False

    registry_token = os.getenv("REGISTRY_GITHUB_TOKEN")
    if not registry_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registry sync token missing. Set REGISTRY_GITHUB_TOKEN on the API server."
        )

    repo_owner = os.getenv("REGISTRY_REPO_OWNER", "letsconfab")
    repo_name = os.getenv("REGISTRY_REPO_NAME", "registry")
    service = GitHubService(
        access_token=registry_token,
        repo_owner=repo_owner,
        repo_name=repo_name,
    )
    return service, github_account, True


# =============================================================================
# Auth Routes
# =============================================================================

@app.post("/auth/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    db_user = User(
        name=user.name,
        email=user.email,
        password_hash=get_password_hash(user.password),
        country=user.country,
        timezone=user.timezone
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    access_token = create_access_token(data={"user_id": db_user.id})
    return UserResponse(
        id=db_user.id, name=db_user.name, email=db_user.email,
        country=db_user.country, timezone=db_user.timezone,
        github_connected=False, access_token=access_token,
        created_at=db_user.created_at, updated_at=db_user.updated_at,
    )


@app.post("/auth/login", response_model=UserResponse)
async def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(data={"user_id": db_user.id})
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == db_user.id).first()

    return UserResponse(
        id=db_user.id, name=db_user.name, email=db_user.email,
        country=db_user.country, timezone=db_user.timezone,
        github_connected=github_account is not None, access_token=access_token,
        created_at=db_user.created_at, updated_at=db_user.updated_at,
    )


@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()
    return UserResponse(
        id=current_user.id, name=current_user.name, email=current_user.email,
        country=current_user.country, timezone=current_user.timezone,
        github_connected=github_account is not None,
        created_at=current_user.created_at, updated_at=current_user.updated_at,
    )


@app.get("/users", response_model=List[UserListItem])
async def list_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.name).all()
    return [UserListItem.model_validate(u) for u in users]


@app.post("/auth/github/connect")
async def connect_github(
    github_data: GitHubConnect,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()
    if existing:
        existing.github_id = github_data.github_id
        existing.github_username = github_data.github_username
        existing.access_token = github_data.access_token
        existing.selected_repo = github_data.selected_repo
        existing.selected_org = github_data.selected_org
    else:
        db.add(GitHubAccount(
            user_id=current_user.id,
            github_id=github_data.github_id,
            github_username=github_data.github_username,
            access_token=github_data.access_token,
            selected_repo=github_data.selected_repo,
            selected_org=github_data.selected_org
        ))
    db.commit()
    return {"message": "GitHub account connected"}


@app.post("/auth/github/login", response_model=UserResponse)
async def github_login(github_data: GitHubLogin, db: Session = Depends(get_db)):
    github_email = await get_github_primary_email(github_data.access_token)
    if not github_email:
        github_email = f"{github_data.github_username}@users.noreply.github.com"

    db_user = db.query(User).filter(User.email == github_email).first()
    if not db_user:
        db_user = User(
            name=github_data.github_username,
            email=github_email,
            password_hash=get_password_hash(os.urandom(24).hex()),
            country="other",
            timezone="utc",
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)

    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == db_user.id).first()
    if github_account:
        github_account.github_id = github_data.github_id
        github_account.github_username = github_data.github_username
        github_account.access_token = github_data.access_token
        github_account.selected_repo = github_data.selected_repo
        github_account.selected_org = github_data.selected_org
    else:
        db.add(GitHubAccount(
            user_id=db_user.id,
            github_id=github_data.github_id,
            github_username=github_data.github_username,
            access_token=github_data.access_token,
            selected_repo=github_data.selected_repo,
            selected_org=github_data.selected_org,
        ))
    db.commit()

    access_token = create_access_token(data={"user_id": db_user.id})
    return UserResponse(
        id=db_user.id, name=db_user.name, email=db_user.email,
        country=db_user.country, timezone=db_user.timezone,
        github_connected=True, access_token=access_token,
        created_at=db_user.created_at, updated_at=db_user.updated_at,
    )


@app.get("/auth/github/repos")
async def get_user_github_repos(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()
    if not github_account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub not connected")
    repos = await get_github_repos(github_account.access_token)
    return {"repos": repos}


# =============================================================================
# Confab Routes
# =============================================================================

@app.get("/confabs", response_model=List[ConfabListItem])
async def list_confabs(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    confabs = db.query(Confab).filter(Confab.user_id == current_user.id).order_by(Confab.created_at.desc()).all()
    return [ConfabListItem.model_validate(c) for c in confabs]


@app.post("/confabs", response_model=ConfabResponse)
async def create_confab(
    confab: ConfabCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_confab = Confab(
        name=confab.name,
        description=confab.description,
        user_id=current_user.id,
        status=confab.status,
        model_provider=confab.model_provider,
        model_name=confab.model_name,
        temperature=confab.temperature,
    )
    db.add(db_confab)
    db.commit()
    db.refresh(db_confab)
    return ConfabResponse.model_validate(db_confab)


@app.get("/confabs/{confab_id}", response_model=ConfabResponse)
async def get_confab(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")
    return ConfabResponse.model_validate(confab)


@app.put("/confabs/{confab_id}", response_model=ConfabResponse)
async def update_confab(
    confab_id: int,
    update: ConfabUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    # Update fields if provided
    if update.name is not None:
        confab.name = update.name
    if update.description is not None:
        confab.description = update.description
    if update.status is not None:
        confab.status = update.status
    if update.purpose is not None:
        confab.purpose = update.purpose
    if update.guardrails is not None:
        confab.guardrails = [g.model_dump() for g in update.guardrails]
    if update.tests is not None:
        confab.tests = [t.model_dump() for t in update.tests]
    if update.skills is not None:
        confab.skills = update.skills
    if update.domains is not None:
        confab.domains = update.domains
    if update.model_provider is not None:
        confab.model_provider = update.model_provider
    if update.model_name is not None:
        confab.model_name = update.model_name
    if update.temperature is not None:
        confab.temperature = update.temperature

    # Increment version
    try:
        parts = confab.version.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        confab.version = ".".join(parts)
    except (ValueError, IndexError):
        confab.version = "1.0.1"

    # Regenerate OASF yaml
    confab.oasf_yaml = export_confab_to_oasf_yaml(confab, db)

    db.commit()
    db.refresh(confab)
    return ConfabResponse.model_validate(confab)


@app.get("/confabs/{confab_id}/export")
async def export_confab_oasf(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export a confab as OASF-compliant files.
    Returns agent.oasf.yaml, PURPOSE.md, GUARDRAILS.md, TESTS.md
    """
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    files = generate_all_export_files(confab, db)

    # Also update the cached oasf_yaml
    confab.oasf_yaml = files["agent.oasf.yaml"]
    db.commit()

    return {
        "confab_id": confab_id,
        "confab_name": confab.name,
        "version": confab.version,
        "files": files
    }


@app.post("/confabs/{confab_id}/definition-files/refresh", response_model=DefinitionFilesRefreshResponse)
async def refresh_definition_files(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Pull latest PURPOSE.md and GUARDRAILS.md from GitHub and hydrate DB fields.
    """
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    try:
        github_service, github_account, _ = _resolve_github_target(current_user, confab, db)
    except HTTPException as e:
        # GitHub not configured - return current DB state without remote sync
        return DefinitionFilesRefreshResponse(
            confab_id=confab.id,
            purpose=confab.purpose,
            guardrails_markdown=_guardrails_to_markdown(confab.name, confab.guardrails) if confab.guardrails else None,
            remote_branch=None,
            remote_source="none",
            refreshed_at=datetime.datetime.now(datetime.timezone.utc),
        )

    confab_folder = _resolve_or_set_confab_folder(confab, current_user, github_account, db)
    file_prefix = confab_folder

    purpose_path = f"{file_prefix}/PURPOSE.md"
    guardrails_path = f"{file_prefix}/GUARDRAILS.md"

    purpose_content: Optional[str] = None
    guardrails_md: Optional[str] = None
    source: Literal["default", "none"] = "none"
    source_branch: Optional[str] = None

    # Get the default branch (main) - we always commit directly to it
    try:
        default_branch = await github_service.get_default_branch()
    except GitHubServiceError:
        # Repo not accessible - return current DB state
        return DefinitionFilesRefreshResponse(
            confab_id=confab.id,
            purpose=confab.purpose,
            guardrails_markdown=_guardrails_to_markdown(confab.name, confab.guardrails) if confab.guardrails else None,
            remote_branch=None,
            remote_source="none",
            refreshed_at=datetime.datetime.now(datetime.timezone.utc),
        )

    # Look for files on the default branch only (no confab-specific branches)
    try:
        purpose_content = await github_service.get_file_contents(purpose_path, branch=default_branch)
        source = "default"
        source_branch = default_branch
    except GitHubFileNotFoundError:
        pass
    except GitHubServiceError:
        # Repo not accessible - return current DB state
        return DefinitionFilesRefreshResponse(
            confab_id=confab.id,
            purpose=confab.purpose,
            guardrails_markdown=_guardrails_to_markdown(confab.name, confab.guardrails) if confab.guardrails else None,
            remote_branch=None,
            remote_source="none",
            refreshed_at=datetime.datetime.now(datetime.timezone.utc),
        )

    try:
        guardrails_md = await github_service.get_file_contents(guardrails_path, branch=default_branch)
        source = "default"
        source_branch = default_branch
    except GitHubFileNotFoundError:
        pass
    except GitHubServiceError:
        pass  # Continue with what we have

    # Hydrate DB from remote files where available
    changed = False
    if purpose_content is not None and confab.purpose != purpose_content:
        confab.purpose = purpose_content
        changed = True
    if guardrails_md is not None:
        parsed_guardrails = _guardrails_from_markdown(guardrails_md)
        if confab.guardrails != parsed_guardrails:
            confab.guardrails = parsed_guardrails
            changed = True

    if changed:
        db.commit()
        db.refresh(confab)

    return DefinitionFilesRefreshResponse(
        confab_id=confab.id,
        purpose=purpose_content,
        guardrails_markdown=guardrails_md,
        remote_branch=source_branch,
        remote_source=source,
        refreshed_at=datetime.datetime.now(datetime.timezone.utc),
    )


@app.post("/confabs/{confab_id}/definition-files/accept-and-commit", response_model=DefinitionFilesCommitResponse)
async def accept_and_commit_definition_files(
    confab_id: int,
    request: DefinitionFilesCommitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Commit PURPOSE.md and/or GUARDRAILS.md in a single batch commit.
    """
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    now = datetime.datetime.now(datetime.timezone.utc)

    # Check if there's content to save
    has_purpose = request.include_purpose and confab.purpose and confab.purpose.strip()
    has_guardrails = request.include_guardrails and confab.guardrails

    if not has_purpose and not has_guardrails:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No definition files available to commit")

    # Try to resolve GitHub target - if it fails, save locally only
    github_service = None
    branch_name = None
    confab_folder = None
    github_error_message = None

    try:
        github_service, github_account, _ = _resolve_github_target(current_user, confab, db)
        confab_folder = _resolve_or_set_confab_folder(confab, current_user, github_account, db)

        # Ensure repo exists before attempting operations (auto-creates "confabs" if needed)
        repo_ok, repo_error = await github_service.ensure_repo_exists()
        if not repo_ok:
            return DefinitionFilesCommitResponse(
                confab_id=confab.id,
                branch=None,
                folder_path=None,
                committed_files=[],
                commit_sha=None,
                status="saved-locally",
                synced_at=now,
                message=repo_error or "Could not access or create GitHub repository.",
            )

        # Commit directly to the default branch (main)
        branch_name = await github_service.get_default_branch()
    except HTTPException as e:
        github_error_message = "GitHub not configured. Connect your GitHub account or ask an admin to set REGISTRY_GITHUB_TOKEN."
        github_service = None
    except GitHubServiceError as e:
        github_error_message = f"Cannot access GitHub repository: {str(e)}"
        github_service = None

    # If GitHub isn't available, return saved-locally status
    if github_service is None:
        return DefinitionFilesCommitResponse(
            confab_id=confab.id,
            branch=None,
            folder_path=None,
            committed_files=[],
            commit_sha=None,
            status="saved-locally",
            synced_at=now,
            message=github_error_message,
        )

    file_prefix = confab_folder
    candidate_files: Dict[str, str] = {}
    if has_purpose:
        candidate_files[f"{file_prefix}/PURPOSE.md"] = confab.purpose
    if has_guardrails:
        guardrails_markdown = _guardrails_to_markdown(confab.name, confab.guardrails)
        if guardrails_markdown.strip():
            candidate_files[f"{file_prefix}/GUARDRAILS.md"] = guardrails_markdown

    # Path guard enforcement
    for path in candidate_files.keys():
        if not _is_path_within_prefix(path, file_prefix):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Blocked file path outside allowed confab folder: {path}"
            )

    # Commit only files that differ from remote branch content
    changed_files: Dict[str, str] = {}
    committed_file_names: List[str] = []
    for path, content in candidate_files.items():
        remote_content: Optional[str] = None
        try:
            remote_content = await github_service.get_file_contents(path, branch=branch_name)
        except GitHubFileNotFoundError:
            remote_content = None

        if remote_content != content:
            changed_files[path] = content
            committed_file_names.append(path.split("/")[-1])

    now = datetime.datetime.now(datetime.timezone.utc)

    if not changed_files:
        confab.github_synced_at = now
        confab.github_sync_version = confab.version
        db.commit()
        db.refresh(confab)
        return DefinitionFilesCommitResponse(
            confab_id=confab.id,
            branch=branch_name,
            folder_path=confab_folder,
            committed_files=[],
            commit_sha=None,
            status="no-op",
            synced_at=now,
        )

    base_commit_message = (request.commit_message or "accept-changes-and-commit").strip()
    commit_message = f"Co Authored by foreman@letsconfab.org: {base_commit_message}"

    result = await github_service.create_or_update_files_batch(
        files=changed_files,
        branch=branch_name,
        message=commit_message
    )

    # Update sync metadata
    confab.github_synced_at = now
    confab.github_sync_version = confab.version
    db.commit()
    db.refresh(confab)

    return DefinitionFilesCommitResponse(
        confab_id=confab.id,
        branch=branch_name,
        folder_path=confab_folder,
        committed_files=committed_file_names,
        commit_sha=result.get("commit_sha"),
        status="committed",
        synced_at=now,
    )


@app.delete("/confabs/{confab_id}")
async def delete_confab(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    # Try to delete the GitHub folder if it exists
    github_folder_deleted = False
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()

    if github_account and github_account.access_token:
        repo_owner = github_account.selected_org or github_account.github_username
        repo_name = github_account.selected_repo
        github_service = GitHubService(
            access_token=github_account.access_token,
            repo_owner=repo_owner,
            repo_name=repo_name,
        )

        # Build list of potential folder paths to try deleting
        # - Current format: confab.github_path (e.g., "myconfab-c123")
        # - Legacy format: confabs/{name}/ (for older confabs created before path standardization)
        paths_to_try = []
        if confab.github_path:
            paths_to_try.append(confab.github_path)

        # Add legacy path format as fallback
        if confab.name:
            legacy_path = f"confabs/{_slugify(confab.name)}"
            if legacy_path not in paths_to_try:
                paths_to_try.append(legacy_path)

        for folder_path in paths_to_try:
            try:
                deleted = await github_service.delete_folder(
                    folder_path=folder_path,
                    commit_message=f"Delete confab: {confab.name}"
                )
                if deleted:
                    github_folder_deleted = True
                    logger.info(f"Deleted GitHub folder {folder_path} for confab {confab_id}")
                    break  # Successfully deleted, no need to try other paths
            except Exception as e:
                logger.warning(f"Failed to delete GitHub folder {folder_path} for confab {confab_id}: {e}")
                # Continue trying other paths

    db.delete(confab)
    db.commit()
    return {
        "message": "Confab deleted",
        "github_folder_deleted": github_folder_deleted
    }


# =============================================================================
# Confab Learnings Routes
# =============================================================================

@app.get("/confabs/{confab_id}/learnings", response_model=List[LearningResponse])
async def list_learnings(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    learnings = db.query(ConfabLearning).filter(ConfabLearning.confab_id == confab_id).order_by(ConfabLearning.created_at.desc()).all()
    return [LearningResponse.model_validate(l) for l in learnings]


@app.post("/confabs/{confab_id}/learnings", response_model=LearningResponse)
async def create_learning(
    confab_id: int,
    learning: LearningCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    db_learning = ConfabLearning(
        confab_id=confab_id,
        content=learning.content,
        summary=learning.summary,
        tags=learning.tags,
        source=learning.source,
        source_thread_id=learning.source_thread_id,
        author_type="user",
        author_id=current_user.id,
        status="draft",
    )
    db.add(db_learning)
    db.commit()
    db.refresh(db_learning)
    return LearningResponse.model_validate(db_learning)


@app.put("/confabs/{confab_id}/learnings/{learning_id}", response_model=LearningResponse)
async def update_learning(
    confab_id: int,
    learning_id: int,
    update: LearningUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    learning = db.query(ConfabLearning).filter(ConfabLearning.id == learning_id, ConfabLearning.confab_id == confab_id).first()
    if not learning:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning not found")

    if update.content is not None:
        learning.content = update.content
    if update.summary is not None:
        learning.summary = update.summary
    if update.tags is not None:
        learning.tags = update.tags
    if update.status is not None:
        learning.status = update.status

    db.commit()
    db.refresh(learning)
    return LearningResponse.model_validate(learning)


@app.delete("/confabs/{confab_id}/learnings/{learning_id}")
async def delete_learning(
    confab_id: int,
    learning_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    learning = db.query(ConfabLearning).filter(ConfabLearning.id == learning_id, ConfabLearning.confab_id == confab_id).first()
    if not learning:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning not found")

    db.delete(learning)
    db.commit()
    return {"message": "Learning deleted"}


# =============================================================================
# Document Store Routes
# =============================================================================

from document_store import (
    DocumentService,
    DocumentUploadRequest,
    DocumentResponse,
    DocumentListItem,
    DocumentUploadResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
    ContextRequest,
    ContextResponse,
    DocumentStoreStats,
)
from fastapi import UploadFile, File, Form


@app.post("/confabs/{confab_id}/documents", response_model=DocumentUploadResponse)
async def upload_document(
    confab_id: int,
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and index a document for RAG retrieval."""
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    # Read file content
    content = await file.read()

    # Parse metadata if provided
    import json
    meta = json.loads(metadata) if metadata else None

    # Determine content type
    content_type = file.content_type or "text/plain"
    if file.filename.endswith(".md"):
        content_type = "text/markdown"
    elif file.filename.endswith(".pdf"):
        content_type = "application/pdf"

    # For text files, decode content
    if content_type in ["text/plain", "text/markdown"]:
        content = content.decode("utf-8")

    service = DocumentService(db)
    result = await service.upload_document(
        confab_id=confab_id,
        content=content,
        filename=file.filename,
        content_type=content_type,
        metadata=meta
    )

    if result.status == "failed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.error_message)

    return DocumentUploadResponse(
        document_id=result.document_id,
        filename=result.filename,
        chunk_count=result.chunk_count,
        status=result.status,
        error_message=result.error_message
    )


@app.get("/confabs/{confab_id}/documents", response_model=List[DocumentListItem])
async def list_documents(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all documents in a confab's document store."""
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    service = DocumentService(db)
    docs = await service.list_documents(confab_id)
    return [DocumentListItem(**doc) for doc in docs]


@app.get("/confabs/{confab_id}/documents/stats", response_model=DocumentStoreStats)
async def get_document_stats(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get document store statistics."""
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    service = DocumentService(db)
    stats = await service.get_stats(confab_id)
    return DocumentStoreStats(**stats)


@app.get("/confabs/{confab_id}/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    confab_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific document's details."""
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    service = DocumentService(db)
    doc = await service.get_document(confab_id, document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return DocumentResponse(**doc)


@app.delete("/confabs/{confab_id}/documents/{document_id}")
async def delete_document(
    confab_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a document from the document store."""
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    service = DocumentService(db)
    success = await service.delete_document(confab_id, document_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return {"message": "Document deleted"}


@app.post("/confabs/{confab_id}/documents/search", response_model=DocumentSearchResponse)
async def search_documents(
    confab_id: int,
    body: DocumentSearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Semantic search across a confab's documents."""
    confab = db.query(Confab).filter(Confab.id == confab_id, Confab.user_id == current_user.id).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")

    service = DocumentService(db)
    results = await service.search(confab_id, body.query, body.top_k, body.filter_type)

    return DocumentSearchResponse(
        results=[
            {
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
                "filename": r.filename,
                "content": r.content,
                "score": r.score,
                "chunk_index": r.chunk_index,
                "source_type": r.source_type,
                "metadata": r.metadata
            }
            for r in results
        ],
        query=body.query,
        total_results=len(results)
    )


# =============================================================================
# Thread Routes
# =============================================================================

@app.get("/threads", response_model=List[ThreadResponse])
async def list_threads(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    threads = db.query(Thread).filter(Thread.owner_user_id == current_user.id).order_by(Thread.created_at.desc()).all()
    return [ThreadResponse.model_validate(t) for t in threads]


@app.post("/threads", response_model=ThreadResponse)
async def create_thread(
    body: ThreadCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_thread = Thread(name=body.name, owner_user_id=current_user.id)
    db.add(db_thread)
    db.commit()
    db.refresh(db_thread)

    # Add owner as participant
    owner_participant = ThreadParticipant(
        thread_id=db_thread.id,
        participant_type="user",
        participant_id=current_user.id,
        role="owner",
    )
    db.add(owner_participant)
    db.commit()

    return ThreadResponse.model_validate(db_thread)


@app.get("/threads/{thread_id}", response_model=ThreadWithParticipants)
async def get_thread(
    thread_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    participants = db.query(ThreadParticipant).filter(ThreadParticipant.thread_id == thread_id).all()

    return ThreadWithParticipants(
        id=thread.id,
        name=thread.name,
        owner_user_id=thread.owner_user_id,
        created_at=thread.created_at,
        participants=[ParticipantResponse.model_validate(p) for p in participants]
    )


@app.delete("/threads/{thread_id}")
async def delete_thread(
    thread_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    db.delete(thread)
    db.commit()
    return {"message": "Thread deleted"}


# =============================================================================
# Thread Participants Routes
# =============================================================================

@app.get("/threads/{thread_id}/participants", response_model=List[ParticipantResponse])
async def list_participants(
    thread_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    participants = db.query(ThreadParticipant).filter(ThreadParticipant.thread_id == thread_id, ThreadParticipant.is_active == True).all()
    return [ParticipantResponse.model_validate(p) for p in participants]


@app.post("/threads/{thread_id}/participants", response_model=ParticipantResponse)
async def add_participant(
    thread_id: int,
    participant: ParticipantAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    # Validate participant exists (for user/confab types)
    if participant.participant_type == "user" and participant.participant_id:
        if not db.query(User).filter(User.id == participant.participant_id).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")
    elif participant.participant_type == "confab" and participant.participant_id:
        if not db.query(Confab).filter(Confab.id == participant.participant_id).first():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confab not found")
    elif participant.participant_type == "system" and not participant.system_agent_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="System agent name required")

    db_participant = ThreadParticipant(
        thread_id=thread_id,
        participant_type=participant.participant_type,
        participant_id=participant.participant_id,
        system_agent_name=participant.system_agent_name,
        role=participant.role,
    )
    db.add(db_participant)
    db.commit()
    db.refresh(db_participant)
    return ParticipantResponse.model_validate(db_participant)


@app.delete("/threads/{thread_id}/participants/{participant_id}")
async def remove_participant(
    thread_id: int,
    participant_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    participant = db.query(ThreadParticipant).filter(
        ThreadParticipant.id == participant_id,
        ThreadParticipant.thread_id == thread_id
    ).first()
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")

    # Soft delete - mark as inactive
    participant.is_active = False
    participant.left_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    return {"message": "Participant removed"}


# =============================================================================
# Messages Routes
# =============================================================================

@app.get("/threads/{thread_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    thread_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    messages = db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.created_at).all()
    return [MessageResponse.model_validate(m) for m in messages]


@app.post("/threads/{thread_id}/messages", response_model=MessageResponse)
async def add_message(
    thread_id: int,
    request: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a message to a thread without triggering agent responses.
    Used for saving initial greetings, persisting messages, etc.
    For full chat with agent responses, use POST /threads/{id}/chat instead.
    """
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    # Calculate depth for subthreading
    depth = 0
    if request.in_reply_to:
        parent = db.query(Message).filter(Message.id == request.in_reply_to).first()
        if parent:
            depth = parent.depth + 1

    message = Message(
        thread_id=thread_id,
        sender_type=request.sender_type,
        sender_id=request.sender_id or (current_user.id if request.sender_type == "user" else None),
        sender_name=request.sender_name or (current_user.name if request.sender_type == "user" else None),
        content=request.content,
        role=request.role,
        in_reply_to=request.in_reply_to,
        depth=depth,
        addressed_to=[a.model_dump() for a in request.addressed_to] if request.addressed_to else None,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return MessageResponse.model_validate(message)


# =============================================================================
# Chat Route (unified endpoint with auto-response)
# =============================================================================

async def should_agent_respond(message_content: str, addressed_to: Optional[List], agent_participant: ThreadParticipant, thread_context: List[Message]) -> bool:
    """Determine if an agent should respond to a message."""
    # If explicitly addressed to this agent, respond
    if addressed_to:
        for addr in addressed_to:
            if addr.get("type") == agent_participant.participant_type:
                if agent_participant.participant_type == "system":
                    if addr.get("name") == agent_participant.system_agent_name:
                        return True
                elif addr.get("id") == agent_participant.participant_id:
                    return True
        return False  # Addressed to someone else

    # Broadcast message - infer from context
    # For now, agents always respond to broadcasts in threads where they participate
    return True


@app.post("/threads/{thread_id}/chat", response_model=ChatResponse)
async def chat(
    thread_id: int,
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unified chat endpoint with automatic agent responses.

    1. Saves user message
    2. Queries thread participants for agents (confabs, system)
    3. For each agent, determines if it should respond (explicit addressing or inference)
    4. Generates and saves agent responses
    5. Returns all messages
    """
    thread = db.query(Thread).filter(Thread.id == thread_id, Thread.owner_user_id == current_user.id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    # Calculate depth for subthreading
    depth = 0
    if request.in_reply_to:
        parent = db.query(Message).filter(Message.id == request.in_reply_to).first()
        if parent:
            depth = parent.depth + 1

    # Save user message
    user_message = Message(
        thread_id=thread_id,
        sender_type="user",
        sender_id=current_user.id,
        sender_name=current_user.name,
        content=request.content,
        role="user",
        in_reply_to=request.in_reply_to,
        depth=depth,
        addressed_to=[a.model_dump() for a in request.addressed_to] if request.addressed_to else None,
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # Get agent participants
    agent_participants = db.query(ThreadParticipant).filter(
        ThreadParticipant.thread_id == thread_id,
        ThreadParticipant.is_active == True,
        ThreadParticipant.participant_type.in_(["confab", "system"])
    ).all()

    # Get thread context for inference
    thread_messages = db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.created_at).limit(20).all()

    agent_responses = []
    foreman_result = None  # Track Foreman's full result for V2 metadata

    for agent in agent_participants:
        # Check if agent should respond
        should_respond = await should_agent_respond(
            request.content,
            [a.model_dump() for a in request.addressed_to] if request.addressed_to else None,
            agent,
            thread_messages
        )

        if not should_respond:
            continue

        try:
            # Generate response based on agent type
            if agent.participant_type == "system" and agent.system_agent_name == "foreman":
                # Get the user's most recent confab in 'building' status
                confab = db.query(Confab).filter(
                    Confab.user_id == current_user.id,
                    Confab.status == "building"
                ).order_by(Confab.created_at.desc()).first()

                if confab:
                    foreman = Foreman(confab.id, db)
                    await foreman.initialize()
                    result = await foreman.process_message(request.content)
                    response_content = result.get("response", "")
                    # Capture full result for V2 metadata
                    foreman_result = result
                else:
                    response_content = "No confab is currently being built. Please start a new confab to begin."

                sender_name = "Foreman"

            elif agent.participant_type == "confab":
                # Get confab and generate response
                confab = db.query(Confab).filter(Confab.id == agent.participant_id).first()
                if not confab:
                    continue

                # Skip confab responses during building phase - Foreman handles this
                if confab.status == "building":
                    continue

                # Build context prompt
                context = f"You are {confab.name}. "
                if confab.purpose:
                    context += f"Your purpose: {confab.purpose}\n"
                if confab.guardrails:
                    context += f"Guardrails: {confab.guardrails}\n"

                context += "\nConversation:\n"
                for msg in thread_messages[-10:]:
                    role = "User" if msg.role == "user" else "Assistant"
                    context += f"{role}: {msg.content}\n"
                context += f"User: {request.content}\n"

                response_content = await ask_llm(prompt=context, temperature=confab.temperature)
                sender_name = confab.name

            else:
                continue

            # Save agent response
            agent_message = Message(
                thread_id=thread_id,
                sender_type=agent.participant_type,
                sender_id=agent.participant_id,
                sender_name=sender_name,
                content=response_content,
                role="assistant",
                in_reply_to=user_message.id,
                depth=user_message.depth,
            )
            db.add(agent_message)
            db.commit()
            db.refresh(agent_message)

            agent_responses.append(MessageResponse.model_validate(agent_message))

        except Exception as e:
            logger.error(f"Error generating response from agent {agent.id}: {e}")
            continue

    # Build foreman metadata if present
    foreman_metadata = None
    if foreman_result:
        from schemas import ForemanChatResponse, SetupProgressResponse, ForemanV2Metadata
        setup_progress = foreman_result.get("setup_progress")
        v2_data = foreman_result.get("v2_metadata")

        foreman_metadata = ForemanChatResponse(
            response=foreman_result.get("response", ""),
            confab_id=foreman_result.get("confab_id", 0),
            thread_id=thread_id,
            setup_progress=SetupProgressResponse(**setup_progress) if setup_progress else None,
            tool_calls=foreman_result.get("tool_calls", []),
            timestamp=datetime.datetime.fromisoformat(foreman_result.get("timestamp", datetime.datetime.now().isoformat())),
            v2_metadata=ForemanV2Metadata(
                stage=v2_data.get("stage", ""),
                stage_status=v2_data.get("stage_status"),
                saved_fields=v2_data.get("saved_fields"),
                next_question=v2_data.get("next_question"),
                next_stage=setup_progress.get("current_stage") if setup_progress else None,
                clarification_needed=v2_data.get("stage_status") == "clarify" if v2_data else False,
            ) if v2_data else None,
            is_v2=v2_data is not None,
        )

    return ChatResponse(
        thread_id=thread_id,
        user_message=MessageResponse.model_validate(user_message),
        agent_responses=agent_responses,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        foreman_metadata=foreman_metadata,
    )


# =============================================================================
# Admin Routes
# =============================================================================

@app.get("/admin/system-status", response_model=SystemStatusResponse)
async def get_system_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_users = db.query(User).count()
    total_confabs = db.query(Confab).count()
    active_threads = db.query(Thread).count()

    return SystemStatusResponse(
        database="healthy",
        llm_service="healthy",
        github_service="healthy",
        active_threads=active_threads,
        total_confabs=total_confabs,
        total_users=total_users,
    )


@app.post("/admin/sync-to-github", response_model=GitHubSyncResponse)
async def sync_to_github(
    request: GitHubSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Sync confabs to GitHub as OASF-compliant artifacts."""
    # Get confabs to sync
    query = db.query(Confab).filter(Confab.user_id == current_user.id)
    if request.confab_ids:
        query = query.filter(Confab.id.in_(request.confab_ids))
    confabs = query.all()

    synced = 0
    failed = 0
    errors = []

    for confab in confabs:
        try:
            github_service, github_account, _ = _resolve_github_target(current_user, confab, db)

            # Generate OASF export files
            files = generate_all_export_files(confab, db)

            # Determine immutable confab folder path
            confab_folder = _resolve_or_set_confab_folder(confab, current_user, github_account, db)
            file_prefix = confab_folder

            # Commit directly to the default branch (main)
            default_branch = await github_service.get_default_branch()

            # Build path->content map and guard paths
            batch_files: Dict[str, str] = {}
            for filename, content in files.items():
                file_path = f"{file_prefix}/{filename}"
                if not _is_path_within_prefix(file_path, file_prefix):
                    raise GitHubServiceError(f"Blocked file path outside allowed prefix: {file_path}")
                batch_files[file_path] = content

            # Commit all files in one batch commit
            await github_service.create_or_update_files_batch(
                files=batch_files,
                branch=default_branch,
                message=f"Sync confab {confab.name} (v{confab.version})"
            )

            # Update sync state
            confab.oasf_yaml = files["agent.oasf.yaml"]
            confab.github_path = confab_folder
            confab.github_synced_at = datetime.datetime.now(datetime.timezone.utc)
            confab.github_sync_version = confab.version
            synced += 1

            logger.info(f"Synced confab {confab.id} to GitHub: {confab_folder}")

        except Exception as e:
            failed += 1
            errors.append({"confab_id": confab.id, "error": str(e)})
            logger.error(f"Failed to sync confab {confab.id}: {e}")

    db.commit()

    return GitHubSyncResponse(synced_count=synced, failed_count=failed, errors=errors)


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
