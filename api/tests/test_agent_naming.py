from agent_naming import slugify


def test_slugify_preserves_legacy_confab_folder_names():
    assert slugify("  Agent Chat -- Policy_Coach!!  ") == "agent-chat-policycoach"
    assert slugify("Already   Spaced") == "already-spaced"
