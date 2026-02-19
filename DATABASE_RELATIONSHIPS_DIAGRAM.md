# Database Relationships & Data Entry Flow Diagram

## 🗄️ Complete Database Schema with Relationships

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          DATABASE OVERVIEW                               │
└──────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐
│      USERS          │
│ ─────────────────── │
│ id (PK)             │
│ name                │
│ email (UNIQUE)      │
│ password_hash       │
│ country             │
│ timezone            │
│ created_at          │
│ updated_at          │
└────────┬────────────┘
         │
    ┌────┴────┐
    │          │
    │ (1:N)    │ (1:1)
    │          │
    ▼          ▼
┌──────────────┐  ┌──────────────────────┐
│   CONFABS    │  │  GITHUB_ACCOUNTS     │
│ ──────────── │  │ ────────────────────  │
│ id (PK)      │  │ id (PK)              │
│ name         │  │ user_id (FK) → users │
│ description  │  │ github_id            │
│ version      │  │ github_username      │
│ status       │  │ access_token         │
│ config (JSON)│  │ selected_org         │
│ github_url   │  │ selected_repo        │
│ user_id (FK) ├──┤ created_at           │
│   ↓ users   │  │ updated_at           │
│ created_at   │  └──────────────────────┘
│ updated_at   │
└──────┬───────┘
       │
       │ (1:N)
       │
       ▼
    ┌──────────────────────────────────────────────────────────────┐
    │             THREAD_MAPPING (KEY LINKING TABLE!)              │
    │ ─────────────────────────────────────────────────────────── │
    │ id (PK)                                                      │
    │ confab_id (FK) ────────────┐                                │
    │   ↓ confabs               │  Links confab to thread         │
    │ thread_id (FK) ───────────┤  Enables querying:             │
    │   ↓ threads               │  - All threads for a confab    │
    │ created_at                │  - All confabs for a thread    │
    └──────────────┬────────────┴──────────────────────────────────┘
                   │
         ┌─────────┘
         │
    ┌────┴────┬────────────────┐
    │          │                │
    │ (1:N)    │ (1:N)    (1:N) │
    │          │                │
    ▼          ▼                ▼
┌─────────┐  ┌──────────┐  ┌────────────┐
│ THREADS │  │ MESSAGES │  │   Other    │
│ ─────── │  │ ────────│  │   Features │
│ id (PK) │  │ id (PK) │  │   (Future) │
│ thread_ │  │ thread_ │  │            │
│ name    │  │ id (FK) │  │            │
│ created ├──┤  ↓      │  │            │
│ _at     │  │ threads │  │            │
│ owner_  │  │ content │  │            │
│ user_id ├──┤ role    │  │            │
│   ↓     │  │ ('user' │  │            │
│ users   │  │  |      │  │            │
│         │  │ 'asst') │  │            │
│         │  │ time    │  │            │
└─────────┘  └──────────┘  └────────────┘
```

---

## 📍 How Data Gets Created

### Phase 1: User Enters @agentchat Page

```
┌─────────────────────────────────────────────────────────────┐
│ LOCATION 1 & 2: useEffect on Component Mount                │
│ File: ui/src/components/AgentChat.tsx (Lines 103-138)       │
│ [CLAUDE: IMPLEMENTATION - Create confab on page load]       │
└─────────────┬───────────────────────────────────────────────┘
              │
              ▼
    ┌──────────────────────┐
    │ Trigger: useEffect   │ (runs on page load)
    │ runs once on mount   │
    └────────┬─────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ API CALL: POST /confabs                      │
    │ {                                            │
    │   "name": "Agent Chat – 2/19/26, 2:30 PM"   │
    │   "description": "Auto-generated confab..   │
    │ }                                            │
    └────────┬─────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ BACKEND: create_confab() endpoint            │
    │ File: api/main.py (Lines 214-254)            │
    │                                              │
    │ 1. Creates Confab record in database         │
    │ 2. Associates with current_user              │
    │ 3. Sets status = "draft"                     │
    │ 4. Returns confab with new ID                │
    └────────┬─────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ DATABASE UPDATE: confabs table                │
    │                                              │
    │ INSERT INTO confabs (name, description,     │
    │   status, user_id, version, created_at)     │
    │ VALUES (                                     │
    │   "Agent Chat – 2/19/26, 2:30 PM",          │
    │   "Auto-generated confab for...",           │
    │   "draft",                                   │
    │   5,                                         │
    │   "1.0.0",                                   │
    │   NOW()                                      │
    │ );                                           │
    │                                              │
    │ New confab created: id = 42                  │
    └────────┬─────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ FRONTEND: Store in React State                │
    │                                              │
    │ currentConfabId = 42  ✅                     │
    │ console.log(                                 │
    │   '[CLAUDE: IMPLEMENTATION] Confab' +       │
    │   'created with ID: 42'                      │
    │ )                                            │
    └──────────────────────────────────────────────┘
```

---

### Phase 2: User Sends First Message

```
┌─────────────────────────────────────────────────────────────┐
│ LOCATION 3: handleSend() function                           │
│ File: ui/src/components/AgentChat.tsx (Lines 185-230)       │
│ [CLAUDE: IMPLEMENTATION - Create thread_mapping...]        │
└─────────────┬───────────────────────────────────────────────┘
              │
              ▼
    ┌──────────────────────────────────────────────┐
    │ USER SENDS MESSAGE                           │
    │ Message: "Create a customer support agent"   │
    └────────┬─────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ STEP 2A: Check if Thread Exists              │
    │                                              │
    │ if (currentThreadId == null) {               │
    │   // First message - need to create thread   │
    │ }                                            │
    └────────┬─────────────────────────────────────┘
             │
             YES (First message)
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ API CALL: POST /threads                      │
    │ {                                            │
    │   "thread_name": "Create Confab – 2/19..."  │
    │ }                                            │
    └────────┬─────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ BACKEND: create_thread() endpoint            │
    │ File: api/main.py (Lines 467-482)            │
    │                                              │
    │ 1. Creates Thread record                     │
    │ 2. Associates with current_user as owner    │
    │ 3. Returns thread with new ID                │
    └────────┬─────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ DATABASE UPDATE: threads table                │
    │                                              │
    │ INSERT INTO threads (thread_name,           │
    │   owner_user_id, created_at)                │
    │ VALUES (                                     │
    │   "Create Confab – 2/19/26",                │
    │   5,                                         │
    │   NOW()                                      │
    │ );                                           │
    │                                              │
    │ New thread created: id = 99                  │
    └────────┬─────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ FRONTEND: Store in React State                │
    │                                              │
    │ currentThreadId = 99  ✅                     │
    └────────┬─────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ STEP 2B: CREATE THREAD_MAPPING               │
    │ [KEY LINKING STEP]                           │
    │                                              │
    │ Check:                                       │
    │ if (tid != null && currentConfabId != null)  │
    │ if (99 != null && 42 != null)                │
    └────────┬─────────────────────────────────────┘
             │
             YES (Both IDs exist!)
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ API CALL: POST /thread-mappings              │
    │ {                                            │
    │   "confab_id": 42,                           │
    │   "thread_id": 99                            │
    │ }                                            │
    └────────┬─────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ BACKEND: create_thread_mapping() endpoint    │
    │ File: api/main.py (Lines 751-776)            │
    │                                              │
    │ 1. Validates confab ownership                │
    │ 2. Validates thread ownership                │
    │ 3. Creates ThreadMapping record              │
    │ 4. Returns mapping with new ID               │
    └────────┬─────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ DATABASE UPDATE: thread_mapping table         │
    │                                              │
    │ INSERT INTO thread_mapping (confab_id,      │
    │   thread_id, created_at)                    │
    │ VALUES (                                     │
    │   42,                                        │
    │   99,                                        │
    │   NOW()                                      │
    │ );                                           │
    │                                              │
    │ New mapping created: id = 1                  │
    │                                              │
    │ ✅ CONFAB 42 IS NOW LINKED TO THREAD 99!    │
    └────────┬─────────────────────────────────────┘
             │
             ▼
    ┌──────────────────────────────────────────────┐
    │ FRONTEND: Confirm in Console                 │
    │                                              │
    │ console.log(                                 │
    │   '[CLAUDE: IMPLEMENTATION]' +              │
    │   'Thread mapping created:'                  │
    │   {id: 1, confab_id: 42, thread_id: 99}    │
    │ )                                            │
    └──────────────────────────────────────────────┘
```

---

### Phase 3: Store Messages

```
┌──────────────────────────────────────────────────────────────┐
│ After thread_mapping is created, store messages in thread   │
└──────────────┬────────────────────────────────────────────────┘
               │
               ▼
    ┌─────────────────────────────────────────────┐
    │ API CALL: POST /threads/99/messages         │
    │                                             │
    │ Message 1 (Assistant greeting):            │
    │ {                                           │
    │   "content": "Hi! I'm your AI confab...",  │
    │   "role": "assistant"                       │
    │ }                                           │
    └────────┬────────────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────────┐
    │ DATABASE UPDATE: messages table              │
    │                                             │
    │ INSERT INTO messages (thread_id, content,   │
    │   role, time)                              │
    │ VALUES (99, "Hi! I'm your...", asst, NOW())│
    │ id = 1                                      │
    └────────┬────────────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────────┐
    │ API CALL: POST /threads/99/messages         │
    │                                             │
    │ Message 2 (User message):                  │
    │ {                                           │
    │   "content": "Create a customer support..", │
    │   "role": "user"                            │
    │ }                                           │
    └────────┬────────────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────────┐
    │ DATABASE UPDATE: messages table              │
    │                                             │
    │ INSERT INTO messages (thread_id, content,   │
    │   role, time)                              │
    │ VALUES (99, "Create a customer...", user,   │
    │   NOW())                                   │
    │ id = 2                                      │
    └────────┬────────────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────────┐
    │ API CALL: POST /threads/99/chat             │
    │                                             │
    │ Message 3 (AI response):                   │
    │ Generated by Ollama with context           │
    │ {                                           │
    │   "content": "Great! I'll help you...",    │
    │   "role": "assistant"                       │
    │ }                                           │
    └────────┬────────────────────────────────────┘
             │
             ▼
    ┌─────────────────────────────────────────────┐
    │ DATABASE UPDATE: messages table              │
    │                                             │
    │ INSERT INTO messages (thread_id, content,   │
    │   role, time)                              │
    │ VALUES (99, "Great! I'll help...", asst,    │
    │   NOW())                                   │
    │ id = 3                                      │
    └─────────────────────────────────────────────┘
```

---

## 🎯 Final Data State After All Operations

```
┌──────────────────────────────────────────────────────────────────┐
│ USERS Table                                                      │
├──────────────────────────────────────────────────────────────────┤
│ id=5, name='John Doe', email='john@example.com'                 │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ CONFABS Table                                                    │
├────┬──────────────────────┬────────┬────────────────────────────┤
│ id │ name                 │ status │ user_id                    │
├────┼──────────────────────┼────────┼────────────────────────────┤
│42  │ Agent Chat – 2/19/26 │ draft  │ 5                         │
└────┴──────────────────────┴────────┴────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ THREADS Table                                                    │
├────┬──────────────────────┬───────────────────────────────────┤
│ id │ thread_name          │ owner_user_id                     │
├────┼──────────────────────┼───────────────────────────────────┤
│99  │ Create Confab – 2/19 │ 5                                │
└────┴──────────────────────┴───────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ THREAD_MAPPING Table [THE KEY LINKING TABLE]                   │
├────┬───────────┬───────────┬──────────────────────────────────┤
│ id │confab_id  │ thread_id │ created_at                       │
├────┼───────────┼───────────┼──────────────────────────────────┤
│ 1  │    42     │     99    │ 2026-02-19 14:30:25            │
└────┴───────────┴───────────┴──────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ MESSAGES Table                                                   │
├────┬───────────┬──────────────────────────────────┬───────────┤
│ id │ thread_id │ content                          │ role      │
├────┼───────────┼──────────────────────────────────┼───────────┤
│ 1  │    99     │ Hi! I'm your AI confab builder...│ assistant │
│ 2  │    99     │ Create a customer support agent..│ user      │
│ 3  │    99     │ Great! I'll help you with that...│ assistant │
└────┴───────────┴──────────────────────────────────┴───────────┘

┌──────────────────────────────────────────────────────────────────┐
│ RELATIONSHIPS IN PLAY                                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User (5) ──owns──> Confab (42)                                 │
│           ──owns──> Thread (99)                                 │
│                                                                  │
│  Confab (42) ──linked via──> Thread_Mapping (1)               │
│  Thread (99) ──linked via──> Thread_Mapping (1)               │
│                                                                  │
│  Thread (99) ──contains──> Messages (1, 2, 3)                 │
│                                                                  │
│  ✅ CAN NOW QUERY:                                              │
│     "Show me all messages for confab 42"                        │
│     via: SELECT m.* FROM messages m                             │
│           JOIN threads t ON m.thread_id = t.id                  │
│           JOIN thread_mapping tm ON t.id = tm.thread_id         │
│           WHERE tm.confab_id = 42                               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 📊 SQL Queries to Verify Everything

```sql
-- 1. Find the confab created
SELECT * FROM confabs 
WHERE name LIKE 'Agent Chat%' 
ORDER BY created_at DESC LIMIT 1;

-- 2. Find the thread created
SELECT * FROM threads 
ORDER BY created_at DESC LIMIT 1;

-- 3. Find the thread_mapping
SELECT * FROM thread_mapping 
ORDER BY created_at DESC LIMIT 1;

-- 4. Verify they're linked correctly
SELECT 
    c.name AS confab_name,
    t.thread_name,
    tm.created_at AS mapping_created
FROM confabs c
JOIN thread_mapping tm ON c.id = tm.confab_id
JOIN threads t ON tm.thread_id = t.id
WHERE c.id = (SELECT confab_id FROM thread_mapping ORDER BY id DESC LIMIT 1);

-- 5. Get all messages for the confab
SELECT 
    m.id,
    m.content,
    m.role,
    m.time
FROM messages m
JOIN threads t ON m.thread_id = t.id
JOIN thread_mapping tm ON t.id = tm.thread_id
JOIN confabs c ON tm.confab_id = c.id
WHERE c.name LIKE 'Agent Chat%'
ORDER BY m.time;

-- 6. Complete audit trail
SELECT 
    'User' AS entity,
    u.name AS name,
    u.created_at AS created_at
FROM users u
WHERE u.id = 5

UNION ALL SELECT 
    'Confab' AS entity,
    c.name AS name,
    c.created_at AS created_at
FROM confabs c
WHERE c.id = 42

UNION ALL SELECT 
    'Thread' AS entity,
    t.thread_name AS name,
    t.created_at AS created_at
FROM threads t
WHERE t.id = 99

UNION ALL SELECT 
    'ThreadMapping' AS entity,
    CONCAT('Maps confab 42 to thread 99') AS name,
    tm.created_at AS created_at
FROM thread_mapping tm
WHERE tm.id = 1

ORDER BY created_at;
```

---

**Document Created:** February 19, 2026  
**Purpose:** Visual understanding of database relationships and data flow  
**Status:** ✅ COMPLETE
