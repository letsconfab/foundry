from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional
import os
from dotenv import load_dotenv

from database import get_db, engine, Base
from models import User, Confab, GitHubAccount
from schemas import UserCreate, UserLogin, UserResponse, ConfabCreate, ConfabResponse, GitHubConnect, ConfabConfig, SimpleConfabConfig
from auth import create_access_token, verify_token, get_password_hash, verify_password
from github_oauth import github_auth_router, get_github_user, get_github_repos
from confab_manager import create_confab_in_github, update_confab_in_github

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
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
        access_token=access_token
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
        access_token=access_token
    )

@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()
    
    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        country=current_user.country,
        timezone=current_user.timezone,
        github_connected=github_account is not None
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

@app.get("/auth/github/repos")
async def get_user_github_repos(current_user: User = Depends(get_current_user)):
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
