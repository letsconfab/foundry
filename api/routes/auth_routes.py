from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, GitHubAccount
from auth import create_access_token, get_password_hash, verify_password
from schemas import UserCreate, UserLogin, UserResponse, GitHubConnect, GitHubLogin
from github_oauth import get_github_repos, get_github_primary_email
from deps import get_current_user
import os

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    db_user = User(
        name=user.name, email=user.email,
        password_hash=get_password_hash(user.password),
        country=user.country, timezone=user.timezone
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


@router.post("/login", response_model=UserResponse)
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


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()
    return UserResponse(
        id=current_user.id, name=current_user.name, email=current_user.email,
        country=current_user.country, timezone=current_user.timezone,
        github_connected=github_account is not None,
        created_at=current_user.created_at, updated_at=current_user.updated_at,
    )


@router.post("/github/connect")
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


@router.post("/github/login", response_model=UserResponse)
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


@router.get("/github/repos")
async def get_user_github_repos(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    github_account = db.query(GitHubAccount).filter(GitHubAccount.user_id == current_user.id).first()
    if not github_account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub not connected")
    repos = await get_github_repos(github_account.access_token)
    return {"repos": repos}
