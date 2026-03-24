"""
Pytest fixtures for Foundry API tests.
"""

import pytest
import os
from typing import Generator
from unittest.mock import MagicMock, AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Set test environment before importing app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing"

from database import Base, get_db
from main import app
from models import User, Confab, GitHubAccount, Thread, Message, ThreadMapping
from auth import get_password_hash, create_access_token


# Create test database engine
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user."""
    user = User(
        name="Test User",
        email="test@example.com",
        password_hash=get_password_hash("testpassword"),
        country="US",
        timezone="America/New_York"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_token(test_user: User) -> str:
    """Create an auth token for the test user."""
    return create_access_token({"user_id": test_user.id, "email": test_user.email})


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Create authorization headers."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def test_confab(db: Session, test_user: User) -> Confab:
    """Create a test confab."""
    confab = Confab(
        name="Test Confab",
        description="A test confab for testing",
        user_id=test_user.id,
        version="1.0.0",
        status="building",
        config={"test": True}
    )
    db.add(confab)
    db.commit()
    db.refresh(confab)
    return confab


@pytest.fixture
def test_thread(db: Session, test_user: User) -> Thread:
    """Create a test thread."""
    thread = Thread(
        thread_name="Test Thread",
        owner_user_id=test_user.id
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


@pytest.fixture
def test_github_account(db: Session, test_user: User) -> GitHubAccount:
    """Create a test GitHub account."""
    github_account = GitHubAccount(
        user_id=test_user.id,
        github_id=12345,
        github_username="testuser",
        access_token="test-github-token",
        selected_repo="test-repo"
    )
    db.add(github_account)
    db.commit()
    db.refresh(github_account)
    return github_account


@pytest.fixture
def mock_github_service():
    """Mock the GitHubService for tests that don't need real GitHub calls."""
    with patch("github_service.GitHubService") as mock:
        instance = MagicMock()
        instance.create_confab_files = AsyncMock(return_value="https://github.com/test/repo/pull/1")
        instance.commit_confab_file = AsyncMock(return_value="https://github.com/test/repo/pull/1")
        instance.get_or_create_branch = AsyncMock(return_value="confab-1")
        mock.return_value = instance
        yield mock
