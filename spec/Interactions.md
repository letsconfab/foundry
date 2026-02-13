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

### 5. Creating a Confab

1. From the Dashboard, user clicks "Create New Confab".
2. Navigates to the `AgentChat` wizard.
3. Walks through 7 steps via a conversational chat interface:
   - **Define Purpose** — Name, description, objectives.
   - **Add Participants** — Users and other confabs with roles.
   - **Configure Memory** — Memory and conversation settings.
   - **Add Tools & APIs** — External integrations.
   - **Guardrails** — Safety constraints and boundaries.
   - **Sample Inputs/Outputs** — Example interactions.
   - **Review & Save** — Final review and submission.
4. On save → `POST /confabs`.
5. If GitHub is connected, backend creates a branch, commits the 4 confab files, and opens a pull request.
6. Confab appears on the Dashboard with `draft` status.

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

### 9. Chatting with a Confab

1. User navigates to the Confab Chat view.
2. Sends messages in a chat interface.
3. Can provide feedback on responses (thumbs up/down with optional modal).
4. Participant list shows who is in the conversation. (Live LLM execution is not yet implemented.)

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
| POST | `/confabs/test-repo` | Test GitHub repository initialization | Yes |

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
| Get branch reference | `GET https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{branch}` | `confab_manager.py` |
| Create branch | `POST https://api.github.com/repos/{owner}/{repo}/git/refs` | `confab_manager.py` |
| Create/update file | `PUT https://api.github.com/repos/{owner}/{repo}/contents/{path}` | `confab_manager.py` |
| Create pull request | `POST https://api.github.com/repos/{owner}/{repo}/pulls` | `confab_manager.py` |
| Create repository | `POST https://api.github.com/user/repos` | `confab_manager.py` |

### PostgreSQL (Database)

- Connection via SQLAlchemy engine using `DATABASE_URL`.
- Default: `postgresql://postgres:password@localhost:7432/confab_foundry_db`.
- Three tables: `users`, `github_accounts`, `confabs`.

### Frontend → Backend (Internal)

- The React frontend calls the FastAPI backend at `VITE_API_URL` (default: `http://localhost:8001`).
- All requests go through the `ApiClient` singleton which injects the JWT Bearer token from `localStorage`.
- CORS is configured on the backend via `ALLOWED_ORIGINS`.
