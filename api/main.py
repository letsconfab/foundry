from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

import os
import json, re
import datetime
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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
from confab_manager import create_confab_in_github, update_confab_in_github, create_github_repository, initialize_confab_repository
# import the setup-step tools so we can execute them when the agent asks
from agent_tools import (
    define_purpose, add_participant, configure_memory, add_tools_and_apis,
    guardrails, sample_io, review_and_save
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
        
        # For GitHub users, create/initialize the actual repository
        repo_name = "confabs"
        repo_owner = github_account.github_username
        
        # Check if repository exists, if not create it
        try:
            # Try to create the repository
            repo_info = await create_github_repository(
                repo_name=repo_name,
                access_token=github_account.access_token,
                description=f"Confabs repository for {github_account.github_username}",
                private=False
            )
        except Exception as e:
            # Repository might already exist, try to initialize it directly
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


def _execute_tool(tool_name: str, args: Dict[str, Any], db: Session) -> str:
    """Dispatch helper to run one of the agent_tools functions."""
    if tool_name == "define_purpose":
        return define_purpose(db, args.get("confab_id"), args.get("purpose_text", ""))
    elif tool_name == "add_participant":
        return add_participant(db, args.get("confab_id"), args.get("email", ""))
    elif tool_name == "configure_memory":
        return configure_memory(db, args.get("confab_id"), args.get("memory_notes", ""), args.get("enable", True))
    elif tool_name == "add_tools_and_apis":
        return add_tools_and_apis(db, args.get("confab_id"), args.get("tool_name", ""), args.get("api_key", ""))
    elif tool_name == "guardrails":
        return guardrails(db, args.get("confab_id"), args.get("guardrails_text", ""))
    elif tool_name == "sample_io":
        return sample_io(db, args.get("confab_id"), args.get("sample_text", ""))
    elif tool_name == "review_and_save":
        return review_and_save(db, args.get("confab_id"))
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
    SYSTEM_PROMPT= ""
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
            tool_result = _execute_tool(tool_instr.get("tool"), tool_instr.get("args", {}), db)
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

@app.post("/confabs/{confab_id}/set-name")
async def set_confab_name(
    confab_id: int,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Set or generate a confab name with user input and skip logic.
    
    Expected request body:
    {
        "user_name": "Optional user-provided name",
        "purpose_text": "Purpose text for auto-generation if user skips",
        "skip": false  // If true, auto-generate from purpose
    }
    """
    from agent_runner import slugify, generate_confab_name_from_purpose
    
    # Validate confab ownership
    confab = db.query(Confab).filter(
        Confab.id == confab_id,
        Confab.user_id == current_user.id
    ).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")
    
    user_name = request.get("user_name", "").strip()
    purpose_text = request.get("purpose_text", "").strip()
    skip = request.get("skip", False)
    
    if skip or not user_name:
        # Auto-generate name from purpose
        if not purpose_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Purpose text is required for auto-generation"
            )
        
        generated_name = generate_confab_name_from_purpose(purpose_text)
        confab.name = generated_name
        db.commit()
        
        return {
            "name": generated_name,
            "source": "auto_generated",
            "message": f"Auto-generated confab name: {generated_name}"
        }
    else:
        # Use user-provided name
        slugified_name = slugify(user_name)
        confab.name = slugified_name
        db.commit()
        
        return {
            "name": slugified_name,
            "source": "user_provided",
            "original": user_name,
            "slugified": slugified_name,
            "message": f"Set confab name: {slugified_name}"
        }

@app.post("/confabs/{confab_id}/create-isolated")
async def create_isolated_confab(
    confab_id: int,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a completely isolated confab with new thread and folder.
    
    Expected request body:
    {
        "name": "Optional confab name",
        "purpose_text": "Purpose for auto-generation if no name provided"
    }
    """
    from agent_runner import slugify, generate_confab_name_from_purpose
    
    # Validate confab ownership
    confab = db.query(Confab).filter(
        Confab.id == confab_id,
        Confab.user_id == current_user.id
    ).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")
    
    user_name = request.get("name", "").strip()
    purpose_text = request.get("purpose_text", "").strip()
    
    # Set confab name
    if user_name:
        confab_name = slugify(user_name)
    elif purpose_text:
        confab_name = generate_confab_name_from_purpose(purpose_text)
    else:
        confab_name = f"confab-{confab_id}"
    
    confab.name = confab_name
    
    # Create new thread for this confab
    new_thread = Thread(
        thread_name=f"Thread for {confab_name}",
        owner_user_id=current_user.id
    )
    db.add(new_thread)
    db.commit()
    db.refresh(new_thread)
    
    # Create thread mapping
    thread_mapping = ThreadMapping(
        confab_id=confab_id,
        thread_id=new_thread.id
    )
    db.add(thread_mapping)
    db.commit()
    
    # Update confab status
    confab.status = "ready"
    db.commit()
    
    return {
        "confab_id": confab_id,
        "confab_name": confab_name,
        "thread_id": new_thread.id,
        "thread_name": new_thread.thread_name,
        "message": f"Created isolated confab '{confab_name}' with new thread {new_thread.id}"
    }

@app.get("/confab/{confab_id}/isolated-status")
async def get_confab_isolation_status(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the isolation status of a confab - which thread it belongs to.
    """
    # Validate confab ownership
    confab = db.query(Confab).filter(
        Confab.id == confab_id,
        Confab.user_id == current_user.id
    ).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")
    
    # Get thread mapping
    thread_mapping = db.query(ThreadMapping).filter(
        ThreadMapping.confab_id == confab_id
    ).first()
    
    if thread_mapping:
        thread = db.query(Thread).filter(Thread.id == thread_mapping.thread_id).first()
        return {
            "confab_id": confab_id,
            "confab_name": confab.name,
            "thread_id": thread.id,
            "thread_name": thread.thread_name,
            "is_isolated": True,
            "message": f"Confab '{confab.name}' is isolated to thread '{thread.thread_name}'"
        }
    else:
        return {
            "confab_id": confab_id,
            "confab_name": confab.name,
            "thread_id": None,
            "thread_name": None,
            "is_isolated": False,
            "message": f"Confab '{confab.name}' is not isolated to any thread"
        }

# === [CLAUDE: Import LangGraph Agent Runner] ===
from agent_runner import run_langgraph_agent, get_agent_status

@app.post("/agent/chat/{confab_id}")
async def chat_with_langgraph_agent(
    confab_id: int,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [CLAUDE: Main LangGraph Agent chat endpoint with confab isolation]
    
    This endpoint implements the new architecture with strict confab isolation:
    1. Validates confab ownership and isolation
    2. Gets or creates isolated thread for this confab
    3. Filters chat history strictly by thread_id
    4. Stores messages only in the isolated thread
    5. Maintains complete separation between confabs
    
    Architecture flow:
    User message -> Validate isolation -> LangGraph Agent -> LLM thinks -> Calls Tool -> Gets result -> Final response
    """
    # Validate confab ownership
    confab = db.query(Confab).filter(
        Confab.id == confab_id,
        Confab.user_id == current_user.id
    ).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")
    
    # Get or create isolated thread for this confab
    thread_mapping = db.query(ThreadMapping).filter(
        ThreadMapping.confab_id == confab_id
    ).first()
    
    if not thread_mapping:
        # Create new isolated thread for this confab
        new_thread = Thread(
            thread_name=f"Thread for {confab.name or f'confab-{confab_id}'}",
            owner_user_id=current_user.id
        )
        db.add(new_thread)
        db.commit()
        db.refresh(new_thread)
        
        # Create thread mapping
        thread_mapping = ThreadMapping(
            confab_id=confab_id,
            thread_id=new_thread.id
        )
        db.add(thread_mapping)
        db.commit()
        db.refresh(thread_mapping)
        
        thread_id = new_thread.id
        logger.info(f"Created new isolated thread {thread_id} for confab {confab_id}")
    else:
        thread_id = thread_mapping.thread_id
        logger.info(f"Using existing isolated thread {thread_id} for confab {confab_id}")
    
    # Extract message from request
    user_message = request.get("message", "")
    if not user_message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is required")
    
    # Store user message in the isolated thread
    user_db_message = Message(
        thread_id=thread_id,
        content=user_message,
        role="user"
    )
    db.add(user_db_message)
    db.commit()
    db.refresh(user_db_message)
    
    try:
        # Run the LangGraph agent
        result = await run_langgraph_agent(confab_id, user_message, db)
        
        if result["success"]:
            # Store AI response in the isolated thread
            assistant_message = Message(
                thread_id=thread_id,
                content=result["response"],
                role="assistant"
            )
            db.add(assistant_message)
            db.commit()
            db.refresh(assistant_message)
            
            return {
                "response": result["response"],
                "tool_calls": result.get("tool_calls", []),
                "confab_id": confab_id,
                "thread_id": thread_id,
                "timestamp": str(datetime.datetime.now()),
                "architecture": "LangGraph with MCP integration",
                "isolation": "strict_thread_filtering",
                "messages": {
                    "user_message_id": user_db_message.id,
                    "assistant_message_id": assistant_message.id
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Agent execution failed")
            )
            
    except Exception as e:
        logger.error(f"Error in LangGraph agent chat: {e}")
        
        # Store error message in the isolated thread
        error_message = Message(
            thread_id=thread_id,
            content=f"Error: Could not generate response - {str(e)}",
            role="assistant"
        )
        db.add(error_message)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {str(e)}"
        )

@app.get("/agent/chat/{confab_id}/history")
async def get_confab_chat_history(
    confab_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get chat history for a specific confab, demonstrating strict isolation.
    
    This endpoint shows only messages from the thread mapped to this confab,
    proving that confab isolation is working correctly.
    """
    # Validate confab ownership
    confab = db.query(Confab).filter(
        Confab.id == confab_id,
        Confab.user_id == current_user.id
    ).first()
    if not confab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confab not found")
    
    # Get thread mapping for this confab
    thread_mapping = db.query(ThreadMapping).filter(
        ThreadMapping.confab_id == confab_id
    ).first()
    
    if not thread_mapping:
        return {
            "confab_id": confab_id,
            "confab_name": confab.name,
            "thread_id": None,
            "messages": [],
            "message": f"No chat history found for confab '{confab.name}'. Start a conversation to create history.",
            "isolation": "no_thread_mapped"
        }
    
    # Get messages only from the mapped thread (strict isolation)
    messages = db.query(Message).filter(
        Message.thread_id == thread_mapping.thread_id
    ).order_by(Message.time).all()
    
    message_history = []
    for msg in messages:
        message_history.append({
            "id": msg.id,
            "content": msg.content,
            "role": msg.role,
            "timestamp": msg.time,
            "thread_id": msg.thread_id
        })
    
    return {
        "confab_id": confab_id,
        "confab_name": confab.name,
        "thread_id": thread_mapping.thread_id,
        "thread_name": db.query(Thread).filter(Thread.id == thread_mapping.thread_id).first().thread_name,
        "messages": message_history,
        "message_count": len(message_history),
        "isolation": "strict_thread_filtering",
        "message": f"Retrieved {len(message_history)} messages for confab '{confab.name}'"
    }

@app.post("/admin/migrate-confabs")
async def migrate_existing_confabs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Migrate existing confabs to the new naming and folder structure.
    
    This endpoint helps with backward compatibility by:
    1. Converting old timestamp-based names to slugified names
    2. Creating thread mappings for isolation
    3. Moving PURPOSE.md files to new folder structure
    """
    from agent_runner import slugify, generate_confab_name_from_purpose
    
    # Get all confabs for the user
    confabs = db.query(Confab).filter(Confab.user_id == current_user.id).all()
    
    migrated_count = 0
    migration_results = []
    
    for confab in confabs:
        result = {
            "confab_id": confab.id,
            "old_name": confab.name,
            "actions": []
        }
        
        # 1. Migrate confab name if it's timestamp-based
        if confab.name and confab.name.startswith("Agent Chat –"):
            try:
                # Try to get purpose to generate a better name
                from agent_tools import get_purpose
                purpose_text = get_purpose(confab.id)
                
                if purpose_text:
                    new_name = generate_confab_name_from_purpose(purpose_text)
                else:
                    new_name = f"confab-{confab.id}"
                
                confab.name = new_name
                result["actions"].append(f"Renamed from timestamp-based to: {new_name}")
                migrated_count += 1
                
            except Exception as e:
                result["actions"].append(f"Failed to rename: {str(e)}")
        
        # 2. Ensure name is slugified
        if confab.name:
            slugified_name = slugify(confab.name)
            if confab.name != slugified_name:
                confab.name = slugified_name
                result["actions"].append(f"Slugified name to: {slugified_name}")
                migrated_count += 1
        
        # 3. Create thread mapping if it doesn't exist
        existing_mapping = db.query(ThreadMapping).filter(
            ThreadMapping.confab_id == confab.id
        ).first()
        
        if not existing_mapping:
            try:
                # Create new thread
                new_thread = Thread(
                    thread_name=f"Thread for {confab.name or f'confab-{confab.id}'}",
                    owner_user_id=current_user.id
                )
                db.add(new_thread)
                db.commit()
                db.refresh(new_thread)
                
                # Create thread mapping
                thread_mapping = ThreadMapping(
                    confab_id=confab.id,
                    thread_id=new_thread.id
                )
                db.add(thread_mapping)
                db.commit()
                
                result["actions"].append(f"Created isolated thread {new_thread.id}")
                migrated_count += 1
                
            except Exception as e:
                result["actions"].append(f"Failed to create thread mapping: {str(e)}")
        
        result["new_name"] = confab.name
        migration_results.append(result)
    
    # Commit all changes
    try:
        db.commit()
        success = True
    except Exception as e:
        db.rollback()
        success = False
        error = str(e)
    
    return {
        "success": success,
        "migrated_count": migrated_count,
        "total_confabs": len(confabs),
        "migration_results": migration_results,
        "error": error if not success else None,
        "message": f"Migration completed. {migrated_count} changes made across {len(confabs)} confabs."
    }

@app.get("/admin/system-status")
async def get_system_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get system status showing migration state and confab isolation status.
    """
    # Get confabs statistics
    total_confabs = db.query(Confab).filter(Confab.user_id == current_user.id).count()
    
    # Count confabs with proper names (non-timestamp)
    proper_named_confabs = db.query(Confab).filter(
        Confab.user_id == current_user.id,
        ~Confab.name.startswith("Agent Chat –")
    ).count()
    
    # Count confabs with thread mappings
    confabs_with_threads = db.query(ThreadMapping).join(Confab).filter(
        Confab.user_id == current_user.id
    ).count()
    
    # Get recent confabs
    recent_confabs = db.query(Confab).filter(
        Confab.user_id == current_user.id
    ).order_by(Confab.created_at.desc()).limit(5).all()
    
    confab_details = []
    for confab in recent_confabs:
        thread_mapping = db.query(ThreadMapping).filter(
            ThreadMapping.confab_id == confab.id
        ).first()
        
        confab_details.append({
            "id": confab.id,
            "name": confab.name,
            "status": confab.status,
            "has_thread_mapping": thread_mapping is not None,
            "thread_id": thread_mapping.thread_id if thread_mapping else None,
            "needs_migration": confab.name.startswith("Agent Chat –") if confab.name else False
        })
    
    return {
        "user": current_user.email,
        "statistics": {
            "total_confabs": total_confabs,
            "proper_named_confabs": proper_named_confabs,
            "confabs_with_threads": confabs_with_threads,
            "migration_needed": total_confabs - proper_named_confabs
        },
        "recent_confabs": confab_details,
        "system_health": {
            "github_structure": "confabs/{confab.name}/PURPOSE.md",
            "isolation": "strict_thread_filtering",
            "naming": "slugified_names"
        }
    }

@app.get("/agent/status")
async def get_langgraph_agent_status(
    current_user: User = Depends(get_current_user)
):
    """
    [CLAUDE: Get LangGraph Agent system status]
    
    Returns the current status of the LangGraph agent system including:
    - Agent status (active/error)
    - LLM provider information
    - Available tools count
    - Architecture information
    """
    try:
        status = get_agent_status()
        return {
            "status": status,
            "user": current_user.email,
            "timestamp": str(datetime.datetime.now())
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": str(datetime.datetime.now())
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
