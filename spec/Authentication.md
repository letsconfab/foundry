# Authentication

## Overview

The platform supports two authentication methods: email/password and GitHub OAuth. Both methods produce an access token that the frontend stores and sends with every subsequent API request.

---

## Email/Password Authentication

### Registration

1. User provides name, email, password, country, and timezone.
2. The backend validates the email is not already registered.
3. The password is hashed before storage. Passwords exceeding 72 UTF-8 bytes must be rejected (bcrypt limit).
4. An access token is generated and returned alongside the user profile.

### Login

1. User provides email and password.
2. The backend verifies the password against the stored hash.
3. An access token is generated and returned.

---

## Access Tokens

- Tokens are JWTs containing the user's ID and an expiration timestamp.
- Default expiry is 30 minutes (configurable).
- Tokens are signed with a server-side secret key.
- Protected endpoints extract the token from the `Authorization: Bearer <token>` header, verify the signature, check expiration, and look up the user by ID.
- If any step fails, the endpoint returns 401 Unauthorized.

### Frontend Token Handling

- The token is stored in `localStorage`.
- The API client injects it into every request automatically.
- On auth errors, the token is cleared from storage.
- On app startup, the frontend validates the stored token by calling `GET /auth/me`. If invalid, the user is treated as logged out.

---

## GitHub OAuth

### Purpose

GitHub OAuth serves two roles:

1. **Login/signup** — Users can create an account or sign in using their GitHub identity.
2. **Account linking** — Existing users can connect their GitHub account to enable confab syncing to GitHub repositories.

### OAuth Flow

1. User clicks "Continue with GitHub" in the frontend.
2. The frontend navigates to the backend's authorization endpoint.
3. The backend redirects to GitHub's OAuth consent page, requesting the `public_repo user:email` scope.
4. The user authorizes the application on GitHub.
5. GitHub redirects back to the backend callback endpoint with an authorization code.
6. The backend exchanges the code for a GitHub access token.
7. The backend fetches the user's GitHub profile.
8. The backend redirects to the frontend, passing the GitHub access token, user ID, and username as query parameters.
9. The frontend handles the callback:
   - If the user is already logged in → connects the GitHub account to the existing user.
   - If the user is not logged in → logs in or creates a new account.

### Auto-Creation on GitHub Login

When a user logs in via GitHub and no account exists for their email:

1. The backend resolves the user's email from GitHub, preferring a primary verified email, falling back to any verified email, then any email, and finally a `noreply` placeholder.
2. A new user is created with the GitHub display name, resolved email, a random unusable password, and default country/timezone values.
3. A GitHub account record is linked to the new user.
4. An access token is returned.

---

## Security Considerations

- Passwords must be hashed with a strong, salted algorithm (e.g., bcrypt).
- The JWT signing key must be a strong random secret in production.
- GitHub access tokens should be treated as sensitive data.
- The OAuth flow should include a `state` parameter for CSRF protection (not yet implemented).
- Secrets must never appear in source code (see Conventions.md).
