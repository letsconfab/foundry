# Features

## Implemented

### User Authentication

- **Email/password registration** — Users sign up with name, email, password, country, and timezone. Passwords are hashed with bcrypt.
- **Email/password login** — Returns a JWT access token (HS256, 30-minute default expiry).
- **Authenticated session** — `GET /auth/me` validates the token and returns the current user profile including GitHub connection status.
- **GitHub OAuth login/signup** — Users can sign in via GitHub. If no account exists, one is created automatically using the GitHub email.
- **GitHub account connection** — Existing users can link their GitHub account post-registration, choosing a repository and optionally an organization.

### Confab Management (CRUD)

- **Create confab** — Stores a confab record in the database with name, description, optional configuration, and a default version of `1.0.0` and status of `draft`.
- **List confabs** — Returns all confabs owned by the authenticated user.
- **Get confab** — Returns a single confab by ID (ownership-scoped).
- **Update confab** — Updates name, description, and auto-increments the version by 0.1. Pushes changes to GitHub if connected.
- **Delete confab** — Removes the confab from the database.

### GitHub Integration

- **Repository creation** — Creates a new GitHub repository via the GitHub API with auto-init and Node gitignore template.
- **Confab file generation** — Generates four structured files per confab (`Confab.toml`, `PURPOSE.md`, `GUARDRAILS.md`, `TESTS.md`) and commits them to a new branch.
- **Pull request creation** — Every new or updated confab is submitted as a pull request for review.
- **Repository listing** — Fetches the user's personal and organization repositories from GitHub.
- **Test repository initialization** — A test endpoint that creates a dummy confab structure in a GitHub repo to verify the integration works.

### Confab Configuration Schema

- **Full configuration** — Supports detailed agent settings: model configuration (provider, model, temperature, max tokens), knowledge base, conversation settings, security settings, integration settings (APIs, webhooks, databases), and deployment settings.
- **Simple configuration** — A lightweight alternative with just model provider, model name, system prompt, temperature, and max tokens.

### Agent Creation Wizard (Frontend)

- **7-step guided flow** — Conversational chat interface that walks users through: Define Purpose, Add Participants, Configure Memory, Add Tools & APIs, Guardrails, Sample Inputs/Outputs, Review & Save.
- **Participant management** — Add users and confabs as participants with roles (owner, admin, editor, viewer).
- **Multi-agent nodes** — Configure moderator rules, tie-breaker logic, and conflict resolution.
- **Repository naming display** — Shows the GitHub repository naming convention for the confab.
- **Test repo button** — Triggers test repository initialization from the chat interface.

### Dashboard

- **Confab grid** — Responsive card layout (1-3 columns) displaying all user confabs.
- **Agent cards** — Show status badge (deployed/active/draft), LLM provider, cloud provider, last modified date, and version.
- **Actions menu** — Per-card dropdown with Publish, Stop, and Delete options.

### Deployment Configuration (Frontend)

- **Deployment type selection** — Cloud vs. self-hosted.
- **Cloud provider selection** — AWS, Azure, GCP, DigitalOcean with region selection.
- **LLM provider selection** — OpenAI, Anthropic, Google, Cohere with model selection.

### Chat Interface (Backend)

- **LangChain runtime** — Chat interactions are powered by LangChain as the agent runtime.
- **Persistent chat history** — All messages are persisted in the database and associated with a specific confab. History survives across sessions.
- **Topic-based threads** — Each confab has a dedicated thread for every high-level configuration topic (e.g., Define Purpose, Add Participants, Configure Memory, Add Tools & APIs, Guardrails, Sample Inputs/Outputs, Review & Save). Threads keep conversations organized by concern.
- **Cross-thread references** — Users can address and post to other threads from within a given thread, enabling cross-topic context sharing without leaving the current conversation.

### Chat Interface (Frontend)

- **Confab chat** — Message interface for interacting with a deployed confab.
- **Feedback** — Thumbs up/down on messages with a feedback modal.
- **Participant list** — Shows participants with online status indicators.
- **Threaded configuration** — Main thread and sub-thread branching conversations for confab configuration.

### Landing Page

- **Hero section** — Call-to-action for creating or managing confabs.
- **Features grid** — Highlights: Confab-Powered Creation, Multi-Cloud Deployment, Multiple LLM Providers, Multi-Confab Systems.
- **How It Works** — Three-step overview: Chat, Collaborate, Deploy.

### UI Infrastructure

- **40+ reusable UI components** — Pre-built Radix UI primitives with Tailwind styling.
- **Dark mode** — Theme switching via `next-themes`.
- **Responsive design** — Mobile-first with breakpoints and a mobile detection hook.
- **Toast notifications** — Via Sonner.

---

## Not Yet Implemented

### Agent Execution

- Actual LLM API calls — confabs are defined and stored but not yet executed against live models.
- Runtime agent orchestration for multi-agent confab systems.

### Deployment Pipeline

- Cloud deployment of confabs to AWS, Azure, GCP, or DigitalOcean (frontend UI exists but no backend provisioning).
- Self-hosted deployment workflow.

### CI/CD

- No automated testing, linting, or deployment pipeline (GitHub Actions or equivalent).

### Advanced Features

- Confab versioning history and rollback (only current version is tracked).
- Confab publishing and marketplace/sharing.
- Real-time collaboration on confab editing.
- Analytics and monitoring for deployed agents.
- Knowledge base ingestion and indexing.
- Webhook and external API integration runtime.
