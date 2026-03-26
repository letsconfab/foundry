# Features

## Implemented

### User Authentication

- **Email/password registration** — Users sign up with name, email, password, country, and timezone. Passwords are hashed with bcrypt.
- **Email/password login** — Returns a JWT access token (HS256, 30-minute default expiry).
- **Authenticated session** — `GET /auth/me` validates the token and returns the current user profile including GitHub connection status.
- **GitHub OAuth login/signup** — Users can sign in via GitHub. If no account exists, one is created automatically using the GitHub email.
- **GitHub account connection** — Existing users can link their GitHub account post-registration, choosing a repository and optionally an organization.

### Confab Management (CRUD)

- **Create confab** — Stores a confab record in the database with name, description, optional configuration, version `1.0.0`, and status `building` (for Foreman-guided creation).
- **List confabs** — Returns all confabs owned by the authenticated user.
- **Get confab** — Returns a single confab by ID (ownership-scoped).
- **Update confab** — Updates name, description, and auto-increments the version by 0.1. Pushes changes to GitHub if connected.
- **Delete confab** — Removes the confab from the database.
- **OASF export** — Exports a confab as OASF-compliant files (agent.oasf.yaml, PURPOSE.md, GUARDRAILS.md, TESTS.md).

### GitHub Integration

- **Repository creation** — Creates a new GitHub repository via the GitHub API with auto-init and Node gitignore template.
- **Confab file generation** — Generates four structured files per confab (`Confab.toml`, `PURPOSE.md`, `GUARDRAILS.md`, `TESTS.md`) and commits them to a new branch.
- **Pull request creation** — Every new or updated confab is submitted as a pull request for review.
- **Repository listing** — Fetches the user's personal and organization repositories from GitHub.
- **Test repository initialization** — A test endpoint that creates a dummy confab structure in a GitHub repo to verify the integration works.

### Confab Configuration Schema

- **Full configuration** — Supports detailed agent settings: model configuration (provider, model, temperature, max tokens), knowledge base, conversation settings, security settings, integration settings (APIs, webhooks, databases), and deployment settings.
- **Simple configuration** — A lightweight alternative with just model provider, model name, system prompt, temperature, and max tokens.

### Foreman Agent (System Orchestrator)

- **System agent type** — The Foreman is a built-in system agent (`participant_type='system'`, `system_agent_name='foreman'`) that orchestrates confab creation.
- **7-step guided process** — Leads users through: Define Purpose, Add Participants, Configure Memory, Set Up Tools, Establish Guardrails, Sample I/O, and Review.
- **Directive conversation style** — Actively guides the conversation rather than passively waiting; ends each response with a clear question for the next step.
- **Progress tracking** — Tracks completed steps in `confab.setup_progress` JSON field, allowing sessions to resume from where they left off.
- **Tool integration** — Uses internal tools (`define_purpose`, `add_participant`, `configure_memory`, etc.) to save configuration incrementally.
- **Resume capability** — When resuming a building confab, generates a contextual resume prompt based on current progress.
- **Distinct visual identity** — Displays with HardHat icon and amber/orange gradient in the UI.

### Agent Creation Wizard (Frontend)

- **Foreman-led conversation** — The Foreman agent guides users through the 7-step confab creation process via natural conversation.
- **Participant management** — Add users and confabs as participants with roles (owner, admin, editor, viewer).
- **Continue Building** — Resume incomplete confabs from the dashboard; conversation history is restored.
- **Multi-agent nodes** — Configure moderator rules, tie-breaker logic, and conflict resolution.
- **Repository naming display** — Shows the GitHub repository naming convention for the confab.
- **Test repo button** — Triggers test repository initialization from the chat interface.

### Dashboard

- **Confab grid** — Responsive card layout (1-3 columns) displaying all user confabs.
- **Agent cards** — Show status badge (building/deployed/active/draft), LLM provider, cloud provider, last modified date, and version.
- **Continue Building** — Button on `building` status confabs to resume the Foreman conversation.
- **Actions menu** — Per-card dropdown with Publish, Stop, and Delete options.

### Deployment Configuration (Frontend)

- **Deployment type selection** — Cloud vs. self-hosted.
- **Cloud provider selection** — AWS, Azure, GCP, DigitalOcean with region selection.
- **LLM provider selection** — OpenAI, Anthropic, Google, Cohere with model selection.

### Chat Interface (Backend)

- **Groq API runtime** — Chat interactions use the Groq API with the qwen/qwen3-32b model.
- **Persistent chat history** — All messages are persisted in the database via Thread/Message tables. History survives across sessions.
- **Thread-based conversations** — Conversations use a participant-based threading model where users, confabs, and system agents can participate.
- **Foreman routing** — During confab building, messages are routed to the Foreman agent; confabs do not respond until deployed.
- **Agent response inference** — When no explicit recipient is specified, participating agents infer whether to respond based on context.

### Chat Interface (Frontend)

- **Confab chat** — Message interface for interacting with a deployed confab.
- **Foreman chat** — Specialized interface for confab building with Foreman's distinct visual identity.
- **Participant sidebar** — Shows all thread participants (users, system agents) with distinct styling per type.
- **Feedback** — Thumbs up/down on messages with a feedback modal.
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

- Multi-agent orchestration for deployed confabs (confab-to-confab communication).
- Runtime execution of deployed confabs against live LLM APIs (building flow works, deployment flow does not).

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
- File upload and PDF parsing during confab building.
