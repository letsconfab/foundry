# Interactions

## User Journeys

### 1. New User Registration (Email)

1. User lands on the home page (`HeroSection`).
2. Clicks "Get Started" or navigates to Register.
3. Fills in: full name, email, password, confirm password, country, timezone.
4. Submits the form → `POST /auth/register`.
5. Backend creates a user record with bcrypt-hashed password, returns a JWT token.
6. Frontend stores the token in `localStorage`, updates `AuthContext`.
7. User is redirected to the Dashboard.

### 2. New User Registration (GitHub)

1. User clicks "Continue with GitHub" on the Register page.
2. Frontend redirects to `GET /auth/github/authorize`.
3. Backend redirects to GitHub's OAuth consent screen (scope: `public_repo user:email`).
4. User authorizes the app on GitHub.
5. GitHub redirects to `GET /auth/github/callback` with an authorization code.
6. Backend exchanges the code for an access token, fetches the user's GitHub profile and primary email.
7. Backend redirects to the frontend's `/auth/github/callback` with the access token, GitHub ID, and username as query parameters.
8. `GitHubCallback` component calls `POST /auth/github/login`.
9. Backend creates a user (if new) and a `GitHubAccount` record, returns a JWT token.
10. Frontend stores the token, updates auth state, navigates to Dashboard.

### 3. Existing User Login

1. User navigates to Login.
2. Enters email and password → `POST /auth/login`.
3. Backend verifies credentials, returns a JWT token.
4. Frontend stores token, redirects to Dashboard.

### 4. Connecting GitHub to an Existing Account

1. Logged-in user clicks "Continue with GitHub" on the Login page (or a GitHub connect prompt).
2. Same OAuth flow as registration (steps 2-7 above).
3. `GitHubCallback` detects an existing token in `localStorage`.
4. Calls `POST /auth/github/connect` with the GitHub data.
5. Backend creates or updates the `GitHubAccount` linked to the current user.
6. User is redirected to Dashboard with GitHub now connected.

### 5. Creating a Confab (with Foreman)

1. From the Dashboard, user clicks "Create New Confab".
2. Backend creates a new confab with `status='building'` and no content → `POST /confabs`.
3. Backend creates a thread with two participants:
   - The user (owner)
   - The Foreman (system agent)
4. UI navigates to `AgentChat` wizard.
5. Foreman sends initial greeting:
   > "Welcome to the Agent Foundry. I am the Foreman, and will walk you through the creation of this confab (Collaborative Agent)."
6. User converses with Foreman through 7 steps:
   - **Define Purpose** — Foreman asks what the agent should do
   - **Add Participants** — Who can access it
   - **Configure Memory** — Should it remember conversations
   - **Set Up Tools** — External capabilities
   - **Establish Guardrails** — Safety boundaries
   - **Sample I/O** — Example interactions
   - **Review** — Finalize configuration
7. Foreman uses tools (`define_purpose`, `guardrails`, etc.) to save configuration incrementally to the confab record.
8. Progress is tracked in `confab.setup_progress` JSON field.
9. On completion, Foreman sets confab status to `draft` (ready for deployment).
10. If GitHub is connected, confab files are synced to the repository.

### 5a. Resuming Confab Building ("Continue Building")

1. From Dashboard, user clicks "Continue Building" on a confab with `status='building'`.
2. Frontend loads the existing confab and finds its Foreman thread.
3. Previous messages are loaded from the thread's message history.
4. Foreman generates a resume prompt based on `setup_progress`:
   - Summarizes completed steps
   - Shows current progress
   - Asks about the next incomplete step
5. User continues the conversation from where they left off.

### 5b. Chatting with Foreman During Building

1. User sends a message in the AgentChat interface.
2. Frontend calls `POST /threads/{thread_id}/chat` with the message.
3. Backend identifies the Foreman as a system participant.
4. Backend finds the user's confab with `status='building'`.
5. Foreman loads full context: confab state, thread history, setup progress.
6. Foreman generates a directive response (acknowledges input, saves relevant data, asks next question).
7. If the response signals step completion, progress is updated in `confab.setup_progress`.
8. Response is saved to the thread and returned to the frontend.
9. UI displays the Foreman's response with HardHat icon and amber gradient.

### 6. Updating a Confab

1. User selects an existing confab from the Dashboard.
2. Navigates to the configuration view (threaded or standard).
3. Modifies settings and saves → `PUT /confabs/{id}`.
4. Backend increments the version by 0.1 and updates the database.
5. If GitHub is connected, a new branch and pull request are created with the updated files.

### 7. Deleting a Confab

1. User opens the actions dropdown on a confab card in the Dashboard.
2. Clicks "Delete" → `DELETE /confabs/{id}`.
3. Confab is removed from the database. (GitHub files remain in the repository.)

### 8. Configuring Deployment

1. User navigates to the Deployment Panel.
2. Selects deployment type: Cloud or Self-hosted.
3. Picks a cloud provider (AWS, Azure, GCP, DigitalOcean) and region.
4. Picks an LLM provider (OpenAI, Anthropic, Google, Cohere) and model.
5. Submits the configuration. (Backend deployment provisioning is not yet implemented.)

### 9. Chatting with a Deployed Confab

1. User navigates to the Confab Chat view.
2. Sends messages in a chat interface.
3. Can provide feedback on responses (thumbs up/down with optional modal).
4. Participant list shows who is in the conversation. (Live LLM execution for deployed confabs is not yet implemented.)

### 10. Testing GitHub Integration

1. In the Agent Chat wizard, user clicks the "Test" button.
2. Frontend calls `POST /confabs/test-repo`.
3. For GitHub-connected users: backend creates a test repository with a dummy confab and opens a PR.
4. For users without GitHub: returns a simulated success response.
5. Result (repo URL, PR URL) is displayed in the chat.

---

## API Interfaces

### Base URL

`http://localhost:8001` (development)

### Authentication Endpoints

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| POST | `/auth/register` | Register a new user | No |
| POST | `/auth/login` | Login with email/password | No |
| GET | `/auth/me` | Get current user profile | Yes |
| POST | `/auth/github/connect` | Link GitHub account to current user | Yes |
| POST | `/auth/github/login` | Login or signup via GitHub | No |
| GET | `/auth/github/repos` | List user's GitHub repositories | Yes |
| GET | `/auth/github/authorize` | Redirect to GitHub OAuth consent | No |
| GET | `/auth/github/callback` | Handle GitHub OAuth callback | No |

### Confab Endpoints

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| POST | `/confabs` | Create a new confab | Yes |
| GET | `/confabs` | List all confabs for current user | Yes |
| GET | `/confabs/{confab_id}` | Get a specific confab | Yes |
| PUT | `/confabs/{confab_id}` | Update a confab | Yes |
| DELETE | `/confabs/{confab_id}` | Delete a confab | Yes |
| GET | `/confabs/{confab_id}/export` | Export as OASF files | Yes |
| POST | `/confabs/test-repo` | Test GitHub repository initialization | Yes |

### Thread Endpoints

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/threads` | List threads owned by current user | Yes |
| POST | `/threads` | Create a new thread | Yes |
| GET | `/threads/{thread_id}` | Get thread with participants | Yes |
| DELETE | `/threads/{thread_id}` | Delete a thread | Yes |
| GET | `/threads/{thread_id}/participants` | List participants | Yes |
| POST | `/threads/{thread_id}/participants` | Add participant | Yes |
| DELETE | `/threads/{thread_id}/participants/{id}` | Remove participant | Yes |
| GET | `/threads/{thread_id}/messages` | List messages | Yes |
| POST | `/threads/{thread_id}/messages` | Add message (no agent response) | Yes |
| POST | `/threads/{thread_id}/chat` | Chat with agent responses | Yes |

### Utility Endpoints

| Method | Path | Description | Auth Required |
|--------|------|-------------|---------------|
| GET | `/` | Health check / API info | No |

### Authentication Scheme

All authenticated endpoints require:
```
Authorization: Bearer <jwt_token>
```

### API Documentation

- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

---

## External Service Interfaces

### GitHub API (Outbound)

The backend communicates with GitHub's REST API v3 for:

| Operation | GitHub Endpoint | Used By |
|-----------|----------------|---------|
| Exchange OAuth code for token | `POST https://github.com/login/oauth/access_token` | `github_oauth.py` |
| Get authenticated user | `GET https://api.github.com/user` | `github_oauth.py` |
| Get user emails | `GET https://api.github.com/user/emails` | `github_oauth.py` |
| List user repos | `GET https://api.github.com/user/repos` | `github_oauth.py` |
| List user orgs | `GET https://api.github.com/user/orgs` | `github_oauth.py` |
| List org repos | `GET https://api.github.com/orgs/{org}/repos` | `github_oauth.py` |
| Check repo permissions | `GET https://api.github.com/repos/{owner}/{repo}` | `github_oauth.py` |
| Get branch reference | `GET https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{branch}` | `github_service.py` |
| Create branch | `POST https://api.github.com/repos/{owner}/{repo}/git/refs` | `github_service.py` |
| Create/update file | `PUT https://api.github.com/repos/{owner}/{repo}/contents/{path}` | `github_service.py` |
| Create pull request | `POST https://api.github.com/repos/{owner}/{repo}/pulls` | `github_service.py` |
| Create repository | `POST https://api.github.com/user/repos` | `github_service.py` |

### Groq API (LLM)

- **Provider:** Groq
- **Model:** qwen/qwen3-32b
- **Used By:** `llm_service.py`
- **Purpose:** Powers the Foreman agent and confab conversations

### PostgreSQL (Database)

- Connection via SQLAlchemy engine using `DATABASE_URL`.
- Default: `postgresql://postgres:password@localhost:7432/confab_foundry_db`.
- Tables: `users`, `github_accounts`, `confabs`, `confab_learnings`, `threads`, `thread_participants`, `messages`.

### Frontend → Backend (Internal)

- The React frontend calls the FastAPI backend at `VITE_API_URL` (default: `http://localhost:8001`).
- All requests go through the `ApiClient` singleton which injects the JWT Bearer token from `localStorage`.
- CORS is configured on the backend via `ALLOWED_ORIGINS`.
