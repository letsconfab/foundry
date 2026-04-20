@github @mock_github @wip
Feature: Commit Definition Files to GitHub
  As an authenticated user with GitHub connected
  I want to commit confab definition files to GitHub
  So that my agent configurations are version controlled

  Background:
    Given the API is available
    And I am logged in as "user@example.com"
    And I have connected my GitHub account to repo "confabs"
    And GitHub API is mocked
    And I have created a confab named "Test Agent"

  @positive
  Scenario: Commit definition files successfully
    Given the confab has purpose and guardrails defined
    When I commit definition files with message "Initial commit"
    Then the response status should be 200
    And the response should contain:
      | field           | value     |
      | status          | committed |
    And the response should include commit_sha
    And the response should include committed_files

  @positive
  Scenario: Commit creates PURPOSE.md and GUARDRAILS.md
    Given the confab has:
      | purpose         | guardrails            |
      | Help users code | Never share secrets   |
    When I commit definition files
    Then the committed_files should include "PURPOSE.md"
    And the committed_files should include "GUARDRAILS.md"

  @positive
  Scenario: Commit only PURPOSE.md
    Given the confab has purpose defined
    When I commit definition files with:
      | include_purpose | include_guardrails |
      | true            | false              |
    Then the response status should be 200
    And the committed_files should include "PURPOSE.md"
    And the committed_files should not include "GUARDRAILS.md"

  @positive
  Scenario: Commit only GUARDRAILS.md
    Given the confab has guardrails defined
    When I commit definition files with:
      | include_purpose | include_guardrails |
      | false           | true               |
    Then the response status should be 200
    And the committed_files should not include "PURPOSE.md"
    And the committed_files should include "GUARDRAILS.md"

  @positive
  Scenario: Commit updates synced_at timestamp
    When I commit definition files
    Then the confab github_synced_at should be updated

  @positive
  Scenario: Commit with custom message
    When I commit definition files with message "Updated agent configuration"
    Then the GitHub commit message should contain "Updated agent configuration"

  @positive
  Scenario: Commit creates folder structure in repo
    When I commit definition files
    Then the response should include folder_path
    And the folder should be created in the GitHub repo

  @negative
  Scenario: Commit fails when no GitHub account connected
    Given I have not connected my GitHub account
    When I commit definition files
    Then the response status should be 400
    And the response should contain error about GitHub not connected

  @negative
  Scenario: Commit fails when repo not configured
    Given my GitHub account has no selected repo
    When I commit definition files
    Then the response status should be 400

  @negative
  Scenario: Commit returns no-op when nothing to commit
    Given the confab has no purpose or guardrails
    When I commit definition files
    Then the response status should be 200
    And the response should contain:
      | status |
      | no-op  |

  @negative
  Scenario: Commit fails for non-existent confab
    When I commit definition files for confab ID 99999
    Then the response status should be 404

  @negative
  Scenario: Commit another user's confab fails
    Given another user "other@example.com" has a confab
    When I try to commit definition files for that confab
    Then the response status should be 404

  @negative
  Scenario: Commit without authentication
    Given I am not authenticated
    When I commit definition files for confab ID 1
    Then the response status should be 401

  @positive
  Scenario: GitHub API error is handled gracefully
    Given GitHub API will return an error
    When I commit definition files
    Then the response status should be 500
    And the response should contain a GitHub error message
