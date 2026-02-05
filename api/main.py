from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import os
import logging
from dotenv import load_dotenv

from database import get_db, engine, Base
from models import User, Confab, GitHubAccount
from schemas import UserCreate, UserLogin, UserResponse, ConfabCreate, ConfabResponse, GitHubConnect, GitHubLogin, ConfabConfig, SimpleConfabConfig, LLMChatRequest, LLMModelsResponse
from auth import create_access_token, verify_token, get_password_hash, verify_password
from github_oauth import github_auth_router, get_github_user, get_github_repos, get_github_primary_email
from confab_manager import create_confab_in_github, update_confab_in_github, create_github_repository, initialize_confab_repository
from llm_proxy import LLMProxy, ChatMessage, PURPOSE_AGENT_SYSTEM_PROMPT

# Configure logging to exclude sensitive headers
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    else ["http://localhost:3000"]
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

# ============================================================================
# LLM Proxy Endpoints
# ============================================================================

@app.get("/llm/models", response_model=LLMModelsResponse)
async def get_available_models():
    """Get available LLM models for each provider."""
    return LLMModelsResponse(
        anthropic=LLMProxy.AVAILABLE_MODELS["anthropic"],
        openai=LLMProxy.AVAILABLE_MODELS["openai"]
    )


@app.post("/llm/chat/stream")
async def llm_chat_stream(
    request: LLMChatRequest,
    x_llm_api_key: str = Header(..., alias="X-LLM-API-Key"),
    current_user: User = Depends(get_current_user)
):
    """
    Stream chat completions from LLM providers.

    The API key is passed via X-LLM-API-Key header and is only held in memory
    during the request - it is NEVER logged or stored.

    Returns: Server-Sent Events (SSE) stream of text chunks
    """
    # Log request (WITHOUT the API key)
    logger.info(f"LLM chat stream request from user {current_user.id}, provider: {request.provider}")

    async def generate():
        try:
            # Convert request messages to ChatMessage objects
            messages = [
                ChatMessage(role=msg.role, content=msg.content)
                for msg in request.messages
            ]

            async for chunk in LLMProxy.stream_chat(
                provider=request.provider,
                api_key=x_llm_api_key,  # In-memory only, never stored
                messages=messages,
                model=request.model,
                system_prompt=request.system_prompt,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                # Send chunk as SSE event
                yield f"data: {chunk}\n\n"

            # Send done signal
            yield "data: [DONE]\n\n"

        except Exception as e:
            # Log error (without sensitive details)
            logger.error(f"LLM stream error for user {current_user.id}: {type(e).__name__}")
            error_msg = str(e)
            yield f"data: [ERROR] {error_msg}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@app.get("/llm/purpose-agent/system-prompt")
async def get_purpose_agent_system_prompt(
    current_user: User = Depends(get_current_user)
):
    """Get the system prompt for the Purpose Defining Agent."""
    return {"system_prompt": PURPOSE_AGENT_SYSTEM_PROMPT}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
