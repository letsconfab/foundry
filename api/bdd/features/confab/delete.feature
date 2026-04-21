@confab @mock_github
Feature: Delete Confab
  As an authenticated user
  I want to delete my confabs
  So that I can remove unwanted AI agent configurations

  Background:
    Given the API is available
    And I am logged in as "user@example.com"
    And GitHub API is mocked

  @positive
  Scenario: Delete confab successfully
    Given I have created a confab named "To Delete"
    When I delete the confab
    Then the response status should be 200
    And the response should contain message "Confab deleted"
    And the confab should no longer exist

  @positive
  Scenario: Delete confab with documents attached
    Given I have created a confab named "With Docs"
    And the confab has documents:
      | filename    |
      | doc1.pdf    |
      | doc2.txt    |
    When I delete the confab
    Then the response status should be 200
    And the response should contain message "Confab deleted"
    And all associated documents should be deleted

  @positive
  Scenario: Delete confab with learnings attached
    Given I have created a confab named "With Learnings"
    And the confab has learnings:
      | content              |
      | User prefers formal  |
      | Avoid jargon         |
    When I delete the confab
    Then the response status should be 200
    And all associated learnings should be deleted

  @positive @wip
  Scenario: Delete confab removes GitHub folder when connected
    # Note: Requires GitHub mock integration
    Given I have connected my GitHub account
    And I have created a confab named "Synced Agent"
    And the confab has been synced to GitHub
    When I delete the confab
    Then the response status should be 200
    And the response should indicate GitHub folder was deleted

  @positive @wip
  Scenario: Delete confab succeeds even if GitHub folder deletion fails
    # Note: Requires GitHub mock integration
    Given I have connected my GitHub account
    And I have created a confab named "Synced Agent"
    And the confab has been synced to GitHub
    And GitHub folder deletion will fail
    When I delete the confab
    Then the response status should be 200
    And the confab should be deleted from database
    And the response should indicate GitHub folder was not deleted

  @positive
  Scenario: Deleting confab removes it from list
    Given I have created the following confabs:
      | name     |
      | Agent 1  |
      | Agent 2  |
      | Agent 3  |
    When I delete the confab named "Agent 2"
    And I list my confabs
    Then the response should contain 2 confabs
    And the list should not contain "Agent 2"

  @negative
  Scenario: Delete confab that does not exist
    When I delete confab with ID 99999
    Then the response status should be 404
    And the response should contain error "Confab not found"

  @negative
  Scenario: Delete another user's confab
    Given another user "other@example.com" has a confab named "Other Agent"
    When I try to delete that confab
    Then the response status should be 404
    And the response should contain error "Confab not found"

  @negative
  Scenario: Delete confab without authentication
    Given a confab exists with ID 1
    And I am not authenticated
    When I delete confab with ID 1
    Then the response status should be 401
