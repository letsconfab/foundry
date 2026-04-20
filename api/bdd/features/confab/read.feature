@confab
Feature: Read Confab
  As an authenticated user
  I want to view my confabs
  So that I can review and manage my AI agent configurations

  Background:
    Given the API is available
    And I am logged in as "user@example.com"

  @positive
  Scenario: Get single confab by ID
    Given I have created a confab named "Test Agent"
    When I get the confab by ID
    Then the response status should be 200
    And the response should contain confab details:
      | name       |
      | Test Agent |
    And the response should contain:
      | field      |
      | id         |
      | version    |
      | status     |
      | created_at |

  @positive
  Scenario: Get confab with all populated fields
    Given I have created a confab with full details:
      | name       | description    | purpose           | status |
      | Full Agent | Test agent     | Help users test   | draft  |
    When I get the confab by ID
    Then the response should contain confab details:
      | name       | description | purpose         | status |
      | Full Agent | Test agent  | Help users test | draft  |

  @positive
  Scenario: List all my confabs
    Given I have created the following confabs:
      | name     |
      | Agent 1  |
      | Agent 2  |
      | Agent 3  |
    When I list my confabs
    Then the response status should be 200
    And the response should contain 3 confabs
    And all confabs should belong to me

  @positive
  Scenario: List confabs returns empty when none exist
    Given I have no confabs
    When I list my confabs
    Then the response status should be 200
    And the response should contain 0 confabs

  @negative
  Scenario: Get confab that does not exist
    When I get confab with ID 99999
    Then the response status should be 404
    And the response should contain error "Confab not found"

  @negative
  Scenario: Get another user's confab
    Given another user "other@example.com" has a confab named "Private Agent"
    When I try to get that confab
    Then the response status should be 404
    And the response should contain error "Confab not found"

  @negative
  Scenario: List confabs only shows my own
    Given another user "other@example.com" has confabs:
      | name          |
      | Other Agent 1 |
      | Other Agent 2 |
    And I have created a confab named "My Agent"
    When I list my confabs
    Then the response should contain 1 confab
    And the confab should be named "My Agent"

  @negative
  Scenario: Get confab without authentication
    Given I am not authenticated
    When I get confab with ID 1
    Then the response status should be 401
