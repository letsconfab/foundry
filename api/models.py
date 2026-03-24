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
    threads = relationship("Thread", back_populates="user")

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
    thread_mappings = relationship("ThreadMapping", back_populates="confab")


# Table 2: threads — thread_id (id), thread_name, createdAt, owner_user_id
class Thread(Base):
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, index=True)
    thread_name = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", back_populates="threads")
    messages = relationship("Message", back_populates="thread", order_by="Message.time")


# Table 3: messages — id, thread_id, content, time (role added for chat UI)
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False)
    content = Column(Text, nullable=False)
    time = Column(DateTime(timezone=True), server_default=func.now())
    role = Column(String(20), nullable=True, default="user")  # 'user' | 'assistant' for display

    # Relationships
    thread = relationship("Thread", back_populates="messages")
# === [CLAUDE: Added thread_mapping table to link confabs to threads for tracking which confab a conversation belongs to] ===
# Table 4: thread_mapping — id, confab_id, thread_id, created_at
class ThreadMapping(Base):
    """
    Maps threads to confabs. Allows tracking which confab a conversation thread belongs to.
    Schema: id, confab_id, thread_id, created_at
    """
    __tablename__ = "thread_mapping"

    id = Column(Integer, primary_key=True, index=True)
    confab_id = Column(Integer, ForeignKey("confabs.id"), nullable=False)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    confab = relationship("Confab", back_populates="thread_mappings", foreign_keys=[confab_id])
    thread = relationship("Thread", foreign_keys=[thread_id])