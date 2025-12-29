from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any, Literal, Union
from datetime import datetime

# User schemas
class UserBase(BaseModel):
    name: str
    email: EmailStr
    country: str
    timezone: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: int
    github_connected: bool
    access_token: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# GitHub schemas
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

# Confab Configuration Models
class AgentCapabilities(BaseModel):
    """Defines what the agent can do"""
    text_generation: bool = True
    code_generation: bool = False
    data_analysis: bool = False
    web_search: bool = False
    file_processing: bool = False
    image_analysis: bool = False
    custom_tools: List[str] = Field(default_factory=list, description="List of custom tool names")

class ModelConfiguration(BaseModel):
    """AI model settings"""
    model_config = ConfigDict(protected_namespaces=())
    provider: Literal["openai", "anthropic", "google", "local"] = "openai"
    model_name: str = Field(..., description="Model name (e.g., 'gpt-4', 'claude-3-sonnet')")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, ge=1, le=100000, description="Maximum response tokens")
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0, description="Nucleus sampling")
    frequency_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0, description="Frequency penalty")
    presence_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0, description="Presence penalty")

class KnowledgeBase(BaseModel):
    """Knowledge base configuration"""
    enabled: bool = False
    type: Literal["documents", "database", "api", "website"] = "documents"
    source: str = Field(..., description="Source location or connection string")
    indexing_method: Literal["vector", "keyword", "hybrid"] = "vector"
    chunk_size: int = Field(default=1000, ge=100, le=10000, description="Text chunk size")
    overlap: int = Field(default=200, ge=0, le=1000, description="Chunk overlap size")

class ConversationSettings(BaseModel):
    """Conversation behavior settings"""
    system_prompt: str = Field(..., description="System prompt that defines agent behavior")
    max_conversation_length: int = Field(default=50, ge=1, le=1000, description="Maximum message history")
    memory_enabled: bool = True
    context_window_size: int = Field(default=10, ge=1, le=100, description="Context window for responses")
    greeting_message: Optional[str] = Field(default=None, description="Initial greeting message")
    error_message: Optional[str] = Field(default=None, description="Error response template")

class SecuritySettings(BaseModel):
    """Security and moderation settings"""
    content_filtering: bool = True
    allowed_domains: List[str] = Field(default_factory=list, description="Allowed domains for web access")
    blocked_keywords: List[str] = Field(default_factory=list, description="Blocked content keywords")
    rate_limiting: bool = True
    max_requests_per_minute: int = Field(default=60, ge=1, le=1000, description="Rate limit per user")
    authentication_required: bool = True

class IntegrationSettings(BaseModel):
    """External service integrations"""
    apis: List[Dict[str, Any]] = Field(default_factory=list, description="API integrations")
    webhooks: List[Dict[str, Any]] = Field(default_factory=list, description="Webhook configurations")
    databases: List[Dict[str, Any]] = Field(default_factory=list, description="Database connections")
    storage: Optional[Dict[str, Any]] = Field(default=None, description="File storage settings")

class DeploymentSettings(BaseModel):
    """Deployment configuration"""
    environment: Literal["development", "staging", "production"] = "development"
    scaling: Dict[str, Any] = Field(default_factory=dict, description="Auto-scaling settings")
    monitoring: bool = True
    logging_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    health_checks: bool = True

class ConfabConfig(BaseModel):
    """Complete confab configuration"""
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    model: ModelConfiguration
    knowledge_base: Optional[KnowledgeBase] = None
    conversation: ConversationSettings
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    integrations: IntegrationSettings = Field(default_factory=IntegrationSettings)
    deployment: DeploymentSettings = Field(default_factory=DeploymentSettings)
    custom_settings: Dict[str, Any] = Field(default_factory=dict, description="Additional custom configuration")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "capabilities": {
                    "text_generation": True,
                    "code_generation": True,
                    "data_analysis": False,
                    "web_search": True,
                    "file_processing": False,
                    "image_analysis": False,
                    "custom_tools": ["calculator", "weather_api"],
                },
                "model": {
                    "provider": "openai",
                    "model_name": "gpt-4",
                    "temperature": 0.7,
                    "max_tokens": 2000,
                    "top_p": 1.0,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                },
                "knowledge_base": {
                    "enabled": True,
                    "type": "documents",
                    "source": "./documents",
                    "indexing_method": "vector",
                    "chunk_size": 1000,
                    "overlap": 200,
                },
                "conversation": {
                    "system_prompt": "You are a helpful AI assistant specialized in software development. Provide clear, accurate, and well-structured responses.",
                    "max_conversation_length": 50,
                    "memory_enabled": True,
                    "context_window_size": 10,
                    "greeting_message": "Hello! I'm your software development assistant. How can I help you today?",
                    "error_message": "I apologize, but I encountered an error. Please try rephrasing your question.",
                },
                "security": {
                    "content_filtering": True,
                    "allowed_domains": ["github.com", "stackoverflow.com"],
                    "blocked_keywords": ["password", "secret", "token"],
                    "rate_limiting": True,
                    "max_requests_per_minute": 60,
                    "authentication_required": True,
                },
                "integrations": {
                    "apis": [
                        {
                            "name": "github_api",
                            "url": "https://api.github.com",
                            "auth_type": "token",
                            "rate_limit": 5000,
                        }
                    ],
                    "webhooks": [],
                    "databases": [],
                    "storage": {
                        "type": "s3",
                        "bucket": "confab-files",
                        "region": "us-west-2",
                    },
                },
                "deployment": {
                    "environment": "development",
                    "scaling": {"min_instances": 1, "max_instances": 5, "target_cpu": 70},
                    "monitoring": True,
                    "logging_level": "INFO",
                    "health_checks": True,
                },
                "custom_settings": {
                    "feature_flags": {"beta_features": True, "advanced_mode": False},
                    "ui_preferences": {"theme": "dark", "language": "en"},
                },
            }
        }
    )

# Simple configuration for basic use cases
class SimpleConfabConfig(BaseModel):
    """Simplified confab configuration for basic use cases"""
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "model_provider": "openai",
                "model_name": "gpt-4",
                "system_prompt": "You are a helpful AI assistant. Provide clear and accurate responses.",
                "temperature": 0.7,
                "max_tokens": 2000,
            }
        },
    )
    model_provider: Literal["openai", "anthropic", "google", "local"] = "openai"
    model_name: str = "gpt-4"
    system_prompt: str = Field(..., description="System prompt that defines agent behavior")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=100000)

# Confab schemas
class ConfabBase(BaseModel):
    name: str
    description: Optional[str] = None

class ConfabCreate(ConfabBase):
    config: Optional[Union[ConfabConfig, SimpleConfabConfig]] = None

class ConfabUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Union[ConfabConfig, SimpleConfabConfig]] = None

class ConfabResponse(ConfabBase):
    id: int
    version: str
    status: str
    github_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Auth schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[int] = None
