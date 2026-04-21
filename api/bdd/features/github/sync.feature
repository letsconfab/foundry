@github @mock_github @wip
Feature: Sync Confab with GitHub
  As an authenticated user with GitHub connected
  I want to sync my confabs with GitHub
  So that I can keep my agent configurations up to date

  Background:
    Given the API is available
    And I am logged in as "user@example.com"
    And I have connected my GitHub account to repo "confabs"
    And GitHub API is mocked
    And I have created a confab named "Test Agent"

  @positive
  Scenario: Refresh definition files from GitHub
    Given the confab has been synced to GitHub
    And GitHub has updated PURPOSE.md content
    When I refresh definition files for the confab
    Then the response status should be 200
    And the response should contain refreshed purpose content
    And the response should include refreshed_at timestamp

  @positive
  Scenario: Refresh fetches both PURPOSE.md and GUARDRAILS.md
    Given GitHub has definition files:
      | file           | content              |
      | PURPOSE.md     | Updated purpose      |
      | GUARDRAILS.md  | Updated guardrails   |
    When I refresh definition files for the confab
    Then the response should contain:
      | purpose         | guardrails_markdown  |
      | Updated purpose | Updated guardrails   |

  @positive
  Scenario: Refresh indicates remote branch source
    Given the confab is synced to branch "main"
    When I refresh definition files for the confab
    Then the response should include:
      | remote_branch | remote_source |
      | main          | branch        |

  @positive
  Scenario: Refresh returns none when files don't exist
    Given GitHub has no definition files for the confab
    When I refresh definition files for the confab
    Then the response status should be 200
    And the response should contain:
      | remote_source |
      | none          |

  @negative
  Scenario: Refresh fails when GitHub not connected
    Given I have not connected my GitHub account
    When I refresh definition files for the confab
    Then the response status should be 400

  @negative
  Scenario: Refresh fails for non-existent confab
    When I refresh definition files for confab ID 99999
    Then the response status should be 404

  @negative
  Scenario: Refresh another user's confab fails
    Given another user "other@example.com" has a confab
    When I try to refresh definition files for that confab
    Then the response status should be 404

  @positive
  Scenario: GitHub API error during refresh is handled
    Given GitHub API will return an error on file fetch
    When I refresh definition files for the confab
    Then the response status should be 200
    And the response should indicate files not found

  @positive
  Scenario: Admin sync all confabs to GitHub
    Given I am an admin user
    And there are 3 confabs to sync
    When I trigger admin sync to GitHub
    Then the response status should be 200
    And the response should indicate 3 synced

  @positive
  Scenario: Admin sync specific confabs
    Given I am an admin user
    And there are confabs with IDs 1, 2, 3
    When I trigger admin sync for confabs [1, 2]
    Then the response status should be 200
    And the response should indicate 2 synced
