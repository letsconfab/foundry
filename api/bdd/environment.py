"""
Behave environment configuration for Foundry BDD tests.

Sets up API client, test database, and mocks for external services.
"""

import os
import sys
import base64
import uuid
import requests
from unittest.mock import MagicMock, AsyncMock, patch

# Add api directory to path for imports
API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, API_DIR)

API_BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8001")

# Global test run ID for unique emails across entire test run
TEST_RUN_ID = uuid.uuid4().hex[:6]
SCENARIO_COUNTER = 0


def before_all(context):
    """Set up test environment before all tests."""
    context.api_url = API_BASE_URL
    context.session = requests.Session()
    context.auth_token = None
    context.current_user = None
    context.test_data = {}
    context.cleanup_actions = []
    context.mocks = {}

    # Test user registry for cross-scenario user references
    context.users = {}
    context.confabs = {}
    context.documents = {}


def before_feature(context, feature):
    """Set up before each feature."""
    # Apply feature-level tags for mocking
    if "mock_github" in feature.tags:
        _start_github_mock(context)
    if "mock_groq" in feature.tags:
        _start_groq_mock(context)


def after_feature(context, feature):
    """Clean up after each feature."""
    _stop_all_mocks(context)


def before_scenario(context, scenario):
    """Set up before each scenario."""
    global SCENARIO_COUNTER
    SCENARIO_COUNTER += 1

    context.response = None
    context.scenario_data = {}
    context.cleanup_actions = []
    context.custom_auth_header = None

    # Unique ID for this scenario's test data
    context.scenario_id = f"{TEST_RUN_ID}_{SCENARIO_COUNTER}"

    # Clear auth for fresh scenario
    context.auth_token = None
    context.current_user = None

    # Start mocks based on scenario tags
    if "mock_github" in scenario.tags and "github_mock" not in context.mocks:
        _start_github_mock(context)
    if "mock_groq" in scenario.tags and "groq_mock" not in context.mocks:
        _start_groq_mock(context)


def after_scenario(context, scenario):
    """Clean up after each scenario."""
    # Run cleanup actions in reverse order
    for action in reversed(context.cleanup_actions):
        try:
            action()
        except Exception as e:
            print(f"Cleanup action failed: {e}")

    # Stop scenario-level mocks (keep feature-level ones)
    if "mock_github" in scenario.tags and "mock_github" not in scenario.feature.tags:
        _stop_mock(context, "github_mock")
    if "mock_groq" in scenario.tags and "mock_groq" not in scenario.feature.tags:
        _stop_mock(context, "groq_mock")

    context.scenario_data = {}


def after_all(context):
    """Clean up after all tests."""
    _stop_all_mocks(context)
    context.session.close()


# =============================================================================
# Mock Helpers
# =============================================================================

def _start_github_mock(context):
    """Start GitHub API mock."""
    if "github_mock" in context.mocks:
        return

    # Create a mock GitHubService instance with async methods
    mock_instance = MagicMock()

    # Sync methods
    mock_instance.delete_folder.return_value = True
    mock_instance.create_or_update_file.return_value = {"sha": "abc123"}
    mock_instance.get_file_content.return_value = None
    mock_instance.get_repo_info.return_value = {"default_branch": "main"}
    mock_instance.list_repos.return_value = []

    # Async methods need AsyncMock
    mock_instance.ensure_repo_exists = AsyncMock(return_value=(True, None))
    mock_instance.get_default_branch = AsyncMock(return_value="main")
    mock_instance.get_file_contents = AsyncMock(return_value=None)
    mock_instance.batch_create_or_update_files = AsyncMock(return_value={"sha": "abc123def456"})

    # Mock the class to return our instance
    mock_class = MagicMock(return_value=mock_instance)

    # Patch in all locations where GitHubService is imported
    context.mocks["github_mock_confab"] = patch("routes.confab_routes.GitHubService", mock_class)
    context.mocks["github_mock_sync"] = patch("routes.github_sync_routes.GitHubService", mock_class)
    context.mocks["github_mock_base"] = patch("github_service.GitHubService", mock_class)

    context.mocks["github_mock_confab"].start()
    context.mocks["github_mock_sync"].start()
    context.mocks["github_mock_base"].start()

    # Store reference for tests to configure
    context.github_service_mock = mock_class
    context.github_mock_instance = mock_instance
    context.mocks["github_mock"] = True  # Flag that github mock is active


def _start_groq_mock(context):
    """Start Groq LLM mock."""
    if "groq_mock" in context.mocks:
        return

    mock_llm = MagicMock()
    mock_llm.return_value = MagicMock()

    context.mocks["groq_mock"] = patch("foreman_v3.graph.get_llm", mock_llm)
    context.mocks["groq_mock"].start()
    context.groq_mock = mock_llm


def _stop_mock(context, mock_name):
    """Stop a specific mock."""
    if mock_name == "github_mock":
        # Stop all github-related mocks
        for key in ["github_mock_confab", "github_mock_sync", "github_mock_base", "github_mock"]:
            if key in context.mocks:
                try:
                    if hasattr(context.mocks[key], 'stop'):
                        context.mocks[key].stop()
                except RuntimeError:
                    pass
                del context.mocks[key]
        context.github_service_mock = None
        context.github_mock_instance = None
    elif mock_name in context.mocks:
        try:
            if hasattr(context.mocks[mock_name], 'stop'):
                context.mocks[mock_name].stop()
        except RuntimeError:
            pass
        del context.mocks[mock_name]


def _stop_all_mocks(context):
    """Stop all active mocks."""
    for mock_name in list(context.mocks.keys()):
        _stop_mock(context, mock_name)


# =============================================================================
# API Request Helper
# =============================================================================

def api_request(context, method, endpoint, json_data=None, **kwargs):
    """Make an API request with authentication."""
    url = f"{context.api_url}{endpoint}"
    headers = kwargs.pop("headers", {})
    headers["Content-Type"] = "application/json"

    if context.auth_token:
        headers["Authorization"] = f"Bearer {context.auth_token}"

    response = context.session.request(
        method, url, headers=headers, json=json_data, **kwargs
    )
    context.response = response
    return response


# =============================================================================
# Test Data Helpers
# =============================================================================

def generate_test_email(context=None):
    """Generate a unique test email."""
    if context and hasattr(context, 'scenario_id'):
        return f"test_{context.scenario_id}_{uuid.uuid4().hex[:4]}@example.com"
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


def generate_test_content(size_kb=1):
    """Generate test file content of specified size."""
    content = b"x" * (size_kb * 1024)
    return base64.b64encode(content).decode()


def create_test_user(context, email=None, password="SecureP@ss123"):
    """Create a test user and return credentials."""
    email = email or generate_test_email()

    response = api_request(context, "POST", "/auth/register", {
        "name": "Test User",
        "email": email,
        "password": password,
        "country": "US",
        "timezone": "UTC"
    })

    if response.status_code == 200:
        data = response.json()
        context.users[email] = {
            "id": data["id"],
            "email": email,
            "password": password,
            "token": data.get("access_token")
        }
        return data
    elif response.status_code == 400 and "already registered" in response.text:
        # User exists, try to login
        return login_user(context, email, password)

    return None


def login_user(context, email, password):
    """Login a user and store the token."""
    response = api_request(context, "POST", "/auth/login", {
        "email": email,
        "password": password
    })

    if response.status_code == 200:
        data = response.json()
        context.auth_token = data.get("access_token")
        context.current_user = data
        return data

    return None
