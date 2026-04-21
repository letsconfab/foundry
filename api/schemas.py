from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


# =============================================================================
# User Schemas
# =============================================================================

class UserBase(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    country: str
    timezone: str


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    github_connected: bool
    access_token: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserListItem(BaseModel):
    """Safe user fields for participants/list."""
    id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# GitHub Schemas
# =============================================================================

class GitHubUser(BaseModel):
    id: int
    login: str
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None


class GitHubRepo(BaseModel):
    id: int
    name: str
    full_name: str
    private: bool
    owner: Dict[str, Any]
    permissions: Dict[str, str]


class GitHubConnect(BaseModel):
    github_id: int
    github_username: str
    access_token: str
    selected_repo: str
    selected_org: Optional[str] = None


class GitHubLogin(BaseModel):
    github_id: int
    github_username: str
    access_token: str
    selected_repo: str = "confabs"
    selected_org: Optional[str] = None


class GitHubRepoResponse(BaseModel):
    repos: List[GitHubRepo]


# =============================================================================
# Confab Schemas (OASF-aligned)
# =============================================================================

class GuardrailRule(BaseModel):
    """A single guardrail rule for the confab."""
    id: str
    rule: str
    severity: Literal["error", "warning", "info"] = "error"
    enabled: bool = True


class TestScenario(BaseModel):
    """A test scenario for validating confab behavior."""
    id: str
    name: str
    input: str
    expected_behavior: str
    tags: List[str] = Field(default_factory=list)


class ConfabCreate(BaseModel):
    """Create a new confab."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    status: Literal["building", "draft", "published", "archived"] = "building"

    # Runtime config
    model_provider: str = "groq"
    model_name: str = "qwen/qwen3-32b"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    model_config = ConfigDict(protected_namespaces=())


class ConfabUpdate(BaseModel):
    """Update an existing confab."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    status: Optional[Literal["building", "draft", "published", "archived"]] = None

    # Core content
    purpose: Optional[str] = None
    guardrails: Optional[List[GuardrailRule]] = None
    tests: Optional[List[TestScenario]] = None

    # OASF metadata
    skills: Optional[List[int]] = None
    domains: Optional[List[str]] = None

    # Runtime config
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)

    model_config = ConfigDict(protected_namespaces=())


class ConfabResponse(BaseModel):
    """Confab response with all fields."""
    id: int
    name: str
    description: Optional[str] = None
    version: str
    status: str

    # OASF metadata
    oasf_schema_version: str
    skills: Optional[List[int]] = None
    domains: Optional[List[str]] = None

    # Core content
    purpose: Optional[str] = None
    guardrails: Optional[List[Dict[str, Any]]] = None
    tests: Optional[List[Dict[str, Any]]] = None

    # Runtime config
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    temperature: float

    # GitHub sync
    github_path: Optional[str] = None
    github_synced_at: Optional[datetime] = None

    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConfabListItem(BaseModel):
    """Lightweight confab for list views."""
    id: int
    name: str
    description: Optional[str] = None
    version: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Confab Learning Schemas
# =============================================================================

class LearningCreate(BaseModel):
    """Create a new learning for a confab."""
    content: str
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    source: Literal["conversation", "manual", "import"] = "manual"
    source_thread_id: Optional[int] = None


class LearningUpdate(BaseModel):
    """Update an existing learning."""
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[Literal["draft", "approved"]] = None


class LearningResponse(BaseModel):
    """Learning response."""
    id: int
    confab_id: int
    content: str
    summary: Optional[str] = None
    tags: Optional[List[str]] = None
    status: str
    author_type: str
    author_id: Optional[int] = None
    source: str
    source_thread_id: Optional[int] = None
    github_filename: Optional[str] = None
    github_synced_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Thread Schemas
# =============================================================================

class ThreadCreate(BaseModel):
    """Create a new thread."""
    name: str
    # Initial participants can be added via separate endpoint


class ThreadResponse(BaseModel):
    """Thread response."""
    id: int
    name: str
    owner_user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ThreadWithParticipants(ThreadResponse):
    """Thread with participant list."""
    participants: List["ParticipantResponse"] = Field(default_factory=list)


# =============================================================================
# Thread Participant Schemas
# =============================================================================

class ParticipantAdd(BaseModel):
    """Add a participant to a thread."""
    participant_type: Literal["user", "confab", "system"]
    participant_id: Optional[int] = None  # NULL for system agents
    system_agent_name: Optional[str] = None  # e.g., "foreman"
    role: Literal["owner", "participant", "observer"] = "participant"


class ParticipantResponse(BaseModel):
    """Participant response."""
    id: int
    thread_id: int
    participant_type: str
    participant_id: Optional[int] = None
    system_agent_name: Optional[str] = None
    role: str
    is_active: bool
    joined_at: datetime
    left_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Message Schemas
# =============================================================================

class AddressedTo(BaseModel):
    """Who a message is addressed to."""
    type: Literal["user", "confab", "system"]
    id: Optional[int] = None
    name: Optional[str] = None  # for system agents


class MessageCreate(BaseModel):
    """Create a new message (used internally)."""
    content: str
    sender_type: Literal["user", "confab", "system"] = "user"
    sender_id: Optional[int] = None
    sender_name: Optional[str] = None
    in_reply_to: Optional[int] = None
    addressed_to: Optional[List[AddressedTo]] = None
    role: Literal["user", "assistant"] = "user"


class MessageResponse(BaseModel):
    """Message response."""
    id: int
    thread_id: int
    sender_type: str
    sender_id: Optional[int] = None
    sender_name: Optional[str] = None
    in_reply_to: Optional[int] = None
    depth: int
    addressed_to: Optional[List[Dict[str, Any]]] = None
    content: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Chat Schemas (unified endpoint)
# =============================================================================

class ChatRequest(BaseModel):
    """Request to send a chat message."""
    content: str
    addressed_to: Optional[List[AddressedTo]] = None  # NULL = broadcast, infer from context
    in_reply_to: Optional[int] = None  # for subthreading


class ChatResponse(BaseModel):
    """Response from chat endpoint, includes user message and any agent responses."""
    thread_id: int
    user_message: MessageResponse
    agent_responses: List[MessageResponse] = Field(default_factory=list)
    timestamp: datetime
    # Foreman-specific metadata (present when chatting with Foreman during confab build)
    foreman_metadata: Optional["ForemanChatResponse"] = Field(
        default=None,
        description="Foreman interview state metadata, present when building a confab"
    )


# =============================================================================
# Auth Schemas
# =============================================================================

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[int] = None


# =============================================================================
# Foreman Agent Schemas
# =============================================================================

class SetupProgressResponse(BaseModel):
    """Setup progress for confab building flow."""
    completed_steps: List[int] = Field(default_factory=list)
    current_stage: str = "purpose"
    total_steps: int = 8
    remaining_steps: List[int] = Field(default_factory=list)


class ForemanV2Metadata(BaseModel):
    """V2 metadata for deterministic interview flow.

    Provides structured information about the current stage state,
    allowing the UI to render the interview without guessing from message text.
    """
    stage: str = Field(description="Current stage name (purpose, participants, etc.)")
    stage_status: Optional[str] = Field(
        default=None,
        description="Stage outcome: complete, clarify, skip, or error"
    )
    saved_fields: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Data that was saved for this stage"
    )
    next_question: Optional[str] = Field(
        default=None,
        description="The suggested next question if clarification needed"
    )
    response_ack: Optional[str] = Field(
        default=None,
        description="Short acknowledgement of what the Foreman just recorded or decided"
    )
    interview_prompt: Optional[str] = Field(
        default=None,
        description="The explicit next call to action the Foreman wants the user to answer"
    )
    next_stage: Optional[str] = Field(
        default=None,
        description="The stage that will be active after this one"
    )
    clarification_needed: bool = Field(
        default=False,
        description="True if the stage needs more input before completing"
    )
    ui_hint: Optional[str] = Field(
        default=None,
        description="UI hint for stage-specific behaviors (e.g., 'show_upload_panel')"
    )


class ForemanChatResponse(BaseModel):
    """Response from Foreman agent (via unified chat endpoint)."""
    response: str
    confab_id: int
    thread_id: int
    setup_progress: Optional[SetupProgressResponse] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp: datetime
    # V2 additions
    v2_metadata: Optional[ForemanV2Metadata] = Field(
        default=None,
        description="V2 interview metadata (present when FOREMAN_V2_ENABLED)"
    )
    is_v2: bool = Field(
        default=False,
        description="True if this response was generated by the V2 flow"
    )
    is_v3: bool = Field(
        default=False,
        description="True if this response was generated by the V3 LangGraph flow"
    )

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Admin Schemas
# =============================================================================

class SystemStatusResponse(BaseModel):
    """System status for admin endpoint."""
    database: str
    llm_service: str
    github_service: str
    active_threads: int
    total_confabs: int
    total_users: int


class GitHubSyncRequest(BaseModel):
    """Request to sync confabs to GitHub."""
    confab_ids: Optional[List[int]] = None  # NULL = sync all


class GitHubSyncResponse(BaseModel):
    """Response from GitHub sync."""
    synced_count: int
    failed_count: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# Definition Files Schemas
# =============================================================================

class DefinitionFilesRefreshResponse(BaseModel):
    """Refreshed PURPOSE.md and GUARDRAILS.md from GitHub."""
    confab_id: int
    purpose: Optional[str] = None
    guardrails_markdown: Optional[str] = None
    remote_branch: Optional[str] = None
    remote_source: Optional[Literal["branch", "default", "none"]] = None
    refreshed_at: datetime


class DefinitionFilesCommitRequest(BaseModel):
    """Commit selected definition files in one batch."""
    commit_message: str = "accept-changes-and-commit"
    include_purpose: bool = True
    include_guardrails: bool = True


class DefinitionFilesCommitResponse(BaseModel):
    """Result of definition files batch commit."""
    confab_id: int
    branch: Optional[str] = None
    folder_path: Optional[str] = None
    committed_files: List[str] = Field(default_factory=list)
    commit_sha: Optional[str] = None
    status: Literal["committed", "no-op", "saved-locally"]
    synced_at: datetime
    message: Optional[str] = None


# =============================================================================
# Conversation Service Schemas (high-level endpoints)
# =============================================================================

class ConversationStartResponse(BaseModel):
    """Response from starting or resuming a conversation."""
    thread_id: int
    confab_id: Optional[int] = None
    conversation_mode: str  # foreman_build | confab_runtime
    messages: List[MessageResponse] = Field(default_factory=list)
    participants: List[ParticipantResponse] = Field(default_factory=list)
    setup_progress: Optional[SetupProgressResponse] = None
    current_stage: Optional[str] = None


class ConversationMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    addressed_to: Optional[List[AddressedTo]] = None
    in_reply_to: Optional[int] = None


# Forward reference update
ThreadWithParticipants.model_rebuild()
ConversationStartResponse.model_rebuild()
