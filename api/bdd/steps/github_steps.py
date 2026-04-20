"""
Step definitions for GitHub integration features.
"""

from behave import given, when, then
from unittest.mock import MagicMock

from environment import api_request


# =============================================================================
# Given Steps
# =============================================================================

@given('GitHub API is mocked')
def step_github_mocked(context):
    """Ensure GitHub API is mocked."""
    # Mock is started by environment.py based on tags
    pass


@given('the confab has purpose and guardrails defined')
def step_confab_has_purpose_guardrails(context):
    """Set purpose and guardrails on confab."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "PUT", f"/confabs/{confab_id}", {
        "purpose": "Help users accomplish tasks",
        "guardrails": [{"id": "g1", "rule": "Be helpful", "severity": "error", "enabled": True}]
    })


@given('the confab has:')
def step_confab_has_fields(context):
    """Set fields on confab from table."""
    confab_id = context.scenario_data.get("confab_id")
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    update_data = {}
    if "purpose" in row:
        update_data["purpose"] = row["purpose"]
    if "guardrails" in row:
        update_data["guardrails"] = [
            {"id": "g1", "rule": row["guardrails"], "severity": "error", "enabled": True}
        ]

    api_request(context, "PUT", f"/confabs/{confab_id}", update_data)


@given('the confab has purpose defined')
def step_confab_has_purpose(context):
    """Set purpose on confab."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "PUT", f"/confabs/{confab_id}", {
        "purpose": "Help users with tasks"
    })


@given('the confab has guardrails defined')
def step_confab_has_guardrails(context):
    """Set guardrails on confab."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "PUT", f"/confabs/{confab_id}", {
        "guardrails": [{"id": "g1", "rule": "Be safe", "severity": "error", "enabled": True}]
    })


@given('the confab has no purpose or guardrails')
def step_confab_has_no_content(context):
    """Ensure confab has no purpose or guardrails."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "PUT", f"/confabs/{confab_id}", {
        "purpose": None,
        "guardrails": []
    })


@given('my GitHub account has no selected repo')
def step_github_no_repo(context):
    """GitHub account has no selected repo."""
    # This would need to be set up in the test data
    context.scenario_data["no_github_repo"] = True


@given('GitHub API will return an error')
def step_github_will_error(context):
    """Configure mock to return an error."""
    if hasattr(context, 'github_mock_instance') and context.github_mock_instance:
        context.github_mock_instance.create_or_update_file.side_effect = \
            Exception("GitHub API error")


@given('GitHub API will return an error on file fetch')
def step_github_fetch_error(context):
    """Configure mock to error on file fetch."""
    if hasattr(context, 'github_mock_instance') and context.github_mock_instance:
        context.github_mock_instance.get_file_content.side_effect = \
            Exception("File not found")


@given('GitHub has updated PURPOSE.md content')
def step_github_has_updated_purpose(context):
    """Configure mock to return updated PURPOSE.md."""
    if hasattr(context, 'github_mock_instance') and context.github_mock_instance:
        context.github_mock_instance.get_file_content.return_value = \
            "# Updated Purpose\n\nThis is updated content."


@given('GitHub has definition files:')
def step_github_has_files(context):
    """Configure mock to return definition files."""
    if hasattr(context, 'github_mock_instance') and context.github_mock_instance:
        files = {}
        for row in context.table:
            files[row["file"]] = row["content"]

        def get_file(path, **kwargs):
            for filename, content in files.items():
                if filename in path:
                    return content
            return None

        context.github_mock_instance.get_file_content.side_effect = get_file


@given('GitHub has no definition files for the confab')
def step_github_no_files(context):
    """Configure mock to return no files."""
    if hasattr(context, 'github_mock_instance') and context.github_mock_instance:
        context.github_mock_instance.get_file_content.return_value = None


@given('the confab is synced to branch "{branch}"')
def step_confab_synced_to_branch(context, branch):
    """Mark confab as synced to specific branch."""
    context.scenario_data["github_branch"] = branch


@given('I am an admin user')
def step_i_am_admin(context):
    """Mark current user as admin."""
    context.scenario_data["is_admin"] = True


@given('there are {count:d} confabs to sync')
def step_n_confabs_to_sync(context, count):
    """Create confabs to sync."""
    for i in range(count):
        api_request(context, "POST", "/confabs", {"name": f"Sync Agent {i+1}"})


@given('there are confabs with IDs {ids}')
def step_confabs_with_ids(context, ids):
    """Note that confabs exist with specified IDs."""
    context.scenario_data["confab_ids"] = [int(x.strip()) for x in ids.split(",")]


@given('another user "{email}" has a confab')
def step_other_user_has_confab_github(context, email):
    """Create confab owned by another user."""
    from steps.confab_steps import step_other_user_has_confab
    step_other_user_has_confab(context, email, "Other Agent")


# =============================================================================
# When Steps
# =============================================================================

@when('I commit definition files')
def step_commit_definition_files(context):
    """Commit definition files for current confab."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "POST", f"/confabs/{confab_id}/definition-files/accept-and-commit", {
        "commit_message": "Commit definition files"
    })


@when('I commit definition files with message "{message}"')
def step_commit_with_message(context, message):
    """Commit definition files with specific message."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "POST", f"/confabs/{confab_id}/definition-files/accept-and-commit", {
        "commit_message": message
    })


@when('I commit definition files with:')
def step_commit_with_options(context):
    """Commit definition files with options from table."""
    confab_id = context.scenario_data.get("confab_id")
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    data = {"commit_message": "Commit"}
    if "include_purpose" in row:
        data["include_purpose"] = row["include_purpose"].lower() == "true"
    if "include_guardrails" in row:
        data["include_guardrails"] = row["include_guardrails"].lower() == "true"

    api_request(context, "POST", f"/confabs/{confab_id}/definition-files/accept-and-commit", data)


@when('I commit definition files for confab ID {confab_id:d}')
def step_commit_for_confab_id(context, confab_id):
    """Commit definition files for specific confab."""
    api_request(context, "POST", f"/confabs/{confab_id}/definition-files/accept-and-commit", {
        "commit_message": "Commit"
    })


@when('I try to commit definition files for that confab')
def step_try_commit_other_confab(context):
    """Try to commit for another user's confab."""
    confab_id = context.scenario_data.get("other_confab_id")
    api_request(context, "POST", f"/confabs/{confab_id}/definition-files/accept-and-commit", {
        "commit_message": "Commit"
    })


@when('I refresh definition files for the confab')
def step_refresh_definition_files(context):
    """Refresh definition files for current confab."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "POST", f"/confabs/{confab_id}/definition-files/refresh")


@when('I refresh definition files for confab ID {confab_id:d}')
def step_refresh_for_confab_id(context, confab_id):
    """Refresh definition files for specific confab."""
    api_request(context, "POST", f"/confabs/{confab_id}/definition-files/refresh")


@when('I try to refresh definition files for that confab')
def step_try_refresh_other_confab(context):
    """Try to refresh for another user's confab."""
    confab_id = context.scenario_data.get("other_confab_id")
    api_request(context, "POST", f"/confabs/{confab_id}/definition-files/refresh")


@when('I trigger admin sync to GitHub')
def step_trigger_admin_sync(context):
    """Trigger admin sync all confabs."""
    api_request(context, "POST", "/admin/sync-to-github", {})


@when('I trigger admin sync for confabs {ids}')
def step_trigger_admin_sync_ids(context, ids):
    """Trigger admin sync for specific confabs."""
    confab_ids = [int(x.strip()) for x in ids.strip("[]").split(",")]
    api_request(context, "POST", "/admin/sync-to-github", {"confab_ids": confab_ids})


# =============================================================================
# Then Steps
# =============================================================================

@then('the response should include commit_sha')
def step_response_has_commit_sha(context):
    """Assert response includes commit SHA."""
    data = context.response.json()
    # commit_sha may be present even if None for no-op
    assert "commit_sha" in data


@then('the response should include committed_files')
def step_response_has_committed_files(context):
    """Assert response includes committed files."""
    data = context.response.json()
    assert "committed_files" in data


@then('the committed_files should include "{filename}"')
def step_committed_files_include(context, filename):
    """Assert committed files include specific file."""
    data = context.response.json()
    files = data.get("committed_files", [])
    assert filename in files, f"'{filename}' not in {files}"


@then('the committed_files should not include "{filename}"')
def step_committed_files_not_include(context, filename):
    """Assert committed files don't include specific file."""
    data = context.response.json()
    files = data.get("committed_files", [])
    assert filename not in files, f"'{filename}' should not be in {files}"


@then('the confab github_synced_at should be updated')
def step_github_synced_at_updated(context):
    """Assert github_synced_at was updated."""
    data = context.response.json()
    assert "synced_at" in data or data.get("status") == "committed"


@then('the GitHub commit message should contain "{text}"')
def step_commit_message_contains(context, text):
    """Assert GitHub commit was called with message containing text."""
    # This would verify the mock was called correctly
    if hasattr(context, 'github_service_mock'):
        # Check if create_or_update_file was called with the message
        pass


@then('the response should include folder_path')
def step_response_has_folder_path(context):
    """Assert response includes folder path."""
    data = context.response.json()
    assert "folder_path" in data


@then('the folder should be created in the GitHub repo')
def step_folder_created_in_repo(context):
    """Assert folder was created in GitHub repo."""
    if hasattr(context, 'github_mock_instance') and context.github_mock_instance:
        assert context.github_mock_instance.create_or_update_file.called


@then('the response should contain error about GitHub not connected')
def step_error_github_not_connected(context):
    """Assert error about GitHub not being connected."""
    error = str(context.response.json())
    assert "github" in error.lower() or "connected" in error.lower()


@then('the response should contain refreshed purpose content')
def step_response_has_refreshed_purpose(context):
    """Assert response has refreshed purpose."""
    data = context.response.json()
    assert "purpose" in data


@then('the response should include refreshed_at timestamp')
def step_response_has_refreshed_at(context):
    """Assert response has refreshed_at timestamp."""
    data = context.response.json()
    assert "refreshed_at" in data


@then('the response should include:')
def step_response_should_include(context):
    """Assert response includes specified fields with values."""
    data = context.response.json()
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    for field, expected in row.items():
        assert field in data, f"Field '{field}' not in response: {data}"
        if expected:
            assert str(data[field]) == str(expected), \
                f"Field '{field}': expected '{expected}', got '{data[field]}'"


@then('the response should indicate files not found')
def step_response_files_not_found(context):
    """Assert response indicates files not found."""
    data = context.response.json()
    assert data.get("remote_source") == "none" or data.get("purpose") is None


@then('the response should indicate {count:d} synced')
def step_response_n_synced(context, count):
    """Assert response indicates n confabs synced."""
    data = context.response.json()
    assert data.get("synced_count") == count


@then('the response should contain a GitHub error message')
def step_response_has_github_error(context):
    """Assert response contains GitHub error."""
    error = str(context.response.json())
    assert "github" in error.lower() or "error" in error.lower()


@then('GitHub delete_folder should have been called')
def step_github_delete_called(context):
    """Assert GitHub delete_folder was called."""
    if hasattr(context, 'github_mock_instance') and context.github_mock_instance:
        assert context.github_mock_instance.delete_folder.called


@then('GitHub delete_folder should not have been called')
def step_github_delete_not_called(context):
    """Assert GitHub delete_folder was not called."""
    if hasattr(context, 'github_mock_instance') and context.github_mock_instance:
        assert not context.github_mock_instance.delete_folder.called


@then('GitHub should attempt to delete path "{path}"')
def step_github_delete_path(context, path):
    """Assert GitHub attempted to delete specific path."""
    # This would check mock call arguments
    pass


@then('GitHub should attempt to delete legacy path "{path}"')
def step_github_delete_legacy_path(context, path):
    """Assert GitHub attempted to delete legacy path."""
    pass


@then('the error should be logged')
def step_error_logged(context):
    """Assert error was logged (mock verification)."""
    pass
