# Let's Confab API

FastAPI backend for Let's Confab platform with user authentication, GitHub OAuth integration, and confab management.

## Features

- **User Authentication**: Registration and login with JWT tokens
- **GitHub OAuth**: Sign in with GitHub and connect repositories
- **Confab Management**: Create, read, update, and delete confabs
- **GitHub Integration**: Store confabs in GitHub repositories with automatic PR creation
- **PostgreSQL Database**: Persistent storage for users and confabs

## Setup

### Prerequisites

- Python 3.8+
- PostgreSQL database
- GitHub OAuth App (for GitHub integration)

### Installation

1. Clone the repository and navigate to the API directory:
```bash
cd api
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Set up the database:
```bash
# Create database migrations
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head
```

### Environment Variables

Key environment variables in `.env`:

```env
# Database
DATABASE_URL=postgresql://postgres:password@localhost/letsconfab

# JWT
SECRET_KEY=your-super-secret-jwt-key
ACCESS_TOKEN_EXPIRE_MINUTES=30

# GitHub OAuth
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GITHUB_REDIRECT_URI=http://localhost:3000/auth/github/callback
```

### Running the API

Start the development server:
```bash
python main.py
```

Or use uvicorn directly:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Authentication

- `POST /auth/register` - Register new user
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user info
- `GET /auth/github/authorize` - GitHub OAuth authorization
- `GET /auth/github/callback` - GitHub OAuth callback
- `POST /auth/github/connect` - Connect GitHub account
- `GET /auth/github/repos` - Get user's GitHub repositories

### Confabs

- `POST /confabs` - Create new confab
- `GET /confabs` - Get user's confabs
- `GET /confabs/{id}` - Get specific confab
- `PUT /confabs/{id}` - Update confab
- `DELETE /confabs/{id}` - Delete confab

## GitHub Integration

The API integrates with GitHub for:

1. **User Authentication**: Users can sign in with their GitHub account
2. **Repository Access**: Users can select organizations and repositories
3. **Confab Storage**: Confabs are stored as structured files in GitHub:
   - `Confab.toml` - Configuration metadata
   - `PURPOSE.md` - Purpose and objectives
   - `GUARDRAILS.md` - Safety and behavioral constraints
   - `TESTS.md` - Test cases and scenarios

### Default Repository

By default, confabs are stored in the `letsconfab/confabs` repository. Users can connect their own repositories for private confabs.

## Database Schema

### Users Table
- `id` - Primary key
- `name` - User's full name
- `email` - Unique email address
- `password_hash` - Bcrypt hashed password
- `country` - User's country
- `timezone` - User's timezone
- `created_at`, `updated_at` - Timestamps

### GitHub Accounts Table
- `id` - Primary key
- `user_id` - Foreign key to users
- `github_id` - GitHub user ID
- `github_username` - GitHub username
- `access_token` - GitHub access token
- `selected_org` - Selected GitHub organization
- `selected_repo` - Selected repository name

### Confabs Table
- `id` - Primary key
- `name` - Confab name
- `description` - Confab description
- `version` - Semantic version
- `status` - draft/published/archived
- `config` - JSON configuration data
- `github_url` - URL to GitHub PR/files
- `user_id` - Foreign key to users
- `created_at`, `updated_at` - Timestamps

## Security

- JWT tokens for authentication
- Password hashing with bcrypt
- CORS configuration for frontend integration
- Environment variable configuration for secrets

## Development

### Database Migrations

Create new migration:
```bash
alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback migrations:
```bash
alembic downgrade -1
```

### Testing

Run tests (when implemented):
```bash
pytest
```

## Deployment

For production deployment:

1. Set environment variables appropriately
2. Use a production database (PostgreSQL)
3. Configure CORS for your frontend domain
4. Use a production WSGI server (Gunicorn)
5. Set up proper SSL/TLS
6. Configure GitHub OAuth with production URLs

Example production command:
```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```
