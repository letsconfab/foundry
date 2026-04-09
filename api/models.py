import uuid

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON, Float, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    """User account"""
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
    threads = relationship("Thread", back_populates="owner")


class GitHubAccount(Base):
    """GitHub OAuth connection for a user"""
    __tablename__ = "github_accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    github_id = Column(Integer, nullable=False)
    github_username = Column(String(255), nullable=False)
    access_token = Column(String(500), nullable=False)
    selected_org = Column(String(255), nullable=True)
    selected_repo = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="github_account")


class Confab(Base):
    """
    Agent definition - DB is source of truth, GitHub is artifact export.
    Supports OASF (Open Agent Specification Format) for portability.
    """
    __tablename__ = "confabs"

    id = Column(Integer, primary_key=True, index=True)

    # Identity
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(50), nullable=False, default="1.0.0")
    status = Column(String(50), nullable=False, default="building")  # building, draft, published, archived

    # Foreman setup progress (for building status)
    setup_progress = Column(JSON, nullable=True)  # {"completed_steps": [1,2], "current_stage": "memory"}

    # OASF record fields
    oasf_schema_version = Column(String(20), nullable=False, default="1.0.0")
    skills = Column(JSON, nullable=True)  # list of OASF skill IDs
    domains = Column(JSON, nullable=True)  # list of domain strings

    # Core content (also exported to GitHub as .md files)
    purpose = Column(Text, nullable=True)  # PURPOSE.md content
    guardrails = Column(JSON, nullable=True)  # structured list of rules
    tests = Column(JSON, nullable=True)  # structured test scenarios

    # Runtime config
    model_provider = Column(String(50), nullable=True, default="groq")
    model_name = Column(String(100), nullable=True, default="qwen/qwen3-32b")
    temperature = Column(Float, nullable=False, default=0.7)

    # Full OASF export (cached)
    oasf_yaml = Column(Text, nullable=True)  # full agent.oasf.yaml content

    # GitHub sync state
    github_path = Column(String(255), nullable=True)  # folder name in repo
    github_synced_at = Column(DateTime(timezone=True), nullable=True)
    github_sync_version = Column(String(50), nullable=True)  # version that was synced

    # Ownership
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="confabs")
    learnings = relationship("ConfabLearning", back_populates="confab", cascade="all, delete-orphan")


class ConfabLearning(Base):
    """
    Knowledge learned during confab operation.
    Synced to GitHub as individual .md files in knowledge/learned/
    """
    __tablename__ = "confab_learnings"

    id = Column(Integer, primary_key=True, index=True)
    confab_id = Column(Integer, ForeignKey("confabs.id"), nullable=False)

    # Content
    content = Column(Text, nullable=False)
    summary = Column(String(500), nullable=True)  # one-line summary for listings
    tags = Column(JSON, nullable=True)  # list of tag strings

    # Status
    status = Column(String(20), nullable=False, default="draft")  # draft, approved

    # Provenance
    author_type = Column(String(20), nullable=False)  # "user" | "confab" | "system"
    author_id = Column(Integer, nullable=True)  # user_id or confab_id
    source = Column(String(50), nullable=False, default="manual")  # "conversation" | "manual" | "import"
    source_thread_id = Column(Integer, ForeignKey("threads.id"), nullable=True)

    # GitHub sync
    github_filename = Column(String(255), nullable=True)  # e.g., "learning-001.md"
    github_synced_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    confab = relationship("Confab", back_populates="learnings")
    source_thread = relationship("Thread", foreign_keys=[source_thread_id])


class Thread(Base):
    """Conversation container with multiple participants"""
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(500), nullable=False)  # was thread_name
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # denormalized for quick lookup
    conversation_mode = Column(String(30), nullable=True)  # "foreman_build" | "confab_runtime" | "multi_agent_workspace"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    owner = relationship("User", back_populates="threads")
    participants = relationship("ThreadParticipant", back_populates="thread", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="thread", order_by="Message.created_at")


class ThreadParticipant(Base):
    """
    Links participants (users, confabs, system agents) to threads.
    Replaces the old ThreadMapping table with a more expressive model.
    """
    __tablename__ = "thread_participants"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False)

    # Polymorphic participant reference
    participant_type = Column(String(20), nullable=False)  # "user" | "confab" | "system"
    participant_id = Column(Integer, nullable=True)  # FK to users/confabs, NULL for system
    system_agent_name = Column(String(100), nullable=True)  # "foreman" etc., only if type=system

    # Role in conversation
    role = Column(String(20), nullable=False, default="participant")  # "owner" | "participant" | "observer"

    # State
    is_active = Column(Boolean, nullable=False, default=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    thread = relationship("Thread", back_populates="participants")


class Message(Base):
    """Individual message in a thread with sender info and threading support"""
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False)

    # Sender (denormalized for quick display)
    sender_type = Column(String(20), nullable=False, default="user")  # "user" | "confab" | "system"
    sender_id = Column(Integer, nullable=True)  # user_id or confab_id, NULL for system
    sender_name = Column(String(255), nullable=True)  # cached display name

    # Threading
    in_reply_to = Column(Integer, ForeignKey("messages.id"), nullable=True)  # NULL = main thread
    depth = Column(Integer, nullable=False, default=0)  # 0 = main, 1+ = subthread depth

    # Addressing
    addressed_to = Column(JSON, nullable=True)  # [{"type": "confab", "id": 5}, ...] or NULL = broadcast

    content = Column(Text, nullable=False)
    role = Column(String(20), nullable=False, default="user")  # "user" | "assistant" for LLM context

    created_at = Column(DateTime(timezone=True), server_default=func.now())  # was 'time'

    # Relationships
    thread = relationship("Thread", back_populates="messages")
    replies = relationship("Message", backref="parent", remote_side=[id])


# =============================================================================
# Document Store V2 Models (with versioning, compression, encryption)
# =============================================================================


class ConfabDocumentV2(Base):
    """
    Document metadata with versioning support (V2).

    Replaces ConfabDocument with proper version tracking.
    Content is stored in DocumentVersion records.
    """
    __tablename__ = "confab_documents_v2"

    id = Column(Integer, primary_key=True, index=True)
    confab_id = Column(Integer, ForeignKey("confabs.id", ondelete="CASCADE"), nullable=False)

    # Identity
    document_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    filename = Column(String(255), nullable=False)  # Sanitized filename
    original_content_type = Column(String(100), nullable=False)

    # Source tracking
    source = Column(String(50), nullable=False, default="upload")  # upload, url, api
    source_url = Column(String(2000), nullable=True)

    # Status
    status = Column(String(20), nullable=False, default="active")  # active, archived

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    confab = relationship("Confab", backref="documents_v2")
    versions = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version_number.desc()"
    )

    # Unique constraint on confab_id + document_uuid
    __table_args__ = (
        {"extend_existing": True},
    )


class DocumentVersion(Base):
    """
    Immutable document version with compressed (and optionally encrypted) content.

    Each version is append-only - content is never modified after creation.
    """
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("confab_documents_v2.id", ondelete="CASCADE"), nullable=False)

    # Version info
    version_number = Column(Integer, nullable=False)

    # Content storage (compressed, optionally encrypted)
    content_blob = Column(LargeBinary, nullable=False)  # zstd compressed (+ encrypted in Phase 2)
    content_hash = Column(String(64), nullable=False)  # SHA-256 of original content
    original_size = Column(Integer, nullable=False)  # Size before compression
    compressed_size = Column(Integer, nullable=False)  # Size after compression

    # Encryption metadata (Phase 2 - nullable for now)
    encryption_key_id = Column(String(64), nullable=True)  # Reference to key
    encryption_iv = Column(LargeBinary, nullable=True)  # AES-GCM IV (12 bytes)
    encryption_tag = Column(LargeBinary, nullable=True)  # AES-GCM auth tag (16 bytes)

    # Extracted text (for display/search)
    extracted_text = Column(Text, nullable=True)
    text_extraction_status = Column(String(20), default="pending")  # pending, completed, failed

    # Metadata
    metadata_json = Column(JSON, nullable=True)  # page_count, author, etc.

    # Timestamps and audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    document = relationship("ConfabDocumentV2", back_populates="versions")
    creator = relationship("User", foreign_keys=[created_by])

    # Unique constraint on document_id + version_number
    __table_args__ = (
        {"extend_existing": True},
    )
