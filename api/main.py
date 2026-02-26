from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

import os
import json, re
from dotenv import load_dotenv

from database import get_db, engine, Base
from models import User, Confab, GitHubAccount, Thread, Message, ThreadMapping
from schemas import (
    UserCreate, UserLogin, UserResponse, UserListItem, ConfabCreate, ConfabResponse,
    GitHubConnect, GitHubLogin, ConfabConfig, SimpleConfabConfig,
    ThreadCreate, ThreadResponse, MessageCreate, MessageResponse,
    ThreadMappingCreate, ThreadMappingResponse, OllamaRequest, OllamaResponse,
)
from auth import create_access_token, verify_token, get_password_hash, verify_password
from github_oauth import github_auth_router, get_github_user, get_github_repos, get_github_primary_email
from confab_manager import (
    create_confab_in_github,
    update_confab_in_github,
    create_github_repository,
    initialize_confab_repository,
    create_confab_file_in_github,  # used by chat tools to push single files
    confab_manager,               # needed by _commit_file_for_confab
)
# import the setup-step tools so we can execute them when the agent asks
from agent_tools import (
    define_purpose, add_participant, configure_memory, add_tools_and_apis,
    guardrails, sample_io, review_and_save,
    # the following helpers are also exposed to the agent for extra flexibility
    get_purpose, search_knowledge_base, update_knowledge_base,
)
# === [CLAUDE: Import Ollama service for dynamic chat responses] ===
from ollama_service import ask_ollama, ollama_client

# Load environment variables
load_dotenv()

# Create database tables (with error handling)
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Warning: Could not connect to database: {e}")
    print("API will start but database operations will fail until database is available.")

app = FastAPI(title="Let's Confab API", version="1.0.0")

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

# Security
security = HTTPBearer()

# Include GitHub OAuth routes
app.include_router(github_auth_router, prefix="/auth/github", tags=["github"])

# Helper function to get current user
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    user = db.query(User).filter(User.id == payload.get("user_id")).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user

@app.get("/")
async def root():
    return {"message": "Let's Confab API"}

@app.post("/auth/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        name=user.name,
        email=user.email,
        password_hash=hashed_password,
        country=user.country,
        timezone=user.timezone
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create access token
    access_token = create_access_token(data={"user_id": db_user.id})
    
    return UserResponse(
        id=db_user.id,
        name=db_user.name,
        email=db_user.email,
        country=db_user.country,
        timezone=db_user.timezone,
        github_connected=False,
        access_token=access_token,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at,
    )

@app.post("/auth/login", response_model=UserResponse)
async def login(user: UserLogin, db: Session = Depends(get_db)):
    # Find user by email
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create access token
    access_token = create_access_token(data={"user_id": db_user.id})
    
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == db_user.id).first()
    
    return UserResponse(
        id=db_user.id,
        name=db_user.name,
        email=db_user.email,
        country=db_user.country,
        timezone=db_user.timezone,
        github_connected=github_account is not None,
        access_token=access_token,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at,
    )

@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()
    
    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        country=current_user.country,
        timezone=current_user.timezone,
        github_connected=github_account is not None,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@app.get("/users", response_model=list[UserListItem])
async def list_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List users from the users table (for participants). Returns id, name, email only."""
    users = db.query(User).order_by(User.name).all()
    return [UserListItem.model_validate(u) for u in users]

@app.post("/auth/github/connect")
async def connect_github(
    github_data: GitHubConnect,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if GitHub account is already connected
    existing_github = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()
    if existing_github:
        # Update existing connection
        existing_github.github_id = github_data.github_id
        existing_github.github_username = github_data.github_username
        existing_github.access_token = github_data.access_token
        existing_github.selected_repo = github_data.selected_repo
        existing_github.selected_org = github_data.selected_org
    else:
        # Create new GitHub connection
        github_account = GitHubAccount(
            user_id=current_user.id,
            github_id=github_data.github_id,
            github_username=github_data.github_username,
            access_token=github_data.access_token,
            selected_repo=github_data.selected_repo,
            selected_org=github_data.selected_org
        )
        db.add(github_account)
    
    db.commit()
    return {"message": "GitHub account connected successfully"}

@app.post("/auth/github/login", response_model=UserResponse)
async def github_login(github_data: GitHubLogin, db: Session = Depends(get_db)):
    # Fetch email from GitHub so we can identify/create the app user
    github_email = await get_github_primary_email(github_data.access_token)
    if not github_email:
        github_email = f"{github_data.github_username}@users.noreply.github.com"

    db_user = db.query(User).filter(User.email == github_email).first()
    if not db_user:
        # Create a new user with placeholder required fields
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

    # Upsert GitHubAccount association
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == db_user.id).first()
    if github_account:
        github_account.github_id = github_data.github_id
        github_account.github_username = github_data.github_username
        github_account.access_token = github_data.access_token
        github_account.selected_repo = github_data.selected_repo
        github_account.selected_org = github_data.selected_org
    else:
        github_account = GitHubAccount(
            user_id=db_user.id,
            github_id=github_data.github_id,
            github_username=github_data.github_username,
            access_token=github_data.access_token,
            selected_repo=github_data.selected_repo,
            selected_org=github_data.selected_org,
        )
        db.add(github_account)
    db.commit()

    access_token = create_access_token(data={"user_id": db_user.id})
    return UserResponse(
        id=db_user.id,
        name=db_user.name,
        email=db_user.email,
        country=db_user.country,
        timezone=db_user.timezone,
        github_connected=True,
        access_token=access_token,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at,
    )

@app.get("/auth/github/repos")
async def get_user_github_repos(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()
    if not github_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub account not connected"
        )
    
    repos = await get_github_repos(github_account.access_token)
    return {"repos": repos}

@app.post("/confabs", response_model=ConfabResponse)
async def create_confab(
    confab: ConfabCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Create confab in database
    db_confab = Confab(
        name=confab.name,
        description=confab.description,
        user_id=current_user.id,
        version="1.0.0",
        status="draft"
    )
    
    db.add(db_confab)
    db.commit()
    db.refresh(db_confab)
    
    # Create confab in GitHub
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()
    
    if github_account:
        # Use user's connected repo
        repo_owner = github_account.selected_org or github_account.github_username
        repo_name = github_account.selected_repo
    else:
        # Use default confabs repo
        repo_owner = "letsconfab"
        repo_name = "confabs"
    
    try:
        github_url = await create_confab_in_github(
            confab_name=confab.name,
            confab_data=confab.dict(),
            repo_owner=repo_owner,
            repo_name=repo_name,
            access_token=github_account.access_token if github_account else None
        )
        
        db_confab.github_url = github_url
        db.commit()
    except Exception as e:
        # If GitHub creation fails, we still have the confab in DB
        pass
    
    return ConfabResponse(
        id=db_confab.id,
        name=db_confab.name,
        description=db_confab.description,
        version=db_confab.version,
        status=db_confab.status,
        github_url=db_confab.github_url,
        created_at=db_confab.created_at,
        updated_at=db_confab.updated_at
    )

@app.get("/confabs", response_model=list[ConfabResponse])
async def get_user_confabs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confabs = db.query(Confab).filter(Confab.user_id == current_user.id).all()
    return [
        ConfabResponse(
            id=confab.id,
            name=confab.name,
            description=confab.description,
            version=confab.version,
            status=confab.status,
            github_url=confab.github_url,
            created_at=confab.created_at,
            updated_at=confab.updated_at
        )
        for confab in confabs
    ]

@app.get("/confabs/{confab_id}", response_model=ConfabResponse)
async def get_confab(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(
        Confab.id == confab_id,
        Confab.user_id == current_user.id
    ).first()
    
    if not confab:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Confab not found"
        )
    
    return ConfabResponse(
        id=confab.id,
        name=confab.name,
        description=confab.description,
        version=confab.version,
        status=confab.status,
        github_url=confab.github_url,
        created_at=confab.created_at,
        updated_at=confab.updated_at
    )

@app.put("/confabs/{confab_id}", response_model=ConfabResponse)
async def update_confab(
    confab_id: int,
    confab_update: ConfabCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(
        Confab.id == confab_id,
        Confab.user_id == current_user.id
    ).first()
    
    if not confab:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Confab not found"
        )
    
    # Update confab in database
    confab.name = confab_update.name
    confab.description = confab_update.description
    confab.version = str(float(confab.version) + 0.1)  # Increment version
    db.commit()
    
    # Update confab in GitHub
    if confab.github_url:
        github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()
        if github_account:
            try:
                await update_confab_in_github(
                    confab_name=confab.name,
                    confab_data=confab_update.dict(),
                    github_url=confab.github_url,
                    access_token=github_account.access_token
                )
            except Exception as e:
                pass  # Log error but don't fail the update
    
    db.refresh(confab)
    
    return ConfabResponse(
        id=confab.id,
        name=confab.name,
        description=confab.description,
        version=confab.version,
        status=confab.status,
        github_url=confab.github_url,
        created_at=confab.created_at,
        updated_at=confab.updated_at
    )

@app.delete("/confabs/{confab_id}")
async def delete_confab(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    confab = db.query(Confab).filter(
        Confab.id == confab_id,
        Confab.user_id == current_user.id
    ).first()
    
    if not confab:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Confab not found"
        )
    
    db.delete(confab)
    db.commit()
    
    return {"message": "Confab deleted successfully"}


# --- Threads & Messages (review chats) ---
# Table 2: threads (thread_id/id, thread_name, createdAt, owner_user_id)
# Table 3: messages (id, thread_id, content, time)

@app.get("/threads", response_model=list[ThreadResponse])
async def list_threads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all chat threads for the current user (for reviewing chats)."""
    threads = db.query(Thread).filter(Thread.owner_user_id == current_user.id).order_by(Thread.created_at.desc()).all()
    return [ThreadResponse.model_validate(t) for t in threads]


@app.post("/threads", response_model=ThreadResponse)
async def create_thread(
    body: ThreadCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat thread."""
    db_thread = Thread(
        thread_name=body.thread_name,
        owner_user_id=current_user.id,
    )
    db.add(db_thread)
    db.commit()
    db.refresh(db_thread)
    return ThreadResponse.model_validate(db_thread)


@app.get("/threads/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a single thread (for review)."""
    thread = db.query(Thread).filter(
        Thread.id == thread_id,
        Thread.owner_user_id == current_user.id
    ).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return ThreadResponse.model_validate(thread)


@app.get("/threads/{thread_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    thread_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List messages in a thread (for reviewing chats)."""
    thread = db.query(Thread).filter(
        Thread.id == thread_id,
        Thread.owner_user_id == current_user.id
    ).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    messages = db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.time).all()
    return [MessageResponse.model_validate(m) for m in messages]


@app.post("/threads/{thread_id}/messages", response_model=MessageResponse)
async def add_message(
    thread_id: int,
    body: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a message to a thread."""
    thread = db.query(Thread).filter(
        Thread.id == thread_id,
        Thread.owner_user_id == current_user.id
    ).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    db_message = Message(
        thread_id=thread_id,
        content=body.content,
        role=body.role or "user",
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return MessageResponse.model_validate(db_message)

@app.post("/confabs/test-repo")
async def test_repo_initialization(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test GitHub repository initialization with dummy data"""
    try:
        # Get GitHub account for the user
        github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()
        
        if not github_account:
            # For users without GitHub, return a simulated success
            return {
                "message": "Test repository initialization simulated for email user",
                "repo_name": "letsconfab/confabs",
                "status": "simulated",
                "dummy_data": {
                    "purpose": "Test confab for demonstration purposes",
                    "created_at": "2024-01-01T00:00:00Z",
                    "test_files": ["README.md", "config.json", "example.py"]
                }
            }
        
        # For GitHub users, determine the repo owner and name from the database
        # (selected_org falls back to github_username if not set).
        repo_owner = github_account.selected_org or github_account.github_username
        repo_name = github_account.selected_repo

        # Check if repository exists, if not create it.  We always use the
        # selected repo name rather than defaulting to "confabs" here.
        try:
            repo_info = await create_github_repository(
                repo_name=repo_name,
                access_token=github_account.access_token,
                description=f"Confabs repository for {repo_owner}",
                private=False
            )
        except Exception:
            # Repository might already exist, just continue to initialization
            pass

        # Initialize repository with confab structure
        init_result = await initialize_confab_repository(
            repo_owner=repo_owner,
            repo_name=repo_name,
            access_token=github_account.access_token
        )
        
        if init_result["success"]:
            return {
                "message": f"Test repository '{repo_owner}/{repo_name}' initialized successfully",
                "repo_name": f"{repo_owner}/{repo_name}",
                "status": "success",
                "dummy_data": {
                    "purpose": f"Test confab for {github_account.github_username}",
                    "created_at": "2024-01-01T00:00:00Z",
                    "test_files": init_result["test_files"],
                    "github_username": github_account.github_username,
                    "pr_url": init_result.get("pr_url", "")
                }
            }
        else:
            raise Exception(init_result["error"])
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test repository initialization: {str(e)}"
        )


# === [CLAUDE: Ollama API Endpoints for Dynamic Chat Responses] ===
# These endpoints handle interactions with the Ollama LLM service

@app.get("/ollama/health")
async def ollama_health_check():
    """
    Check if Ollama service is running and accessible.
    Returns health status indicating if Ollama is available.
    """
    is_healthy = await ollama_client.health_check()
    return {
        "status": "healthy" if is_healthy else "unavailable",
        "ollama_url": ollama_client.base_url,
        "model": ollama_client.model,
        "healthy": is_healthy
    }


@app.get("/ollama/models")
async def ollama_list_models():
    """
    Get list of available models in Ollama.
    """
    try:
        models = await ollama_client.list_models()
        return models
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Ollama: {str(e)}"
        )


@app.post("/ollama/generate")
async def ollama_generate(request: OllamaRequest):
    """
    Generate a response from Ollama using the provided prompt.
    
    [CLAUDE: Direct endpoint for generating text with Ollama, useful for testing]
    """
    try:
        response = await ask_ollama(
            prompt=request.prompt,
            temperature=request.temperature
        )
        return {
            "model": ollama_client.model,
            "response": response,
            "success": True
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ollama service error: {str(e)}"
        )


# System prompt that instructs the LLM how to behave during the confab setup conversation.
SYSTEM_PROMPT = """You are a Confab Setup Agent.

You must:
- Detect which setup step the user is working on
- Call the correct tool
- Update step progress
- Guide user to next step

The agent also has access to several helper tools for inspecting or
updating configuration documents directly.  Every time a setup step is
completed the corresponding markdown file (PURPOSE.md, PARTICIPANTS.md,
MEMORY.md, INTEGRATIONS.md, GUARDRAILS.md, SAMPLE_IO.md, REVIEW.md,
or other knowledge‑base document) will be written to GitHub on a new
branch and a pull request will be opened.  The PR link will be returned
as part of the tool output.

Available steps:
1 Define Purpose
2 Add Participants
3 Configure Memory
4 Add Tools & APIs
5 Guardrails
6 Sample Inputs/Outputs
7 Review & Save

Helper tools:
- get_purpose(confab_id)                 # returns the current purpose text
- update_purpose(confab_id, purpose_text)  # save purpose (commits PURPOSE.md)
- search_knowledge_base(confab_id, query)  # look up stored memory documents
- update_knowledge_base(confab_id, file_name, information)  # save a memory file
"""


def _parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """Look for a JSON-like tool call in the model output.

    The agent is instructed to emit a JSON object such as:
    {"tool": "define_purpose", "args": {"confab_id":123, "purpose_text":"..."}}
    The function returns the parsed dictionary or None if nothing relevant is found.
    """
    try:
        obj = json.loads(text.strip())
        if isinstance(obj, dict) and "tool" in obj:
            return obj
    except Exception:
        pass
    # fallback: search for embedded JSON blob
    m = re.search(r"\{\s*\"tool\".*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


async def _commit_file_for_confab(
    db: Session,
    confab_id: int,
    file_path: str,
    content: str
) -> str:
    """Helper that looks up the user's GitHub account and commits a single file.

    If the confab or account cannot be found the function returns an empty
    string, otherwise it will return a message containing the pull request URL
    or an error description.
    """
    # fetch confab and owner
    confab = db.query(Confab).filter(Confab.id == confab_id).first()
    if not confab:
        return "[github] confab not found"
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == confab.user_id).first()
    if not github_account:
        return "[github] no GitHub connection for user"
    repo_owner = github_account.selected_org or github_account.github_username
    repo_name = github_account.selected_repo
    try:
        pr_url = await confab_manager.commit_confab_file(
            confab_name=confab.name,
            file_path=file_path,
            content=content,
            repo_owner=repo_owner,
            repo_name=repo_name,
            access_token=github_account.access_token,
        )
        return f"[github] pull request created: {pr_url}"
    except Exception as e:
        msg = str(e)
        # if repository is missing, attempt to create it automatically
        if "not found" in msg.lower():
            try:
                await create_github_repository(
                    repo_name=repo_name,
                    access_token=github_account.access_token,
                    description=f"Confabs repository for {github_account.github_username}",
                    private=False,
                )
                pr_url = await confab_manager.commit_confab_file(
                    confab_name=confab.name,
                    file_path=file_path,
                    content=content,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    access_token=github_account.access_token,
                )
                return f"[github] repository created, pull request created: {pr_url}"
            except Exception as e2:
                return f"[github error creating repo] {str(e2)}"
        return f"[github error] {msg}"


async def _execute_tool(tool_name: str, args: Dict[str, Any], db: Session) -> str:
    """Dispatch helper to run one of the agent_tools functions and perform GH commits."""
    # purpose helpers
    if tool_name == "define_purpose":
        result = define_purpose(db, args.get("confab_id"), args.get("purpose_text", ""))
        # commit updated purpose file to GitHub
        try:
            commit_info = await _commit_file_for_confab(db, args.get("confab_id"), "PURPOSE.md", args.get("purpose_text", ""))
            result += "\n" + commit_info
        except Exception as e:
            result += f"\n[github commit failed] {e}"
        return result
    elif tool_name == "get_purpose":
        val = get_purpose(db, args.get("confab_id"))
        return val or "(no purpose defined yet)"
    # participant/memory/tools previously existing
    elif tool_name == "add_participant":
        # update DB
        result = add_participant(db, args.get("confab_id"), args.get("email", ""))
        # commit participant list to GitHub
        try:
            cid = args.get("confab_id")
            confab = db.query(Confab).filter(Confab.id == cid).first()
            if confab:
                parts = (confab.config or {}).get("participants", [])
                md = "# Participants\n\n" + "\n".join(f"- {e}" for e in parts)
                ci = await _commit_file_for_confab(db, cid, "PARTICIPANTS.md", md)
                result += "\n" + ci
        except Exception as e:
            result += f"\n[github commit failed] {e}"
        return result
    elif tool_name == "configure_memory":
        result = configure_memory(db, args.get("confab_id"), args.get("memory_notes", ""), args.get("enable", True))
        try:
            cid = args.get("confab_id")
            confab = db.query(Confab).filter(Confab.id == cid).first()
            if confab:
                cfg = confab.config or {}
                notes = cfg.get("custom_settings", {}).get("memory_notes", "")
                enabled = cfg.get("conversation", {}).get("memory_enabled", False)
                md = f"# Memory (enabled={enabled})\n\n{notes}"
                ci = await _commit_file_for_confab(db, cid, "MEMORY.md", md)
                result += "\n" + ci
        except Exception as e:
            result += f"\n[github commit failed] {e}"
        return result
    elif tool_name == "add_tools_and_apis":
        result = add_tools_and_apis(db, args.get("confab_id"), args.get("tool_name", ""), args.get("api_key", ""))
        try:
            cid = args.get("confab_id")
            confab = db.query(Confab).filter(Confab.id == cid).first()
            if confab:
                apis = (confab.config or {}).get("integrations", {}).get("apis", [])
                md = "# Integrations\n\n" + "\n".join(f"- {a.get('name')} : {a.get('key')}" for a in apis)
                ci = await _commit_file_for_confab(db, cid, "INTEGRATIONS.md", md)
                result += "\n" + ci
        except Exception as e:
            result += f"\n[github commit failed] {e}"
        return result
    elif tool_name == "guardrails":
        result = guardrails(db, args.get("confab_id"), args.get("guardrails_text", ""))
        try:
            cid = args.get("confab_id")
            confab = db.query(Confab).filter(Confab.id == cid).first()
            if confab:
                guard = (confab.config or {}).get("custom_settings", {}).get("guardrails", "")
                md = f"# Guardrails\n\n{guard}"
                ci = await _commit_file_for_confab(db, cid, "GUARDRAILS.md", md)
                result += "\n" + ci
        except Exception as e:
            result += f"\n[github commit failed] {e}"
        return result
    elif tool_name == "sample_io":
        result = sample_io(db, args.get("confab_id"), args.get("sample_text", ""))
        try:
            cid = args.get("confab_id")
            confab = db.query(Confab).filter(Confab.id == cid).first()
            if confab:
                sample = (confab.config or {}).get("custom_settings", {}).get("sample_io", "")
                md = f"# Sample I/O\n\n{sample}"
                ci = await _commit_file_for_confab(db, cid, "SAMPLE_IO.md", md)
                result += "\n" + ci
        except Exception as e:
            result += f"\n[github commit failed] {e}"
        return result
    elif tool_name == "review_and_save":
        result = review_and_save(db, args.get("confab_id"))
        try:
            cid = args.get("confab_id")
            ci = await _commit_file_for_confab(db, cid, "REVIEW.md", "# Review\n\nConfab marked ready.")
            result += "\n" + ci
        except Exception as e:
            result += f"\n[github commit failed] {e}"
        return result
    # knowledge base helpers for memory
    elif tool_name == "search_knowledge_base":
        results = search_knowledge_base(db, args.get("confab_id"), args.get("query", ""))
        return json.dumps(results)
    elif tool_name == "update_knowledge_base":
        success = update_knowledge_base(db, args.get("confab_id"), args.get("file_name", ""), args.get("information", ""))
        msg = "Knowledge base updated." if success else "Failed to update knowledge base."
        if success:
            try:
                ci = await _commit_file_for_confab(db, args.get("confab_id"), args.get("file_name", ""), args.get("information", ""))
                msg += "\n" + ci
            except Exception as e:
                msg += f"\n[github commit failed] {e}"
        return msg
    else:
        return f"Unknown tool: {tool_name}"


@app.post("/threads/{thread_id}/chat")
async def chat_with_ollama(
    thread_id: int,
    request: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [CLAUDE: Main chat endpoint - takes user message, generates response from Ollama, and stores both in DB]

    This endpoint:
    1. Validates the thread belongs to the current user
    2. Stores the user's message in the database
    3. Calls Ollama to generate a response based on message history
    4. Stores the AI response in the database
    5. Returns both messages to the client
    """
    # Validate thread ownership
    thread = db.query(Thread).filter(
        Thread.id == thread_id,
        Thread.owner_user_id == current_user.id
    ).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    # [CLAUDE: Store user message in database]
    user_message = Message(
        thread_id=thread_id,
        content=request.content,
        role="user"
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    # [CLAUDE: Build context from message history for Ollama prompt]
    messages = db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.time).all()

    # Build prompt with conversation context
    context_prompt = SYSTEM_PROMPT + "\n\nBased on the following conversation, provide a helpful and coherent response.\n\n"
    for msg in messages[-10:]:  # Use last 10 messages for context
        role = "User" if msg.role == "user" else "Assistant"
        context_prompt += f"{role}: {msg.content}\n"

    try:
        # [CLAUDE: Generate response from Ollama using the full context]
        ai_response = await ask_ollama(
            prompt=context_prompt,
            temperature=0.7
        )

        # check for a tool call in the text
        tool_instr = _parse_tool_call(ai_response)
        if tool_instr:
            tool_result = await _execute_tool(tool_instr.get("tool"), tool_instr.get("args", {}), db)
            # compute progress summary from confab config if available
            try:
                cid = int(tool_instr.get("args", {}).get("confab_id"))
                confab = db.query(Confab).filter(Confab.id == cid).first()
                if confab:
                    cfg = confab.config or {}
                    completed = cfg.get("setup_steps_completed", [])
                    remaining = [i for i in range(1, 8) if i not in completed]
                    tool_result += f"\n[progress] completed steps: {completed}, remaining: {remaining}"
            except Exception:
                pass

            # store the tool output as its own message in the thread
            tool_message = Message(
                thread_id=thread_id,
                content=f"[tool:{tool_instr.get('tool')}] {tool_result}",
                role="assistant"
            )
            db.add(tool_message)
            db.commit()
            db.refresh(tool_message)

            # call the model again to continue conversation after tool
            context_prompt += f"Assistant: {ai_response}\nTool output: {tool_result}\n"
            ai_response = await ask_ollama(
                prompt=context_prompt,
                temperature=0.7
            )

        # [CLAUDE: Store final AI response in database]
        assistant_message = Message(
            thread_id=thread_id,
            content=ai_response,
            role="assistant"
        )
        db.add(assistant_message)
        db.commit()
        db.refresh(assistant_message)

        response_payload = {
            "user_message": MessageResponse.model_validate(user_message),
            "assistant_message": MessageResponse.model_validate(assistant_message),
            "success": True
        }
        if tool_instr and tool_message is not None:
            response_payload["tool_message"] = MessageResponse.model_validate(tool_message)
        return response_payload
    except Exception as e:
        # [CLAUDE: If Ollama fails, still return the user message but with error for assistant]
        error_message = Message(
            thread_id=thread_id,
            content=f"Error: Could not generate response - {str(e)}",
            role="assistant"
        )
        db.add(error_message)
        db.commit()
        db.refresh(error_message)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ollama service error: {str(e)}"
        )


@app.post("/thread-mappings", response_model=ThreadMappingResponse)
async def create_thread_mapping(
    mapping: ThreadMappingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [CLAUDE: Create a mapping between a confab and a thread]
    
    This links a conversation thread to a specific confab so we can track
    which confab a conversation belongs to.
    """
    # Validate confab ownership
    confab = db.query(Confab).filter(
        Confab.id == mapping.confab_id,
        Confab.user_id == current_user.id
    ).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")
    
    # Validate thread ownership
    thread = db.query(Thread).filter(
        Thread.id == mapping.thread_id,
        Thread.owner_user_id == current_user.id
    ).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    
    # Create mapping
    db_mapping = ThreadMapping(
        confab_id=mapping.confab_id,
        thread_id=mapping.thread_id
    )
    db.add(db_mapping)
    db.commit()
    db.refresh(db_mapping)
    
    return ThreadMappingResponse.model_validate(db_mapping)


@app.get("/thread-mappings")
async def list_thread_mappings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [CLAUDE: List all thread mappings for the current user's confabs and threads]
    """
    # Get all confabs for the user
    user_confab_ids = db.query(Confab.id).filter(Confab.user_id == current_user.id).all()
    user_confab_ids = [c[0] for c in user_confab_ids]
    
    # Get all threads for the user
    user_thread_ids = db.query(Thread.id).filter(Thread.owner_user_id == current_user.id).all()
    user_thread_ids = [t[0] for t in user_thread_ids]
    
    # Get mappings that involve the user's confabs and threads
    mappings = db.query(ThreadMapping).filter(
        ThreadMapping.confab_id.in_(user_confab_ids) if user_confab_ids else False,
        ThreadMapping.thread_id.in_(user_thread_ids) if user_thread_ids else False
    ).all()
    
    return [ThreadMappingResponse.model_validate(m) for m in mappings]


@app.get("/confab/{confab_id}/threads")
async def get_confab_threads(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [CLAUDE: Get all threads mapped to a specific confab]
    """
    # Validate confab ownership
    confab = db.query(Confab).filter(
        Confab.id == confab_id,
        Confab.user_id == current_user.id
    ).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")
    
    # Get all thread mappings for this confab
    mappings = db.query(ThreadMapping).filter(ThreadMapping.confab_id == confab_id).all()
    thread_ids = [m.thread_id for m in mappings]
    
    # Get the threads
    threads = db.query(Thread).filter(Thread.id.in_(thread_ids)) if thread_ids else []
    
    return [ThreadResponse.model_validate(t) for t in threads]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
