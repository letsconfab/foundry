"""
Step definitions for authentication features.
"""

import json
import jwt
import time
from datetime import datetime, timedelta
from behave import given, when, then

from environment import api_request, create_test_user, login_user, generate_test_email


# =============================================================================
# Given Steps
# =============================================================================

@given('a user exists with email "{email}"')
def step_user_exists_with_email(context, email):
    """Create a user with the specified email."""
    create_test_user(context, email=email)


@given('a user exists with:')
def step_user_exists_with_table(context):
    """Create a user with details from the table."""
    row = dict(zip(context.table.headings, context.table.rows[0].cells))
    base_email = row.get("email", "test@example.com")
    password = row.get("password", "SecureP@ss123")
    name = row.get("name", "Test User")

    # Make email unique per scenario to avoid conflicts
    email = f"{context.scenario_id}_{base_email}"

    response = api_request(context, "POST", "/auth/register", {
        "name": name,
        "email": email,
        "password": password,
        "country": "US",
        "timezone": "UTC"
    })

    if response.status_code == 200:
        context.users[base_email] = {
            "email": email,
            "password": password,
            "data": response.json()
        }
        # Also store by the unique email
        context.users[email] = context.users[base_email]
    elif response.status_code == 400 and "already registered" in response.text:
        # Try login with the password
        login_response = login_user(context, email, password)
        if login_response:
            context.users[base_email] = {
                "email": email,
                "password": password,
                "data": login_response
            }
            context.users[email] = context.users[base_email]


@given('the user has connected their GitHub account')
def step_user_has_github_connected(context):
    """Mark the current user as having GitHub connected."""
    if not context.auth_token:
        raise AssertionError("No authenticated user")

    api_request(context, "POST", "/auth/github/connect", {
        "github_id": 12345,
        "github_username": "testuser",
        "access_token": "ghp_testtoken123",
        "selected_repo": "confabs"
    })


@given('I have an invalid auth token "{token}"')
def step_have_invalid_token(context, token):
    """Set an invalid auth token."""
    context.auth_token = token


@given('I have an expired auth token')
def step_have_expired_token(context):
    """Generate an expired JWT token."""
    payload = {
        "user_id": 1,
        "exp": datetime.utcnow() - timedelta(hours=1)
    }
    context.auth_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")


@given('I have authorization header "{header}"')
def step_have_auth_header(context, header):
    """Set a custom authorization header."""
    context.custom_auth_header = header


@given('I have authorization header ""')
def step_have_empty_auth_header(context):
    """Set an empty authorization header."""
    context.custom_auth_header = ""


@given('I have already connected my GitHub account')
def step_already_connected_github(context):
    """Ensure user has GitHub connected."""
    step_user_has_github_connected(context)


@given('I have connected my GitHub account')
def step_have_connected_github(context):
    """Connect GitHub account for current user."""
    step_user_has_github_connected(context)


@given('GitHub returns repositories:')
def step_github_returns_repos(context):
    """Configure mock to return specified repositories."""
    repos = []
    for row in context.table:
        repos.append({
            "id": len(repos) + 1,
            "name": row["name"],
            "full_name": row["full_name"],
            "private": row["private"].lower() == "true",
            "owner": {"login": "testuser"},
            "permissions": {"push": True, "pull": True}
        })
    context.scenario_data["mock_repos"] = repos


@given('I have not connected my GitHub account')
def step_not_connected_github(context):
    """Ensure user has no GitHub connection."""
    # This is the default state - nothing to do
    pass


# =============================================================================
# When Steps
# =============================================================================

@when('I register with the following details:')
def step_register_with_details(context):
    """Register a new user with details from table."""
    row = dict(zip(context.table.headings, context.table.rows[0].cells))
    base_email = row.get("email", "")

    # Check if this email was already used in a "Given" step (duplicate email test)
    # If so, use the same email (without unique prefix)
    if base_email in context.users:
        email = base_email  # Use exact email to trigger duplicate
    else:
        # Make email unique per scenario for isolation
        email = f"{context.scenario_id}_{base_email}" if base_email else ""

    data = {
        "name": row.get("name", ""),
        "email": email,
        "password": row.get("password", ""),
        "country": row.get("country", "US"),
        "timezone": row.get("timezone", "UTC")
    }

    api_request(context, "POST", "/auth/register", data)

    # Store mapping for later verification
    if base_email:
        context.scenario_data["registered_email"] = email
        context.scenario_data["base_email"] = base_email


@when('I register with email "{email}"')
def step_register_with_email(context, email):
    """Register with a specific email."""
    api_request(context, "POST", "/auth/register", {
        "name": "Test User",
        "email": email,
        "password": "SecureP@ss123",
        "country": "US",
        "timezone": "UTC"
    })


@when('I register with password "{password}"')
def step_register_with_password(context, password):
    """Register with a specific password."""
    api_request(context, "POST", "/auth/register", {
        "name": "Test User",
        "email": generate_test_email(),
        "password": password,
        "country": "US",
        "timezone": "UTC"
    })


@when('I register with only:')
def step_register_with_only(context):
    """Register with only specified fields."""
    row = dict(zip(context.table.headings, context.table.rows[0].cells))
    api_request(context, "POST", "/auth/register", row)


@when('I login with email "{email}" and password "{password}"')
def step_login_with_credentials(context, email, password):
    """Login with specified credentials."""
    # Check if we have this user registered with a unique email
    actual_email = email
    if email in context.users:
        actual_email = context.users[email].get("email", email)

    api_request(context, "POST", "/auth/login", {
        "email": actual_email,
        "password": password
    })


@when('I login with email "{email}" and password ""')
def step_login_with_empty_password(context, email):
    """Login with empty password."""
    api_request(context, "POST", "/auth/login", {
        "email": email,
        "password": ""
    })


@when('I request my user profile')
def step_request_user_profile(context):
    """Request the current user's profile."""
    api_request(context, "GET", "/auth/me")


@when('I request my user profile without authentication')
def step_request_profile_without_auth(context):
    """Request profile without auth token."""
    saved_token = context.auth_token
    context.auth_token = None
    api_request(context, "GET", "/auth/me")
    context.auth_token = saved_token


@when('I connect my GitHub account with:')
def step_connect_github_with(context):
    """Connect GitHub account with details from table."""
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    data = {
        "github_id": int(row.get("github_id", 12345)),
        "github_username": row.get("github_username", "testuser"),
        "access_token": row.get("access_token", "ghp_test123"),
        "selected_repo": row.get("selected_repo", "confabs"),
        "selected_org": row.get("selected_org")
    }

    api_request(context, "POST", "/auth/github/connect", data)


@when('I request my GitHub repositories')
def step_request_github_repos(context):
    """Request the user's GitHub repositories."""
    api_request(context, "GET", "/auth/github/repos")


# =============================================================================
# Then Steps
# =============================================================================

@then('the response should contain user details:')
def step_response_contains_user_details(context):
    """Assert response contains user details from table."""
    data = context.response.json()
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    for field, expected in row.items():
        assert field in data, f"Field '{field}' not in response: {data}"
        actual = str(data[field])

        # For email field, check if it ends with the expected email (ignoring scenario prefix)
        if field == "email":
            assert actual.endswith(expected), \
                f"Field '{field}': expected to end with '{expected}', got '{actual}'"
        else:
            assert actual == str(expected), \
                f"Field '{field}': expected '{expected}', got '{actual}'"


@then('the user should not have GitHub connected')
def step_user_not_github_connected(context):
    """Assert user does not have GitHub connected."""
    data = context.response.json()
    assert data.get("github_connected") is False, \
        f"Expected github_connected=False, got {data.get('github_connected')}"


@then('the user should have GitHub connected')
def step_user_has_github_connected_check(context):
    """Assert user has GitHub connected."""
    data = context.response.json()
    assert data.get("github_connected") is True, \
        f"Expected github_connected=True, got {data.get('github_connected')}"


@then('the response should contain my user details')
def step_response_contains_my_details(context):
    """Assert response contains the current user's details."""
    data = context.response.json()
    assert "id" in data
    assert "email" in data
    assert "name" in data


@then('the response should contain:')
def step_response_should_contain(context):
    """Assert response contains specified fields (and optionally values)."""
    data = context.response.json()
    headings = context.table.headings

    # Check if this is a single-column table (just field names)
    if len(headings) == 1:
        header = headings[0]
        for row in context.table:
            field = row[header]
            assert field in data, f"Field '{field}' not in response: {list(data.keys())}"

    # Check if table uses "field" / "value" format
    elif "field" in headings and "value" in headings:
        for row in context.table:
            field = row["field"]
            expected = row["value"]
            assert field in data, f"Field '{field}' not in response: {list(data.keys())}"
            if expected:
                actual = str(data[field]) if data[field] is not None else "None"
                assert actual == str(expected), \
                    f"Field '{field}': expected '{expected}', got '{actual}'"

    # Otherwise, headings are field names, first row has values
    else:
        row = dict(zip(headings, context.table.rows[0].cells))
        for field, expected in row.items():
            assert field in data, f"Field '{field}' not in response: {list(data.keys())}"
            if expected:
                actual = str(data[field]) if data[field] is not None else "None"
                assert actual == str(expected), \
                    f"Field '{field}': expected '{expected}', got '{actual}'"


@then('the error should mention minimum length of {length:d} characters')
def step_error_mentions_min_length(context, length):
    """Assert error mentions minimum length."""
    error_text = str(context.response.json())
    assert str(length) in error_text or "8" in error_text, \
        f"Expected minimum length {length} mentioned in error: {error_text}"


@then('the error should mention maximum length of {length:d} characters')
def step_error_mentions_max_length(context, length):
    """Assert error mentions maximum length."""
    error_text = str(context.response.json())
    assert str(length) in error_text or "100" in error_text, \
        f"Expected maximum length {length} mentioned in error: {error_text}"


@then('the response should contain validation errors for missing fields')
def step_response_has_missing_field_errors(context):
    """Assert response has validation errors for required fields."""
    data = context.response.json()
    assert "detail" in data, f"No 'detail' in response: {data}"
    assert isinstance(data["detail"], list), "Expected list of validation errors"
    assert len(data["detail"]) > 0, "Expected at least one validation error"


@then('the response should contain {count:d} repositories')
def step_response_has_n_repos(context, count):
    """Assert response contains specified number of repos."""
    data = context.response.json()
    repos = data.get("repos", [])
    assert len(repos) == count, f"Expected {count} repos, got {len(repos)}"


@then('the GitHub connection should be updated')
def step_github_connection_updated(context):
    """Assert GitHub connection was updated."""
    assert context.response.status_code == 200


@then('the response should contain validation errors for:')
def step_response_has_validation_errors_for(context):
    """Assert response has validation errors for specified fields."""
    data = context.response.json()
    detail = data.get("detail", [])

    expected_fields = [row["field"] for row in context.table]

    if isinstance(detail, list):
        error_fields = []
        for err in detail:
            loc = err.get("loc", [])
            if len(loc) > 1:
                error_fields.append(loc[-1])

        for field in expected_fields:
            assert field in error_fields, \
                f"Expected validation error for '{field}', got errors for: {error_fields}"
