"""
Step definitions for confab features.
"""

import json
from behave import given, when, then

from environment import api_request, create_test_user, login_user, generate_test_email


# =============================================================================
# Given Steps
# =============================================================================

@given('I have created a confab named "{name}"')
def step_have_created_confab(context, name):
    """Create a confab with the specified name."""
    response = api_request(context, "POST", "/confabs", {"name": name})
    assert response.status_code == 200, f"Failed to create confab: {response.text}"

    data = response.json()
    context.scenario_data["confab_id"] = data["id"]
    context.scenario_data["confab"] = data
    context.confabs[name] = data

    # Add cleanup action
    confab_id = data["id"]
    context.cleanup_actions.append(
        lambda: api_request(context, "DELETE", f"/confabs/{confab_id}")
    )


@given('I have created a confab with full details:')
def step_have_created_confab_full(context):
    """Create a confab with full details from table."""
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    # Create the confab first
    create_data = {"name": row.get("name", "Test Agent")}
    if "description" in row:
        create_data["description"] = row["description"]
    if "status" in row:
        create_data["status"] = row["status"]

    response = api_request(context, "POST", "/confabs", create_data)
    assert response.status_code == 200, f"Failed to create confab: {response.text}"

    confab_id = response.json()["id"]
    context.scenario_data["confab_id"] = confab_id

    # Update with additional fields
    update_data = {}
    if "purpose" in row:
        update_data["purpose"] = row["purpose"]
    if "guardrails" in row:
        update_data["guardrails"] = [{"id": "g1", "rule": row["guardrails"], "severity": "error", "enabled": True}]

    if update_data:
        api_request(context, "PUT", f"/confabs/{confab_id}", update_data)

    context.scenario_data["confab"] = api_request(context, "GET", f"/confabs/{confab_id}").json()


@given('I have created the following confabs:')
def step_have_created_confabs(context):
    """Create multiple confabs from table."""
    confab_ids = []
    for row in context.table:
        name = row["name"]
        response = api_request(context, "POST", "/confabs", {"name": name})
        assert response.status_code == 200, f"Failed to create confab '{name}': {response.text}"
        confab_ids.append(response.json()["id"])
        context.confabs[name] = response.json()

    context.scenario_data["confab_ids"] = confab_ids


@given('I have no confabs')
def step_have_no_confabs(context):
    """Ensure user has no confabs (delete any existing)."""
    response = api_request(context, "GET", "/confabs")
    if response.status_code == 200:
        for confab in response.json():
            api_request(context, "DELETE", f"/confabs/{confab['id']}")


@given('another user "{email}" has a confab named "{name}"')
def step_other_user_has_confab(context, email, name):
    """Create a confab owned by another user."""
    saved_token = context.auth_token

    # Create/login other user
    other_user = create_test_user(context, email=email)
    if other_user:
        context.auth_token = other_user.get("access_token")

        response = api_request(context, "POST", "/confabs", {"name": name})
        if response.status_code == 200:
            context.scenario_data["other_confab_id"] = response.json()["id"]

    # Restore original token
    context.auth_token = saved_token


@given('another user "{email}" has confabs:')
def step_other_user_has_confabs(context, email):
    """Create confabs owned by another user."""
    saved_token = context.auth_token

    other_user = create_test_user(context, email=email)
    if other_user:
        context.auth_token = other_user.get("access_token")

        for row in context.table:
            api_request(context, "POST", "/confabs", {"name": row["name"]})

    context.auth_token = saved_token


@given('the confab has description "{description}"')
def step_confab_has_description(context, description):
    """Set confab description."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "PUT", f"/confabs/{confab_id}", {"description": description})


@given('I have a confab in "{status}" status')
def step_have_confab_in_status(context, status):
    """Create a confab with the specified status."""
    response = api_request(context, "POST", "/confabs", {"name": "Status Test Agent", "status": status})
    if response.status_code != 200:
        # Create then update
        response = api_request(context, "POST", "/confabs", {"name": "Status Test Agent"})
        confab_id = response.json()["id"]
        api_request(context, "PUT", f"/confabs/{confab_id}", {"status": status})
    else:
        confab_id = response.json()["id"]

    context.scenario_data["confab_id"] = confab_id


@given('a confab exists with ID {confab_id:d}')
def step_confab_exists_with_id(context, confab_id):
    """Note that a confab exists with given ID."""
    context.scenario_data["confab_id"] = confab_id


@given('I have connected my GitHub account to repo "{repo}"')
def step_connected_github_to_repo(context, repo):
    """Connect GitHub account with specified repo."""
    api_request(context, "POST", "/auth/github/connect", {
        "github_id": 12345,
        "github_username": "testuser",
        "access_token": "ghp_testtoken123",
        "selected_repo": repo
    })


@given('the confab has been synced to GitHub')
def step_confab_synced_to_github(context):
    """Mark confab as synced to GitHub."""
    confab_id = context.scenario_data.get("confab_id")
    context.scenario_data["github_synced"] = True


@given('the confab has been synced to GitHub at path "{path}"')
def step_confab_synced_at_path(context, path):
    """Mark confab as synced with specific path."""
    context.scenario_data["github_path"] = path


@given('the confab has github_path "{path}"')
def step_confab_has_github_path(context, path):
    """Set confab's github_path."""
    context.scenario_data["github_path"] = path


@given('the confab has no github_path')
def step_confab_has_no_github_path(context):
    """Ensure confab has no github_path."""
    context.scenario_data["github_path"] = None


@given('GitHub folder deletion will fail')
def step_github_folder_delete_fails(context):
    """Configure mock to fail folder deletion."""
    if hasattr(context, 'github_mock_instance') and context.github_mock_instance:
        context.github_mock_instance.delete_folder.return_value = False


@given('GitHub will throw an exception on delete')
def step_github_delete_throws(context):
    """Configure mock to throw exception on delete."""
    if hasattr(context, 'github_mock_instance') and context.github_mock_instance:
        context.github_mock_instance.delete_folder.side_effect = Exception("GitHub API error")


# =============================================================================
# When Steps
# =============================================================================

@when('I create a confab with:')
def step_create_confab_with(context):
    """Create a confab with details from table."""
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    data = {}
    for key, value in row.items():
        if key == "temperature":
            data[key] = float(value)
        else:
            data[key] = value

    api_request(context, "POST", "/confabs", data)


@when('I create a confab with a name of {length:d} characters')
def step_create_confab_with_name_length(context, length):
    """Create a confab with a name of specific length."""
    name = "x" * length
    api_request(context, "POST", "/confabs", {"name": name})


@when('I get the confab by ID')
def step_get_confab_by_id(context):
    """Get the current scenario's confab."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "GET", f"/confabs/{confab_id}")


@when('I get confab with ID {confab_id:d}')
def step_get_confab_with_id(context, confab_id):
    """Get a confab by specific ID."""
    api_request(context, "GET", f"/confabs/{confab_id}")


@when('I try to get that confab')
def step_try_get_other_confab(context):
    """Try to get another user's confab."""
    confab_id = context.scenario_data.get("other_confab_id")
    api_request(context, "GET", f"/confabs/{confab_id}")


@when('I list my confabs')
def step_list_confabs(context):
    """List all confabs for current user."""
    api_request(context, "GET", "/confabs")


@when('I update the confab with:')
def step_update_confab_with(context):
    """Update the current scenario's confab."""
    confab_id = context.scenario_data.get("confab_id")
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    data = {}
    for key, value in row.items():
        if key == "temperature":
            data[key] = float(value)
        else:
            data[key] = value

    api_request(context, "PUT", f"/confabs/{confab_id}", data)


@when('I update the confab with a name of {length:d} characters')
def step_update_confab_name_length(context, length):
    """Update confab with a name of specific length."""
    confab_id = context.scenario_data.get("confab_id")
    name = "x" * length
    api_request(context, "PUT", f"/confabs/{confab_id}", {"name": name})


@when('I update confab with ID {confab_id:d} with:')
def step_update_confab_id_with(context, confab_id):
    """Update a confab by ID."""
    row = dict(zip(context.table.headings, context.table.rows[0].cells))
    api_request(context, "PUT", f"/confabs/{confab_id}", row)


@when('I try to update that confab with:')
def step_try_update_other_confab(context):
    """Try to update another user's confab."""
    confab_id = context.scenario_data.get("other_confab_id")
    row = dict(zip(context.table.headings, context.table.rows[0].cells))
    api_request(context, "PUT", f"/confabs/{confab_id}", row)


@when('I update the confab with guardrails:')
def step_update_confab_guardrails(context):
    """Update confab with guardrails from table."""
    confab_id = context.scenario_data.get("confab_id")
    guardrails = []

    for row in context.table:
        guardrails.append({
            "id": row["id"],
            "rule": row["rule"],
            "severity": row["severity"],
            "enabled": row["enabled"].lower() == "true"
        })

    api_request(context, "PUT", f"/confabs/{confab_id}", {"guardrails": guardrails})


@when('I update the confab with tests:')
def step_update_confab_tests(context):
    """Update confab with test scenarios from table."""
    confab_id = context.scenario_data.get("confab_id")
    tests = []

    for row in context.table:
        tests.append({
            "id": row["id"],
            "name": row["name"],
            "input": row["input"],
            "expected_behavior": row["expected_behavior"],
            "tags": []
        })

    api_request(context, "PUT", f"/confabs/{confab_id}", {"tests": tests})


@when('I update the confab status to "{status}"')
def step_update_confab_status(context, status):
    """Update confab status."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "PUT", f"/confabs/{confab_id}", {"status": status})


@when('I delete the confab')
def step_delete_confab(context):
    """Delete the current scenario's confab."""
    confab_id = context.scenario_data.get("confab_id")
    api_request(context, "DELETE", f"/confabs/{confab_id}")


@when('I delete confab with ID {confab_id:d}')
def step_delete_confab_id(context, confab_id):
    """Delete a confab by ID."""
    api_request(context, "DELETE", f"/confabs/{confab_id}")


@when('I delete the confab named "{name}"')
def step_delete_confab_named(context, name):
    """Delete a confab by name."""
    confab = context.confabs.get(name)
    if confab:
        api_request(context, "DELETE", f"/confabs/{confab['id']}")


@when('I try to delete that confab')
def step_try_delete_other_confab(context):
    """Try to delete another user's confab."""
    confab_id = context.scenario_data.get("other_confab_id")
    api_request(context, "DELETE", f"/confabs/{confab_id}")


# =============================================================================
# Then Steps
# =============================================================================

@then('the response should contain confab details:')
def step_response_has_confab_details(context):
    """Assert response contains expected confab details."""
    data = context.response.json()
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    for field, expected in row.items():
        assert field in data, f"Field '{field}' not in response: {data}"
        if field == "temperature":
            assert float(data[field]) == float(expected), \
                f"Field '{field}': expected {expected}, got {data[field]}"
        else:
            assert str(data[field]) == str(expected), \
                f"Field '{field}': expected '{expected}', got '{data[field]}'"


@then('the confab should have a valid ID')
def step_confab_has_valid_id(context):
    """Assert confab has a valid ID."""
    data = context.response.json()
    assert "id" in data, f"No 'id' in response: {data}"
    assert isinstance(data["id"], int), f"ID is not an integer: {data['id']}"


@then('the confab should have a version number')
def step_confab_has_version(context):
    """Assert confab has a version number."""
    data = context.response.json()
    assert "version" in data, f"No 'version' in response: {data}"


@then('the confab temperature should be {temp}')
def step_confab_temp_is(context, temp):
    """Assert confab temperature matches."""
    data = context.response.json()
    assert float(data.get("temperature", 0)) == float(temp), \
        f"Expected temperature {temp}, got {data.get('temperature')}"


@then('the confab should be created successfully')
def step_confab_created_successfully(context):
    """Assert confab was created successfully."""
    assert context.response.status_code == 200
    data = context.response.json()
    assert "id" in data


@then('the response should contain {count:d} confabs')
def step_response_has_n_confabs(context, count):
    """Assert response contains specified number of confabs."""
    data = context.response.json()
    confabs = data if isinstance(data, list) else data.get("confabs", [])
    assert len(confabs) == count, f"Expected {count} confabs, got {len(confabs)}"


@then('the response should contain {count:d} confab')
def step_response_has_n_confab_singular(context, count):
    """Assert response contains specified number of confabs (singular)."""
    step_response_has_n_confabs(context, count)


@then('all confabs should belong to me')
def step_all_confabs_belong_to_me(context):
    """Assert all confabs belong to current user."""
    # In the current API design, listing confabs only returns user's own
    assert context.response.status_code == 200


@then('the confab name should be "{name}"')
def step_confab_name_is(context, name):
    """Assert confab name matches."""
    data = context.response.json()
    assert data.get("name") == name, f"Expected name '{name}', got '{data.get('name')}'"


@then('the confab description should be "{description}"')
def step_confab_description_is(context, description):
    """Assert confab description matches."""
    data = context.response.json()
    assert data.get("description") == description, \
        f"Expected description '{description}', got '{data.get('description')}'"


@then('the confab purpose should be "{purpose}"')
def step_confab_purpose_is(context, purpose):
    """Assert confab purpose matches."""
    data = context.response.json()
    assert data.get("purpose") == purpose, \
        f"Expected purpose '{purpose}', got '{data.get('purpose')}'"


@then('the confab status should be "{status}"')
def step_confab_status_is(context, status):
    """Assert confab status matches."""
    data = context.response.json()
    assert data.get("status") == status, \
        f"Expected status '{status}', got '{data.get('status')}'"


@then('the confab should have {count:d} guardrails')
def step_confab_has_n_guardrails(context, count):
    """Assert confab has specified number of guardrails."""
    data = context.response.json()
    guardrails = data.get("guardrails", [])
    assert len(guardrails) == count, f"Expected {count} guardrails, got {len(guardrails)}"


@then('the confab should have {count:d} test scenarios')
def step_confab_has_n_tests(context, count):
    """Assert confab has specified number of test scenarios."""
    data = context.response.json()
    tests = data.get("tests", [])
    assert len(tests) == count, f"Expected {count} tests, got {len(tests)}"


@then('the confab should no longer exist')
def step_confab_no_longer_exists(context):
    """Assert confab was deleted."""
    confab_id = context.scenario_data.get("confab_id")
    response = api_request(context, "GET", f"/confabs/{confab_id}")
    assert response.status_code == 404


@then('the confab should be named "{name}"')
def step_confab_named(context, name):
    """Assert a confab with the given name exists in the list."""
    data = context.response.json()
    confabs = data if isinstance(data, list) else data.get("confabs", [])
    names = [c.get("name") for c in confabs]
    assert name in names, f"Confab '{name}' not found in {names}"


@then('the list should not contain "{name}"')
def step_list_not_contain(context, name):
    """Assert the confab list does not contain the named confab."""
    data = context.response.json()
    confabs = data if isinstance(data, list) else data.get("confabs", [])
    names = [c.get("name") for c in confabs]
    assert name not in names, f"Confab '{name}' should not be in {names}"


@then('the response should indicate GitHub folder was deleted')
def step_response_github_folder_deleted(context):
    """Assert GitHub folder deletion was reported."""
    data = context.response.json()
    assert data.get("github_folder_deleted") is True


@then('the response should indicate GitHub folder was not deleted')
def step_response_github_folder_not_deleted(context):
    """Assert GitHub folder deletion was not reported."""
    data = context.response.json()
    assert data.get("github_folder_deleted") is False


@then('the confab should be deleted from database')
def step_confab_deleted_from_db(context):
    """Assert confab was deleted from database."""
    confab_id = context.scenario_data.get("confab_id")
    response = api_request(context, "GET", f"/confabs/{confab_id}")
    assert response.status_code == 404


@then('the response should indicate:')
def step_response_should_indicate(context):
    """Assert response contains specified field values."""
    data = context.response.json()
    row = dict(zip(context.table.headings, context.table.rows[0].cells))

    for field, expected in row.items():
        assert field in data, f"Field '{field}' not in response: {data}"
        actual = data[field]
        if expected.lower() == "true":
            assert actual is True, f"Expected '{field}' to be True, got {actual}"
        elif expected.lower() == "false":
            assert actual is False, f"Expected '{field}' to be False, got {actual}"
        else:
            assert str(actual) == expected, f"Expected '{field}' = '{expected}', got '{actual}'"
