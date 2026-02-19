# Changes: Review Chats + DB Alignment

This document marks where work was done to support **reviewing chats** and to align the project with your database structure:

- **Table 1 – users**: `id`, `name`, `email`, `createdAt` (DB: `created_at`), `password_hash` (existing in API; extra columns like `country`, `timezone` remain).
- **Table 2 – threads**: `thread_id` (API uses `id` as PK), `thread_name`, `createdAt` (DB: `created_at`), `owner_user_id`.
- **Table 3 – messages**: `id`, `thread_id`, `content`, `time` (plus optional `role` for user/assistant in the UI).

---

## Backend (API)

| Area | File | What was done |
|------|------|----------------|
| **Models** | `api/models.py` | Added `Thread` (thread_name, created_at, owner_user_id) and `Message` (thread_id, content, time, role). Added `threads` relationship on `User`. |
| **Migration** | `api/alembic/versions/add_threads_and_messages.py` | New migration creating `threads` and `messages` tables. |
| **Schemas** | `api/schemas.py` | Added `ThreadBase`, `ThreadCreate`, `ThreadResponse`, `MessageBase`, `MessageCreate`, `MessageResponse`. |
| **Routes** | `api/main.py` | Added `GET/POST /threads`, `GET /threads/{id}`, `GET/POST /threads/{id}/messages`; list threads for current user, create thread, list/add messages (for review chats). |

---

## Frontend (UI)

| Area | File | What was done |
|------|------|----------------|
| **API client** | `ui/src/api/client.js` | Added `getThreads()`, `createThread(threadName)`, `getThread(threadId)`, `getThreadMessages(threadId)`, `addMessage(threadId, content, role)`. |
| **Review Chats view** | `ui/src/components/ReviewChats.tsx` | **New file.** Lists threads from DB, selects one, shows messages (read-only review). Uses tables `threads` and `messages`. |
| **ConfabChat** | `ui/src/components/ConfabChat.tsx` | Optional `threadId` prop: when set, loads messages from API and persists new user/assistant messages to DB. Added “Save to my chats” to create a thread and save current messages, then navigate to Review Chats. |
| **App routing** | `ui/src/App.tsx` | Added view `review-chats` and render of `ReviewChats`. |
| **Header** | `ui/src/components/Header.tsx` | Added “Review Chats” nav item and view type `review-chats`. |

---

## How to run

1. **Apply DB migration** (from repo root):
   ```bash
   cd api && alembic upgrade head
   ```
   Or ensure the API has run so `Base.metadata.create_all(bind=engine)` can create the new tables if you are not using migrations.

2. **Start API** (e.g. port 8001) and **start UI** (e.g. `npm run dev` in `ui`).

3. **Use Review Chats**: Log in → click **Review Chats** in the header → select a thread to review messages.  
   To have threads/messages to review: open a confab chat, send a few messages, then click **Save to my chats**; the thread appears under Review Chats.

---

## Optional: existing DB

If your database already has `threads` and `messages` with the same column names (`id`, `thread_name`, `created_at`, `owner_user_id` for threads; `id`, `thread_id`, `content`, `time` for messages), you can skip the migration or run it only if it won’t conflict. The `messages` table in this migration also has an optional `role` column for `user`/`assistant`; if your table doesn’t have it, add it or make it nullable and handle `NULL` in the UI (default to “user”).
