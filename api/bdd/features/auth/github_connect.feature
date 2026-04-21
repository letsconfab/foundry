@auth @mock_github
Feature: GitHub Account Connection
  As an authenticated user
  I want to connect my GitHub account
  So that I can sync my confabs to GitHub repositories

  Background:
    Given the API is available
    And I am logged in as "user@example.com"
    And GitHub API is mocked

  @positive
  Scenario: Successfully connect GitHub account
    When I connect my GitHub account with:
      | github_id | github_username | access_token    | selected_repo |
      | 12345     | testuser        | ghp_test123456  | confabs       |
    Then the response status should be 200
    And the response should contain message "GitHub account connected"

  @positive
  Scenario: Connect GitHub account with organization
    When I connect my GitHub account with:
      | github_id | github_username | access_token   | selected_repo | selected_org |
      | 12345     | testuser        | ghp_test123456 | confabs       | my-org       |
    Then the response status should be 200
    And the response should contain message "GitHub account connected"

  @positive
  Scenario: Update existing GitHub connection
    Given I have already connected my GitHub account
    When I connect my GitHub account with:
      | github_id | github_username | access_token      | selected_repo |
      | 12345     | testuser        | ghp_newtoken789   | new-repo      |
    Then the response status should be 200
    And the GitHub connection should be updated

  @positive @wip
  Scenario: List available GitHub repositories
    # Note: Requires GitHub API mocking
    Given I have connected my GitHub account
    And GitHub returns repositories:
      | name    | full_name       | private |
      | confabs | testuser/confabs| false   |
      | private | testuser/private| true    |
    When I request my GitHub repositories
    Then the response status should be 200
    And the response should contain 2 repositories

  @negative
  Scenario: Connect GitHub fails without authentication
    Given I am not authenticated
    When I connect my GitHub account with:
      | github_id | github_username | access_token   | selected_repo |
      | 12345     | testuser        | ghp_test123456 | confabs       |
    Then the response status should be 401
