from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    country = Column(String(100), nullable=False)
    timezone = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    confabs = relationship("Confab", back_populates="user")
    github_account = relationship("GitHubAccount", back_populates="user", uselist=False)

class GitHubAccount(Base):
    __tablename__ = "github_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    github_id = Column(Integer, nullable=False)
    github_username = Column(String(255), nullable=False)
    access_token = Column(String(500), nullable=False)
    selected_org = Column(String(255), nullable=True)  # GitHub organization name
    selected_repo = Column(String(255), nullable=False)  # Repository name
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="github_account")

class Confab(Base):
    __tablename__ = "confabs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(50), nullable=False, default="1.0.0")
    status = Column(String(50), nullable=False, default="draft")  # draft, published, archived
    config = Column(JSON, nullable=True)  # Store confab configuration as JSON
    github_url = Column(String(500), nullable=True)  # URL to GitHub repo/files
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="confabs")
