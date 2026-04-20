@github @mock_github @wip
Feature: Delete GitHub Folder on Confab Deletion
  As an authenticated user with GitHub connected
  I want GitHub folders to be deleted when I delete confabs
  So that my GitHub repo stays clean

  Background:
    Given the API is available
    And I am logged in as "user@example.com"
    And I have connected my GitHub account to repo "confabs"
    And GitHub API is mocked

  @positive
  Scenario: Deleting confab removes GitHub folder
    Given I have created a confab named "Test Agent"
    And the confab has been synced to GitHub at path "test-agent-abc123"
    When I delete the confab
    Then the response status should be 200
    And the response should indicate:
      | github_folder_deleted |
      | true                  |
    And GitHub delete_folder should have been called

  @positive
  Scenario: Delete tries multiple path formats
    Given I have created a confab named "Legacy Agent"
    And the confab has github_path "legacy-agent-xyz789"
    When I delete the confab
    Then GitHub should attempt to delete path "legacy-agent-xyz789"
    And GitHub should attempt to delete legacy path "confabs/legacy-agent"

  @positive
  Scenario: Confab deleted even if GitHub folder deletion fails
    Given I have created a confab named "Test Agent"
    And the confab has been synced to GitHub
    And GitHub folder deletion will fail
    When I delete the confab
    Then the response status should be 200
    And the confab should be deleted from database
    And the response should indicate:
      | github_folder_deleted |
      | false                 |

  @positive
  Scenario: Delete confab without GitHub connection skips folder deletion
    Given I have not connected my GitHub account
    And I have created a confab named "Local Agent"
    When I delete the confab
    Then the response status should be 200
    And GitHub delete_folder should not have been called
    And the response should indicate:
      | github_folder_deleted |
      | false                 |

  @positive
  Scenario: Delete confab never synced to GitHub
    Given I have created a confab named "Unsynced Agent"
    And the confab has no github_path
    When I delete the confab
    Then the response status should be 200
    And the confab should be deleted
    And the response should indicate:
      | github_folder_deleted |
      | false                 |

  @positive
  Scenario: GitHub folder deletion error is logged but not fatal
    Given I have created a confab named "Test Agent"
    And the confab has been synced to GitHub
    And GitHub will throw an exception on delete
    When I delete the confab
    Then the response status should be 200
    And the confab should be deleted from database
    And the error should be logged
