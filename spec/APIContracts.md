# API Contracts

## Overview

The backend exposes a REST API. All authenticated endpoints require a Bearer token in the `Authorization` header. Errors are returned as JSON with a `detail` field.

---

## Authentication Endpoints

### Register

`POST /auth/register`

Creates a new user account and returns an access token.

- **Request body:** name, email, password, country, timezone
- **Response:** User profile with access token
- **Errors:** 400 if email already registered, 400 if password too long

### Login

`POST /auth/login`

Authenticates with email and password.

- **Request body:** email, password
- **Response:** User profile with access token
- **Errors:** 401 if credentials are invalid

### Get Current User

`GET /auth/me` (authenticated)

Returns the current user's profile, including whether a GitHub account is connected.

- **Response:** User profile with `github_connected` flag
- **Errors:** 401 if token is invalid or expired

### Connect GitHub

`POST /auth/github/connect` (authenticated)

Links a GitHub account to the current user.

- **Request body:** github_id, github_username, access_token, selected_repo, optional selected_org
- **Response:** Success message

### GitHub Login

`POST /auth/github/login`

Logs in or creates an account using GitHub credentials. If no user exists for the GitHub email, one is created automatically.

- **Request body:** github_id, github_username, access_token, optional selected_repo (defaults to `"confabs"`), optional selected_org
- **Response:** User profile with access token
- **Errors:** 400 if GitHub user info cannot be retrieved

### GitHub Authorization

`GET /auth/github/authorize`

Redirects the user to GitHub's OAuth consent page.

- **Response:** HTTP redirect to GitHub
- **Errors:** 500 if GitHub OAuth is not configured

### GitHub Callback

`GET /auth/github/callback`

Handles the OAuth callback from GitHub. Exchanges the authorization code for an access token, then redirects to the frontend with the GitHub credentials as query parameters.

- **Query param:** `code`
- **Response:** HTTP redirect to frontend with access_token, github_id, github_username
- **Errors:** 400 if code is missing or exchange fails, 502 on GitHub timeout

### List GitHub Repos

`GET /auth/github/repos` (authenticated)

Returns the user's accessible GitHub repositories (personal and organization).

- **Response:** List of repositories with name, full_name, private flag, owner, and permissions
- **Errors:** 400 if GitHub is not connected

---

## Confab Endpoints

### Create Confab

`POST /confabs` (authenticated)

Creates a new confab. Defaults to `status='building'` for the Foreman-guided creation flow. If GitHub is connected and the confab is published, also creates a branch with confab files and opens a pull request.

- **Request body:** name (optional), description (optional), config (optional), generate_placeholder (optional), status (optional)
- **Response:** Confab with id, version (`"1.0.0"`), status, timestamps, optional github_url

### List Confabs

`GET /confabs` (authenticated)

Returns all confabs owned by the current user.

- **Response:** List of confabs

### Get Confab

`GET /confabs/{confab_id}` (authenticated)

Returns a single confab. Only the owner can access it.

- **Response:** Confab
- **Errors:** 404 if not found or not owned by current user

### Update Confab

`PUT /confabs/{confab_id}` (authenticated)

Updates a confab's name and description. Auto-increments the version by 0.1. If GitHub is connected, creates a new branch and pull request with updated files.

- **Request body:** name, optional description, optional config
- **Response:** Updated confab
- **Errors:** 404 if not found

### Delete Confab

`DELETE /confabs/{confab_id}` (authenticated)

Deletes a confab from the database. GitHub files are not removed.

- **Response:** Success message
- **Errors:** 404 if not found

### Export Confab as OASF

`GET /confabs/{confab_id}/export` (authenticated)

Exports a confab as OASF-compliant files.

- **Response:**
  - `confab_id`
  - `confab_name`
  - `version`
  - `files` - Object with keys: `agent.oasf.yaml`, `PURPOSE.md`, `GUARDRAILS.md`, `TESTS.md`
- **Errors:** 404 if not found

### Test Repository

`POST /confabs/test-repo` (authenticated)

Tests the GitHub integration by creating a dummy confab structure. For users without GitHub, returns a simulated success response.

- **Response:** repo_name, repo_url, pr_url, test_files

---

## Thread Endpoints

### List Threads

`GET /threads` (authenticated)

Returns all threads owned by the current user.

- **Response:** Array of threads with id, name, owner_user_id, created_at

### Create Thread

`POST /threads` (authenticated)

Creates a new thread. Automatically adds the current user as owner participant.

- **Request body:** `name` (string, required)
- **Response:** Thread object

### Get Thread with Participants

`GET /threads/{thread_id}` (authenticated)

Returns a thread with its participants list.

- **Response:** Thread with participants array
- **Errors:** 404 if not found or not owned by current user

### Delete Thread

`DELETE /threads/{thread_id}` (authenticated)

Deletes a thread and all its participants and messages.

- **Response:** 204 No Content
- **Errors:** 404 if not found

---

## Thread Participant Endpoints

### List Participants

`GET /threads/{thread_id}/participants` (authenticated)

Returns active participants in a thread.

- **Response:** Array of participants with id, thread_id, participant_type, participant_id, system_agent_name, role, is_active, joined_at

### Add Participant

`POST /threads/{thread_id}/participants` (authenticated)

Adds a participant to a thread.

- **Request body:**
  - `participant_type` (string, required) - `user`, `confab`, or `system`
  - `participant_id` (integer, required for user/confab types)
  - `system_agent_name` (string, required for system type) - e.g., `"foreman"`
  - `role` (string, optional) - defaults to `participant`
- **Response:** Created participant

### Remove Participant

`DELETE /threads/{thread_id}/participants/{participant_id}` (authenticated)

Soft-deletes a participant (sets `is_active=false`, records `left_at`).

- **Response:** 204 No Content
- **Errors:** 404 if not found

---

## Message Endpoints

### List Messages

`GET /threads/{thread_id}/messages` (authenticated)

Returns all messages in a thread, ordered by created_at.

- **Response:** Array of messages with id, thread_id, sender_type, sender_id, sender_name, content, role, in_reply_to, depth, addressed_to, created_at

### Add Message (No Agent Response)

`POST /threads/{thread_id}/messages` (authenticated)

Adds a message to a thread without triggering agent responses. Used for:
- Saving initial greetings
- Persisting messages manually
- System notifications

- **Request body:**
  - `content` (string, required)
  - `role` (string, required) - `user` or `assistant`
  - `sender_type` (string, optional) - `user`, `confab`, or `system`
  - `sender_id` (integer, optional)
  - `sender_name` (string, optional)
  - `in_reply_to` (integer, optional)
  - `addressed_to` (array, optional)
- **Response:** The saved message

### Chat with Agent Responses

`POST /threads/{thread_id}/chat` (authenticated)

Unified chat endpoint that saves user messages and generates responses from thread participants (confabs and system agents).

- **Request body:**
  - `content` (string, required) - The user message
  - `in_reply_to` (integer, optional) - Message ID for subthread replies
  - `addressed_to` (array, optional) - Explicit recipients: `[{"type": "confab", "id": 5}]`
- **Response:**
  - `thread_id` - The thread ID
  - `user_message` - The saved user message
  - `agent_responses` - Array of responses from participating agents
  - `timestamp` - ISO 8601 timestamp

**Foreman Routing:** If the thread has a system participant with `system_agent_name='foreman'`, the endpoint:
1. Finds the user's most recent confab with `status='building'`
2. Initializes the Foreman agent with that confab's context
3. Returns the Foreman's response (not the confab's)

**Confab Routing:** For confab participants:
- Confabs with `status='building'` do NOT respond (Foreman handles the conversation)
- Confabs with other statuses respond using their configured purpose and guardrails

**Response Inference:** When `addressed_to` is NULL (broadcast), agents infer whether to respond. Currently, all active agents respond to broadcasts.

**Foreman Tools:** The Foreman has access to setup tools:

| Tool | Description |
|------|-------------|
| `define_purpose` | Save the purpose text and mark step 1 complete |
| `add_participant` | Add an email to the participant list |
| `configure_memory` | Toggle memory settings |
| `add_tools_and_apis` | Record external API configuration |
| `guardrails` | Write guardrail rules |
| `sample_io` | Save example input/output scenarios |
| `review_and_save` | Finalize confab, set status to `draft` |
| `update_purpose` | Modify existing purpose |

---

## Utility Endpoints

### Health Check

`GET /`

- **Response:** `{"message": "Let's Confab API"}`

---

## Cross-Cutting Concerns

### Error Format

All errors return JSON:

```json
{"detail": "<human-readable message>"}
```

### Status Codes

| Code | Usage |
|------|-------|
| 400 | Invalid input, duplicate data, missing prerequisites |
| 401 | Invalid or expired token, wrong credentials |
| 404 | Resource not found or not accessible |
| 500 | Server misconfiguration |
| 502 | Upstream service failure (e.g., GitHub API timeout) |

### CORS

The API must allow cross-origin requests from the frontend origin. Credentials, all methods, and all headers should be permitted.

### GitHub Resilience

GitHub operations during confab create/update must not block the primary operation. If GitHub is unreachable or returns an error, the confab should still be saved to the database. The `github_url` will be null in that case.
