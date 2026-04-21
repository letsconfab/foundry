@confab
Feature: Update Confab
  As an authenticated user
  I want to update my confabs
  So that I can refine my AI agent configurations

  Background:
    Given the API is available
    And I am logged in as "user@example.com"
    And I have created a confab named "Original Agent"

  @positive
  Scenario: Update confab name
    When I update the confab with:
      | name        |
      | Renamed Agent|
    Then the response status should be 200
    And the confab name should be "Renamed Agent"

  @positive
  Scenario: Update confab description
    When I update the confab with:
      | description          |
      | Updated description  |
    Then the response status should be 200
    And the confab description should be "Updated description"

  @positive
  Scenario: Update confab purpose
    When I update the confab with:
      | purpose                    |
      | Help users accomplish tasks|
    Then the response status should be 200
    And the confab purpose should be "Help users accomplish tasks"

  @positive
  Scenario: Update confab status
    When I update the confab with:
      | status |
      | draft  |
    Then the response status should be 200
    And the confab status should be "draft"

  @positive
  Scenario: Update confab temperature
    When I update the confab with:
      | temperature |
      | 1.5         |
    Then the response status should be 200
    And the confab temperature should be 1.5

  @positive
  Scenario: Update multiple fields at once
    When I update the confab with:
      | name         | description     | status    | temperature |
      | Multi Update | New description | published | 0.9         |
    Then the response status should be 200
    And the response should contain confab details:
      | name         | description     | status    | temperature |
      | Multi Update | New description | published | 0.9         |

  @positive
  Scenario: Partial update preserves unchanged fields
    Given the confab has description "Original description"
    When I update the confab with:
      | name       |
      | New Name   |
    Then the response status should be 200
    And the confab name should be "New Name"
    And the confab description should be "Original description"

  @positive
  Scenario: Update confab with guardrails
    When I update the confab with guardrails:
      | id   | rule                    | severity | enabled |
      | g1   | Never share PII         | error    | true    |
      | g2   | Be polite always        | warning  | true    |
    Then the response status should be 200
    And the confab should have 2 guardrails

  @positive
  Scenario: Update confab with test scenarios
    When I update the confab with tests:
      | id  | name         | input       | expected_behavior    |
      | t1  | Greeting     | Hello       | Respond with hello   |
      | t2  | Help request | Help me     | Offer assistance     |
    Then the response status should be 200
    And the confab should have 2 test scenarios

  @negative @validation
  Scenario: Update fails with name exceeding 100 characters
    When I update the confab with a name of 101 characters
    Then the response status should be 422
    And the response should contain a validation error for "name"

  @negative @validation
  Scenario: Update fails with invalid status
    When I update the confab with:
      | status     |
      | not-valid  |
    Then the response status should be 422
    And the response should contain a validation error for "status"

  @negative @validation
  Scenario: Update fails with temperature out of range
    When I update the confab with:
      | temperature |
      | 3.0         |
    Then the response status should be 422
    And the response should contain a validation error for "temperature"

  @negative
  Scenario: Update confab that does not exist
    When I update confab with ID 99999 with:
      | name       |
      | Ghost Agent|
    Then the response status should be 404
    And the response should contain error "Confab not found"

  @negative
  Scenario: Update another user's confab
    Given another user "other@example.com" has a confab named "Other Agent"
    When I try to update that confab with:
      | name     |
      | Hijacked |
    Then the response status should be 404
    And the response should contain error "Confab not found"

  @negative
  Scenario: Update confab without authentication
    Given I am not authenticated
    When I update confab with ID 1 with:
      | name      |
      | Unauth    |
    Then the response status should be 401
