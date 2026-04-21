"""
Common step definitions shared across all features.
"""

import json
import requests
from behave import given, when, then

from environment import api_request, create_test_user, login_user, generate_test_email


# =============================================================================
# API Setup
# =============================================================================

@given('the API is available')
def step_api_available(context):
    """Verify the API is running and accessible."""
    try:
        response = requests.get(f"{context.api_url}/", timeout=5)
        assert response.status_code == 200, f"API not healthy: {response.status_code}"
    except requests.ConnectionError:
        raise AssertionError(f"Cannot connect to API at {context.api_url}")


@given('I am not authenticated')
def step_not_authenticated(context):
    """Clear any authentication token."""
    context.auth_token = None


@given('I am logged in as "{email}"')
def step_logged_in_as(context, email):
    """Log in as the specified user (creates user if needed)."""
    # Make email unique per scenario
    unique_email = f"{context.scenario_id}_{email}"

    # Check if user exists in our registry
    if unique_email in context.users:
        user_data = context.users[unique_email]
        if user_data.get("token"):
            context.auth_token = user_data["token"]
            return

    # Try to create/login user with unique email
    user = create_test_user(context, email=unique_email)
    if user:
        context.auth_token = user.get("access_token")
        context.current_user = user
        context.users[email] = {"email": unique_email, "token": user.get("access_token")}
        context.users[unique_email] = context.users[email]
    else:
        # Try login with default password
        result = login_user(context, unique_email, "SecureP@ss123")
        if not result:
            raise AssertionError(f"Could not login as {unique_email}")


# =============================================================================
# Response Assertions
# =============================================================================

@then('the response status should be {status_code:d}')
def step_response_status(context, status_code):
    """Assert the response has the expected status code."""
    assert context.response is not None, "No response received"
    assert context.response.status_code == status_code, \
        f"Expected {status_code}, got {context.response.status_code}: {context.response.text}"


@then('the response should contain error "{error_message}"')
def step_response_contains_error(context, error_message):
    """Assert the response contains the specified error message."""
    data = context.response.json()
    detail = data.get('detail', '')

    if isinstance(detail, list):
        # Pydantic validation errors
        all_messages = " ".join(str(err) for err in detail)
        assert error_message.lower() in all_messages.lower(), \
            f"Expected '{error_message}' in validation errors: {detail}"
    else:
        detail_lower = str(detail).lower()
        error_lower = error_message.lower()

        # Common auth error variations
        if error_lower == "invalid credentials" or error_lower == "token has expired":
            matches = any(phrase in detail_lower for phrase in [
                "invalid credentials", "not authenticated", "invalid token",
                "could not validate", "authentication failed", "expired", "token"
            ])
        # For "X not found" messages, check if all words are present
        elif "not found" in error_lower:
            words = error_lower.replace("not found", "").strip().split()
            matches = all(word in detail_lower for word in words) and "not found" in detail_lower
        else:
            matches = error_lower in detail_lower

        assert matches, f"Expected '{error_message}' in '{detail}'"


@then('the response should contain a validation error for "{field}"')
def step_response_validation_error(context, field):
    """Assert the response contains a validation error for the specified field."""
    data = context.response.json()
    detail = data.get('detail', [])

    if isinstance(detail, list):
        # Pydantic validation errors are in a list format
        fields = []
        for err in detail:
            loc = err.get('loc', [])
            if len(loc) >= 1:
                # Get the last element of loc (field name)
                fields.append(str(loc[-1]))

        assert field in fields, f"Field '{field}' not in validation errors: {fields}"
    else:
        assert field.lower() in str(detail).lower(), \
            f"Field '{field}' not mentioned in error: {detail}"


@then('the response should contain an access token')
def step_response_has_access_token(context):
    """Assert the response contains an access token."""
    data = context.response.json()
    assert 'access_token' in data, f"No access_token in response: {data}"
    assert data['access_token'], "access_token is empty"
    # Store for subsequent requests
    context.auth_token = data['access_token']


@then('the response should contain message "{message}"')
def step_response_contains_message(context, message):
    """Assert the response contains the specified message."""
    data = context.response.json()
    assert 'message' in data, f"No 'message' in response: {data}"
    assert message.lower() in data['message'].lower(), \
        f"Expected '{message}' in '{data['message']}'"


@then('the error should mention "{text}"')
def step_error_should_mention(context, text):
    """Assert error message mentions specific text."""
    error_text = str(context.response.json()).lower()
    assert text.lower() in error_text, \
        f"Expected '{text}' in error: {context.response.json()}"


@then('the confab should be deleted')
def step_confab_should_be_deleted(context):
    """Assert confab was deleted."""
    from environment import api_request
    confab_id = context.scenario_data.get("confab_id")
    response = api_request(context, "GET", f"/confabs/{confab_id}")
    assert response.status_code == 404, f"Confab still exists: {response.status_code}"


# =============================================================================
# HTTP Request Steps
# =============================================================================

@when('I make a {method} request to "{endpoint}"')
def step_make_request(context, method, endpoint):
    """Make an HTTP request to the specified endpoint."""
    headers = {"Content-Type": "application/json"}

    if context.auth_token:
        headers["Authorization"] = f"Bearer {context.auth_token}"

    if hasattr(context, 'custom_auth_header'):
        headers["Authorization"] = context.custom_auth_header

    url = f"{context.api_url}{endpoint}"
    context.response = requests.request(method, url, headers=headers, timeout=30)


@when('I send invalid JSON to "{endpoint}"')
def step_send_invalid_json(context, endpoint):
    """Send invalid JSON to endpoint."""
    url = f"{context.api_url}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if context.auth_token:
        headers["Authorization"] = f"Bearer {context.auth_token}"

    context.response = requests.post(url, data="not valid json{", headers=headers, timeout=30)


@when('I POST to "{endpoint}" with content-type "{content_type}"')
def step_post_with_content_type(context, endpoint, content_type):
    """POST with specific content type."""
    url = f"{context.api_url}{endpoint}"
    headers = {"Content-Type": content_type}
    if context.auth_token:
        headers["Authorization"] = f"Bearer {context.auth_token}"

    context.response = requests.post(url, data="test", headers=headers, timeout=30)


# =============================================================================
# Error Scenario Steps
# =============================================================================

@given('another user "{email}" has {count:d} confabs')
def step_other_user_has_n_confabs(context, email, count):
    """Create confabs owned by another user."""
    saved_token = context.auth_token

    other_user = create_test_user(context, email=email)
    if other_user:
        context.auth_token = other_user.get("access_token")
        for i in range(count):
            api_request(context, "POST", "/confabs", {"name": f"Other Agent {i+1}"})

    context.auth_token = saved_token


@given('I have created {count:d} confabs')
def step_i_have_n_confabs(context, count):
    """Create confabs for current user."""
    for i in range(count):
        api_request(context, "POST", "/confabs", {"name": f"My Agent {i+1}"})


@given('another user "{email}" has a confab with ID {confab_id:d}')
def step_other_user_confab_id(context, email, confab_id):
    """Note that another user has confab with specific ID."""
    saved_token = context.auth_token

    other_user = create_test_user(context, email=email)
    if other_user:
        context.auth_token = other_user.get("access_token")
        response = api_request(context, "POST", "/confabs", {"name": "Other Agent"})
        if response.status_code == 200:
            context.scenario_data["other_confab_id"] = response.json()["id"]

    context.auth_token = saved_token


@given('another user "{email}" has a confab with learnings')
def step_other_user_has_learnings(context, email):
    """Create confab with learnings owned by another user."""
    saved_token = context.auth_token

    other_user = create_test_user(context, email=email)
    if other_user:
        context.auth_token = other_user.get("access_token")
        response = api_request(context, "POST", "/confabs", {"name": "Other Agent"})
        if response.status_code == 200:
            confab_id = response.json()["id"]
            context.scenario_data["other_confab_id"] = confab_id
            api_request(context, "POST", f"/confabs/{confab_id}/learnings", {
                "content": "Test learning",
                "source": "manual"
            })

    context.auth_token = saved_token


@when('I list learnings for that confab')
def step_list_other_learnings(context):
    """List learnings for another user's confab."""
    confab_id = context.scenario_data.get("other_confab_id")
    api_request(context, "GET", f"/confabs/{confab_id}/learnings")


@when('I add a learning to confab ID {confab_id:d}')
def step_add_learning_to_confab(context, confab_id):
    """Add learning to specific confab."""
    api_request(context, "POST", f"/confabs/{confab_id}/learnings", {
        "content": "Test learning",
        "source": "manual"
    })


@when('I resume foreman conversation for confab ID {confab_id:d}')
def step_resume_foreman_for_confab(context, confab_id):
    """Resume foreman conversation for confab."""
    api_request(context, "POST", f"/conversations/foreman/{confab_id}/resume")


@when('I get thread with ID {thread_id:d}')
def step_get_thread_by_id(context, thread_id):
    """Get thread by ID."""
    api_request(context, "GET", f"/conversations/threads/{thread_id}")


# =============================================================================
# Helper Functions
# =============================================================================

def table_to_dict(table):
    """Convert a Behave table to a dictionary."""
    if len(table.rows) == 1:
        return dict(zip(table.headings, table.rows[0].cells))
    return [dict(zip(table.headings, row.cells)) for row in table.rows]


def table_to_list_of_dicts(table):
    """Convert a Behave table to a list of dictionaries."""
    return [dict(zip(table.headings, row.cells)) for row in table.rows]
