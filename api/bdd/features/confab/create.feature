@confab
Feature: Create Confab
  As an authenticated user
  I want to create new confabs
  So that I can build AI agent configurations

  Background:
    Given the API is available
    And I am logged in as "user@example.com"

  @positive
  Scenario: Create confab with minimal fields
    When I create a confab with:
      | name          |
      | My First Agent|
    Then the response status should be 200
    And the response should contain confab details:
      | name           | status   |
      | My First Agent | building |
    And the confab should have a valid ID
    And the confab should have a version number

  @positive
  Scenario: Create confab with all fields
    When I create a confab with:
      | name         | description              | model_provider | model_name       | temperature |
      | Full Agent   | A comprehensive agent    | groq           | qwen/qwen3-32b   | 0.8         |
    Then the response status should be 200
    And the response should contain confab details:
      | name       | description           | model_provider | temperature |
      | Full Agent | A comprehensive agent | groq           | 0.8         |

  @positive
  Scenario: Create confab with custom temperature
    When I create a confab with:
      | name        | temperature |
      | Cool Agent  | 0.2         |
    Then the response status should be 200
    And the confab temperature should be 0.2

  @positive
  Scenario: Create confab with maximum temperature
    When I create a confab with:
      | name      | temperature |
      | Hot Agent | 2.0         |
    Then the response status should be 200
    And the confab temperature should be 2.0

  @negative @validation
  Scenario: Create confab fails without name
    When I create a confab with:
      | description     |
      | Missing a name  |
    Then the response status should be 422
    And the response should contain a validation error for "name"

  @negative @validation
  Scenario: Create confab fails with empty name
    When I create a confab with:
      | name |
      |      |
    Then the response status should be 422
    And the response should contain a validation error for "name"

  @negative @validation
  Scenario: Create confab fails with name exceeding 100 characters
    When I create a confab with a name of 101 characters
    Then the response status should be 422
    And the response should contain a validation error for "name"
    And the error should mention maximum length of 100 characters

  @positive @validation
  Scenario: Create confab succeeds with name of exactly 100 characters
    When I create a confab with a name of 100 characters
    Then the response status should be 200
    And the confab should be created successfully

  @negative @validation
  Scenario: Create confab fails with temperature below 0
    When I create a confab with:
      | name       | temperature |
      | Bad Temp   | -0.1        |
    Then the response status should be 422
    And the response should contain a validation error for "temperature"

  @negative @validation
  Scenario: Create confab fails with temperature above 2.0
    When I create a confab with:
      | name       | temperature |
      | Bad Temp   | 2.1         |
    Then the response status should be 422
    And the response should contain a validation error for "temperature"

  @negative @validation
  Scenario: Create confab fails with invalid status
    When I create a confab with:
      | name       | status  |
      | Bad Status | invalid |
    Then the response status should be 422
    And the response should contain a validation error for "status"

  @negative
  Scenario: Create confab fails without authentication
    Given I am not authenticated
    When I create a confab with:
      | name       |
      | Unauth Test|
    Then the response status should be 401
