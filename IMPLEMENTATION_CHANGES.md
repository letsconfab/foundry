# [CLAUDE] - Implementation Documentation: Ollama Integration & Database Updates

**Date**: February 19, 2026  
**Developer**: Claude (AI Assistant via GitHub Copilot)  
**Project**: Let's Confab - AI Confab Builder Platform

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration Changes](#configuration-changes)
3. [Database Schema Updates](#database-schema-updates)
4. [Backend API Changes](#backend-api-changes)
5. [Frontend Component Updates](#frontend-component-updates)
6. [File-by-File Changes](#file-by-file-changes)
7. [Setup and Testing](#setup-and-testing)
8. [API Endpoints Reference](#api-endpoints-reference)
9. [Troubleshooting](#troubleshooting)

---

## Overview

This document describes comprehensive updates made to the Let's Confab platform to integrate dynamic Ollama LLM responses and implement a robust thread-based message storage system.

### Key Improvements

1. **Dynamic Chat Responses**: Chat responses now come from Ollama API (gemma3:4b model) instead of static predefined responses
2. **Enhanced Database Schema**: Added 4th table (`thread_mapping`) to link confabs with conversation threads
3. **Ollama Service Integration**: Complete backend service for interacting with Ollama API
4. **Real-time Conversation Storage**: All chat messages are persisted in the database immediately
5. **Error Handling**: Graceful degradation when Ollama service is unavailable
6. **Health Monitoring**: Built-in Ollama service health checks

### System Architecture

```
User Input (AgentChat.tsx)
    ↓
API Client (client.js) → /threads/{id}/chat endpoint
    ↓
FastAPI Backend (main.py)
    ↓
Ollama Service (ollama_service.py) → Ollama API (http://localhost:11434)
    ↓
Response → Database Storage → Display to User
```

---

## Configuration Changes

### File: `.env`

**[CLAUDE: Added Ollama API configuration]**

```dotenv
# === OLLAMA API CONFIGURATION ===
# Base URL for Ollama API
VITE_OLLAMA_BASE_URL=http://localhost:11434

# API Key for Ollama
VITE_OLLAMA_API_KEY=ollama

# Model name for Ollama
VITE_OLLAMA_MODEL_NAME=gemma3:4b

# === BACKEND OLLAMA CONFIGURATION ===
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_API_KEY=ollama
OLLAMA_MODEL_NAME=gemma3:4b
```

**What These Do:**
- Frontend uses `VITE_` prefixed variables to communicate with Ollama
- Backend uses the non-prefixed versions for server-side Ollama interactions
- `gemma3:4b` is a lightweight 4B parameter model suitable for local development

---

## Database Schema Updates

### Complete Database Schema

#### Table 1: `users`
**Purpose**: Store user accounts and authentication data  
**Schema**:
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    country VARCHAR(100) NOT NULL,
    timezone VARCHAR(100) NOT NULL,
    created_at TIMESTAMP (DEFAULT NOW()),
    updated_at TIMESTAMP (DEFAULT NOW())
);
```

#### Table 2: `threads`
**Purpose**: Store chat conversation threads  
**Schema**:
```sql
CREATE TABLE threads (
    id INTEGER PRIMARY KEY,
    thread_name VARCHAR(500) NOT NULL,
    created_at TIMESTAMP (DEFAULT NOW()),
    owner_user_id INTEGER NOT NULL REFERENCES users(id)
);
```

#### Table 3: `messages`
**Purpose**: Store individual messages within threads  
**Schema**:
```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES threads(id),
    content TEXT NOT NULL,
    time TIMESTAMP (DEFAULT NOW()),
    role VARCHAR(20) DEFAULT 'user'  -- 'user' or 'assistant'
);
```

#### Table 4: `thread_mapping` [NEW - CLAUDE]
**Purpose**: Link conversation threads to their associated confabs  
**Schema**:
```sql
CREATE TABLE thread_mapping (
    id INTEGER PRIMARY KEY,
    confab_id INTEGER NOT NULL REFERENCES confabs(id),
    thread_id INTEGER NOT NULL REFERENCES threads(id),
    created_at TIMESTAMP (DEFAULT NOW())
);
```

### Why Table 4?

The `thread_mapping` table enables:
- Tracking which confab a conversation belongs to
- Retrieving all threads related to a specific confab
- Supporting multiple conversations per confab
- Clean separation of concerns between confab configuration and chat history

---

## Backend API Changes

### File: `api/models.py`
[CLAUDE: Added ThreadMapping model]

**New Class: `ThreadMapping`**
```python
class ThreadMapping(Base):
    """Maps threads to confabs for tracking which confab a conversation belongs to."""
    __tablename__ = "thread_mapping"
    
    id = Column(Integer, primary_key=True, index=True)
    confab_id = Column(Integer, ForeignKey("confabs.id"), nullable=False)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    confab = relationship("Confab", foreign_keys=[confab_id])
    thread = relationship("Thread", foreign_keys=[thread_id])
```

### File: `api/schemas.py`
[CLAUDE: Added Ollama and ThreadMapping schemas]

**New Schemas**:

1. **`OllamaRequest`** - Request structure for Ollama API
   - `model`: str - Model name (e.g., 'gemma3:4b')
   - `prompt`: str - User prompt
   - `stream`: bool - Whether to stream response
   - `temperature`: float - Sampling temperature

2. **`OllamaResponse`** - Response from Ollama
   - `model`: str
   - `response`: str - Generated text
   - `done`: bool

3. **`ThreadMappingCreate`** - Create thread mapping
   - `confab_id`: int
   - `thread_id`: int

4. **`ThreadMappingResponse`** - Response for thread mapping
   - `id`: int
   - `confab_id`: int
   - `thread_id`: int
   - `created_at`: datetime

5. **`ChatRequest`** - Request for chat completion
   - `thread_id`: int
   - `message`: str
   - `confab_id`: Optional[int]

6. **`ChatResponse`** - Response for chat completion
   - `thread_id`: int
   - `message_id`: int
   - `response`: str
   - `timestamp`: datetime

### File: `api/ollama_service.py`
[CLAUDE: New file - Ollama service module]

**Purpose**: Centralized Ollama API interactions

**Main Components**:

1. **`OllamaClient` Class**
   - `__init__()`: Initialize with Ollama URL, API key, and model
   - `generate_response()`: Generate text from Ollama
   - `health_check()`: Check if Ollama is running
   - `list_models()`: Get available models

2. **`ask_ollama()` Function**
   - Convenience function for generating responses
   - Handles aiohttp async calls
   - Includes error handling and logging

**Key Features**:
- Async/await pattern for non-blocking I/O
- 5-minute timeout for long-running responses
- Comprehensive error messages
- Health check capability

### File: `api/main.py`
[CLAUDE: Added Ollama endpoints and ThreadMapping imports]

**New Endpoints**:

1. **`GET /ollama/health`**
   - Check Ollama service status
   - Returns: `{"status": "healthy|unavailable", "healthy": bool}`

2. **`GET /ollama/models`**
   - List available models in Ollama
   - Returns: Models array from Ollama

3. **`POST /ollama/generate`**
   - Direct Ollama text generation
   - Request: `OllamaRequest`
   - Returns: `{"model": str, "response": str, "success": bool}`

4. **`POST /threads/{thread_id}/chat`** [MAIN ENDPOINT - CLAUDE]
   - Take user message and generate AI response
   - Store both user and assistant messages in database
   - Use conversation history for context
   - Returns both messages with IDs for UI synchronization
   - **Process**:
     1. Validate thread ownership
     2. Save user message to DB
     3. Load message history (last 10 messages)
     4. Send context to Ollama
     5. Save AI response to DB
     6. Return both messages

5. **`POST /thread-mappings`**
   - Create confab-to-thread mapping
   - Validates both confab and thread ownership
   - Returns: `ThreadMappingResponse`

6. **`GET /thread-mappings`**
   - List all thread mappings for current user
   - Filters to user's confabs and threads

7. **`GET /confab/{confab_id}/threads`**
   - Get all threads for a specific confab
   - Returns: List of `ThreadResponse`

---

## Frontend Component Updates

### File: `ui/src/components/AgentChat.tsx`
[CLAUDE: Updated to use Ollama for dynamic responses]

**State Changes**:

```typescript
// New Ollama-related state
const [ollamaHealthy, setOllamaHealthy] = useState(false);
const [ollamaError, setOllamaError] = useState<string | null>(null);
```

**useEffect Hook Added**:
```typescript
// Check Ollama health on component mount
useEffect(() => {
  const checkOllama = async () => {
    try {
      const health = await apiClient.ollamaHealthCheck();
      setOllamaHealthy(health.healthy);
      if (!health.healthy) {
        setOllamaError('Ollama service is not available...');
      }
    } catch (error) {
      setOllamaHealthy(false);
      setOllamaError('Could not connect to Ollama service');
    }
  };
  checkOllama();
}, []);
```

**`handleSend()` Function Completely Rewritten** [CLAUDE]:

**Old Behavior**:
- Used predefined static responses array
- Responses rotated based on message count
- No actual AI processing

**New Behavior**:
1. Check if Ollama is available
2. If unavailable, provide user-friendly message
3. If available, call `/threads/{thread_id}/chat` endpoint
4. Ollama generates context-aware response
5. Both user and AI messages stored in database
6. Graceful error handling with user-friendly messages

**Key Code**:
```typescript
// Generate AI response from Ollama API
try {
  if (!ollamaHealthy) {
    assistantContent = "I notice that the Ollama service is not currently available...";
  } else {
    if (tid != null) {
      const response = await apiClient.chatWithOllama(tid, content);
      assistantContent = response.assistant_message?.content;
    }
  }
} catch (error) {
  assistantContent = `I encountered an error: ${error.message}`;
  setOllamaError(error.message);
}
```

**Ollama Status Display** [CLAUDE]:

Added visual indicator in Repository Configuration section:

```tsx
{!ollamaHealthy && (
  <div className="p-3 bg-yellow-50 rounded-lg">
    <AlertCircle className="w-4 h-4 text-yellow-600" />
    <span>Ollama Service Status</span>
    <p>Ollama is not available...</p>
  </div>
)}

{ollamaHealthy && (
  <div className="p-3 bg-green-50 rounded-lg">
    <CheckCircle className="w-4 h-4 text-green-600" />
    <span>Ollama Service Active</span>
  </div>
)}
```

### File: `ui/src/api/client.js`
[CLAUDE: Added Ollama and ThreadMapping methods]

**New Methods**:

1. **`chatWithOllama(threadId, message)`**
   - Send message to thread with Ollama response
   - Returns both user and assistant messages

2. **`ollamaHealthCheck()`**
   - Check Ollama service availability
   - Returns: `{status, healthy, model, ollama_url}`

3. **`ollamaGenerateResponse(prompt)`**
   - Direct Ollama generation without thread storage
   - Returns: `{model, response, success}`

4. **`ollamaListModels()`**
   - Get available models
   - Returns: Models list from Ollama

5. **`createThreadMapping(confabId, threadId)`**
   - Link confab to thread
   - Returns: `ThreadMappingResponse`

6. **`getThreadMappings()`**
   - Get all user's thread mappings

7. **`getConfabThreads(confabId)`**
   - Get threads for specific confab

---

## File-by-File Changes

### Summary by File

| File | Type | Change | Impact |
|------|------|--------|--------|
| `.env` | Config | Added Ollama vars | High |
| `api/models.py` | Backend | Added ThreadMapping class | High |
| `api/schemas.py` | Backend | Added Ollama/mapping schemas | High |
| `api/ollama_service.py` | Backend | NEW FILE | High |
| `api/main.py` | Backend | Added 7 endpoints, imports | High |
| `ui/src/components/AgentChat.tsx` | Frontend | Updated handleSend, added health check | High |
| `ui/src/api/client.js` | Frontend | Added 7 Ollama/mapping methods | High |

### Changes with Line Numbers

**See specific files for detailed modifications marked with [CLAUDE]**

---

## Setup and Testing

### Prerequisites

1. **Ollama Running Locally**
   ```bash
   # On Windows/Mac/Linux
   # Download from ollama.ai and run
   ollama serve
   ```

2. **Pull Model**
   ```bash
   ollama pull gemma3:4b
   ```

3. **Database Setup**
   ```bash
   cd api
   . .venv/bin/activate
   alembic upgrade head
   ```

### Testing the Integration

#### 1. Check Ollama Health
```bash
curl http://localhost:11434/api/tags
```

**Expected Response**:
```json
{
  "models": [
    {
      "name": "gemma3:4b:latest",
      "modified_at": "2024-01-01T00:00:00Z",
      "size": 2548900000,
      "digest": "..."
    }
  ]
}
```

#### 2. Test Ollama Generation
```bash
curl -X POST http://localhost:8001/ollama/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "model": "gemma3:4b",
    "prompt": "What is a confab?",
    "stream": false
  }'
```

#### 3. Test Chat Endpoint
```bash
# Create thread first
THREAD_ID=1

# Send chat message
curl -X POST http://localhost:8001/threads/$THREAD_ID/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "content": "Create a customer support agent",
    "role": "user"
  }'
```

#### 4. Browser Testing
1. Start frontend: `npm run dev`
2. Navigate to AgentChat
3. Observe Ollama status indicator
4. Type message and click Send
5. Watch for Ollama response
6. Check console for [CLAUDE] debug logs

### Verification Checklist

- [ ] `.env` contains all Ollama variables
- [ ] Database migrations run successfully
- [ ] Ollama service is running at localhost:11434
- [ ] Health check shows "Ollama Service Active"
- [ ] Chat messages appear and persist
- [ ] Database contains threads and messages
- [ ] Thread mappings created for confabs

---

## API Endpoints Reference

### Ollama Endpoints

**GET** `/ollama/health`
- Check Ollama service status
- Returns: Health status object
- Requires: No auth (can be unauthenticated for health checks)

**GET** `/ollama/models`
- List available Ollama models
- Returns: Models array
- Requires: Bearer token

**POST** `/ollama/generate`
- Generate text directly from Ollama
- Body: `{model, prompt, stream, temperature}`
- Returns: `{model, response, success}`
- Requires: Bearer token

### Chat Endpoints

**POST** `/threads/{thread_id}/chat` [MAIN ENDPOINT]
- Send message and get Ollama response
- Body: `{content, role}`
- Returns: `{user_message, assistant_message, success}`
- Process: Validates → Saves user msg → Gets context → Calls Ollama → Saves asst msg → Returns both
- Requires: Bearer token (validates ownership)

### Thread Mapping Endpoints

**POST** `/thread-mappings`
- Create confab-thread mapping
- Body: `{confab_id, thread_id}`
- Returns: `ThreadMappingResponse`
- Requires: Bearer token

**GET** `/thread-mappings`
- List user's thread mappings
- Returns: Array of `ThreadMappingResponse`
- Requires: Bearer token

**GET** `/confab/{confab_id}/threads`
- Get threads for a confab
- Returns: Array of `ThreadResponse`
- Requires: Bearer token (validates confab ownership)

---

## Troubleshooting

### Problem: "Ollama service is not available"

**Check**:
1. Is Ollama running? `ollama serve`
2. Is it at localhost:11434? Check `OLLAMA_BASE_URL`
3. Browser console for specific error

**Solution**:
```bash
# Restart Ollama
make db  # If using Docker

# Or manually
ollama serve
```

### Problem: Chat responses are generic/not specific

**Check**:
1. Is the context being built correctly?
2. Are messages stored in database?
3. Is Ollama model loaded? `ollama list`

**Solution**:
1. Check `/threads/{id}/messages` endpoint
2. Verify message order in database
3. Ensure conversation history is recent

### Problem: Slow response times

**Check**:
1. CPU usage during generation (normal if high)
2. Network latency
3. Model size (gemma3:4b is small, should be fast)

**Solution**:
1. Give Ollama more time to think
2. Check `OLLAMA_BASE_URL` for network distance
3. Reduce context window in handleSend (change -10 to -5)

### Problem: Database doesn't show messages

**Check**:
1. Thread created? `SELECT * FROM threads WHERE owner_user_id = YOUR_ID`
2. Messages inserted? `SELECT * FROM messages WHERE thread_id = THREAD_ID`
3. Thread ownership validation

**Solution**:
```bash
cd api
. .venv/bin/activate
sqlite3 postgres.db "SELECT * FROM messages LIMIT 10;"
```

### Problem: CORS errors in browser console

**Solution**:
Check `.env` `ALLOWED_ORIGINS` includes `http://localhost:3002`

---

## Developer Notes

### Key Design Decisions

1. **Ollama Service Layer**: Separate `ollama_service.py` module provides clean abstraction
2. **Thread Mapping Table**: Flexible design supports multiple use cases
3. **Async/Await**: Non-blocking Ollama calls prevent UI freezing
4. **Health Checks**: Proactive service monitoring for better UX
5. **Message Context**: Uses last 10 messages for Ollama (configurable)

### Performance Considerations

- Ollama gemma3:4b: ~2.5GB model, fast responses
- Message context limit: 10 messages (configurable)
- Database queries: Indexed on thread_id, owner_user_id
- Frontend debouncing: Not needed (sequential messages)

### Security Considerations

- All endpoints require Bearer token authentication
- Thread/confab ownership validated server-side
- No sensitive data in Ollama prompts
- API key stored in environment variables

### Future Enhancements

1. Stream responses (requires WebSocket)
2. Model selection UI
3. Temperature/sampling parameter UI
4. Conversation export
5. Offline mode with cached responses
6. Multi-turn conversation optimization

---

## Summary

This implementation provides a complete integration of Ollama LLM capabilities into the Let's Confab platform with persistent conversation storage. The system is designed to be:

- **Robust**: Error handling for Ollama unavailability
- **Scalable**: Database-backed message storage
- **User-Friendly**: Visual status indicators and helpful notifications
- **Developer-Friendly**: Clean separation of concerns and comprehensive documentation

All changes are marked with **[CLAUDE]** tags in source code for easy identification.

**Total Files Modified**: 7  
**New Files Created**: 1  
**New Database Tables**: 1  
**New API Endpoints**: 7

---

**End of Documentation**

*Generated by: GitHub Copilot using Claude Haiku 4.5*  
*Date: February 19, 2026*
