# MCP LangChain Integration Documentation

## Overview

This document describes the complete implementation of the new LangGraph-based agent architecture with MCP (Model Context Protocol) integration for the Let's Confab platform. The implementation follows the requested architecture:

```
User message
   ↓
LangGraph Agent
   ↓
LLM thinks
   ↓
Calls Tool (DB / GitHub / API)
   ↓
Gets result
   ↓
Thinks again
   ↓
More tools if needed
   ↓
Final response
```

## Architecture Changes

### 1. New Agent Architecture

The old Ollama-based system has been replaced with a more sophisticated LangGraph-based agent that:

- Uses LangGraph's `create_react_agent` for intelligent tool calling
- Integrates with MCP for tool management
- Supports multiple LLM providers (Ollama, OpenAI, Azure OpenAI)
- Implements the requested thinking → tool → result → thinking cycle

### 2. Database Integration

The system reads from the exact database schema as specified:

#### Tables Used:
- **confabs**: Main configuration storage
- **users**: User management
- **github_accounts**: GitHub integration
- **threads**: Conversation threads
- **messages**: Chat messages
- **thread_mapping**: Links confabs to threads

## File Changes and Implementations

### 1. `api/agent_tools.py` (Lines 1-186)

**Purpose**: Provides MCP-based tools for database and GitHub operations.

**Key Features**:
- MCP server initialization with FastMCP
- Four core tools as requested:
  1. `get_purpose(confab_id)` - Fetches purpose from GitHub PURPOSE.md or database
  2. `update_purpose(confab_id, purpose_markdown)` - Updates purpose in GitHub and database
  3. `search_knowledge_base(confab_id, query)` - Searches knowledge base documents
  4. `update_knowledge_base(confab_id, file_name, information)` - Updates knowledge base

**Implementation Details**:
```python
# MCP tool decorators
@mcp.tool()
def get_purpose(confab_id: int) -> Optional[str]:
    """Get the purpose markdown for a confab from GitHub repo's PURPOSE.md file or database."""

# LangChain tool wrappers
@tool(args_schema=GetPurposeInput)
def get_purpose_tool(confab_id: int) -> str:
    """Get the purpose for a confab from GitHub repo or database."""
```

**Database Integration**:
- Uses SQLAlchemy ORM to query Confab table
- Reads from `confab.config` JSON field for system prompts
- Integrates with GitHub API for PURPOSE.md file operations

### 2. `api/agent_runner.py` (Lines 1-200)

**Purpose**: Implements the LangGraph agent with the requested architecture.

**Key Features**:
- LangGraph `create_react_agent` implementation
- MCP server integration support
- LLM provider abstraction (supports Ollama, OpenAI, Azure)
- Tool calling with context injection

**Core Function**:
```python
async def run_langgraph_agent(confab_id: int, user_message: str, db: Session) -> Dict[str, Any]:
    """
    Architecture:
    User message -> LangGraph Agent -> LLM thinks -> Calls Tool -> Gets result -> Thinks again -> More tools -> Final response
    """
```

**Implementation Details**:
- **Line 25-35**: LLM initialization with fallback providers
- **Line 45-75**: Agent creation with tool integration
- **Line 77-120**: Message processing and response extraction
- **Line 122-150**: MCP server support for advanced tool management

**Architecture Flow**:
1. Receives user message and confab_id
2. Gets system prompt from confab configuration
3. Creates LangGraph agent with available tools
4. Processes message through agent
5. Agent thinks and calls tools as needed
6. Returns structured response with tool calls

### 3. `api/main.py` (Lines 948-1040)

**Purpose**: Adds new API endpoints for LangGraph agent integration.

**New Endpoints**:

#### `/agent/chat/{confab_id}` (Lines 951-1008)
```python
@app.post("/agent/chat/{confab_id}")
async def chat_with_langgraph_agent(
    confab_id: int,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
```

**Features**:
- Validates confab ownership
- Extracts user message from request
- Calls LangGraph agent
- Returns structured response with tool calls
- Implements the complete architecture flow

#### `/agent/status` (Lines 1010-1035)
```python
@app.get("/agent/status")
async def get_langgraph_agent_status(
    current_user: User = Depends(get_current_user)
):
```

**Features**:
- Returns agent system status
- LLM provider information
- Available tools count
- Architecture information

### 4. `ui/src/api/client.js` (Lines 238-250)

**Purpose**: Frontend API client methods for LangGraph integration.

**New Methods**:
```javascript
// Lines 240-246: LangGraph Agent chat endpoint
async chatWithLangGraphAgent(confabId, message) {
    return this.request(`/agent/chat/${confabId}`, {
        method: 'POST',
        body: JSON.stringify({ message }),
    });
}

// Lines 248-250: Agent status endpoint
async getAgentStatus() {
    return this.request('/agent/status');
}
```

### 5. `ui/src/components/AgentChat.tsx` (Lines 244-290)

**Purpose**: Updated frontend to use LangGraph agent instead of direct Ollama calls.

**Key Changes**:
- **Lines 249-261**: Primary LangGraph agent integration
- **Lines 263-290**: Fallback to Ollama if LangGraph fails
- **Line 253**: Uses `chatWithLangGraphAgent` API call
- **Line 254**: Extracts response from new response structure

**Architecture Implementation**:
```typescript
// Try LangGraph agent even if Ollama is not healthy
if (currentConfabId != null) {
    response = await apiClient.chatWithLangGraphAgent(currentConfabId, content);
    assistantContent = response.response || "I couldn't generate a response. Please try again.";
}
```

## Tool Implementation Details

### 1. Purpose Tools

#### `get_purpose(confab_id)`
- **Database Query**: `confabs` table → `config` JSON field
- **GitHub Integration**: Fetches `PURPOSE.md` from repo
- **Fallback**: Returns database-stored purpose if GitHub fails

#### `update_purpose(confab_id, purpose_markdown)`
- **Database Update**: Updates `config.conversation.system_prompt`
- **GitHub Integration**: Creates/updates `PURPOSE.md` in repo
- **Dual Storage**: Maintains both GitHub and database copies

### 2. Memory Tools

#### `search_knowledge_base(confab_id, query)`
- **Database Query**: Searches `config.knowledge_documents` array
- **Search Logic**: Case-insensitive substring matching
- **Return Format**: Array of matching documents with title/content

#### `update_knowledge_base(confab_id, file_name, information)`
- **Database Update**: Upserts documents in `config.knowledge_documents`
- **File Management**: Uses `file_name` as unique identifier
- **Content Storage**: Stores full document content in JSON field

## Database Schema Integration

### Confab Table Structure
```sql
CREATE TABLE confabs (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    version VARCHAR(50) DEFAULT '1.0.0',
    status VARCHAR(50) DEFAULT 'draft',
    config JSON,  -- Stores all agent configuration
    github_url VARCHAR(500),
    user_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Config JSON Structure
```json
{
    "conversation": {
        "system_prompt": "Purpose statement here",
        "memory_enabled": true
    },
    "custom_settings": {
        "purpose": "Purpose statement here",
        "memory_notes": "Memory configuration"
    },
    "knowledge_documents": [
        {
            "file_name": "document1.md",
            "title": "Document 1",
            "content": "Document content here"
        }
    ],
    "setup_steps_completed": [1, 2, 3]
}
```

## Architecture Flow Implementation

### 1. User Message Processing
```python
# AgentChat.tsx Line 253
response = await apiClient.chatWithLangGraphAgent(currentConfabId, content);
```

### 2. LangGraph Agent Processing
```python
# agent_runner.py Lines 45-75
agent = create_react_agent(model=model, tools=tools)
result = await agent.ainvoke({"messages": messages})
```

### 3. Tool Calling
```python
# agent_tools.py Lines 85-95
@tool(args_schema=GetPurposeInput)
def get_purpose_tool(confab_id: int) -> str:
    result = get_purpose(confab_id)
    return result or "No purpose found"
```

### 4. Database Operations
```python
# agent_tools.py Lines 15-25
confab = db.query(Confab).filter(Confab.id == confab_id).first()
cfg = confab.config or {}
return cfg.get("conversation", {}).get("system_prompt")
```

## Error Handling and Fallbacks

### 1. LLM Provider Fallback
```python
# agent_runner.py Lines 25-35
try:
    from langchain_community.llms import Ollama
    return Ollama(model="llama2", temperature=0.7)
except ImportError:
    try:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-3.5-turbo", temperature=0.7)
```

### 2. Frontend Fallback
```typescript
// AgentChat.tsx Lines 271-290
try {
    response = await apiClient.chatWithLangGraphAgent(currentConfabId, content);
} catch (langGraphError) {
    // Fallback to Ollama if LangGraph fails
    response = await apiClient.chatWithOllama(tid, content);
}
```

### 3. GitHub Integration Fallback
```python
# agent_tools.py Lines 20-30
try:
    g = Github(github_account.access_token)
    repo = g.get_repo(f"{github_account.selected_org}/{github_account.selected_repo}")
    purpose_file = repo.get_contents("PURPOSE.md")
    return purpose_file.decoded_content.decode('utf-8')
except Exception as e:
    logger.warning(f"Could not fetch PURPOSE.md from GitHub: {e}")
    # Fallback to database
```

## Installation Requirements

### Backend Dependencies
```bash
pip install langgraph langchain langchain-openai langchain-community langchain-mcp-adapters mcp fastmcp
```

### Frontend Dependencies
No additional dependencies required - uses existing API client structure.

## Configuration

### Environment Variables
```bash
# Existing variables remain the same
ALLOWED_ORIGINS=http://localhost:3002
DATABASE_URL=sqlite:///./confabs.db

# New optional variables for LLM configuration
OPENAI_API_KEY=your_openai_key
AZURE_OPENAI_ENDPOINT=your_azure_endpoint
AZURE_OPENAI_KEY=your_azure_key
```

## Testing the Implementation

### 1. Agent Status Check
```bash
curl -H "Authorization: Bearer <token>" http://localhost:8001/agent/status
```

### 2. Agent Chat
```bash
curl -X POST -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"message": "What is the purpose of this confab?"}' \
     http://localhost:8001/agent/chat/1
```

### 3. Tool Testing
The agent will automatically call tools based on user input:
- "What is our purpose?" → Calls `get_purpose`
- "Update our purpose to..." → Calls `update_purpose`
- "Search for information about..." → Calls `search_knowledge_base`
- "Add this to knowledge base..." → Calls `update_knowledge_base`

## Migration Notes

### Backward Compatibility
- Legacy `run_stage` function maintained for existing stage-based system
- Old Ollama endpoints remain functional
- Database schema unchanged

### Breaking Changes
- New agent architecture requires confab_id for all operations
- Response format changed to include tool_calls information
- Frontend updated to use new API endpoints

## Performance Considerations

### 1. Tool Caching
- GitHub API responses could be cached to reduce API calls
- Database queries are optimized with proper indexing

### 2. Async Operations
- All agent operations are async for better performance
- Database connections properly managed with context managers

### 3. Error Recovery
- Graceful fallbacks ensure system remains functional
- Comprehensive error logging for debugging

## Future Enhancements

### 1. Additional MCP Tools
- File system operations
- Web search capabilities
- External API integrations

### 2. Advanced Agent Features
- Multi-agent collaboration
- Tool chaining and composition
- Custom tool development

### 3. Performance Optimizations
- Tool result caching
- Parallel tool execution
- Streaming responses

## Summary

This implementation successfully transforms the Let's Confab platform from a simple Ollama-based chat system to a sophisticated LangGraph agent with MCP integration. The new architecture provides:

1. **Intelligent Tool Calling**: Agent can decide which tools to use based on context
2. **Database Integration**: Direct access to confabs, users, and knowledge base
3. **GitHub Integration**: Purpose management through GitHub repositories
4. **Extensible Architecture**: Easy to add new tools and capabilities
5. **Robust Error Handling**: Multiple fallbacks ensure system reliability
6. **Modern UI Integration**: Frontend updated to work with new agent architecture

The system now follows the requested architecture pattern where the agent thinks, calls tools, gets results, thinks again, and provides intelligent responses based on the available data and capabilities.
