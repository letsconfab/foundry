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

Creates a new confab. If GitHub is connected, also creates a branch with confab files and opens a pull request. GitHub failures do not prevent the confab from being saved.

- **Request body:** name, optional description, optional config (full or simple format)
- **Response:** Confab with id, version (`"1.0.0"`), status (`"draft"`), timestamps, optional github_url

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

Updates a confab's name and description. Auto-increments the version by 0.1. If GitHub is connected, creates a new branch and pull request with updated files. GitHub failures do not prevent the update from being saved.

- **Request body:** name, optional description, optional config
- **Response:** Updated confab
- **Errors:** 404 if not found

### Delete Confab

`DELETE /confabs/{confab_id}` (authenticated)

Deletes a confab from the database. GitHub files are not removed.

- **Response:** Success message
- **Errors:** 404 if not found

### Test Repository

`POST /confabs/test-repo` (authenticated)

Tests the GitHub integration by creating a dummy confab structure. For users without GitHub, returns a simulated success response.

- **Response:** repo_name, repo_url, pr_url, test_files

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
